import mimetypes
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from supabase import Client

from app.config import get_settings
from app.deps import get_supabase_client
from app.repos.item_images import load_images_for_items
from app.schemas import DayAvailability, DayStatus, ItemDetail, ItemImageOut, ItemSummary
from app.services.dates import iter_days_inclusive
from app.services.item_availability import day_availability_range
from app.services.item_images_storage import local_asset_file_path

router = APIRouter(prefix="/items", tags=["items"])


def _decimal(v: object) -> Decimal:
    return Decimal(str(v))


@router.get("", response_model=list[ItemSummary])
def list_items(
    category: str | None = None,
    min_cost_per_day: Decimal | None = None,
    max_cost_per_day: Decimal | None = None,
    open_from: date | None = None,
    open_to: date | None = None,
    client: Client = Depends(get_supabase_client),
) -> list[ItemSummary]:
    if (open_from is None) ^ (open_to is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both open_from and open_to are required to filter by open-for-booking dates.",
        )
    if open_from and open_to and open_from > open_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="open_from must be on or before open_to.",
        )

    q = client.table("items").select(
        "id,title,description,category,cost_per_day,minimum_day_rental,deposit_amount,user_requirements,towable,active"
    ).eq("active", True)
    if category and category.strip():
        q = q.eq("category", category.strip())
    res = q.order("title").execute()
    rows = res.data or []

    filtered: list[dict] = []
    for row in rows:
        c = _decimal(row["cost_per_day"])
        if min_cost_per_day is not None and c < min_cost_per_day:
            continue
        if max_cost_per_day is not None and c > max_cost_per_day:
            continue
        filtered.append(row)

    if open_from and open_to:
        needed_days = len(iter_days_inclusive(open_from, open_to))
        if needed_days == 0:
            return []
        ids = [r["id"] for r in filtered]
        if not ids:
            filtered = []
        else:
            st_res = (
                client.table("item_day_status")
                .select("item_id")
                .eq("status", DayStatus.open_for_booking.value)
                .in_("item_id", ids)
                .gte("day", open_from.isoformat())
                .lte("day", open_to.isoformat())
                .execute()
            )
            counts = Counter(r["item_id"] for r in (st_res.data or []))
            allowed_ids = {i for i, n in counts.items() if n == needed_days}
            filtered = [r for r in filtered if r["id"] in allowed_ids]

    by_item = load_images_for_items(client, [r["id"] for r in filtered])
    out: list[ItemSummary] = []
    for row in filtered:
        c = _decimal(row["cost_per_day"])
        imgs = by_item.get(row["id"], [])
        urls = [i["url"] for i in sorted(imgs, key=lambda x: x["sort_order"])]
        out.append(
            ItemSummary(
                id=row["id"],
                title=row["title"],
                category=row["category"],
                cost_per_day=c,
                minimum_day_rental=int(row["minimum_day_rental"]),
                deposit_amount=_decimal(row["deposit_amount"]),
                towable=bool(row.get("towable", False)),
                image_urls=urls,
                active=bool(row.get("active", True)),
            )
        )
    return out


@router.get("/categories", response_model=list[str])
def list_categories(client: Client = Depends(get_supabase_client)) -> list[str]:
    res = client.table("items").select("category").eq("active", True).execute()
    rows = res.data or []
    seen = {(r.get("category") or "").strip() for r in rows if (r.get("category") or "").strip()}
    return sorted(seen, key=str.lower)


@router.get("/asset-images/{item_id}/{filename}")
def serve_local_item_asset_image(item_id: str, filename: str):
    settings = get_settings()
    if settings.item_images_storage != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    local = local_asset_file_path(settings, item_id, filename)
    if not local:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    media, _ = mimetypes.guess_type(local.name)
    return FileResponse(local, media_type=media or "application/octet-stream")


@router.get("/{item_id}", response_model=ItemDetail)
def get_item(item_id: str, client: Client = Depends(get_supabase_client)) -> ItemDetail:
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
    if not bool(row.get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
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
        active=True,
    )


@router.get("/{item_id}/availability", response_model=list[DayAvailability])
def get_availability(
    item_id: str,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    client: Client = Depends(get_supabase_client),
) -> list[DayAvailability]:
    check = client.table("items").select("id,active").eq("id", item_id).limit(1).execute()
    chk_rows = check.data or []
    if not chk_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not bool(chk_rows[0].get("active", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return day_availability_range(client, item_id, date_from, date_to)
