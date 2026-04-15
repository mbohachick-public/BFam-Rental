from datetime import date
from decimal import Decimal

from app.services.booking import compute_rental_amounts, validate_booking_dates


def test_compute_rental_amounts_no_discount() -> None:
    base, pct, sub, dep = compute_rental_amounts(Decimal("100"), 2, Decimal("50"))
    assert base == Decimal("200.00")
    assert pct == Decimal("0")
    assert sub == Decimal("200.00")
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
