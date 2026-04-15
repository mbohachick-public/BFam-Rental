"""Tests for public /items endpoints."""

from datetime import date, timedelta


def test_list_items_returns_active_only(client, seed_item, admin_headers):
    seed_item(title="Active Item", active=True)
    seed_item(title="Hidden Item", active=False)

    res = client.get("/items")
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()]
    assert "Active Item" in titles
    assert "Hidden Item" not in titles


def test_list_items_filter_by_category(client, seed_item):
    seed_item(title="Trailer A", active=True)

    res = client.get("/items", params={"category": "general"})
    assert res.status_code == 200
    for item in res.json():
        assert item["category"] == "general"


def test_list_items_filter_by_price_range(client, seed_item):
    seed_item(title="Cheap", cost_per_day=10.0, active=True)
    seed_item(title="Expensive", cost_per_day=500.0, active=True)

    res = client.get("/items", params={"min_cost_per_day": "100", "max_cost_per_day": "600"})
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()]
    assert "Cheap" not in titles
    assert "Expensive" in titles


def test_list_items_open_from_to_validation(client):
    # Providing only one of the pair should fail
    res = client.get("/items", params={"open_from": "2026-05-01"})
    assert res.status_code == 400
    assert "open_from" in res.json()["detail"].lower() or "open_to" in res.json()["detail"].lower()


def test_list_items_open_from_after_to_is_rejected(client):
    res = client.get("/items", params={"open_from": "2026-06-01", "open_to": "2026-05-01"})
    assert res.status_code == 400


def test_list_items_open_date_range_auto_seeds_availability(client, seed_item):
    """Items with no prior item_day_status rows still match open_from/open_to after lazy seed."""
    seed_item(title="Auto Seed Open", active=True)
    d0 = date.today()
    d1 = d0 + timedelta(days=2)
    res = client.get(
        "/items",
        params={"open_from": d0.isoformat(), "open_to": d1.isoformat()},
    )
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()]
    assert "Auto Seed Open" in titles


def test_get_item_returns_detail(client, seed_item):
    item = seed_item(title="Detail Test", active=True)
    res = client.get(f"/items/{item['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Detail Test"
    assert "description" in body
    assert "images" in body


def test_get_item_inactive_returns_404(client, seed_item):
    item = seed_item(title="Inactive", active=False)
    res = client.get(f"/items/{item['id']}")
    assert res.status_code == 404


def test_get_item_nonexistent_returns_404(client):
    res = client.get("/items/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_categories_excludes_inactive_items(client, seed_item):
    seed_item(title="InCat", active=False)
    seed_item(title="VisCat", active=True)

    res = client.get("/items/categories")
    assert res.status_code == 200


def test_availability_returns_days(client, seed_item, seed_day_statuses):
    item = seed_item(active=True)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    seed_day_statuses(item["id"], [(tomorrow, "open_for_booking")])

    res = client.get(
        f"/items/{item['id']}/availability",
        params={"from": tomorrow, "to": tomorrow},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["status"] == "open_for_booking"


def test_availability_inactive_item_404(client, seed_item):
    item = seed_item(active=False)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = client.get(
        f"/items/{item['id']}/availability",
        params={"from": tomorrow, "to": tomorrow},
    )
    assert res.status_code == 404


def test_item_summary_includes_active_field(client, seed_item):
    seed_item(title="With Active", active=True)
    res = client.get("/items")
    assert res.status_code == 200
    items = res.json()
    if items:
        assert "active" in items[0]
        assert items[0]["active"] is True
