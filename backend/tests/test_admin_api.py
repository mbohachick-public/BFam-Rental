"""Tests for /admin endpoints."""

import io
from datetime import date, timedelta


def test_admin_create_item(client, admin_headers):
    body = {
        "title": "Admin Created",
        "description": "Test item",
        "category": "trailers",
        "cost_per_day": "75.00",
        "minimum_day_rental": 2,
        "deposit_amount": "150.00",
        "user_requirements": "Valid license",
        "towable": True,
        "active": True,
        "image_urls": [],
    }
    res = client.post("/admin/items", json=body, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Admin Created"
    assert data["towable"] is True
    assert data["active"] is True


def test_admin_create_item_missing_token(client):
    res = client.post("/admin/items", json={"title": "No Auth"})
    assert res.status_code == 401


def test_admin_create_item_wrong_token(client):
    res = client.post(
        "/admin/items",
        json={"title": "Wrong"},
        headers={"X-Admin-Token": "bad-token"},
    )
    assert res.status_code == 401


def test_admin_patch_item(client, admin_headers, seed_item):
    item = seed_item(title="Before Patch")
    res = client.patch(
        f"/admin/items/{item['id']}",
        json={"title": "After Patch"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["title"] == "After Patch"


def test_admin_patch_active_toggle(client, admin_headers, seed_item):
    item = seed_item(title="Toggle Me", active=True)

    # Deactivate
    res = client.patch(
        f"/admin/items/{item['id']}",
        json={"active": False},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["active"] is False

    # Reactivate
    res = client.patch(
        f"/admin/items/{item['id']}",
        json={"active": True},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["active"] is True


def test_admin_patch_nonexistent_item(client, admin_headers):
    res = client.patch(
        "/admin/items/00000000-0000-0000-0000-000000000000",
        json={"title": "Ghost"},
        headers=admin_headers,
    )
    assert res.status_code == 404


def test_admin_list_items_includes_inactive(client, admin_headers, seed_item):
    seed_item(title="Active Admin", active=True)
    seed_item(title="Inactive Admin", active=False)

    res = client.get("/admin/items", headers=admin_headers)
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()]
    assert "Active Admin" in titles
    assert "Inactive Admin" in titles


def test_admin_get_item_includes_inactive(client, admin_headers, seed_item):
    item = seed_item(title="Inactive Detail", active=False)
    res = client.get(f"/admin/items/{item['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["title"] == "Inactive Detail"


def test_admin_set_availability(client, admin_headers, seed_item):
    item = seed_item()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    body = {"days": [{"day": tomorrow, "status": "open_for_booking"}]}
    res = client.put(
        f"/admin/items/{item['id']}/availability",
        json=body,
        headers=admin_headers,
    )
    assert res.status_code == 204


def test_admin_get_availability_for_inactive(client, admin_headers, seed_item, seed_day_statuses):
    item = seed_item(active=False)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    seed_day_statuses(item["id"], [(tomorrow, "open_for_booking")])

    res = client.get(
        f"/admin/items/{item['id']}/availability",
        params={"from": tomorrow, "to": tomorrow},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_admin_upload_image(client, admin_headers, seed_item):
    item = seed_item()
    tiny_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
        b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05'
        b'\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    files = {"file": ("test.png", io.BytesIO(tiny_png), "image/png")}
    res = client.post(
        f"/admin/items/{item['id']}/images",
        files=files,
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "url" in data
    assert "id" in data


def test_admin_delete_image(client, admin_headers, seed_item, db_store):
    item = seed_item()
    # Insert a fake image row
    import uuid as _uuid

    img_id = str(_uuid.uuid4())
    db_store["item_images"].append({
        "id": img_id,
        "item_id": item["id"],
        "url": "http://localhost/fake.jpg",
        "sort_order": 0,
    })

    res = client.delete(
        f"/admin/items/{item['id']}/images/{img_id}",
        headers=admin_headers,
    )
    assert res.status_code == 200


def test_admin_accept_booking(client, admin_headers, seed_item, seed_day_statuses, db_store):
    item = seed_item()
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=6)).isoformat()
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    import uuid as _uuid
    bid = str(_uuid.uuid4())
    db_store["booking_requests"].append({
        "id": bid,
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "status": "pending",
        "customer_email": "test@e2e.com",
        "customer_phone": "5551234567",
        "customer_first_name": "Test",
        "customer_last_name": "User",
        "customer_address": "123 Main St",
        "notes": None,
        "base_amount": 100.0,
        "discount_percent": 10.0,
        "discounted_subtotal": 90.0,
        "deposit_amount": 100.0,
        "drivers_license_path": None,
        "license_plate_path": None,
        "decline_reason": None,
        "created_at": "2026-04-01T00:00:00",
    })

    res = client.post(
        f"/admin/booking-requests/{bid}/accept",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"


def test_admin_decline_booking(client, admin_headers, seed_item, seed_day_statuses, db_store):
    item = seed_item()
    start = (date.today() + timedelta(days=8)).isoformat()
    end = (date.today() + timedelta(days=9)).isoformat()
    seed_day_statuses(item["id"], [
        (start, "open_for_booking"),
        (end, "open_for_booking"),
    ])

    import uuid as _uuid
    bid = str(_uuid.uuid4())
    db_store["booking_requests"].append({
        "id": bid,
        "item_id": item["id"],
        "start_date": start,
        "end_date": end,
        "status": "pending",
        "customer_email": "decline@e2e.com",
        "customer_phone": "5559876543",
        "customer_first_name": "Dec",
        "customer_last_name": "Line",
        "customer_address": "456 St",
        "notes": None,
        "base_amount": 100.0,
        "discount_percent": 10.0,
        "discounted_subtotal": 90.0,
        "deposit_amount": 100.0,
        "drivers_license_path": None,
        "license_plate_path": None,
        "decline_reason": None,
        "created_at": "2026-04-01T00:00:00",
    })

    res = client.post(
        f"/admin/booking-requests/{bid}/decline",
        json={"reason": "Maintenance scheduled"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rejected"
    assert data["decline_reason"] == "Maintenance scheduled"
