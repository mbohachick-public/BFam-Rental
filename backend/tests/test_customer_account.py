"""Customer account routes: /booking-requests/mine, /me/contact, and auth0_sub on create."""

import io
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from test_booking_api import _future, _tiny_jpeg

AUTH = {"Authorization": "Bearer testtoken"}
SUB = "auth0|fixture-sub"


@pytest.fixture
def customer_token_ok():
    with patch(
        "app.deps.verify_auth0_access_token",
        return_value={"sub": SUB, "email": "cust@test.com"},
    ):
        yield


def test_mine_returns_501_when_auth0_not_configured(client, customer_token_ok):
    res = client.get("/booking-requests/mine", headers=AUTH)
    assert res.status_code == 501


def test_mine_requires_bearer_when_auth0_configured(client, fake_settings, customer_token_ok):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    res = client.get("/booking-requests/mine")
    assert res.status_code == 401


def test_mine_empty_list(client, fake_settings, customer_token_ok):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    res = client.get("/booking-requests/mine", headers=AUTH)
    assert res.status_code == 200
    assert res.json() == []


def test_mine_returns_summaries(client, fake_settings, customer_token_ok, seed_item, db_store):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    item = seed_item(title="Test Kayak")
    bid = str(uuid.uuid4())
    start, end = _future(5), _future(6)
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": start,
            "end_date": end,
            "status": "requested",
            "customer_email": "cust@test.com",
            "customer_phone": "5551234567",
            "customer_first_name": "A",
            "customer_last_name": "B",
            "customer_address": "1 Main St",
            "customer_auth0_sub": SUB,
            "notes": None,
            "base_amount": 100.0,
            "discount_percent": 0.0,
            "discounted_subtotal": 100.0,
            "deposit_amount": 50.0,
            "sales_tax_rate_percent": 4.225,
            "sales_tax_amount": 4.23,
            "rental_total_with_tax": 104.23,
            "sales_tax_source": "fallback",
            "drivers_license_path": None,
            "license_plate_path": None,
            "decline_reason": None,
            "created_at": "2026-04-01T00:00:00",
        }
    )
    res = client.get("/booking-requests/mine", headers=AUTH)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    row = data[0]
    assert row["id"] == bid
    assert row["item_id"] == item["id"]
    assert row["item_title"] == "Test Kayak"
    assert row["item_active"] is True
    assert row["status"] == "requested"
    assert "drivers_license" not in row


def test_contact_404_when_no_bookings(client, fake_settings, customer_token_ok):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    res = client.get("/booking-requests/me/contact", headers=AUTH)
    assert res.status_code == 404


def test_contact_returns_latest(client, fake_settings, customer_token_ok, seed_item, db_store):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    item = seed_item()
    for i, created in enumerate(["2026-01-01T00:00:00", "2026-06-01T00:00:00"]):
        db_store["booking_requests"].append(
            {
                "id": str(uuid.uuid4()),
                "item_id": item["id"],
                "start_date": (date.today() + timedelta(days=5)).isoformat(),
                "end_date": (date.today() + timedelta(days=6)).isoformat(),
                "status": "requested",
                "customer_email": f"old{i}@test.com" if i == 0 else "newer@test.com",
                "customer_phone": "1111111111" if i == 0 else "2222222222",
                "customer_first_name": "Old" if i == 0 else "New",
                "customer_last_name": "Name",
                "customer_address": "X" if i == 0 else "456 Oak Ave",
                "customer_auth0_sub": SUB,
                "notes": None,
                "base_amount": 10.0,
                "discount_percent": 0.0,
                "discounted_subtotal": 10.0,
                "deposit_amount": 1.0,
                "sales_tax_rate_percent": 4.225,
                "sales_tax_amount": 0.42,
                "rental_total_with_tax": 10.42,
                "sales_tax_source": "fallback",
                "drivers_license_path": None,
                "license_plate_path": None,
                "decline_reason": None,
                "created_at": created,
            }
        )
    res = client.get("/booking-requests/me/contact", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["customer_email"] == "newer@test.com"
    assert body["customer_phone"] == "2222222222"
    assert body["customer_first_name"] == "New"
    assert body["customer_address"] == "456 Oak Ave"


def test_create_booking_persists_auth0_sub(
    client, fake_settings, customer_token_ok, seed_item, seed_day_statuses, db_store
):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"
    item = seed_item(towable=False, cost_per_day=50.0)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [(start, "open_for_booking"), (end, "open_for_booking")])

    jpeg = _tiny_jpeg()
    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "book@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "T",
        "customer_last_name": "U",
        "customer_address": "123 Main St, 64089",
    }
    files = {"drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg")}
    res = client.post("/booking-requests", data=data, files=files, headers=AUTH)
    assert res.status_code == 201
    stored = db_store["booking_requests"][-1]
    assert stored.get("customer_auth0_sub") == SUB
