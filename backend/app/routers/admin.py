from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.deps import get_supabase_client, require_admin_stub
from app.schemas import (
    AvailabilityBulkUpdate,
    BookingRequestOut,
    BookingRequestStatus,
    DayStatus,
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

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_stub)])


def _decimal(v: object):
    from decimal import Decimal

    return Decimal(str(v))


def _load_item_detail(client: Client, item_id: str) -> ItemDetail:
    res = (
        client.table("items")
        .select(
            "id,title,description,category,cost_per_day,minimum_day_rental,deposit_amount,user_requirements,towable"
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
    if patch:
        client.table("items").update(patch).eq("id", item_id).execute()
    if body.image_urls is not None:
        client.table("item_images").delete().eq("item_id", item_id).execute()
        for idx, url in enumerate(body.image_urls):
            client.table("item_images").insert(
                {"item_id": item_id, "url": url, "sort_order": idx}
            ).execute()
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
            )
        )
    return out
