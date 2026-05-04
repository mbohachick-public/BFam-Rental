from datetime import date, datetime, timezone
from decimal import Decimal
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from supabase import Client

from app.config import get_settings
from app.deps import customer_jwt_claims, get_supabase_client, require_customer_jwt
from app.schemas import (
    BookingCompleteBody,
    BookingCompletionPresignBody,
    BookingCompletionPresignOut,
    BookingCompletionSummaryOut,
    BookingContactForm,
    BookingIntakeCreate,
    BookingIntakeOut,
    BookingPaymentStatusPublic,
    BookingPresignRequest,
    BookingPresignResponse,
    BookingQuote,
    BookingQuoteRequest,
    BookingRequestOut,
    BookingRequestStatus,
    BookingStripeSetupIntentOut,
    BookingUploadSlot,
    BookingVerificationSubmit,
    CustomerBookingDetailOut,
    CustomerBookingSummary,
    CustomerContactProfile,
    DayStatus,
    DepositAuthorizationStatus,
)
from app.services.booking import compute_rental_amounts, validate_booking_dates
from app.services.delivery_pricing import compute_logistics_charges
from app.services.sales_tax import (
    compute_sales_tax_amount,
    lookup_sales_tax_rate_percent,
    resolve_postal_for_tax,
)
from app.services.item_availability_seed import ensure_booking_window_day_status
from app.services.booking_documents import (
    ext_for_content_type,
    normalize_booking_document_upload_content_type,
    normalize_booking_image_content_type,
    validate_image_upload,
)
from app.services.booking_storage import (
    BOOKING_UPLOAD_PRESIGN_EXPIRES_SEC,
    assert_booking_document_path,
    create_presigned_booking_upload_slot,
    customer_booking_file_response,
    customer_executed_contract_file_response,
    remove_booking_storage_prefix,
    save_booking_document,
    verify_booking_document_uploaded,
)
from app.services.admin_notify import try_notify_admin_approval_needed
from app.services.booking_response import booking_out_from_row
from app.services.dates import iter_days_inclusive
from app.services.quote_email import (
    send_booking_intake_continue_email,
    send_booking_pending_review_notice_email,
    send_quote_email,
)
from app.services.stripe_customer_setup import create_booking_setup_intent, stripe_payment_collection_enabled

router = APIRouter(prefix="/booking-requests", tags=["booking-requests"])

log = logging.getLogger(__name__)


def _rental_days_inclusive_or_400(start: date, end: date) -> list[date]:
    """Inclusive rental day list; 400 if end is before start (``iter_days_inclusive`` is then empty)."""
    days = iter_days_inclusive(start, end)
    if not days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date.",
        )
    return days


def _dispatch_booking_intake_emails(
    *,
    to_addr: str,
    item_title: str,
    start_date_iso: str,
    end_date_iso: str,
    complete_url: str,
    num_days: int,
    discounted_subtotal: Decimal,
    sales_tax_rate_percent: Decimal,
    sales_tax_amount: Decimal,
    rental_total_with_tax: Decimal,
    deposit_amount: Decimal,
    delivery_fee: Decimal,
    pickup_fee: Decimal,
    delivery_distance_miles: Decimal | None,
    pickup_distance_miles: Decimal | None,
) -> None:
    """Run after HTTP response so SMTP slowness does not block step-1 submit."""
    try:
        settings = get_settings()
        send_booking_intake_continue_email(
            settings,
            to_addr=to_addr,
            item_title=item_title,
            start_date=start_date_iso,
            end_date=end_date_iso,
            complete_url=complete_url,
        )
        send_quote_email(
            settings,
            to_addr=to_addr,
            item_title=item_title,
            start_date=start_date_iso,
            end_date=end_date_iso,
            num_days=num_days,
            discounted_subtotal=discounted_subtotal,
            sales_tax_rate_percent=sales_tax_rate_percent,
            sales_tax_amount=sales_tax_amount,
            rental_total_with_tax=rental_total_with_tax,
            deposit_amount=deposit_amount,
            delivery_fee=delivery_fee,
            pickup_fee=pickup_fee,
            delivery_distance_miles=delivery_distance_miles,
            pickup_distance_miles=pickup_distance_miles,
        )
    except Exception:
        log.exception("Booking intake follow-up emails failed (to=%s)", to_addr)


def _upsert_booking_date_hold(client: Client, item_id: str, start_date: date, end_date: date) -> None:
    """Reserve item dates when a booking row is created; cleared on abandon/decline or set to booked on confirm."""
    days = iter_days_inclusive(start_date, end_date)
    rows = [
        {"item_id": item_id, "day": d.isoformat(), "status": DayStatus.pending_request.value}
        for d in days
    ]
    if rows:
        client.table("item_day_status").upsert(rows).execute()


def _release_booking_date_hold(client: Client, item_id: str, start_date: date, end_date: date) -> None:
    """Re-open days when a draft booking is deleted before admin confirmation."""
    days = iter_days_inclusive(start_date, end_date)
    rows = [
        {"item_id": item_id, "day": d.isoformat(), "status": DayStatus.open_for_booking.value}
        for d in days
    ]
    if rows:
        client.table("item_day_status").upsert(rows).execute()


def _decimal(v: object) -> Decimal:
    return Decimal(str(v))


def _today_utc() -> date:
    return date.today()


def _read_upload(upload: UploadFile) -> tuple[bytes, str | None]:
    raw = upload.file.read()
    return raw, upload.content_type


def _sales_tax_parts(
    settings,
    discounted_subtotal: Decimal,
    *,
    tax_postal_code: str | None,
    customer_address: str | None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    postal = resolve_postal_for_tax(
        explicit_zip=tax_postal_code,
        customer_address=customer_address,
        default_zip=settings.sales_tax_default_postal_code,
    )
    rate_pct, source = lookup_sales_tax_rate_percent(settings, postal_code=postal)
    tax_amt = compute_sales_tax_amount(discounted_subtotal, rate_pct)
    total = (discounted_subtotal + tax_amt).quantize(Decimal("0.01"))
    return rate_pct, tax_amt, total, source


def _sales_tax_or_http(
    settings,
    discounted_subtotal: Decimal,
    *,
    tax_postal_code: str | None,
    customer_address: str | None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    try:
        return _sales_tax_parts(
            settings,
            discounted_subtotal,
            tax_postal_code=tax_postal_code,
            customer_address=customer_address,
        )
    except ValueError as e:
        detail = str(e)
        if "Sales tax is not configured" in detail:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from e
        if "Sales tax response was not valid JSON" in detail or "Tax API JSON" in detail:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=detail) from e
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Sales tax lookup failed: {e}",
        ) from e


def _validation_detail(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) if parts else "Invalid input"


