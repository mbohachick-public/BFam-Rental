"""Tests for /booking-requests endpoints (quote, create booking)."""

import io
import json
from datetime import date, timedelta
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
    assert "FALLBACK" in body["sales_tax_source"]


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
    assert "FALLBACK" in body["sales_tax_source"]
    assert "JSONDecodeError" in body["sales_tax_source"] or "failed" in body["sales_tax_source"].lower()


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
    assert body["status"] == "requested"
    assert body["customer_email"] == "book@test.com"
    assert body["sales_tax_rate_percent"] is not None
    assert float(body["sales_tax_amount"]) > 0
    assert float(body["rental_total_with_tax"]) == float(body["discounted_subtotal"]) + float(
        body["sales_tax_amount"]
    )


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


def test_presign_and_complete_non_towable(client, fake_client, fake_settings, seed_item, seed_day_statuses):
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
