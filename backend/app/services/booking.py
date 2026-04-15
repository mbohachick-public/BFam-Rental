from datetime import date, timedelta
from decimal import Decimal

from app.services.dates import iter_days_inclusive


def compute_rental_amounts(
    cost_per_day: Decimal, num_days: int, deposit: Decimal
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Returns (base_amount, discount_percent, discounted_subtotal, deposit_amount).
    Rental subtotal is cost_per_day × days (no duration discount). discount_percent is
    always 0 and discounted_subtotal equals base_amount; columns kept for existing rows/API.
    """
    base = (cost_per_day * num_days).quantize(Decimal("0.01"))
    zero = Decimal("0")
    return base, zero, base, deposit


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
