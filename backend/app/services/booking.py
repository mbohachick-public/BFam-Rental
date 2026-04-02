from datetime import date, timedelta
from decimal import Decimal

from app.services.dates import iter_days_inclusive


def duration_discount_percent(num_days: int) -> Decimal:
    """5% per day of rental, capped at 15%."""
    if num_days <= 0:
        return Decimal("0")
    raw = Decimal(num_days * 5)
    cap = Decimal("15")
    return raw if raw <= cap else cap


def compute_rental_amounts(
    cost_per_day: Decimal, num_days: int, deposit: Decimal
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Returns (base_amount, discount_percent, discounted_subtotal, deposit_amount).
    Discount applies to rental subtotal only, not deposit.
    """
    base = cost_per_day * num_days
    pct = duration_discount_percent(num_days)
    factor = Decimal("1") - (pct / Decimal("100"))
    discounted = (base * factor).quantize(Decimal("0.01"))
    return base, pct, discounted, deposit


def booking_window_end(today: date) -> date:
    return today + timedelta(days=60)


def validate_booking_dates(
    today: date,
    start: date,
    end: date,
    minimum_days: int,
    open_dates: set[date],
) -> str | None:
    """Return error message or None if OK."""
    if start < today:
        return "Start date cannot be before today."
    if end < start:
        return "End date must be on or after start date."
    if end > booking_window_end(today):
        return "All dates must fall within the next 60 days from today."
    days = iter_days_inclusive(start, end)
    if len(days) < minimum_days:
        return f"Rental must be at least {minimum_days} day(s)."
    for d in days:
        if d not in open_dates:
            return f"Date {d.isoformat()} is not open for booking."
        if d > booking_window_end(today):
            return "All dates must fall within the next 60 days from today."
    return None