def _dec_opt(v: object | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


def _multipart_workflow_defaults() -> dict:
    return {
        "payment_method_preference": "card",
        "is_repeat_contractor": False,
        "request_not_confirmed_ack": True,
    }


_BOOKING_SCHEMA_STALE_DETAIL = (
    "Supabase table public.booking_requests is missing columns the API expects "
    "(PostgREST error PGRST204), or the schema cache is stale. "
    "Run Specs/supabase-migration-booking-step2.sql in the Supabase SQL editor, wait a few seconds, "
    "then retry. If it still fails, run: NOTIFY pgrst, 'reload schema';"
)


def _maybe_raise_booking_schema_error(exc: BaseException) -> None:
    """Turn missing-column schema errors into an actionable HTTP response."""
    if "PGRST204" not in str(exc):
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_BOOKING_SCHEMA_STALE_DETAIL,
    ) from exc


def _workflow_from_presign(body: BookingPresignRequest) -> dict:
    return {
        "company_name": (body.company_name or "").strip() or None,
        "payment_method_preference": "card",
        "is_repeat_contractor": body.is_repeat_contractor,
        "tow_vehicle_year": body.tow_vehicle_year,
        "tow_vehicle_make": (body.tow_vehicle_make or "").strip() or None,
        "tow_vehicle_model": (body.tow_vehicle_model or "").strip() or None,
        "tow_vehicle_tow_rating_lbs": body.tow_vehicle_tow_rating_lbs,
        "has_brake_controller": body.has_brake_controller,
        "request_not_confirmed_ack": body.request_not_confirmed_ack,
    }


