"""Tests for /booking-requests endpoints (quote, create booking)."""

import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch


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
    assert float(body["discount_percent"]) == 0.0
    assert float(body["base_amount"]) == 300.0
    assert float(body["discounted_subtotal"]) == 300.0
    assert float(body["sales_tax_rate_percent"]) == 4.225
    assert float(body["sales_tax_amount"]) == 12.68
    assert float(body["rental_total_with_tax"]) == 312.68
    assert float(body.get("delivery_fee", 0)) == 0.0
    assert body.get("delivery_distance_miles") in (None, 0, "0")


def test_quote_with_delivery_adds_fee_and_tax_on_subtotal(
    client, seed_item, seed_day_statuses, fake_settings, db_store, monkeypatch
):
    fake_settings.google_maps_api_key = "fake-key"
    monkeypatch.setattr(
        "app.services.delivery_pricing.fetch_road_distance_miles",
        lambda *_a, **_k: Decimal("10.00"),
    )
    row = db_store["delivery_settings"][0]
    row["enabled"] = True
    row["origin_address"] = "100 Depot St, Kansas City, MO"
    row["price_per_mile"] = 2.0
    row["minimum_fee"] = 0.0
    row["free_miles"] = 0.0
    row["max_delivery_miles"] = 100.0

    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(item["id"], [
        (_future(5), "open_for_booking"),
        (_future(6), "open_for_booking"),
        (_future(7), "open_for_booking"),
    ])

    res = client.post(
        "/booking-requests/quote",
        json={
            "item_id": item["id"],
            "start_date": start,
            "end_date": end,
            "customer_email": "delquote@test.com",
            "delivery_requested": True,
            "delivery_address": "200 Main St, Kansas City, MO",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert float(body["delivery_fee"]) == 20.0
    assert float(body["discounted_subtotal"]) == 300.0
    assert abs(float(body["sales_tax_amount"]) - 13.52) < 0.02
    assert abs(float(body["rental_total_with_tax"]) - 333.52) < 0.02


def test_quote_delivery_unavailable_on_item_returns_400(client, seed_item, seed_day_statuses, db_store):
    row = db_store["delivery_settings"][0]
    row["enabled"] = True
    row["origin_address"] = "100 Depot St, Kansas City, MO"
    row["price_per_mile"] = 1.0

    item = seed_item(cost_per_day=50.0, minimum_day_rental=1)
    item["delivery_available"] = False
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [(start, "open_for_booking"), (end, "open_for_booking")])

    res = client.post(
        "/booking-requests/quote",
        json={
            "item_id": item["id"],
            "start_date": start,
            "end_date": end,
            "customer_email": "x@test.com",
            "delivery_requested": True,
            "delivery_address": "200 Main St",
        },
    )
    assert res.status_code == 400


def test_quote_inactive_item_returns_404(client, seed_item):
    item = seed_item(active=False)
    res = client.post("/booking-requests/quote", json={
        "item_id": item["id"],
        "start_date": _future(5),
        "end_date": _future(7),
        "customer_email": "test@test.com",
    })
    assert res.status_code == 404


def test_quote_uses_sales_tax_rate_url_when_configured(client, seed_item, seed_day_statuses, fake_settings):
    fake_settings.sales_tax_rate_url = "https://tax.test/rates/{zip}"
    fake_settings.sales_tax_fallback_percent = ""
    fake_settings.sales_tax_default_postal_code = "64111"

    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(item["id"], [
        (_future(5), "open_for_booking"),
        (_future(6), "open_for_booking"),
        (_future(7), "open_for_booking"),
    ])

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"rate_percent": "10"}

    mock_inner = MagicMock()
    mock_inner.get.return_value = mock_resp
    mock_client_ctx = MagicMock()
    mock_client_ctx.__enter__.return_value = mock_inner
    mock_client_ctx.__exit__.return_value = None

    with patch("app.services.sales_tax.httpx.Client", return_value=mock_client_ctx):
        res = client.post(
            "/booking-requests/quote",
            json={
                "item_id": item["id"],
                "start_date": start,
                "end_date": end,
                "customer_email": "urlquote@test.com",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert float(body["sales_tax_rate_percent"]) == 10.0
    assert float(body["sales_tax_amount"]) == 30.0
    assert float(body["rental_total_with_tax"]) == 330.0
    mock_inner.get.assert_called_once()
    called_url = mock_inner.get.call_args[0][0]
    assert "64111" in called_url


def test_quote_falls_back_when_tax_url_non_json_but_fallback_set(
    client, seed_item, seed_day_statuses, fake_settings
):
    """Live URL may be misconfigured (e.g. HTML); fallback avoids 502 when both are set."""
    fake_settings.sales_tax_rate_url = "https://tax.test/rates/{zip}"
    fake_settings.sales_tax_fallback_percent = "5.0"
    fake_settings.sales_tax_default_postal_code = "64111"

    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(item["id"], [
        (_future(5), "open_for_booking"),
        (_future(6), "open_for_booking"),
        (_future(7), "open_for_booking"),
    ])

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "x", 0)

    mock_inner = MagicMock()
    mock_inner.get.return_value = mock_resp
    mock_client_ctx = MagicMock()
    mock_client_ctx.__enter__.return_value = mock_inner
    mock_client_ctx.__exit__.return_value = None

    with patch("app.services.sales_tax.httpx.Client", return_value=mock_client_ctx):
        res = client.post(
            "/booking-requests/quote",
            json={
                "item_id": item["id"],
                "start_date": start,
                "end_date": end,
                "customer_email": "fbquote@test.com",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert float(body["sales_tax_rate_percent"]) == 5.0


def test_quote_nonexistent_item_returns_404(client):
    res = client.post("/booking-requests/quote", json={
        "item_id": "00000000-0000-0000-0000-000000000000",
        "start_date": _future(5),
        "end_date": _future(7),
        "customer_email": "test@test.com",
    })
    assert res.status_code == 404


def test_create_booking_success(client, seed_item, seed_day_statuses, db_store):
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
    assert body["status"] == "requested"
    assert body["customer_email"] == "book@test.com"
    assert body["sales_tax_rate_percent"] is not None
    assert float(body["sales_tax_amount"]) > 0
    assert float(body["rental_total_with_tax"]) == float(body["discounted_subtotal"]) + float(
        body["sales_tax_amount"]
    )
    held = [
        r
        for r in db_store["item_day_status"]
        if r["item_id"] == item["id"] and r["day"] in (start, end)
    ]
    assert {r["status"] for r in held} == {"pending_request"}


def test_create_booking_second_customer_same_dates_rejected(
    client, seed_item, seed_day_statuses, db_store
):
    item = seed_item(cost_per_day=50.0, towable=False)
    start, end = _future(12), _future(13)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])
    jpeg = _tiny_jpeg()
    base = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_phone": "5551234567",
        "customer_first_name": "A",
        "customer_last_name": "B",
        "customer_address": "1 St",
    }
    r1 = client.post(
        "/booking-requests",
        data={**base, "customer_email": "first@test.com"},
        files={"drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/booking-requests",
        data={**base, "customer_email": "second@test.com"},
        files={"drivers_license": ("license2.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert r2.status_code == 400
    assert len([b for b in db_store["booking_requests"] if b["item_id"] == item["id"]]) == 1


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


def test_create_booking_towable_without_tow_rating_succeeds(client, seed_item, seed_day_statuses):
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
        "customer_email": "tow2@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Tow",
        "customer_last_name": "Two",
        "customer_address": "789 St",
        "tow_vehicle_year": "2020",
        "tow_vehicle_make": "Ford",
        "tow_vehicle_model": "F-150",
        "has_brake_controller": "false",
    }
    files = {
        "drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg"),
        "license_plate": ("plate.jpg", io.BytesIO(jpeg), "image/jpeg"),
    }
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 201


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
        "tow_vehicle_year": "2020",
        "tow_vehicle_make": "Ford",
        "tow_vehicle_model": "F-150",
        "has_brake_controller": "false",
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


def test_create_booking_multipart_rejected_when_supabase_storage(
    client, fake_settings, seed_item, seed_day_statuses
):
    fake_settings.booking_documents_storage = "supabase"
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
        "customer_email": "x@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "A",
        "customer_last_name": "B",
        "customer_address": "1 St",
    }
    files = {"drivers_license": ("license.jpg", io.BytesIO(jpeg), "image/jpeg")}
    res = client.post("/booking-requests", data=data, files=files)
    assert res.status_code == 400
    assert "presign" in res.json()["detail"].lower()


def test_presign_towable_without_tow_rating_succeeds(client, fake_settings, seed_item, seed_day_statuses):
    fake_settings.booking_documents_storage = "supabase"
    item = seed_item(towable=True)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])
    body = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "towpre@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "T",
        "customer_last_name": "P",
        "customer_address": "1 St",
        "drivers_license_content_type": "image/jpeg",
        "license_plate_content_type": "image/jpeg",
        "request_not_confirmed_ack": True,
        "tow_vehicle_year": 2020,
        "tow_vehicle_make": "Ford",
        "tow_vehicle_model": "F-150",
    }
    pre = client.post("/booking-requests/presign", json=body)
    assert pre.status_code == 201
    assert pre.json().get("booking_id")


