"""Edge-case and boundary-condition tests."""

import io
from datetime import date, timedelta
from decimal import Decimal

from app.services.booking import compute_rental_amounts, validate_booking_dates


# ---------------------------------------------------------------------------
# Pure business logic edge cases
# ---------------------------------------------------------------------------

def test_compute_amounts_zero_cost():
    base, pct, sub, dep = compute_rental_amounts(Decimal("0"), 3, Decimal("50"))
    assert base == Decimal("0.00")
    assert pct == Decimal("0")
    assert sub == Decimal("0.00")
    assert dep == Decimal("50")


def test_validate_start_before_today():
    today = date(2026, 4, 3)
    err = validate_booking_dates(today, date(2026, 4, 2), date(2026, 4, 5), 1, set())
    assert err is not None
    assert "before today" in err.lower()


def test_validate_end_before_start():
    today = date(2026, 4, 3)
    err = validate_booking_dates(today, date(2026, 4, 10), date(2026, 4, 8), 1, set())
    assert err is not None


def test_validate_beyond_60_days():
    today = date(2026, 4, 3)
    start = today + timedelta(days=61)
    end = start + timedelta(days=1)
    err = validate_booking_dates(today, start, end, 1, set())
    assert err is not None
    assert "60 days" in err


def test_validate_minimum_days_not_met():
    today = date(2026, 4, 3)
    start = date(2026, 4, 5)
    end = date(2026, 4, 5)  # 1 day but min is 3
    err = validate_booking_dates(today, start, end, 3, {start})
    assert err is not None
    assert "at least 3" in err


def test_validate_day_not_open():
    today = date(2026, 4, 3)
    start = date(2026, 4, 5)
    end = date(2026, 4, 7)
    # Only 2 of 3 days are open
    open_dates = {date(2026, 4, 5), date(2026, 4, 7)}
    err = validate_booking_dates(today, start, end, 1, open_dates)
    assert err is not None
    assert "not open" in err.lower()


# ---------------------------------------------------------------------------
# API edge cases
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_admin_without_auth0_env_returns_503(client):
    res = client.get("/admin/items")
    assert res.status_code == 503


def test_admin_without_bearer_returns_401(client, fake_settings):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.test/"
    res = client.get("/admin/items")
    assert res.status_code == 401


def test_admin_x_admin_token_header_does_not_authorize(client, fake_settings):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.test/"
    res = client.get("/admin/items", headers={"X-Admin-Token": "any-secret"})
    assert res.status_code == 401


def test_admin_query_param_token_does_not_authorize(client, fake_settings):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.test/"
    res = client.get("/admin/items", params={"admin_token": "any-secret"})
    assert res.status_code == 401


def test_nonexistent_booking_confirm_404(client, admin_headers):
    res = client.post(
        "/admin/booking-requests/00000000-0000-0000-0000-000000000000/confirm",
        headers=admin_headers,
    )
    assert res.status_code == 404


def test_nonexistent_booking_decline_404(client, admin_headers):
    res = client.post(
        "/admin/booking-requests/00000000-0000-0000-0000-000000000000/decline",
        json={"reason": "Does not exist"},
        headers=admin_headers,
    )
    assert res.status_code == 404


def test_confirm_wrong_status_returns_400(client, admin_headers, seed_item, db_store):
    import uuid as _uuid
    item = seed_item()
    bid = str(_uuid.uuid4())
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=6)).isoformat()
    db_store["booking_requests"].append({
        "id": bid,
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "status": "confirmed",
        "customer_email": "already@done.com",
        "customer_phone": "5550000000",
        "customer_first_name": "A",
        "customer_last_name": "B",
        "customer_address": "X",
        "notes": None,
        "base_amount": 100,
        "discount_percent": 5,
        "discounted_subtotal": 95,
        "deposit_amount": 50,
        "drivers_license_path": None,
        "license_plate_path": None,
        "decline_reason": None,
        "created_at": "2026-04-01T00:00:00",
    })

    res = client.post(
        f"/admin/booking-requests/{bid}/confirm",
        headers=admin_headers,
    )
    assert res.status_code == 400


def test_decline_already_declined_booking(client, admin_headers, seed_item, db_store):
    import uuid as _uuid
    item = seed_item()
    bid = str(_uuid.uuid4())
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=6)).isoformat()
    db_store["booking_requests"].append({
        "id": bid,
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "status": "declined",
        "customer_email": "rejected@done.com",
        "customer_phone": "5550000000",
        "customer_first_name": "R",
        "customer_last_name": "J",
        "customer_address": "Y",
        "notes": None,
        "base_amount": 100,
        "discount_percent": 5,
        "discounted_subtotal": 95,
        "deposit_amount": 50,
        "drivers_license_path": None,
        "license_plate_path": None,
        "decline_reason": "Old reason",
        "created_at": "2026-04-01T00:00:00",
    })

    res = client.post(
        f"/admin/booking-requests/{bid}/decline",
        json={"reason": "Re-decline"},
        headers=admin_headers,
    )
    assert res.status_code == 400


def test_decline_empty_reason_rejected(client, admin_headers, seed_item, db_store):
    import uuid as _uuid
    item = seed_item()
    bid = str(_uuid.uuid4())
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=6)).isoformat()
    db_store["booking_requests"].append({
        "id": bid,
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "status": "requested",
        "customer_email": "empty@reason.com",
        "customer_phone": "5550000001",
        "customer_first_name": "E",
        "customer_last_name": "R",
        "customer_address": "Z",
        "notes": None,
        "base_amount": 100,
        "discount_percent": 5,
        "discounted_subtotal": 95,
        "deposit_amount": 50,
        "drivers_license_path": None,
        "license_plate_path": None,
        "decline_reason": None,
        "created_at": "2026-04-01T00:00:00",
    })

    # Empty reason should be rejected by Pydantic (min_length=1)
    res = client.post(
        f"/admin/booking-requests/{bid}/decline",
        json={"reason": ""},
        headers=admin_headers,
    )
    assert res.status_code == 422


def test_image_urls_max_10_on_create(client, admin_headers):
    body = {
        "title": "Too Many URLs",
        "cost_per_day": "50",
        "minimum_day_rental": 1,
        "deposit_amount": "0",
        "image_urls": [f"http://example.com/{i}.jpg" for i in range(11)],
    }
    res = client.post("/admin/items", json=body, headers=admin_headers)
    assert res.status_code == 422


def test_image_urls_max_10_on_patch(client, admin_headers, seed_item):
    item = seed_item()
    body = {
        "image_urls": [f"http://example.com/{i}.jpg" for i in range(11)],
    }
    res = client.patch(
        f"/admin/items/{item['id']}",
        json=body,
        headers=admin_headers,
    )
    assert res.status_code == 422


def test_price_filter_zero_min(client, seed_item):
    seed_item(title="Free", cost_per_day=0.0, active=True)
    res = client.get("/items", params={"min_cost_per_day": "0"})
    assert res.status_code == 200


def test_price_filter_high_max(client, seed_item):
    seed_item(title="Premium", cost_per_day=999.0, active=True)
    res = client.get("/items", params={"max_cost_per_day": "10000"})
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()]
    assert "Premium" in titles
