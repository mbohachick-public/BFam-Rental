from datetime import date
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from supabase import Client

from app.config import get_settings
from app.deps import customer_jwt_claims, get_supabase_client, require_customer_jwt
from app.schemas import (
    BookingCompleteBody,
    BookingContactForm,
    BookingPaymentStatusPublic,
    BookingPresignRequest,
    BookingPresignResponse,
    BookingQuote,
    BookingQuoteRequest,
    BookingRequestOut,
    BookingRequestStatus,
    BookingUploadSlot,
    CustomerBookingSummary,
    CustomerContactProfile,
    DayStatus,
)
from app.services.booking import compute_rental_amounts, validate_booking_dates
from app.services.delivery_pricing import compute_delivery_charge
from app.services.sales_tax import (
    compute_sales_tax_amount,
    lookup_sales_tax_rate_percent,
    resolve_postal_for_tax,
)
from app.services.item_availability_seed import ensure_booking_window_day_status
from app.services.booking_documents import (
    ext_for_content_type,
    normalize_booking_image_content_type,
    validate_image_upload,
)
from app.services.booking_storage import (
    BOOKING_UPLOAD_PRESIGN_EXPIRES_SEC,
    assert_booking_document_path,
    create_presigned_booking_upload_slot,
    remove_booking_storage_prefix,
    save_booking_document,
    verify_booking_document_uploaded,
)
from app.services.admin_notify import try_notify_admin_approval_needed
from app.services.booking_response import booking_out_from_row
from app.services.dates import iter_days_inclusive
from app.services.quote_email import send_quote_email

router = APIRouter(prefix="/booking-requests", tags=["booking-requests"])


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


def _validate_tow_vehicle_fields_for_towable(
    *,
    towable: bool,
    tow_vehicle_year: int | None,
    tow_vehicle_make: str | None,
    tow_vehicle_model: str | None,
    tow_vehicle_tow_rating_lbs: int | None,
) -> None:
    if not towable:
        return
    if tow_vehicle_year is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tow vehicle year is required for towable pickup rentals.",
        )
    if not (tow_vehicle_make or "").strip() or not (tow_vehicle_model or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tow vehicle make and model are required for towable pickup rentals.",
        )
    if tow_vehicle_tow_rating_lbs is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tow vehicle tow rating (lbs) is required for towable pickup rentals.",
        )
    if tow_vehicle_tow_rating_lbs < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tow vehicle tow rating must be at least 1 lb.",
        )


def _validate_tow_vehicle_for_towable(body: BookingPresignRequest, *, towable: bool) -> None:
    _validate_tow_vehicle_fields_for_towable(
        towable=towable,
        tow_vehicle_year=body.tow_vehicle_year,
        tow_vehicle_make=body.tow_vehicle_make,
        tow_vehicle_model=body.tow_vehicle_model,
        tow_vehicle_tow_rating_lbs=body.tow_vehicle_tow_rating_lbs,
    )


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
    delivery_address: str | None = None,
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
    days = iter_days_inclusive(start_date, end_date)

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
    try:
        delivery_fee, delivery_miles = compute_delivery_charge(
            client,
            settings,
            item_delivery_available=bool(item.get("delivery_available", True)),
            delivery_requested=delivery_requested,
            delivery_address=delivery_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    taxable_subtotal = disc_sub + delivery_fee
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
        "delivery_address": ((delivery_address or "").strip() or None)
        if delivery_requested
        else None,
        "delivery_fee": float(delivery_fee),
        "delivery_distance_miles": float(delivery_miles) if delivery_miles is not None else None,
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
            delivery_address=body.delivery_address,
        )
    )
    insert_row.update(_workflow_from_presign(body))
    _validate_tow_vehicle_for_towable(body, towable=towable)
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

    insert_res = client.table("booking_requests").insert(insert_row).execute()
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
    try:
        dl_slot_raw = create_presigned_booking_upload_slot(client, path_dl)
        dl_slot_out = BookingUploadSlot.model_validate(dl_slot_raw)
        if towable and lp_type_norm is not None:
            lp_ext = ext_for_content_type(lp_type_norm)
            path_lp = f"{bid}/license_plate{lp_ext}"
            lp_slot_raw = create_presigned_booking_upload_slot(client, path_lp)
            lp_slot_out = BookingUploadSlot.model_validate(lp_slot_raw)
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client.table("booking_requests").update(
        {"drivers_license_path": body.drivers_license_path, "license_plate_path": path_lp}
    ).eq("id", booking_id).execute()

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
    delivery_address: str | None = Form(None),
    tow_vehicle_year: int | None = Form(default=None),
    tow_vehicle_make: str | None = Form(default=None),
    tow_vehicle_model: str | None = Form(default=None),
    tow_vehicle_tow_rating_lbs: int | None = Form(default=None),
    has_brake_controller: str | None = Form(default=None),
    drivers_license: UploadFile = File(),
    license_plate: UploadFile | None = File(default=None),
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
    if delivery_requested_bool and not (delivery_address or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delivery_address is required when delivery is requested.",
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
        delivery_address=delivery_address,
    )
    brake_raw = str(has_brake_controller or "").strip().lower()
    has_brake = brake_raw in ("1", "true", "on", "yes")
    _validate_tow_vehicle_fields_for_towable(
        towable=towable,
        tow_vehicle_year=tow_vehicle_year,
        tow_vehicle_make=tow_vehicle_make,
        tow_vehicle_model=tow_vehicle_model,
        tow_vehicle_tow_rating_lbs=tow_vehicle_tow_rating_lbs,
    )
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

    insert_res = client.table("booking_requests").insert(insert_row).execute()
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

        client.table("booking_requests").update(
            {"drivers_license_path": path_dl, "license_plate_path": path_lp_val}
        ).eq("id", bid).execute()
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
    """Preview pricing; emails the quote when SMTP is configured."""
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
    days = iter_days_inclusive(body.start_date, body.end_date)
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
    try:
        delivery_fee, delivery_miles = compute_delivery_charge(
            client,
            settings,
            item_delivery_available=bool(item.get("delivery_available", True)),
            delivery_requested=body.delivery_requested,
            delivery_address=body.delivery_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    taxable_subtotal = disc_sub + delivery_fee
    tax_rate, tax_amt, rental_w_tax, _tax_src = _sales_tax_or_http(
        settings,
        taxable_subtotal,
        tax_postal_code=body.tax_postal_code,
        customer_address=None,
    )
    emailed = send_quote_email(
        settings,
        to_addr=str(body.customer_email),
        item_title=item_title,
        start_date=body.start_date.isoformat(),
        end_date=body.end_date.isoformat(),
        num_days=num_days,
        discounted_subtotal=disc_sub,
        sales_tax_rate_percent=tax_rate,
        sales_tax_amount=tax_amt,
        rental_total_with_tax=rental_w_tax,
        deposit_amount=dep,
        delivery_fee=delivery_fee,
        delivery_distance_miles=delivery_miles,
    )
    return BookingQuote(
        num_days=num_days,
        base_amount=base,
        discount_percent=disc_pct,
        discounted_subtotal=disc_sub,
        deposit_amount=dep,
        delivery_fee=delivery_fee,
        delivery_distance_miles=delivery_miles,
        sales_tax_rate_percent=tax_rate,
        sales_tax_amount=tax_amt,
        rental_total_with_tax=rental_w_tax,
        email_sent=emailed,
    )