def test_presign_and_complete_non_towable(
    client, fake_client, fake_settings, seed_item, seed_day_statuses, db_store
):
    fake_settings.booking_documents_storage = "supabase"
    item = seed_item(towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])
    jpeg = _tiny_jpeg()
    body = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "pre@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Pre",
        "customer_last_name": "Sign",
        "customer_address": "2 St",
        "drivers_license_content_type": "image/jpeg",
        "request_not_confirmed_ack": True,
    }
    pre = client.post("/booking-requests/presign", json=body)
    assert pre.status_code == 201
    pj = pre.json()
    bid = pj["booking_id"]
    held = [
        r
        for r in db_store["item_day_status"]
        if r["item_id"] == item["id"] and r["day"] in (start, end)
    ]
    assert {r["status"] for r in held} == {"pending_request"}
    dl_path = pj["drivers_license"]["path"]
    assert pj["license_plate"] is None
    fake_client.storage.upload(dl_path, jpeg, file_options={"content-type": "image/jpeg"})
    co = client.post(
        f"/booking-requests/{bid}/complete",
        json={"drivers_license_path": dl_path, "license_plate_path": None},
    )
    assert co.status_code == 200
    assert co.json()["status"] == "requested"
    assert co.json()["customer_email"] == "pre@test.com"


