"""Permanently remove a catalog item and related rows / storage files."""

from __future__ import annotations

from supabase import Client

from app.config import Settings
from app.services.booking_storage import try_delete_booking_document
from app.services.item_images_storage import try_delete_item_image_for_url


def _delete_booking_storage_and_child_rows(
    settings: Settings, client: Client, booking_id: str, row: dict
) -> None:
    for table in (
        "stripe_webhook_events",
        "booking_action_tokens",
        "booking_signatures",
        "booking_documents",
    ):
        try:
            client.table(table).delete().eq("booking_id", booking_id).execute()
        except Exception:
            pass
    try_delete_booking_document(settings, client, row.get("drivers_license_path"))
    try_delete_booking_document(settings, client, row.get("license_plate_path"))


def delete_item_and_related_data(settings: Settings, client: Client, item_id: str) -> int:
    """
    Remove one catalog item, its storage files, and related database rows.

    Explicit child deletes keep in-memory test fakes aligned with Postgres CASCADE.
    Returns the number of booking rows processed for file cleanup.
    """
    bookings_processed = 0
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
        _delete_booking_storage_and_child_rows(settings, client, str(row["id"]), row)

    imgs = (
        client.table("item_images").select("url").eq("item_id", item_id).execute().data or []
    )
    for row in imgs:
        try_delete_item_image_for_url(settings, client, str(row["url"]))

    client.table("booking_requests").delete().eq("item_id", item_id).execute()
    client.table("item_images").delete().eq("item_id", item_id).execute()
    client.table("item_day_status").delete().eq("item_id", item_id).execute()
    try:
        client.table("trailer_match_requests").update({"recommended_catalog_item_id": None}).eq(
            "recommended_catalog_item_id", item_id
        ).execute()
    except Exception:
        pass
    client.table("items").delete().eq("id", item_id).execute()
    return bookings_processed
