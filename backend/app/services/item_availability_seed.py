"""Seed and maintain item_day_status rows for the bookable window [today, booking_window_end(today)]."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from supabase import Client

from app.schemas import DayStatus
from app.services.booking import booking_window_end
from app.services.dates import iter_days_inclusive

_UPSERT_CHUNK = 200
_OPEN = DayStatus.open_for_booking.value


def _upsert_day_status_chunked(client: Client, rows: list[dict]) -> None:
    for i in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[i : i + _UPSERT_CHUNK]
        client.table("item_day_status").upsert(chunk).execute()


def seed_day_status_for_new_item(client: Client, item_id: str, today: date | None = None) -> None:
    """Insert open_for_booking rows for every day from today through booking_window_end (inclusive)."""
    t = today or date.today()
    end = booking_window_end(t)
    days = iter_days_inclusive(t, end)
    rows = [{"item_id": item_id, "day": d.isoformat(), "status": _OPEN} for d in days]
    if rows:
        _upsert_day_status_chunked(client, rows)


def ensure_booking_window_day_status(client: Client, item_id: str, today: date | None = None) -> None:
    """Upsert any missing days in the bookable window as open_for_booking (does not change existing rows)."""
    t = today or date.today()
    end = booking_window_end(t)
    wanted = set(iter_days_inclusive(t, end))
    if not wanted:
        return
    res = (
        client.table("item_day_status")
        .select("day")
        .eq("item_id", item_id)
        .gte("day", t.isoformat())
        .lte("day", end.isoformat())
        .execute()
    )
    have = {date.fromisoformat(str(r["day"])) for r in (res.data or [])}
    missing = wanted - have
    if not missing:
        return
    rows = [{"item_id": item_id, "day": d.isoformat(), "status": _OPEN} for d in sorted(missing)]
    _upsert_day_status_chunked(client, rows)


def ensure_booking_window_day_status_for_items(
    client: Client, item_ids: list[str], today: date | None = None
) -> None:
    """Same as ensure_booking_window_day_status, batched for many items (e.g. catalog date filter)."""
    if not item_ids:
        return
    t = today or date.today()
    end = booking_window_end(t)
    wanted_days = iter_days_inclusive(t, end)
    if not wanted_days:
        return
    res = (
        client.table("item_day_status")
        .select("item_id,day")
        .in_("item_id", item_ids)
        .gte("day", t.isoformat())
        .lte("day", end.isoformat())
        .execute()
    )
    by_item: dict[str, set[date]] = defaultdict(set)
    for r in res.data or []:
        by_item[str(r["item_id"])].add(date.fromisoformat(str(r["day"])))
    wanted_set = set(wanted_days)
    rows: list[dict] = []
    for iid in item_ids:
        have = by_item.get(iid, set())
        for d in wanted_set:
            if d not in have:
                rows.append({"item_id": iid, "day": d.isoformat(), "status": _OPEN})
    if rows:
        _upsert_day_status_chunked(client, rows)
