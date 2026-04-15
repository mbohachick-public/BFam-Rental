from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from supabase import Client

from app.config import get_settings
from app.deps import get_supabase_client, require_admin
from app.schemas import (
    AvailabilityBulkUpdate,
    BookingDeclineBody,
    BookingRequestOut,
    BookingRequestStatus,
    DayAvailability,
    DayStatus,
    E2eCleanupBody,
    E2eCleanupResult,
    ItemCreate,
    ItemDetail,
    ItemImageOut,
    ItemSummary,
    ItemUpdate,
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
from app.services.quote_email import send_booking_declined_email

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _decimal(v: object):
    from decimal import Decimal

    return Decimal(str(v))


def _load_item_detail(client: Client, item_id: str) -> ItemDetail:
    res = (
        client.table("items")
        .select(
            "id,title,description,category,cost_per_day,minimum_day_rental,deposit_amount,user_requirements,towable,active"
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
        image_urls=urls,
        description=row["description"],
        user_requirements=row["user_requirements"],
        images=images,
        active=bool(row.get("active", True)),
    )


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
def admin_list_bookings(client: Client = Depends(get_supabase_client)) -> list[BookingRequestOut]:
    res = (
        client.table("booking_requests")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return [
        booking_out_from_row(client, row, sign_document_urls=True)
        for row in (res.data or [])
    ]


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


@router.post("/booking-requests/{request_id}/accept", response_model=BookingRequestOut)
def admin_accept_booking(
    request_id: str, client: Client = Depends(get_supabase_client)
) -> BookingRequestOut:
    res = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Booking request not found")
    row = rows[0]
    if row["status"] != BookingRequestStatus.pending.value:
        raise HTTPException(status_code=400, detail="Only pending requests can be accepted")
    item_id = row["item_id"]
    start = date.fromisoformat(str(row["start_date"]))
    end = date.fromisoformat(str(row["end_date"]))
    days = iter_days_inclusive(start, end)
    upsert_rows = [
        {"item_id": item_id, "day": d.isoformat(), "status": DayStatus.booked.value} for d in days
    ]
    if upsert_rows:
        client.table("item_day_status").upsert(upsert_rows).execute()
    client.table("booking_requests").update({"status": BookingRequestStatus.accepted.value}).eq(
        "id", request_id
    ).execute()
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    row2 = res2.data[0]
    return booking_out_from_row(client, row2, sign_document_urls=True)


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
    if row["status"] != BookingRequestStatus.pending.value:
        raise HTTPException(status_code=400, detail="Only pending requests can be declined")
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
            "status": BookingRequestStatus.rejected.value,
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
