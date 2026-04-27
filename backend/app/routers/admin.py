import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from supabase import Client

from app.config import get_settings
from app.deps import get_supabase_client, require_admin
from app.schemas import (
    AvailabilityBulkUpdate,
    BookingApproveBody,
    BookingDeclineBody,
    BookingRequestOut,
    BookingRequestStatus,
    DayAvailability,
    DayStatus,
    DeliverySettingsOut,
    DeliverySettingsUpdate,
    E2eCleanupBody,
    E2eCleanupResult,
    ItemCreate,
    ItemDetail,
    ItemImageOut,
    ItemSummary,
    ItemUpdate,
    PaymentPath,
    ResendSignatureOut,
    StripeCheckoutSessionOut,
    StripeCheckoutSyncOut,
    payment_path_from_stored,
)
from app.repos.item_images import load_images_for_items
from app.services.booking_response import booking_out_from_row
from app.services.booking_storage import admin_booking_file_response
from app.services.dates import iter_days_inclusive
from app.services.item_availability import day_availability_range
from app.services.item_availability_seed import seed_day_status_for_new_item
from app.services.item_images_storage import (
    MAX_ITEM_IMAGES,
    save_item_image_bytes,
    try_delete_item_image_for_url,
)
from app.services.e2e_cleanup import cleanup_e2e_test_items
from app.services.admin_notify import try_notify_admin_confirm_needed
from app.services.booking_events import log_booking_event
from app.services.contract_signing import create_signing_package, signing_url
from app.services.delivery_pricing import load_delivery_settings_row
from app.services.pickup_instructions_email import try_send_pickup_instructions_after_confirm
from app.services.quote_email import (
    send_booking_approved_email,
    send_booking_declined_email,
)
from app.services.stripe_checkout import create_checkout_session_for_booking
from app.services.stripe_deposit_refund import refund_stripe_deposit_for_booking
from app.services.stripe_payment_reconcile import sync_booking_checkout_sessions_from_stripe

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/session")
def admin_session() -> dict[str, bool]:
    """Confirm the caller's Bearer token is authorized for admin routes (same checks as require_admin)."""
    return {"admin": True}


def _decimal(v: object) -> Decimal:
    return Decimal(str(v))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payment_collection_url_from_template(settings, booking_id: str) -> str | None:
    t = (settings.payment_collection_url_template or "").strip()
    if not t:
        return None
    return t.replace("{booking_id}", booking_id).replace("{id}", booking_id)


def _try_create_card_checkout_sessions(
    client: Client, settings, booking_id: str
) -> dict[str, Any] | None:
    """Create Stripe Checkout sessions when possible; returns None if Stripe is not configured."""
    if not (settings.stripe_secret_key or "").strip():
        return None
    try:
        return create_checkout_session_for_booking(client, settings, booking_id=booking_id)
    except ValueError as e:
        logger.warning("stripe_checkout_at_email_skipped booking_id=%s err=%s", booking_id, e)
        return None


_APPROVABLE_STATUSES = frozenset(
    {
        BookingRequestStatus.requested.value,
        BookingRequestStatus.under_review.value,
        BookingRequestStatus.pending.value,
    }
)

_DECLINABLE_STATUSES = frozenset(
    {
        BookingRequestStatus.requested.value,
        BookingRequestStatus.under_review.value,
        BookingRequestStatus.pending.value,
        BookingRequestStatus.approved_awaiting_signature.value,
        BookingRequestStatus.approved_pending_payment.value,
        BookingRequestStatus.approved_pending_check_clearance.value,
    }
)

_PRE_CONFIRM_APPROVED = frozenset(
    {
        BookingRequestStatus.approved_pending_payment.value,
        BookingRequestStatus.approved_pending_check_clearance.value,
    }
)


