"""Remove rental items created by automated tests (known E2E categories) and related storage."""

from __future__ import annotations

from supabase import Client

from app.config import Settings
from app.services.booking_storage import try_delete_booking_document
from app.services.item_images_storage import try_delete_item_image_for_url

# Playwright/API tests use these categories — never use for real catalog data.
E2E_ITEM_CATEGORIES: frozenset[str] = frozenset({"e2e-test", "e2e-admin"})


def cleanup_e2e_test_items(settings: Settings, client: Client) -> tuple[int, int]:
    """
    Delete items whose category is in E2E_ITEM_CATEGORIES, after removing booking docs
    and catalog images from storage. Child rows (bookings, item_images, item_day_status)
    are deleted explicitly so tests match production CASCADE behavior.

    Returns (number of items deleted, number of booking rows processed for file cleanup).
    """
    all_items = client.table("items").select("id,category").execute().data or []
    e2e_ids = [str(r["id"]) for r in all_items if str(r.get("category", "")) in E2E_ITEM_CATEGORIES]
    if not e2e_ids:
        return (0, 0)

    bookings_processed = 0
    for item_id in e2e_ids:
        br = (
            client.table("booking_requests")
            .select("id,drivers_license_path,license_plate_path")
            .eq("item_id", item_id)
            .execute()
            .data
            or []
        )
        for row in br:
            bookings_processed += 1
            try_delete_booking_document(settings, client, row.get("drivers_license_path"))
            try_delete_booking_document(settings, client, row.get("license_plate_path"))

    for item_id in e2e_ids:
        imgs = (
            client.table("item_images").select("url").eq("item_id", item_id).execute().data or []
        )
        for row in imgs:
            try_delete_item_image_for_url(settings, client, str(row["url"]))

    # Explicit child deletes so in-memory test fakes match production CASCADE behavior.
    client.table("booking_requests").delete().in_("item_id", e2e_ids).execute()
    client.table("item_images").delete().in_("item_id", e2e_ids).execute()
    client.table("item_day_status").delete().in_("item_id", e2e_ids).execute()
    client.table("items").delete().in_("id", e2e_ids).execute()
    return (len(e2e_ids), bookings_processed)
