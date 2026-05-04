"""Finalize a booking on the calendar — shared by admin Confirm and automatic finalize after pay + sign."""

from __future__ import annotations

from datetime import date

from supabase import Client

from app.schemas import BookingRequestStatus, DayStatus
from app.services.booking_events import log_booking_event
from app.services.dates import iter_days_inclusive

_PRE_CONFIRM = frozenset(
    {
        BookingRequestStatus.approved_pending_payment.value,
        BookingRequestStatus.approved_pending_check_clearance.value,
    }
)


def apply_booking_confirmation(client: Client, row: dict, *, actor_type: str = "system") -> dict | None:
    """
    Set rental days to ``booked`` and booking status to ``confirmed``.
    Returns the updated booking row, or ``None`` if the row was not in a confirmable status.
    """
    request_id = str(row.get("id") or "").strip()
    if not request_id:
        return None
    st = str(row.get("status") or "")
    if st not in _PRE_CONFIRM:
        return None
    item_id = row.get("item_id")
    if not item_id:
        return None
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
    log_booking_event(client, booking_id=request_id, event_type="confirmed", actor_type=actor_type)
    res2 = client.table("booking_requests").select("*").eq("id", request_id).limit(1).execute()
    rows2 = res2.data or []
    return rows2[0] if rows2 else None