def _load_item_detail(client: Client, item_id: str) -> ItemDetail:
    res = (
        client.table("items")
        .select(
            "id,title,description,category,cost_per_day,minimum_day_rental,deposit_amount,user_requirements,towable,delivery_available,active"
        )
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    row = rows[0]
    img_res = (
        client.table("item_images")
        .select("id,url,sort_order")
        .eq("item_id", item_id)
        .order("sort_order")
        .execute()
    )
    imgs = img_res.data or []
    images = [
        ItemImageOut(id=i["id"], url=i["url"], sort_order=int(i["sort_order"])) for i in imgs
    ]
    urls = [i.url for i in images]
    return ItemDetail(
        id=row["id"],
        title=row["title"],
        category=row["category"],
        cost_per_day=_decimal(row["cost_per_day"]),
        minimum_day_rental=int(row["minimum_day_rental"]),
        deposit_amount=_decimal(row["deposit_amount"]),
        towable=bool(row.get("towable", False)),
        delivery_available=bool(row.get("delivery_available", True)),
        image_urls=urls,
        description=row["description"],
        user_requirements=row["user_requirements"],
        images=images,
        active=bool(row.get("active", True)),
    )


def _delivery_settings_out(client: Client, settings) -> DeliverySettingsOut:
    row = load_delivery_settings_row(client)
    max_m = row.get("max_delivery_miles")
    return DeliverySettingsOut(
        id=int(row.get("id") or 1),
        enabled=bool(row.get("enabled")),
        origin_address=str(row.get("origin_address") or ""),
        price_per_mile=_decimal(row.get("price_per_mile") or 0),
        minimum_fee=_decimal(row.get("minimum_fee") or 0),
        free_miles=_decimal(row.get("free_miles") or 0),
        max_delivery_miles=_decimal(max_m) if max_m is not None else None,
        google_maps_configured=bool((settings.google_maps_api_key or "").strip()),
    )


@router.get("/delivery-settings", response_model=DeliverySettingsOut)
def admin_get_delivery_settings(
    client: Client = Depends(get_supabase_client),
) -> DeliverySettingsOut:
    return _delivery_settings_out(client, get_settings())


@router.patch("/delivery-settings", response_model=DeliverySettingsOut)
def admin_patch_delivery_settings(
    body: DeliverySettingsUpdate,
    client: Client = Depends(get_supabase_client),
) -> DeliverySettingsOut:
    settings = get_settings()
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        return _delivery_settings_out(client, settings)
    patch: dict[str, Any] = {}
    if "enabled" in raw:
        patch["enabled"] = raw["enabled"]
    if "origin_address" in raw:
        patch["origin_address"] = raw["origin_address"]
    if "price_per_mile" in raw:
        patch["price_per_mile"] = float(raw["price_per_mile"])
    if "minimum_fee" in raw:
        patch["minimum_fee"] = float(raw["minimum_fee"])
    if "free_miles" in raw:
        patch["free_miles"] = float(raw["free_miles"])
    if "max_delivery_miles" in raw:
        v = raw["max_delivery_miles"]
        patch["max_delivery_miles"] = float(v) if v is not None else None
    upd = client.table("delivery_settings").update(patch).eq("id", 1).execute()
    if not (upd.data or []):
        ins: dict[str, Any] = {
            "id": 1,
            "enabled": False,
            "origin_address": "",
            "price_per_mile": 0.0,
            "minimum_fee": 0.0,
            "free_miles": 0.0,
            "max_delivery_miles": None,
        }
        ins.update(patch)
        client.table("delivery_settings").insert(ins).execute()
    return _delivery_settings_out(client, settings)


@router.post("/items", response_model=ItemDetail, status_code=status.HTTP_201_CREATED)
def admin_create_item(body: ItemCreate, client: Client = Depends(get_supabase_client)) -> ItemDetail:
    ins = (
        client.table("items")
        .insert(
            {
                "title": body.title,
                "description": body.description,
                "category": body.category,
                "cost_per_day": float(body.cost_per_day),
                "minimum_day_rental": body.minimum_day_rental,
                "deposit_amount": float(body.deposit_amount),
                "user_requirements": body.user_requirements,
                "towable": body.towable,
                "delivery_available": body.delivery_available,
                "active": body.active,
            }
        )
        .execute()
    )
    if not ins.data:
        raise HTTPException(status_code=500, detail="Failed to create item")
    item_id = ins.data[0]["id"]
    for idx, url in enumerate(body.image_urls):
        client.table("item_images").insert(
            {"item_id": item_id, "url": url, "sort_order": idx}
        ).execute()
    seed_day_status_for_new_item(client, item_id)
    return _load_item_detail(client, item_id)


@router.patch("/items/{item_id}", response_model=ItemDetail)
def admin_update_item(
    item_id: str, body: ItemUpdate, client: Client = Depends(get_supabase_client)
) -> ItemDetail:
    _load_item_detail(client, item_id)
    patch: dict = {}
    if body.title is not None:
        patch["title"] = body.title
    if body.description is not None:
        patch["description"] = body.description
    if body.category is not None:
        patch["category"] = body.category
    if body.cost_per_day is not None:
        patch["cost_per_day"] = float(body.cost_per_day)
    if body.minimum_day_rental is not None:
        patch["minimum_day_rental"] = body.minimum_day_rental
    if body.deposit_amount is not None:
        patch["deposit_amount"] = float(body.deposit_amount)
    if body.user_requirements is not None:
        patch["user_requirements"] = body.user_requirements
    if body.towable is not None:
        patch["towable"] = body.towable
    if body.delivery_available is not None:
        patch["delivery_available"] = body.delivery_available
    if body.active is not None:
        patch["active"] = body.active
    if patch:
        client.table("items").update(patch).eq("id", item_id).execute()
    if body.image_urls is not None:
        settings = get_settings()
        old_rows = (
            client.table("item_images").select("url").eq("item_id", item_id).execute().data
            or []
        )
        for old in old_rows:
            try_delete_item_image_for_url(settings, client, str(old["url"]))
        client.table("item_images").delete().eq("item_id", item_id).execute()
        for idx, url in enumerate(body.image_urls):
            client.table("item_images").insert(
                {"item_id": item_id, "url": url, "sort_order": idx}
            ).execute()
    return _load_item_detail(client, item_id)


@router.post("/items/{item_id}/images", response_model=ItemImageOut)
async def admin_upload_item_image(
    item_id: str,
    file: UploadFile = File(...),
    client: Client = Depends(get_supabase_client),
) -> ItemImageOut:
    settings = get_settings()
    _load_item_detail(client, item_id)
    existing = client.table("item_images").select("id").eq("item_id", item_id).execute().data or []
    if len(existing) >= MAX_ITEM_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_ITEM_IMAGES} images per item.",
        )
    raw = await file.read()
    max_res = (
        client.table("item_images")
        .select("sort_order")
        .eq("item_id", item_id)
        .order("sort_order", desc=True)
        .limit(1)
        .execute()
    )
    max_rows = max_res.data or []
    next_order = int(max_rows[0]["sort_order"]) + 1 if max_rows else 0
    try:
        url = save_item_image_bytes(
            settings,
            client,
            item_id,
            raw,
            file.content_type or "application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    ins = (
        client.table("item_images")
        .insert({"item_id": item_id, "url": url, "sort_order": next_order})
        .execute()
    )
    if not ins.data:
        raise HTTPException(status_code=500, detail="Failed to save image record")
    row = ins.data[0]
    return ItemImageOut(
        id=row["id"], url=row["url"], sort_order=int(row["sort_order"])
    )


