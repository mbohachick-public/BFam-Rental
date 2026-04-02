from datetime import date
from decimal import Decimal

from app.services.booking import (
    compute_rental_amounts,
    duration_discount_percent,
    validate_booking_dates,
)


def test_discount_per_day_caps_at_15() -> None:
    assert duration_discount_percent(1) == Decimal("5")
    assert duration_discount_percent(2) == Decimal("10")
    assert duration_discount_percent(3) == Decimal("15")
    assert duration_discount_percent(10) == Decimal("15")


def test_compute_rental_amounts() -> None:
    base, pct, sub, dep = compute_rental_amounts(Decimal("100"), 2, Decimal("50"))
    assert base == Decimal("200")
    assert pct == Decimal("10")
    assert sub == Decimal("180.00")
    assert dep == Decimal("50")


def test_validate_booking_dates_ok() -> None:
    today = date(2026, 4, 1)
    start = date(2026, 4, 5)
    end = date(2026, 4, 7)
    open_dates = {date(2026, 4, 5), date(2026, 4, 6), date(2026, 4, 7)}
    assert validate_booking_dates(today, start, end, 1, open_dates) is None


def test_validate_rejects_outside_window() -> None:
    today = date(2026, 4, 1)
    start = date(2026, 6, 15)
    end = date(2026, 6, 20)  # beyond 60 days from Apr 1
    open_dates = set()
    msg = validate_booking_dates(today, start, end, 1, open_dates)
    assert msg is not None
