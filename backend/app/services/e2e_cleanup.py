"""Remove rental items created by automated tests (known E2E categories) and related storage."""

from __future__ import annotations

from supabase import Client

from app.config import Settings
from app.services.item_delete import delete_item_and_related_data

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
        bookings_processed += delete_item_and_related_data(settings, client, item_id)
    return (len(e2e_ids), bookings_processed)