@router.delete("/items/{item_id}/images/{image_id}", response_model=ItemDetail)
def admin_delete_item_image(
    item_id: str,
    image_id: str,
    client: Client = Depends(get_supabase_client),
) -> ItemDetail:
    settings = get_settings()
    _load_item_detail(client, item_id)
    row_res = (
        client.table("item_images")
        .select("id,url")
        .eq("id", image_id)
        .eq("item_id", item_id)
        .limit(1)
        .execute()
    )
    rows = row_res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    try_delete_item_image_for_url(settings, client, str(rows[0]["url"]))
    client.table("item_images").delete().eq("id", image_id).execute()
    return _load_item_detail(client, item_id)


@router.put("/items/{item_id}/availability", status_code=status.HTTP_204_NO_CONTENT)
def admin_set_availability(
    item_id: str, body: AvailabilityBulkUpdate, client: Client = Depends(get_supabase_client)
) -> None:
    _load_item_detail(client, item_id)
    rows = [
        {
            "item_id": item_id,
            "day": u.day.isoformat(),
            "status": u.status.value,
        }
        for u in body.days
    ]
    if rows:
        client.table("item_day_status").upsert(rows).execute()


@router.get("/booking-requests", response_model=list[BookingRequestOut])
def admin_list_bookings(
    client: Client = Depends(get_supabase_client),
    status: str | None = None,
) -> list[BookingRequestOut]:
    q = client.table("booking_requests").select("*")
    if status and status.strip():
        q = q.eq("status", status.strip())
    res = q.order("created_at", desc=True).execute()
    return [
        booking_out_from_row(client, row, sign_document_urls=True)
        for row in (res.data or [])
    ]