def _validated_booking_insert_row(
    client: Client,
    settings,
    customer: dict | None,
    item_id: str,
    start_date: date,
    end_date: date,
    contact: BookingContactForm,
    notes: str | None,
    *,
    delivery_requested: bool = False,
    pickup_from_site_requested: bool = False,
    logistics_address: str | None = None,
) -> tuple[dict, str, bool, int, Decimal, Decimal, Decimal, Decimal, Decimal, str, Decimal]:
    """
    Validate item/dates/contact/tax and build the insert dict (no document paths).
    Returns insert_row, item_title, towable, num_days, disc_sub, tax_rate, tax_amt,
    rental_w_tax, tax_src, dep.
    """
    clean_notes = (notes or "").strip() or None
    item_res = (
        client.table("items")
        .select(
            "id,cost_per_day,minimum_day_rental,deposit_amount,towable,title,active,delivery_available"
        )
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    rows = item_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = rows[0]
    if not bool(item.get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    towable = bool(item.get("towable", False))
    item_title = str(item.get("title") or "Rental item")
    cost = _decimal(item["cost_per_day"])
    min_days = int(item["minimum_day_rental"])
    deposit = _decimal(item["deposit_amount"])

    today = _today_utc()
    days = _rental_days_inclusive_or_400(start_date, end_date)

    ensure_booking_window_day_status(client, item_id, today)
    status_res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", item_id)
        .gte("day", min(days).isoformat())
        .lte("day", max(days).isoformat())
        .execute()
    )
    open_dates: set[date] = set()
    for r in status_res.data or []:
        d = date.fromisoformat(str(r["day"]))
        if r["status"] == DayStatus.open_for_booking.value:
            open_dates.add(d)

    err = validate_booking_dates(today, start_date, end_date, min_days, open_dates)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    num_days = len(days)
    base, disc_pct, disc_sub, dep = compute_rental_amounts(cost, num_days, deposit)
    logistics_addr = (
        ((logistics_address or "").strip() or None)
        if (delivery_requested or pickup_from_site_requested)
        else None
    )
    try:
        delivery_fee, delivery_miles, pickup_fee, pickup_miles = compute_logistics_charges(
            client,
            settings,
            item_delivery_available=bool(item.get("delivery_available", True)),
            delivery_requested=delivery_requested,
            pickup_from_site_requested=pickup_from_site_requested,
            logistics_address=logistics_addr,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    taxable_subtotal = disc_sub + delivery_fee + pickup_fee
    tax_rate, tax_amt, rental_w_tax, tax_src = _sales_tax_or_http(
        settings,
        taxable_subtotal,
        tax_postal_code=None,
        customer_address=contact.customer_address,
    )

    auth_sub: str | None = None
    if customer is not None:
        raw_sub = customer.get("sub")
        auth_sub = str(raw_sub).strip() if raw_sub else None

    insert_row: dict = {
        "item_id": item_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "status": BookingRequestStatus.requested.value,
        "customer_email": str(contact.customer_email),
        "customer_phone": contact.customer_phone,
        "customer_first_name": contact.customer_first_name,
        "customer_last_name": contact.customer_last_name,
        "customer_address": contact.customer_address,
        "notes": clean_notes,
        "base_amount": float(base),
        "discount_percent": float(disc_pct),
        "discounted_subtotal": float(disc_sub),
        "deposit_amount": float(dep),
        "sales_tax_rate_percent": float(tax_rate),
        "sales_tax_amount": float(tax_amt),
        "rental_total_with_tax": float(rental_w_tax),
        "sales_tax_source": tax_src,
        "delivery_requested": delivery_requested,
        "pickup_from_site_requested": pickup_from_site_requested,
        "delivery_address": logistics_addr,
        "delivery_fee": float(delivery_fee),
        "delivery_distance_miles": float(delivery_miles) if delivery_miles is not None else None,
        "pickup_fee": float(pickup_fee),
        "pickup_distance_miles": float(pickup_miles) if pickup_miles is not None else None,
    }
    if auth_sub:
        insert_row["customer_auth0_sub"] = auth_sub

    insert_row.update(_multipart_workflow_defaults())

    return (
        insert_row,
        item_title,
        towable,
        num_days,
        disc_sub,
        tax_rate,
        tax_amt,
        rental_w_tax,
        tax_src,
        dep,
    )


def _intake_booking_insert_row(
    client: Client,
    settings,
    customer: dict | None,
    body: BookingIntakeCreate,
) -> tuple[dict, str]:
    """Step 1: pricing without billing address — tax postal optional; persist rental_subtotal_snapshot."""
    clean_notes = (body.notes or "").strip() or None
    item_res = (
        client.table("items")
        .select(
            "id,cost_per_day,minimum_day_rental,deposit_amount,towable,title,active,delivery_available"
        )
        .eq("id", body.item_id)
        .limit(1)
        .execute()
    )
    rows = item_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = rows[0]
    if not bool(item.get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item_title = str(item.get("title") or "Rental item")
    cost = _decimal(item["cost_per_day"])
    min_days = int(item["minimum_day_rental"])
    deposit = _decimal(item["deposit_amount"])

    today = _today_utc()
    days = _rental_days_inclusive_or_400(body.start_date, body.end_date)

    ensure_booking_window_day_status(client, body.item_id, today)
    status_res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", body.item_id)
        .gte("day", min(days).isoformat())
        .lte("day", max(days).isoformat())
        .execute()
    )
    open_dates: set[date] = set()
    for r in status_res.data or []:
        d = date.fromisoformat(str(r["day"]))
        if r["status"] == DayStatus.open_for_booking.value:
            open_dates.add(d)

    err = validate_booking_dates(today, body.start_date, body.end_date, min_days, open_dates)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    delivery_requested = body.delivery_requested
    pickup_from_site = body.pickup_from_site_requested
    cust_addr = (body.customer_address or "").strip()
    logistics_addr = (
        ((body.job_site_address or "").strip() or None)
        if (delivery_requested or pickup_from_site)
        else None
    )
    num_days = len(days)
    base, disc_pct, disc_sub, dep = compute_rental_amounts(cost, num_days, deposit)
    try:
        delivery_fee, delivery_miles, pickup_fee, pickup_miles = compute_logistics_charges(
            client,
            settings,
            item_delivery_available=bool(item.get("delivery_available", True)),
            delivery_requested=delivery_requested,
            pickup_from_site_requested=pickup_from_site,
            logistics_address=logistics_addr,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    taxable_subtotal = disc_sub + delivery_fee + pickup_fee
    zp = (body.tax_postal_code or "").strip() or None
    tax_rate, tax_amt, rental_w_tax, tax_src = _sales_tax_or_http(
        settings,
        taxable_subtotal,
        tax_postal_code=zp,
        customer_address=cust_addr or None,
    )

    auth_sub: str | None = None
    if customer is not None:
        raw_sub = customer.get("sub")
        auth_sub = str(raw_sub).strip() if raw_sub else None

    insert_row: dict = {
        "item_id": body.item_id,
        "start_date": body.start_date.isoformat(),
        "end_date": body.end_date.isoformat(),
        "status": BookingRequestStatus.requested.value,
        "customer_email": str(body.customer_email),
        "customer_phone": body.customer_phone,
        "customer_first_name": body.customer_first_name,
        "customer_last_name": body.customer_last_name,
        "customer_address": cust_addr,
        "notes": clean_notes,
        "base_amount": float(base),
        "discount_percent": float(disc_pct),
        "discounted_subtotal": float(disc_sub),
        "deposit_amount": float(dep),
        "sales_tax_rate_percent": float(tax_rate),
        "sales_tax_amount": float(tax_amt),
        "rental_total_with_tax": float(rental_w_tax),
        "sales_tax_source": tax_src,
        "delivery_requested": delivery_requested,
        "pickup_from_site_requested": pickup_from_site,
        "delivery_address": logistics_addr,
        "delivery_fee": float(delivery_fee),
        "delivery_distance_miles": float(delivery_miles) if delivery_miles is not None else None,
        "pickup_fee": float(pickup_fee),
        "pickup_distance_miles": float(pickup_miles) if pickup_miles is not None else None,
        "company_name": (body.company_name or "").strip() or None,
        "rental_subtotal_snapshot": float(disc_sub),
        "damage_waiver_daily_amount": float(_damage_waiver_daily(settings)),
        "damage_waiver_line_total": 0.0,
        "damage_waiver_selected": False,
    }
    if auth_sub:
        insert_row["customer_auth0_sub"] = auth_sub

    insert_row.update(_multipart_workflow_defaults())

    return insert_row, item_title


def _damage_waiver_daily(settings) -> Decimal:
    try:
        return Decimal(str(settings.damage_waiver_per_day_usd or "0").strip() or "0")
    except Exception:
        return Decimal("0")


def _verification_pricing_update(
    settings,
    row: dict,
    *,
    customer_address: str,
    damage_waiver_selected: bool,
) -> dict[str, float | str]:
    """Recompute rental line + tax after waiver + billing address."""
    delivery_fee = Decimal(str(row.get("delivery_fee") or "0"))
    pickup_fee = Decimal(str(row.get("pickup_fee") or "0"))
    raw_snap = row.get("rental_subtotal_snapshot")
    if raw_snap is not None:
        rent_part = Decimal(str(raw_snap))
    else:
        rent_part = Decimal(str(row.get("discounted_subtotal") or "0"))
    start_d = date.fromisoformat(str(row["start_date"]))
    end_d = date.fromisoformat(str(row["end_date"]))
    n_days = len(iter_days_inclusive(start_d, end_d))
    w_daily = Decimal(str(row.get("damage_waiver_daily_amount") or "0"))
    waiver_line = (w_daily * n_days) if damage_waiver_selected and w_daily > 0 else Decimal("0")
    taxable = rent_part + waiver_line + delivery_fee + pickup_fee
    tax_rate, tax_amt, rental_w_tax, tax_src = _sales_tax_or_http(
        settings,
        taxable,
        tax_postal_code=None,
        customer_address=customer_address,
    )
    new_discounted = rent_part + waiver_line
    return {
        "discounted_subtotal": float(new_discounted),
        "damage_waiver_line_total": float(waiver_line),
        "sales_tax_rate_percent": float(tax_rate),
        "sales_tax_amount": float(tax_amt),
        "rental_total_with_tax": float(rental_w_tax),
        "sales_tax_source": tax_src,
    }


def _booking_store_error_detail(settings) -> str:
    if settings.booking_documents_storage == "local":
        return (
            "Could not save booking documents to disk. Check that "
            f"BOOKING_DOCUMENTS_LOCAL_DIR ({settings.booking_documents_local_dir}) is writable."
        )
    return (
        "Could not store booking documents in Supabase Storage. Ensure the "
        "'booking-documents' bucket exists and policies allow the service role to upload."
    )


@router.post("/intake", response_model=BookingIntakeOut, status_code=status.HTTP_201_CREATED)
def create_booking_intake(
    body: BookingIntakeCreate,
    background_tasks: BackgroundTasks,
    customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingIntakeOut:
    """Step 1: lightweight request without documents; customer continues on /booking/:id/complete."""
    settings = get_settings()
    insert_row, item_title = _intake_booking_insert_row(client, settings, customer, body)
    try:
        insert_res = client.table("booking_requests").insert(insert_row).execute()
    except Exception as exc:
        _maybe_raise_booking_schema_error(exc)
        raise
    data = insert_res.data or []
    if not data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    row = data[0]
    bid = str(row["id"])
    _upsert_booking_date_hold(client, body.item_id, body.start_date, body.end_date)
    base_fe = (settings.frontend_public_url or "").strip().rstrip("/")
    complete_url = f"{base_fe}/booking/{bid}/complete"
    em = str(body.customer_email).strip()
    if em:
        num_days = len(iter_days_inclusive(body.start_date, body.end_date))
        background_tasks.add_task(
            _dispatch_booking_intake_emails,
            to_addr=em,
            item_title=item_title,
            start_date_iso=body.start_date.isoformat(),
            end_date_iso=body.end_date.isoformat(),
            complete_url=complete_url,
            num_days=num_days,
            discounted_subtotal=_decimal(insert_row["discounted_subtotal"]),
            sales_tax_rate_percent=_decimal(insert_row["sales_tax_rate_percent"]),
            sales_tax_amount=_decimal(insert_row["sales_tax_amount"]),
            rental_total_with_tax=_decimal(insert_row["rental_total_with_tax"]),
            deposit_amount=_decimal(insert_row["deposit_amount"]),
            delivery_fee=_decimal(insert_row.get("delivery_fee") or 0),
            pickup_fee=_decimal(insert_row.get("pickup_fee") or 0),
            delivery_distance_miles=_dec_opt(insert_row.get("delivery_distance_miles")),
            pickup_distance_miles=_dec_opt(insert_row.get("pickup_distance_miles")),
        )
    return BookingIntakeOut(
        booking_id=bid,
        complete_path=f"/booking/{bid}/complete",
        status=BookingRequestStatus(row.get("status") or BookingRequestStatus.requested.value),
    )


@router.get("/{booking_id}/completion-summary", response_model=BookingCompletionSummaryOut)
def get_booking_completion_summary(
    booking_id: str, client: Client = Depends(get_supabase_client)
) -> BookingCompletionSummaryOut:
    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    st = str(row.get("status") or "")
    if st not in (BookingRequestStatus.requested.value, BookingRequestStatus.pending_approval.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking is no longer editable on the completion step.",
        )
    item_res = (
        client.table("items").select("title,towable,active").eq("id", row["item_id"]).limit(1).execute()
    )
    it_rows = item_res.data or []
    if not it_rows or not bool(it_rows[0].get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item_title = str(it_rows[0].get("title") or "Rental item")
    towable = bool(it_rows[0].get("towable"))
    start_d = date.fromisoformat(str(row["start_date"]))
    end_d = date.fromisoformat(str(row["end_date"]))
    n_days = len(iter_days_inclusive(start_d, end_d))
    settings = get_settings()
    stripe_on = stripe_payment_collection_enabled(settings)
    try:
        w_daily = Decimal(str(row.get("damage_waiver_daily_amount") or "0"))
    except Exception:
        w_daily = _damage_waiver_daily(settings)
    if w_daily <= 0:
        w_daily = _damage_waiver_daily(settings)
    rt = (settings.rental_terms_url or "").strip() or None
    deliv_raw = row.get("delivery_address")
    deliv_str = (str(deliv_raw).strip() if deliv_raw is not None else "") or None
    cust_raw = row.get("customer_address")
    cust_str = (str(cust_raw).strip() if cust_raw is not None else "") or None
    return BookingCompletionSummaryOut(
        booking_id=str(row["id"]),
        status=BookingRequestStatus(row["status"]),
        item_title=item_title,
        start_date=start_d,
        end_date=end_d,
        num_days=n_days,
        towable=towable,
        delivery_requested=bool(row.get("delivery_requested")),
        pickup_from_site_requested=bool(row.get("pickup_from_site_requested")),
        discounted_subtotal=_decimal(row.get("discounted_subtotal") or 0),
        deposit_amount=_decimal(row.get("deposit_amount") or 0),
        rental_total_with_tax=_decimal(row.get("rental_total_with_tax") or 0),
        delivery_fee=_decimal(row.get("delivery_fee") or 0),
        pickup_fee=_decimal(row.get("pickup_fee") or 0),
        damage_waiver_daily_amount=w_daily,
        stripe_payment_collection_enabled=stripe_on,
        rental_terms_url=rt,
        logistics_address=deliv_str,
        delivery_address=deliv_str,
        job_site_address=deliv_str,
        customer_address=cust_str,
    )


@router.post("/{booking_id}/completion-uploads/presign", response_model=BookingCompletionPresignOut)
def completion_upload_presign(
    booking_id: str,
    body: BookingCompletionPresignBody,
    _customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingCompletionPresignOut:
    settings = get_settings()
    if settings.booking_documents_storage != "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completion uploads require BOOKING_DOCUMENTS_STORAGE=supabase.",
        )
    res = (
        client.table("booking_requests")
        .select("id,status,drivers_license_path,license_plate_path")
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    brow = rows[0]
    if str(brow.get("status") or "") != BookingRequestStatus.requested.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload slots are only available before verification is submitted.",
        )
    if brow.get("drivers_license_path"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver license is already attached to this booking.",
        )
    try:
        dl_type = normalize_booking_document_upload_content_type(
            body.drivers_license_content_type, "Driver's license"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    ins_slot_out = None
    ins_type_norm = None
    ins_raw = (body.insurance_card_content_type or "").strip()
    if ins_raw:
        try:
            ins_type_norm = normalize_booking_document_upload_content_type(ins_raw, "Insurance card")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    dl_ext = ext_for_content_type(dl_type)
    path_dl = f"{booking_id}/drivers_license{dl_ext}"
    try:
        dl_slot_raw = create_presigned_booking_upload_slot(client, path_dl)
        dl_slot_out = BookingUploadSlot.model_validate(dl_slot_raw)
        if ins_type_norm is not None:
            ins_ext = ext_for_content_type(ins_type_norm)
            path_ins = f"{booking_id}/insurance_card{ins_ext}"
            ins_raw_slot = create_presigned_booking_upload_slot(client, path_ins)
            ins_slot_out = BookingUploadSlot.model_validate(ins_raw_slot)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create signed upload URLs. Check Supabase Storage configuration.",
        ) from exc
    return BookingCompletionPresignOut(
        drivers_license=dl_slot_out,
        insurance_card=ins_slot_out,
        expires_in=BOOKING_UPLOAD_PRESIGN_EXPIRES_SEC,
    )


@router.post("/{booking_id}/stripe-setup-intent", response_model=BookingStripeSetupIntentOut)
def booking_stripe_setup_intent(
    booking_id: str,
    _customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingStripeSetupIntentOut:
    settings = get_settings()
    if not stripe_payment_collection_enabled(settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card collection is not enabled (Stripe secret key is unset).",
        )
    pk = (settings.stripe_publishable_key or "").strip()
    if not pk:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe publishable key is not configured (set STRIPE_PUBLISHABLE_KEY on the API).",
        )
    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    if str(row.get("status") or "") != BookingRequestStatus.requested.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SetupIntent is only available before verification is submitted.",
        )
    try:
        intent = create_booking_setup_intent(
            settings,
            booking_id=booking_id,
            customer_email=str(row.get("customer_email") or "").strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return BookingStripeSetupIntentOut(client_secret=intent["client_secret"], publishable_key=pk)


@router.post("/{booking_id}/verification", response_model=BookingRequestOut)
def submit_booking_verification(
    booking_id: str,
    body: BookingVerificationSubmit,
    _customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    settings = get_settings()
    storage_mode = settings.booking_documents_storage
    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    if str(row.get("status") or "") != BookingRequestStatus.requested.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification was already submitted or this booking cannot be edited here.",
        )
    item_res = client.table("items").select("towable").eq("id", row["item_id"]).limit(1).execute()
    towable = bool((item_res.data or [{}])[0].get("towable"))

    stripe_on = stripe_payment_collection_enabled(settings)
    pm = (body.stripe_payment_method_id or "").strip() or None
    if stripe_on:
        if not pm or not pm.startswith("pm_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe is enabled — save a payment method before submitting.",
            )

    addr = body.customer_address.strip()
    needs_job_site = bool(row.get("delivery_requested")) or bool(row.get("pickup_from_site_requested"))
    job_site = (body.job_site_address or "").strip() if body.job_site_address else ""
    if needs_job_site:
        if not job_site:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="job_site_address is required when delivery or pickup from site was requested.",
            )
    else:
        job_site = ""

    if towable and not body.vehicle_tow_capable_ack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm your vehicle can safely tow this trailer.",
        )

    path_ins = None
    try:
        assert_booking_document_path(booking_id, body.drivers_license_path, role="drivers_license")
        if storage_mode == "supabase":
            verify_booking_document_uploaded(client, body.drivers_license_path, "Driver's license")
        elif storage_mode != "supabase":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completing uploads requires BOOKING_DOCUMENTS_STORAGE=supabase.",
            )
        if body.insurance_card_path:
            assert_booking_document_path(booking_id, body.insurance_card_path, role="insurance_card")
            verify_booking_document_uploaded(client, body.insurance_card_path, "Insurance card")
            path_ins = body.insurance_card_path
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    now_iso = datetime.now(timezone.utc).isoformat()
    price_patch = _verification_pricing_update(
        settings, row, customer_address=addr, damage_waiver_selected=body.damage_waiver_selected
    )
    deposit_stat: str
    dep_amt_raw = row.get("deposit_amount")
    try:
        dep_need = dep_amt_raw is not None and float(dep_amt_raw) > 0
    except (TypeError, ValueError):
        dep_need = bool(dep_amt_raw)
    if not stripe_on or not dep_need:
        deposit_stat = DepositAuthorizationStatus.not_required.value
    else:
        deposit_stat = DepositAuthorizationStatus.not_started.value

    upd: dict = {
        **price_patch,
        "drivers_license_path": body.drivers_license_path,
        "insurance_card_path": path_ins,
        "license_plate_path": None,
        "customer_address": addr,
        "vehicle_tow_capable_ack": body.vehicle_tow_capable_ack,
        "agreement_terms_acknowledged": False,
        "request_approval_acknowledged": body.request_approval_acknowledged,
        "agreement_sign_intent_acknowledged": body.agreement_sign_intent_acknowledged,
        "damage_waiver_selected": body.damage_waiver_selected,
        "stripe_saved_payment_method_id": pm,
        "deposit_authorization_status": deposit_stat,
        "verification_submitted_at": now_iso,
        "status": BookingRequestStatus.pending_approval.value,
    }
    if needs_job_site:
        upd["delivery_address"] = job_site
    try:
        client.table("booking_requests").update(upd).eq("id", booking_id).execute()
    except Exception as exc:
        _maybe_raise_booking_schema_error(exc)
        raise
    res2 = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    final = (res2.data or [None])[0]
    if not final:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")
    try_notify_admin_approval_needed(client, settings, booking_id)
    to_addr = (final.get("customer_email") or "").strip()
    if to_addr:
        it = client.table("items").select("title").eq("id", final["item_id"]).limit(1).execute()
        titles = it.data or []
        tit = str((titles or [{}])[0].get("title") or "Rental item") if titles else "Rental item"
        send_booking_pending_review_notice_email(
            settings,
            to_addr=to_addr,
            item_title=tit,
            start_date=str(final["start_date"]),
            end_date=str(final["end_date"]),
        )
    return booking_out_from_row(client, final, sign_document_urls=False)


@router.get("/mine", response_model=list[CustomerBookingSummary])
def list_my_booking_requests(
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
) -> list[CustomerBookingSummary]:
    sub = str(customer["sub"])
    br = (
        client.table("booking_requests")
        .select("*")
        .eq("customer_auth0_sub", sub)
        .order("created_at", desc=True)
        .execute()
    )
    rows = br.data or []
    if not rows:
        return []
    item_ids = list({str(r["item_id"]) for r in rows})
    ir = client.table("items").select("id,title,active").in_("id", item_ids).execute()
    items_map: dict[str, dict] = {str(it["id"]): it for it in (ir.data or [])}
    out: list[CustomerBookingSummary] = []
    for r in rows:
        iid = str(r["item_id"])
        it = items_map.get(iid) or {}
        title = str(it.get("title") or "Rental item")
        active = bool(it.get("active", True))
        st = str(r.get("status") or "")
        pay_url: str | None = None
        stripe_url: str | None = None
        stripe_deposit_url: str | None = None
        if st in (
            BookingRequestStatus.approved_pending_payment.value,
            BookingRequestStatus.approved_pending_check_clearance.value,
        ):
            raw = r.get("payment_collection_url")
            pay_url = str(raw).strip() if raw else None
            if not r.get("rental_paid_at"):
                su = r.get("stripe_checkout_url")
                stripe_url = str(su).strip() if su else None
            if not r.get("deposit_secured_at"):
                du = r.get("stripe_deposit_checkout_url")
                stripe_deposit_url = str(du).strip() if du else None
        out.append(
            CustomerBookingSummary(
                id=str(r["id"]),
                item_id=iid,
                item_title=title,
                item_active=active,
                start_date=date.fromisoformat(str(r["start_date"])),
                end_date=date.fromisoformat(str(r["end_date"])),
                status=BookingRequestStatus(r["status"]),
                discounted_subtotal=_dec_opt(r.get("discounted_subtotal")),
                rental_total_with_tax=_dec_opt(r.get("rental_total_with_tax")),
                deposit_amount=_dec_opt(r.get("deposit_amount")),
                payment_collection_url=pay_url,
                stripe_checkout_url=stripe_url,
                stripe_deposit_checkout_url=stripe_deposit_url,
            )
        )
    return out


def _booking_has_executed_contract(client: Client, booking_id: str) -> bool:
    res = (
        client.table("booking_documents")
        .select("id")
        .eq("booking_id", booking_id)
        .eq("document_type", "EXECUTED_PACKET")
        .limit(1)
        .execute()
    )
    return bool(res.data or [])


@router.get("/mine/{booking_id}/files/drivers-license")
def my_booking_drivers_license_file(
    booking_id: str,
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
):
    return customer_booking_file_response(
        client, booking_id, "drivers-license", customer_auth0_sub=str(customer["sub"])
    )


@router.get("/mine/{booking_id}/files/license-plate")
def my_booking_license_plate_file(
    booking_id: str,
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
):
    return customer_booking_file_response(
        client, booking_id, "license-plate", customer_auth0_sub=str(customer["sub"])
    )


@router.get("/mine/{booking_id}/files/insurance-card")
def my_booking_insurance_card_file(
    booking_id: str,
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
):
    return customer_booking_file_response(
        client, booking_id, "insurance-card", customer_auth0_sub=str(customer["sub"])
    )


@router.get("/mine/{booking_id}/executed-contract")
def my_booking_executed_contract_file(
    booking_id: str,
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
):
    return customer_executed_contract_file_response(
        client, booking_id, customer_auth0_sub=str(customer["sub"])
    )


@router.get("/mine/{booking_id}", response_model=CustomerBookingDetailOut)
def get_my_booking_detail(
    booking_id: str,
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
) -> CustomerBookingDetailOut:
    sub = str(customer["sub"])
    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    if str(row.get("customer_auth0_sub") or "") != sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    base = booking_out_from_row(
        client, row, sign_document_urls=True, customer_portal_document_urls=True
    )
    it_res = (
        client.table("items")
        .select("title,active")
        .eq("id", row["item_id"])
        .limit(1)
        .execute()
    )
    it_rows = it_res.data or []
    title = str(it_rows[0]["title"]) if it_rows else "Rental item"
    item_active = bool(it_rows[0].get("active", True)) if it_rows else True
    has_contract = _booking_has_executed_contract(client, booking_id)
    payload = base.model_dump()
    payload["item_title"] = title
    payload["has_executed_contract"] = has_contract
    payload["item_active"] = item_active
    return CustomerBookingDetailOut.model_validate(payload)


@router.get("/me/contact", response_model=CustomerContactProfile)
def get_my_contact_profile(
    customer: dict = Depends(require_customer_jwt),
    client: Client = Depends(get_supabase_client),
) -> CustomerContactProfile:
    sub = str(customer["sub"])
    res = (
        client.table("booking_requests")
        .select(
            "customer_email,customer_phone,customer_first_name,customer_last_name,customer_address,created_at"
        )
        .eq("customer_auth0_sub", sub)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved contact from previous bookings.",
        )
    row = data[0]
    try:
        return CustomerContactProfile.model_validate(
            {
                "customer_email": row.get("customer_email"),
                "customer_phone": row.get("customer_phone") or "",
                "customer_first_name": row.get("customer_first_name") or "",
                "customer_last_name": row.get("customer_last_name") or "",
                "customer_address": row.get("customer_address") or "",
            }
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid saved contact from previous bookings.",
        ) from None


@router.get("/{booking_id}/payment-status", response_model=BookingPaymentStatusPublic)
def public_booking_payment_status(booking_id: str, client: Client = Depends(get_supabase_client)):
    """Post-Stripe thank-you page: minimal booking state (no auth; UUID is the secret)."""
    res = (
        client.table("booking_requests")
        .select("id,status,rental_paid_at,rental_payment_status,item_id,deposit_secured_at,deposit_amount")
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    item_res = (
        client.table("items")
        .select("title")
        .eq("id", row["item_id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    item_title = str(item_res[0].get("title") or "Rental") if item_res else "Rental"
    paid = bool(row.get("rental_paid_at"))
    rps = row.get("rental_payment_status")
    dep_secured = bool(row.get("deposit_secured_at"))
    dep_raw = row.get("deposit_amount")
    try:
        requires_deposit = dep_raw is not None and float(dep_raw) > 0
    except (TypeError, ValueError):
        requires_deposit = False
    return BookingPaymentStatusPublic(
        booking_id=str(row["id"]),
        status=str(row.get("status") or ""),
        rental_paid=paid,
        rental_payment_status=str(rps).strip() if rps is not None else None,
        item_title=item_title,
        deposit_secured=dep_secured,
        requires_deposit=requires_deposit,
    )


@router.post("/presign", response_model=BookingPresignResponse, status_code=status.HTTP_201_CREATED)
def presign_booking_uploads(
    body: BookingPresignRequest,
    customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingPresignResponse:
    """Create a booking row and signed Supabase upload URLs (no file bytes on this API)."""
    settings = get_settings()
    if settings.booking_documents_storage != "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Presigned uploads require BOOKING_DOCUMENTS_STORAGE=supabase. "
                "For local storage, use POST /booking-requests with multipart form data."
            ),
        )
    try:
        contact = BookingContactForm(
            customer_email=body.customer_email,
            customer_phone=body.customer_phone,
            customer_first_name=body.customer_first_name,
            customer_last_name=body.customer_last_name,
            customer_address=body.customer_address,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_detail(e),
        ) from e

    try:
        dl_type = normalize_booking_image_content_type(
            body.drivers_license_content_type, "Driver's license"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    lp_ct_raw = (body.license_plate_content_type or "").strip()
    lp_type_norm = None
    if lp_ct_raw:
        try:
            lp_type_norm = normalize_booking_image_content_type(lp_ct_raw, "License plate")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    ins_ct_raw = (body.insurance_card_content_type or "").strip()
    ins_type_norm = None
    if ins_ct_raw:
        try:
            ins_type_norm = normalize_booking_image_content_type(ins_ct_raw, "Insurance card")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    insert_row, _item_title, towable, _num_days, _disc_sub, _tax_rate, _tax_amt, _rental_w_tax, _tax_src, _dep = (
        _validated_booking_insert_row(
            client,
            settings,
            customer,
            body.item_id,
            body.start_date,
            body.end_date,
            contact,
            body.notes,
            delivery_requested=body.delivery_requested,
            pickup_from_site_requested=body.pickup_from_site_requested,
            logistics_address=body.job_site_address,
        )
    )
    insert_row.update(_workflow_from_presign(body))
    if towable and lp_type_norm is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="license_plate_content_type is required for towable items.",
        )
    if not towable and lp_type_norm is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="license_plate_content_type is only allowed for towable items.",
        )

    try:
        insert_res = client.table("booking_requests").insert(insert_row).execute()
    except Exception as exc:
        _maybe_raise_booking_schema_error(exc)
        raise
    data = insert_res.data
    if not data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    row = data[0]
    bid = str(row["id"])
    _upsert_booking_date_hold(client, body.item_id, body.start_date, body.end_date)

    dl_ext = ext_for_content_type(dl_type)
    path_dl = f"{bid}/drivers_license{dl_ext}"
    dl_slot_out: BookingUploadSlot
    lp_slot_out: BookingUploadSlot | None = None
    ins_slot_out: BookingUploadSlot | None = None
    try:
        dl_slot_raw = create_presigned_booking_upload_slot(client, path_dl)
        dl_slot_out = BookingUploadSlot.model_validate(dl_slot_raw)
        if towable and lp_type_norm is not None:
            lp_ext = ext_for_content_type(lp_type_norm)
            path_lp = f"{bid}/license_plate{lp_ext}"
            lp_slot_raw = create_presigned_booking_upload_slot(client, path_lp)
            lp_slot_out = BookingUploadSlot.model_validate(lp_slot_raw)
        if ins_type_norm is not None:
            ins_ext = ext_for_content_type(ins_type_norm)
            path_ins = f"{bid}/insurance_card{ins_ext}"
            ins_slot_raw = create_presigned_booking_upload_slot(client, path_ins)
            ins_slot_out = BookingUploadSlot.model_validate(ins_slot_raw)
    except Exception as exc:
        try:
            client.table("booking_requests").delete().eq("id", bid).execute()
        except Exception:
            pass
        _release_booking_date_hold(client, body.item_id, body.start_date, body.end_date)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create signed upload URLs. Check Supabase Storage configuration.",
        ) from exc

    return BookingPresignResponse(
        booking_id=bid,
        drivers_license=dl_slot_out,
        license_plate=lp_slot_out,
        insurance_card=ins_slot_out,
        expires_in=BOOKING_UPLOAD_PRESIGN_EXPIRES_SEC,
    )


@router.post("/{booking_id}/complete", response_model=BookingRequestOut)
def complete_booking_uploads(
    booking_id: str,
    body: BookingCompleteBody,
    _customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    """After direct-to-Supabase uploads, verify objects and finalize the booking row."""
    settings = get_settings()
    if settings.booking_documents_storage != "supabase":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete step is only used when BOOKING_DOCUMENTS_STORAGE=supabase.",
        )
    res = (
        client.table("booking_requests")
        .select("*")
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    st = row.get("status")
    if st not in (BookingRequestStatus.pending.value, BookingRequestStatus.requested.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft booking uploads (requested / legacy pending) can be completed.",
        )
    if row.get("drivers_license_path") or row.get("license_plate_path"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking documents are already attached.",
        )

    item_res = (
        client.table("items")
        .select("towable")
        .eq("id", row["item_id"])
        .limit(1)
        .execute()
    )
    it_rows = item_res.data or []
    towable = bool(it_rows[0].get("towable")) if it_rows else False

    path_lp: str | None = None
    path_ins: str | None = None
    try:
        assert_booking_document_path(booking_id, body.drivers_license_path, role="drivers_license")
        verify_booking_document_uploaded(client, body.drivers_license_path, "Driver's license")
        if towable:
            if not body.license_plate_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="license_plate_path is required for towable items.",
                )
            assert_booking_document_path(booking_id, body.license_plate_path, role="license_plate")
            verify_booking_document_uploaded(client, body.license_plate_path, "License plate")
            path_lp = body.license_plate_path
        elif body.license_plate_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="license_plate_path is not allowed for non-towable items.",
            )
        if body.insurance_card_path:
            assert_booking_document_path(booking_id, body.insurance_card_path, role="insurance_card")
            verify_booking_document_uploaded(client, body.insurance_card_path, "Insurance card")
            path_ins = body.insurance_card_path
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    try:
        client.table("booking_requests").update(
            {
                "drivers_license_path": body.drivers_license_path,
                "license_plate_path": path_lp,
                "insurance_card_path": path_ins,
            }
        ).eq("id", booking_id).execute()
    except Exception as exc:
        _maybe_raise_booking_schema_error(exc)
        raise

    res2 = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    final = res2.data[0]
    try_notify_admin_approval_needed(client, settings, booking_id)
    return booking_out_from_row(client, final, sign_document_urls=False)


@router.delete("/{booking_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
def abandon_booking_upload(
    booking_id: str,
    client: Client = Depends(get_supabase_client),
) -> None:
    """Drop a pending booking that never completed uploads (cleanup)."""
    settings = get_settings()
    res = (
        client.table("booking_requests")
        .select("id,status,item_id,start_date,end_date,drivers_license_path,license_plate_path")
        .eq("id", booking_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    row = rows[0]
    st = row.get("status")
    if st not in (BookingRequestStatus.pending.value, BookingRequestStatus.requested.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft booking uploads (requested / legacy pending) can be abandoned.",
        )
    if row.get("drivers_license_path") or row.get("license_plate_path"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking already has documents attached.",
        )
    remove_booking_storage_prefix(settings, client, booking_id)
    item_id = str(row["item_id"])
    start = date.fromisoformat(str(row["start_date"]))
    end = date.fromisoformat(str(row["end_date"]))
    client.table("booking_requests").delete().eq("id", booking_id).execute()
    _release_booking_date_hold(client, item_id, start, end)


@router.post("", response_model=BookingRequestOut, status_code=status.HTTP_201_CREATED)
def create_booking_request(
    customer: dict | None = Depends(customer_jwt_claims),
    item_id: str = Form(),
    start_date: date = Form(),
    end_date: date = Form(),
    customer_email: str = Form(),
    customer_phone: str = Form(),
    customer_first_name: str = Form(),
    customer_last_name: str = Form(),
    customer_address: str = Form(),
    notes: str | None = Form(None),
    delivery_requested: str | None = Form(default=None),
    pickup_from_site_requested: str | None = Form(default=None),
    delivery_address: str | None = Form(None),
    tow_vehicle_year: int | None = Form(default=None),
    tow_vehicle_make: str | None = Form(default=None),
    tow_vehicle_model: str | None = Form(default=None),
    tow_vehicle_tow_rating_lbs: int | None = Form(default=None),
    has_brake_controller: str | None = Form(default=None),
    drivers_license: UploadFile = File(),
    license_plate: UploadFile | None = File(default=None),
    insurance_card: UploadFile | None = File(default=None),
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    """Multipart booking create (use when BOOKING_DOCUMENTS_STORAGE=local)."""
    settings = get_settings()
    if settings.booking_documents_storage != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Multipart booking upload is only for BOOKING_DOCUMENTS_STORAGE=local. "
                "With Supabase Storage, use POST /booking-requests/presign then complete."
            ),
        )
    try:
        contact = BookingContactForm(
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_first_name=customer_first_name,
            customer_last_name=customer_last_name,
            customer_address=customer_address,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_detail(e),
        ) from e

    if not drivers_license.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A driver's license image is required.",
        )
    dr_raw = str(delivery_requested or "").strip().lower()
    delivery_requested_bool = dr_raw in ("1", "true", "on", "yes")
    pr_raw = str(pickup_from_site_requested or "").strip().lower()
    pickup_from_site_bool = pr_raw in ("1", "true", "on", "yes")
    needs_logistics = delivery_requested_bool or pickup_from_site_bool
    if needs_logistics and not (delivery_address or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delivery_address (job site) is required when delivery or pickup from site is selected.",
        )

    insert_row, item_title, towable, *_ = _validated_booking_insert_row(
        client,
        settings,
        customer,
        item_id,
        start_date,
        end_date,
        contact,
        notes,
        delivery_requested=delivery_requested_bool,
        pickup_from_site_requested=pickup_from_site_bool,
        logistics_address=delivery_address,
    )
    brake_raw = str(has_brake_controller or "").strip().lower()
    has_brake = brake_raw in ("1", "true", "on", "yes")
    if towable:
        insert_row["tow_vehicle_year"] = tow_vehicle_year
        insert_row["tow_vehicle_make"] = (tow_vehicle_make or "").strip() or None
        insert_row["tow_vehicle_model"] = (tow_vehicle_model or "").strip() or None
        insert_row["tow_vehicle_tow_rating_lbs"] = tow_vehicle_tow_rating_lbs
        insert_row["has_brake_controller"] = has_brake
    elif (
        tow_vehicle_year is not None
        or (tow_vehicle_make or "").strip()
        or (tow_vehicle_model or "").strip()
        or tow_vehicle_tow_rating_lbs is not None
        or brake_raw
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tow vehicle fields are only allowed for towable items.",
        )
    lp_has_file = bool(license_plate and license_plate.filename)
    if towable and not lp_has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A license plate image is required for towable items.",
        )
    if not towable and lp_has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License plate image is only allowed for towable items.",
        )

    try:
        insert_res = client.table("booking_requests").insert(insert_row).execute()
    except Exception as exc:
        _maybe_raise_booking_schema_error(exc)
        raise
    data = insert_res.data
    if not data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    row = data[0]
    bid = row["id"]
    _upsert_booking_date_hold(client, item_id, start_date, end_date)

    try:
        dl_raw, dl_ct = _read_upload(drivers_license)
        try:
            dl_type = validate_image_upload(dl_ct, len(dl_raw), "Driver's license")
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        dl_ext = ext_for_content_type(dl_type)
        path_dl = f"{bid}/drivers_license{dl_ext}"
        save_booking_document(settings, client, path_dl, dl_raw, dl_type)

        path_lp_val = None
        if towable and license_plate is not None:
            lp_raw, lp_ct = _read_upload(license_plate)
            try:
                lp_type = validate_image_upload(lp_ct, len(lp_raw), "License plate")
            except ValueError as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
            lp_ext = ext_for_content_type(lp_type)
            path_lp_val = f"{bid}/license_plate{lp_ext}"
            save_booking_document(settings, client, path_lp_val, lp_raw, lp_type)

        path_ins_val = None
        if insurance_card is not None and insurance_card.filename:
            ins_raw, ins_ct = _read_upload(insurance_card)
            try:
                ins_type = validate_image_upload(ins_ct, len(ins_raw), "Insurance card")
            except ValueError as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
            ins_ext = ext_for_content_type(ins_type)
            path_ins_val = f"{bid}/insurance_card{ins_ext}"
            save_booking_document(settings, client, path_ins_val, ins_raw, ins_type)

        try:
            client.table("booking_requests").update(
                {
                    "drivers_license_path": path_dl,
                    "license_plate_path": path_lp_val,
                    "insurance_card_path": path_ins_val,
                }
            ).eq("id", bid).execute()
        except Exception as exc:
            client.table("booking_requests").delete().eq("id", bid).execute()
            _release_booking_date_hold(client, item_id, start_date, end_date)
            _maybe_raise_booking_schema_error(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_booking_store_error_detail(settings),
            ) from exc
    except HTTPException:
        client.table("booking_requests").delete().eq("id", bid).execute()
        _release_booking_date_hold(client, item_id, start_date, end_date)
        raise
    except Exception as exc:
        client.table("booking_requests").delete().eq("id", bid).execute()
        _release_booking_date_hold(client, item_id, start_date, end_date)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_booking_store_error_detail(settings),
        ) from exc

    res2 = client.table("booking_requests").select("*").eq("id", bid).limit(1).execute()
    final = res2.data[0]
    try_notify_admin_approval_needed(client, settings, str(bid))
    return booking_out_from_row(client, final, sign_document_urls=False)


