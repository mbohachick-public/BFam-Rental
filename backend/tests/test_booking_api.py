"""Tests for /booking-requests endpoints (quote, create booking)."""

import io
from datetime import date, timedelta


def _tiny_jpeg() -> bytes:
    """Minimal valid JPEG for upload testing."""
    import base64
    return base64.b64decode(
        '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMCwsK'
        'CwsLDBAQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQU'
        'FBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAABAAEDASIAAhEB'
        'AxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9'
        'AQIDAAQRBRIHMQUGE0FRcRMiI4EUMpGhBxWxQiPBUtHhMxZi8CRygvElQzRTkqKyY3PCNUQnk6Oz'
        'NhdUZHTD0uIIJoMJChgZhJRFRqS0VtNVKBry4/PE1OT0ZXWFlaW1xdXl9WZ2hpamtsbW5vYnN0dX'
        'Z3eHl6e3x9fn9zhIWGh4iJiouMjY6PgpOUlZaXmJmam5ydnp+So6SlpqeoqaqrrK2ur6/9oADAMB'
        'AAIRAxEAPwD9U6KKKACiiigD/9k='
    )


def _future(d: int) -> str:
    return (date.today() + timedelta(days=d)).isoformat()


def test_quote_returns_pricing(client, seed_item, seed_day_statuses):
    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(item["id"], [
        (_future(5), "open_for_booking"),
        (_future(6), "open_for_booking"),
        (_future(7), "open_for_booking"),
    ])

    res = client.post("/booking-requests/quote", json={
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "quote@test.com",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["num_days"] == 3
    assert float(body["discount_percent"]) == 15.0  # 3 days = max 15%
    assert float(body["base_amount"]) == 300.0


def test_quote_inactive_item_returns_404(client, seed_item):
    item = seed_item(active=False)
    res = client.post("/booking-requests/quote", json={
        "item_id": item["id"],
        "start_date": _future(5),
        "end_date": _future(7),
        "customer_email": "test@test.com",
    })
    assert res.status_code == 404


def test_quote_nonexistent_item_returns_404(client):
    res = client.post("/booking-requests/quote", json={
        "item_id": "00000000-0000-0000-0000-000000000000",
        "start_date": _future(5),
        "end_date": _future(7),
        "customer_email": "test@test.com",
    })
    assert res.status_code == 404


def test_create_booking_success(client, seed_item, seed_day_statuses):
    item = seed_item(cost_per_day=50.0, towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    jpeg = _tiny_jpeg()
    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "book@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Test",
        "customer_last_name": "User",
        "customer_address": "123 Main St",
    }
    files = {
        "drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg"),
    }
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"
    assert body["customer_email"] == "book@test.com"


def test_create_booking_missing_license(client, seed_item, seed_day_statuses):
    item = seed_item(towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "nofile@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "No",
        "customer_last_name": "File",
        "customer_address": "456 St",
    }
    # Empty file upload (no filename) — FastAPI returns 422 (validation) or 400
    files = {"drivers_license": ("", io.BytesIO(b""), "application/octet-stream")}
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code in (400, 422)


def test_create_booking_towable_requires_plate(client, seed_item, seed_day_statuses):
    item = seed_item(towable=True)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    jpeg = _tiny_jpeg()
    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "tow@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Tow",
        "customer_last_name": "User",
        "customer_address": "789 St",
    }
    files = {
        "drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg"),
    }
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 400
    assert "license plate" in res.json()["detail"].lower()


def test_create_booking_non_towable_rejects_plate(client, seed_item, seed_day_statuses):
    item = seed_item(towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    jpeg = _tiny_jpeg()
    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "noplate@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "No",
        "customer_last_name": "Plate",
        "customer_address": "101 St",
    }
    files = {
        "drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg"),
        "license_plate": ("plate.jpg", io.BytesIO(jpeg), "image/jpeg"),
    }
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 400
    assert "only allowed for towable" in res.json()["detail"].lower()


def test_create_booking_inactive_item(client, seed_item, seed_day_statuses):
    item = seed_item(active=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    jpeg = _tiny_jpeg()
    data = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "dead@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Dead",
        "customer_last_name": "Item",
        "customer_address": "0 St",
    }
    files = {
        "drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg"),
    }
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 404