@router.get("/booking-requests/{request_id}", response_model=BookingRequestOut)
def admin_get_booking(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking request not found")
    out = booking_out_from_row(client, rows[0], sign_document_urls=True)
    it_res = (
        client.table("items")
        .select("title")
        .eq("id", out.item_id)
        .limit(1)
        .execute()
    )
    it_rows = it_res.data or []
    title = str(it_rows[0]["title"]) if it_rows else None
    return out.model_copy(update={"item_title": title})


@router.get("/booking-requests/{request_id}/files/drivers-license")
def admin_booking_drivers_license_file(
    request_id: str, client: Client = Depends(get_supabase_client)
):
    return admin_booking_file_response(client, request_id, "drivers-license")


@router.get("/booking-requests/{request_id}/files/license-plate")
def admin_booking_license_plate_file(
    request_id: str, client: Client = Depends(get_supabase_client)
):
    return admin_booking_file_response(client, request_id, "license-plate")


@router.post("/booking-requests/{request_id}/approve", response_model=BookingRequestOut)
def admin_approve_booking(
    request_id: str,
    body: BookingApproveBody,
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    settings = get_settings()
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    st = str(row.get("status") or "")
    if st not in _APPROVABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Only requested / under_review / legacy pending bookings can be approved.",
        )
    item_res = (
        client.table("items")
        .select("title")
        .eq("id", row["item_id"])
        .limit(1)
        .execute()
    )
    item_title = str((item_res.data or [{}])[0].get("title") or "Rental item")
    try:
        raw_token = create_signing_package(
            client,
            settings,
            booking_id=request_id,
            booking_row=row,
            item_title=item_title,
            payment_path=body.payment_path,
        )
    except Exception as exc:
        logger.exception(
            "create_signing_package failed for booking %s (apply Specs/supabase-setup.sql if missing tables/enum)",
            request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Could not create signing package. Run Specs/supabase-setup.sql "
                f"(see Specs/contract-signing/README.md). ({exc})"
            ),
        ) from exc
    next_status = BookingRequestStatus.approved_awaiting_signature.value
    pay_url = _payment_collection_url_from_template(settings, request_id)
    now = _now_iso()
    client.table("booking_requests").update(
        {
            "status": next_status,
            "payment_path": body.payment_path.value,
            "approved_at": now,
            **({"payment_collection_url": pay_url} if pay_url is not None else {}),
        }
    ).eq("id", request_id).execute()
    log_booking_event(
        client,
        booking_id=request_id,
        event_type="approved",
        actor_type="admin",
        metadata={"payment_path": body.payment_path.value, "status": next_status},
    )
    _try_create_card_checkout_sessions(client, settings, request_id)
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    row2 = res2.data[0]
    sign_url = signing_url(settings, raw_token)
    to_addr = (row2.get("customer_email") or "").strip()
    if to_addr:
        send_booking_approved_email(
            settings,
            to_addr=to_addr,
            item_title=item_title,
            start_date=str(row2["start_date"]),
            end_date=str(row2["end_date"]),
            rental_total_with_tax=_decimal(row2.get("rental_total_with_tax") or 0),
            deposit_amount=_decimal(row2.get("deposit_amount") or 0),
            payment_collection_url=row2.get("payment_collection_url") or pay_url,
            signing_url=sign_url,
            rental_checkout_url=row2.get("stripe_checkout_url"),
            deposit_checkout_url=row2.get("stripe_deposit_checkout_url"),
            payment_path=body.payment_path.value,
        )
    return booking_out_from_row(client, row2, sign_document_urls=True, signing_url=sign_url)