@router.post("/quote", response_model=BookingQuote)
def quote_booking(
    body: BookingQuoteRequest,
    _customer: dict | None = Depends(customer_jwt_claims),
    client: Client = Depends(get_supabase_client),
) -> BookingQuote:
    """Preview pricing for the UI; the quote email is sent when the customer submits intake."""
    settings = get_settings()
    item_res = (
        client.table("items")
        .select("id,title,cost_per_day,minimum_day_rental,deposit_amount,active,delivery_available")
        .eq("id", body.item_id)
        .limit(1)
        .execute()
    )
    rows = item_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = rows[0]
    if not bool(item.get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item_title = str(item.get("title") or "Rental item")
    cost = _decimal(item["cost_per_day"])
    min_days = int(item["minimum_day_rental"])
    deposit = _decimal(item["deposit_amount"])

    today = _today_utc()
    days = _rental_days_inclusive_or_400(body.start_date, body.end_date)
    ensure_booking_window_day_status(client, body.item_id, today)
    status_res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", body.item_id)
        .gte("day", min(days).isoformat())
        .lte("day", max(days).isoformat())
        .execute()
    )
    open_dates: set[date] = set()
    for r in status_res.data or []:
        d = date.fromisoformat(str(r["day"]))
        if r["status"] == DayStatus.open_for_booking.value:
            open_dates.add(d)

    err = validate_booking_dates(today, body.start_date, body.end_date, min_days, open_dates)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    num_days = len(days)
    base, disc_pct, disc_sub, dep = compute_rental_amounts(cost, num_days, deposit)
    logistics_addr = (
        ((body.job_site_address or "").strip() or None)
        if (body.delivery_requested or body.pickup_from_site_requested)
        else None
    )
    try:
        delivery_fee, delivery_miles, pickup_fee, pickup_miles = compute_logistics_charges(
            client,
            settings,
            item_delivery_available=bool(item.get("delivery_available", True)),
            delivery_requested=body.delivery_requested,
            pickup_from_site_requested=body.pickup_from_site_requested,
            logistics_address=logistics_addr,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    taxable_subtotal = disc_sub + delivery_fee + pickup_fee
    tax_rate, tax_amt, rental_w_tax, _tax_src = _sales_tax_or_http(
        settings,
        taxable_subtotal,
        tax_postal_code=body.tax_postal_code,
        customer_address=(body.customer_address or "").strip() or None,
    )
    return BookingQuote(
        num_days=num_days,
        base_amount=base,
        discount_percent=disc_pct,
        discounted_subtotal=disc_sub,
        deposit_amount=dep,
        delivery_fee=delivery_fee,
        pickup_fee=pickup_fee,
        delivery_distance_miles=delivery_miles,
        pickup_distance_miles=pickup_miles,
        sales_tax_rate_percent=tax_rate,
        sales_tax_amount=tax_amt,
        rental_total_with_tax=rental_w_tax,
        email_sent=False,
    )
