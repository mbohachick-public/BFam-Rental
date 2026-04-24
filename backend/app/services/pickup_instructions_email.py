"""Email pickup details to the customer after admin confirms a non-delivery booking."""

from __future__ import annotations

import logging
from datetime import date

from supabase import Client

from app.config import Settings
from app.services.booking_events import log_booking_event
from app.services.quote_email import (
    pickup_email_logo_url,
    send_pickup_confirmed_email,
    smtp_configured,
)

log = logging.getLogger(__name__)

PICKUP_INSTRUCTIONS_EMAIL_EVENT = "customer_pickup_instructions_sent"


def _booking_event_exists(client: Client, booking_id: str, event_type: str) -> bool:
    try:
        res = (
            client.table("booking_events")
            .select("id")
            .eq("booking_id", booking_id)
            .eq("event_type", event_type)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        log.debug("booking_events check skipped: %s", exc)
        return False


def _pickup_date_long(start_date_raw: str) -> str:
    try:
        d = date.fromisoformat(str(start_date_raw)[:10])
        return d.strftime("%A, %B %d, %Y")
    except ValueError:
        return str(start_date_raw)


def try_send_pickup_instructions_after_confirm(
    client: Client, settings: Settings, row: dict
) -> None:
    """If the booking is customer pickup, email facility address and standard pickup time once."""
    if bool(row.get("delivery_requested")):
        return
    if not smtp_configured(settings):
        log.info("Pickup instructions email skipped (SMTP not configured)")
        return
    booking_id = str(row.get("id") or "").strip()
    if not booking_id:
        return
    if _booking_event_exists(client, booking_id, PICKUP_INSTRUCTIONS_EMAIL_EVENT):
        return
    to_addr = (row.get("customer_email") or "").strip()
    if not to_addr:
        log.warning("Pickup instructions email skipped: no customer_email for booking %s", booking_id)
        return

    item_id = str(row.get("item_id") or "").strip()
    item_title = "Rental item"
    if item_id:
        try:
            it = client.table("items").select("title").eq("id", item_id).limit(1).execute()
            rows = it.data or []
            if rows:
                item_title = str(rows[0].get("title") or item_title)
        except Exception as exc:
            log.debug("Could not load item title for pickup email: %s", exc)

    start_raw = str(row.get("start_date") or "")
    pickup_long = _pickup_date_long(start_raw)
    fn = row.get("customer_first_name")
    greeting_name = str(fn).strip() if fn else None

    logo = pickup_email_logo_url(settings)
    if send_pickup_confirmed_email(
        settings,
        to_addr=to_addr,
        greeting_name=greeting_name,
        item_title=item_title,
        pickup_date_long=pickup_long,
        logo_url=logo,
    ):
        log_booking_event(
            client,
            booking_id=booking_id,
            event_type=PICKUP_INSTRUCTIONS_EMAIL_EVENT,
            actor_type="system",
        )