def test_complete_fails_without_upload(client, fake_client, fake_settings, seed_item, seed_day_statuses):
    fake_settings.booking_documents_storage = "supabase"
    item = seed_item(towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])
    body = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "miss@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "M",
        "customer_last_name": "S",
        "customer_address": "3 St",
        "drivers_license_content_type": "image/jpeg",
        "request_not_confirmed_ack": True,
    }
    pre = client.post("/booking-requests/presign", json=body)
    bid = pre.json()["booking_id"]
    dl_path = pre.json()["drivers_license"]["path"]
    co = client.post(
        f"/booking-requests/{bid}/complete",
        json={"drivers_license_path": dl_path},
    )
    assert co.status_code == 400


def test_abandon_after_presign(client, fake_settings, db_store, seed_item, seed_day_statuses):
    fake_settings.booking_documents_storage = "supabase"
    item = seed_item(towable=False)
    start, end = _future(5), _future(6)
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])
    body = {
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "customer_email": "ab@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "A",
        "customer_last_name": "B",
        "customer_address": "4 St",
        "drivers_license_content_type": "image/jpeg",
        "request_not_confirmed_ack": True,
    }
    pre = client.post("/booking-requests/presign", json=body)
    bid = pre.json()["booking_id"]
    r = client.delete(f"/booking-requests/{bid}/abandon")
    assert r.status_code == 204
    assert not any(str(rw.get("id")) == bid for rw in db_store.get("booking_requests", []))
    reopened = [
        rw
        for rw in db_store["item_day_status"]
        if rw["item_id"] == item["id"] and rw["day"] in (start, end)
    ]
    assert {rw["status"] for rw in reopened} == {"open_for_booking"}