@router.post(
    "/booking-requests/{request_id}/resend-signature",
    response_model=ResendSignatureOut,
)
def admin_resend_signature_link(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> ResendSignatureOut:
    settings = get_settings()
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    if str(row.get("status") or "") != BookingRequestStatus.approved_awaiting_signature.value:
        raise HTTPException(
            status_code=400,
            detail="Resend is only available while awaiting customer signature.",
        )
    path_raw = row.get("payment_path")
    if not path_raw:
        raise HTTPException(status_code=400, detail="Booking is missing payment_path.")
    try:
        pp = payment_path_from_stored(path_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payment_path on booking.") from e
    item_res = (
        client.table("items")
        .select("title")
        .eq("id", row["item_id"])
        .limit(1)
        .execute()
    )
    item_title = str((item_res.data or [{}])[0].get("title") or "Rental item")
    raw_token = create_signing_package(
        client,
        settings,
        booking_id=request_id,
        booking_row=row,
        item_title=item_title,
        payment_path=pp,
    )
    client.table("booking_requests").update({"payment_path": PaymentPath.card.value}).eq("id", request_id).execute()
    sign_url = signing_url(settings, raw_token)
    _try_create_card_checkout_sessions(client, settings, request_id)
    res_row = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    row_f = (res_row.data or [row])[0]
    to_addr = (row_f.get("customer_email") or "").strip()
    if to_addr:
        send_booking_approved_email(
            settings,
            to_addr=to_addr,
            item_title=item_title,
            start_date=str(row_f["start_date"]),
            end_date=str(row_f["end_date"]),
            rental_total_with_tax=_decimal(row_f.get("rental_total_with_tax") or 0),
            deposit_amount=_decimal(row_f.get("deposit_amount") or 0),
            payment_collection_url=row_f.get("payment_collection_url"),
            signing_url=sign_url,
            rental_checkout_url=row_f.get("stripe_checkout_url"),
            deposit_checkout_url=row_f.get("stripe_deposit_checkout_url"),
            payment_path=pp.value,
        )
    return ResendSignatureOut(signing_url=sign_url)


@router.post(
    "/booking-requests/{request_id}/stripe-checkout-session",
    response_model=StripeCheckoutSessionOut,
)
def admin_create_stripe_checkout_session(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> StripeCheckoutSessionOut:
    """Create Stripe Checkout for card path after signature (rental total + deposit when configured)."""
    settings = get_settings()
    try:
        out = create_checkout_session_for_booking(client, settings, booking_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("stripe_checkout_session_failed booking_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe checkout could not be created: {e}",
        ) from e
    return StripeCheckoutSessionOut(
        stripe_checkout_session_id=out["stripe_checkout_session_id"],
        stripe_checkout_url=out["stripe_checkout_url"],
        stripe_checkout_created_at=out["stripe_checkout_created_at"],
        stripe_deposit_checkout_session_id=out.get("stripe_deposit_checkout_session_id"),
        stripe_deposit_checkout_url=out.get("stripe_deposit_checkout_url"),
        stripe_deposit_checkout_created_at=out.get("stripe_deposit_checkout_created_at"),
        stripe_checkout_email_status="skipped_payment_links_in_approval_email",
    )


@router.post("/booking-requests/{request_id}/sync-stripe-checkout", response_model=StripeCheckoutSyncOut)
def admin_sync_stripe_checkout(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> StripeCheckoutSyncOut:
    """
    Retrieve stored Checkout Session ids from Stripe; if Stripe shows paid, apply the same
    updates as the webhook (for missed webhooks in dev or network blips).
    """
    settings = get_settings()
    try:
        result = sync_booking_checkout_sessions_from_stripe(client, settings, booking_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("admin_sync_stripe_checkout_failed booking_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not sync with Stripe: {e}",
        ) from e
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res2.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking request not found")
    return StripeCheckoutSyncOut(
        actions=result.get("actions") or [],
        booking=booking_out_from_row(client, rows[0], sign_document_urls=True),
    )


@router.post("/booking-requests/{request_id}/refund-stripe-deposit", response_model=BookingRequestOut)
def admin_refund_stripe_deposit(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    """Partial Stripe refund for the security deposit (combined Checkout with deposit line only)."""
    settings = get_settings()
    try:
        refund_stripe_deposit_for_booking(client, settings, booking_id=request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.exception("admin_refund_stripe_deposit_failed booking_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe refund failed: {e}",
        ) from e
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res2.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    return booking_out_from_row(client, rows[0], sign_document_urls=True)


@router.post("/booking-requests/{request_id}/mark-rental-paid", response_model=BookingRequestOut)
def admin_mark_rental_paid(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    settings = get_settings()
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    if str(row.get("status") or "") not in _PRE_CONFIRM_APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Rental paid can only be marked while awaiting payment or check clearance.",
        )
    client.table("booking_requests").update(
        {"rental_paid_at": _now_iso(), "rental_payment_status": "paid"}
    ).eq("id", request_id).execute()
    log_booking_event(client, booking_id=request_id, event_type="rental_paid_marked", actor_type="admin")
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    try_notify_admin_confirm_needed(client, settings, request_id)
    return booking_out_from_row(client, res2.data[0], sign_document_urls=True)


@router.post("/booking-requests/{request_id}/mark-deposit-secured", response_model=BookingRequestOut)
def admin_mark_deposit_secured(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    if str(row.get("status") or "") not in _PRE_CONFIRM_APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Deposit can only be marked while awaiting payment or check clearance.",
        )
    client.table("booking_requests").update({"deposit_secured_at": _now_iso()}).eq("id", request_id).execute()
    log_booking_event(client, booking_id=request_id, event_type="deposit_secured_marked", actor_type="admin")
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    try_notify_admin_confirm_needed(client, get_settings(), request_id)
    return booking_out_from_row(client, res2.data[0], sign_document_urls=True)


@router.post("/booking-requests/{request_id}/mark-agreement-signed", response_model=BookingRequestOut)
def admin_mark_agreement_signed(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    if str(row.get("status") or "") not in _PRE_CONFIRM_APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Agreement can only be marked while awaiting payment or check clearance.",
        )
    client.table("booking_requests").update({"agreement_signed_at": _now_iso()}).eq("id", request_id).execute()
    log_booking_event(client, booking_id=request_id, event_type="agreement_signed_marked", actor_type="admin")
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    try_notify_admin_confirm_needed(client, get_settings(), request_id)
    return booking_out_from_row(client, res2.data[0], sign_document_urls=True)


@router.post("/booking-requests/{request_id}/confirm", response_model=BookingRequestOut)
def admin_confirm_booking(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    st = str(row.get("status") or "")
    if st not in _PRE_CONFIRM_APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Only approved (awaiting payment) bookings can be confirmed.",
        )
    missing: list[str] = []
    rp = str(row.get("rental_payment_status") or "").strip().lower()
    if not row.get("rental_paid_at") and rp != "paid":
        missing.append("rental_paid_at")
    dep_need = False
    try:
        d0 = row.get("deposit_amount")
        dep_need = d0 is not None and Decimal(str(d0)) > 0
    except Exception:
        dep_need = row.get("deposit_amount") is not None
    if dep_need and not row.get("deposit_secured_at"):
        missing.append("deposit_secured_at")
    if not row.get("agreement_signed_at"):
        missing.append("agreement_signed_at")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Confirm blocked until marked: {', '.join(missing)}.",
        )
    item_id = row["item_id"]
    start = date.fromisoformat(str(row["start_date"]))
    end = date.fromisoformat(str(row["end_date"]))
    days = iter_days_inclusive(start, end)
    upsert_rows = [
        {"item_id": item_id, "day": d.isoformat(), "status": DayStatus.booked.value} for d in days
    ]
    if upsert_rows:
        client.table("item_day_status").upsert(upsert_rows).execute()
    client.table("booking_requests").update({"status": BookingRequestStatus.confirmed.value}).eq(
        "id", request_id
    ).execute()
    log_booking_event(client, booking_id=request_id, event_type="confirmed", actor_type="admin")
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    try_send_pickup_instructions_after_confirm(client, get_settings(), res2.data[0])
    return booking_out_from_row(client, res2.data[0], sign_document_urls=True)


@router.post("/booking-requests/{request_id}/decline", response_model=BookingRequestOut)
def admin_decline_booking(
    request_id: str,
    body: BookingDeclineBody,
    client: Client = Depends(get_supabase_client),
) -> BookingRequestOut:
    settings = get_settings()
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    st = str(row.get("status") or "")
    if st not in _DECLINABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="This booking cannot be declined from its current status.",
        )
    item_id = row["item_id"]
    item_res = (
        client.table("items")
        .select("title")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    item_rows = item_res.data or []
    item_title = str(item_rows[0]["title"]) if item_rows else "Rental item"
    start = date.fromisoformat(str(row["start_date"]))
    end = date.fromisoformat(str(row["end_date"]))
    days = iter_days_inclusive(start, end)
    reopen_rows = [
        {"item_id": item_id, "day": d.isoformat(), "status": DayStatus.open_for_booking.value}
        for d in days
    ]
    if reopen_rows:
        client.table("item_day_status").upsert(reopen_rows).execute()
    client.table("booking_requests").update(
        {
            "status": BookingRequestStatus.declined.value,
            "decline_reason": body.reason,
        }
    ).eq("id", request_id).execute()
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    row2 = res2.data[0]
    email_sent = False
    to_addr = (row.get("customer_email") or "").strip()
    if to_addr:
        email_sent = send_booking_declined_email(
            settings,
            to_addr=to_addr,
            item_title=item_title,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            reason=body.reason,
        )
    log_booking_event(
        client,
        booking_id=request_id,
        event_type="declined",
        actor_type="admin",
        metadata={"reason": body.reason},
    )
    return booking_out_from_row(
        client, row2, sign_document_urls=True, decline_email_sent=email_sent
    )


@router.get("/items", response_model=list[ItemSummary])
def admin_list_items(client: Client = Depends(get_supabase_client)) -> list[ItemSummary]:
    res = client.table("items").select("*").order("title").execute()
    rows = res.data or []
    by_item = load_images_for_items(client, [r["id"] for r in rows])
    out: list[ItemSummary] = []
    for row in rows:
        imgs = by_item.get(row["id"], [])
        urls = [i["url"] for i in sorted(imgs, key=lambda x: x["sort_order"])]
        out.append(
            ItemSummary(
                id=row["id"],
                title=row["title"],
                category=row["category"],
                cost_per_day=_decimal(row["cost_per_day"]),
                minimum_day_rental=int(row["minimum_day_rental"]),
                deposit_amount=_decimal(row["deposit_amount"]),
                towable=bool(row.get("towable", False)),
                delivery_available=bool(row.get("delivery_available", True)),
                image_urls=urls,
                active=bool(row.get("active", True)),
            )
        )
    return out


@router.get("/items/{item_id}", response_model=ItemDetail)
def admin_get_item(item_id: str, client: Client = Depends(get_supabase_client)) -> ItemDetail:
    """Item detail including inactive items (not exposed on public GET /items/{id})."""
    return _load_item_detail(client, item_id)


@router.get("/items/{item_id}/availability", response_model=list[DayAvailability])
def admin_get_item_availability(
    item_id: str,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    client: Client = Depends(get_supabase_client),
) -> list[DayAvailability]:
    """Availability for any item, including inactive (public GET hides inactive items)."""
    _load_item_detail(client, item_id)
    return day_availability_range(client, item_id, date_from, date_to)


@router.post("/maintenance/cleanup-e2e-test-data", response_model=E2eCleanupResult)
def admin_cleanup_e2e_test_data(
    body: E2eCleanupBody,
    client: Client = Depends(get_supabase_client),
) -> E2eCleanupResult:
    """Remove items in e2e-test / e2e-admin categories and related storage (booking docs, images)."""
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm=true to run cleanup",
        )
    settings = get_settings()
    items_deleted, bookings_processed = cleanup_e2e_test_items(settings, client)
    return E2eCleanupResult(
        items_deleted=items_deleted,
        bookings_processed_for_file_cleanup=bookings_processed,
    )
