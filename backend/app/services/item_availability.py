"""Per-item day status rows for a date range (used by public and admin availability endpoints)."""

from datetime import date

from supabase import Client

from app.schemas import DayAvailability, DayStatus
from app.services.item_availability_seed import ensure_booking_window_day_status


def day_availability_range(
    client: Client,
    item_id: str,
    date_from: date,
    date_to: date,
) -> list[DayAvailability]:
    ensure_booking_window_day_status(client, item_id)
    res = (
        client.table("item_day_status")
        .select("day,status")
        .eq("item_id", item_id)
        .gte("day", date_from.isoformat())
        .lte("day", date_to.isoformat())
        .execute()
    )
    status_by_day: dict[date, DayStatus] = {}
    for r in res.data or []:
        d = date.fromisoformat(str(r["day"]))
        status_by_day[d] = DayStatus(r["status"])

    out: list[DayAvailability] = []
    d = date_from
    while d <= date_to:
        st = status_by_day.get(d)
        out.append(DayAvailability(day=d, status=st))
        d = date.fromordinal(d.toordinal() + 1)
    return out
