"""Auth boundary for anonymous quote vs authenticated intake (Auth0 configured)."""

from copy import deepcopy
from unittest.mock import patch

from test_booking_api import QUOTE_CUSTOMER_ADDRESS, _future

AUTH = {"Authorization": "Bearer testtoken"}
SUB = "auth0|quote-boundary-sub"


def _enable_auth0(fake_settings):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.id"


def _quote_payload(item_id: str, start: str, end: str) -> dict:
    return {
        "item_id": item_id,
        "start_date": start,
        "end_date": end,
        "customer_email": "anon-quote@test.com",
        "customer_address": QUOTE_CUSTOMER_ADDRESS,
    }


def _intake_payload(item_id: str, start: str, end: str, **extra) -> dict:
    return {
        "item_id": item_id,
        "start_date": start,
        "end_date": end,
        "customer_email": "intake@test.com",
        "customer_phone": "5551234567",
        "customer_first_name": "In",
        "customer_last_name": "Take",
        "customer_address": QUOTE_CUSTOMER_ADDRESS,
        **extra,
    }


def test_quote_anonymous_succeeds_when_auth0_configured(
    client, fake_settings, seed_item, seed_day_statuses
):
    _enable_auth0(fake_settings)
    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(
        item["id"],
        [
            (_future(5), "open_for_booking"),
            (_future(6), "open_for_booking"),
            (_future(7), "open_for_booking"),
        ],
    )
    res = client.post("/booking-requests/quote", json=_quote_payload(item["id"], start, end))
    assert res.status_code == 200
    body = res.json()
    assert body["num_days"] == 3
    assert float(body["discounted_subtotal"]) == 300.0


def test_quote_anonymous_creates_no_booking_hold_or_email(
    client, fake_settings, seed_item, seed_day_statuses, db_store
):
    _enable_auth0(fake_settings)
    item = seed_item(cost_per_day=100.0, minimum_day_rental=1)
    start, end = _future(5), _future(7)
    seed_day_statuses(
        item["id"],
        [
            (_future(5), "open_for_booking"),
            (_future(6), "open_for_booking"),
            (_future(7), "open_for_booking"),
        ],
    )
    days_before = deepcopy(list(db_store["item_day_status"]))
    bookings_before = list(db_store.get("booking_requests", []))
    events_before = list(db_store.get("booking_events", []))

    with patch("app.routers.booking_requests.send_quote_email") as qmail:
        res = client.post("/booking-requests/quote", json=_quote_payload(item["id"], start, end))

    assert res.status_code == 200
    assert res.json().get("email_sent") is False
    qmail.assert_not_called()
    assert list(db_store.get("booking_requests", [])) == bookings_before
    assert list(db_store.get("booking_events", [])) == events_before
    held = [
        r
        for r in db_store["item_day_status"]
        if r["item_id"] == item["id"] and r["day"] in (_future(5), _future(6), _future(7))
    ]
    assert held
    assert all(r["status"] == "open_for_booking" for r in held)
    assert not any(r["status"] == "pending_request" for r in db_store["item_day_status"])
    # Seeding the booking window may insert additional open days; none of the originally
    # open requested days may be converted into a date hold.
    before_by_day = {(r["item_id"], r["day"]): r["status"] for r in days_before}
    for r in db_store["item_day_status"]:
        prev = before_by_day.get((r["item_id"], r["day"]))
        if prev == "open_for_booking":
            assert r["status"] == "open_for_booking"


def test_intake_anonymous_unauthorized_when_auth0_configured(
    client, fake_settings, seed_item, seed_day_statuses, db_store
):
    _enable_auth0(fake_settings)
    item = seed_item(cost_per_day=50.0, minimum_day_rental=1, towable=False)
    start, end = _future(8), _future(9)
    seed_day_statuses(item["id"], [(start, "open_for_booking"), (end, "open_for_booking")])
    days_before = deepcopy(list(db_store["item_day_status"]))

    with (
        patch("app.routers.booking_requests.send_quote_email") as qmail,
        patch("app.routers.booking_requests.send_booking_intake_continue_email") as cont,
    ):
        res = client.post(
            "/booking-requests/intake",
            json=_intake_payload(item["id"], start, end),
        )

    assert res.status_code == 401
    assert db_store.get("booking_requests", []) == []
    assert list(db_store["item_day_status"]) == days_before
    qmail.assert_not_called()
    cont.assert_not_called()


def test_intake_authenticated_still_works_when_auth0_configured(
    client, fake_settings, seed_item, seed_day_statuses, db_store
):
    _enable_auth0(fake_settings)
    item = seed_item(cost_per_day=50.0, minimum_day_rental=1, towable=False)
    start, end = _future(8), _future(9)
    seed_day_statuses(item["id"], [(start, "open_for_booking"), (end, "open_for_booking")])

    with (
        patch(
            "app.deps.verify_auth0_access_token",
            return_value={"sub": SUB, "email": "intake@test.com"},
        ),
        patch("app.routers.booking_requests.send_quote_email", return_value=True),
        patch("app.routers.booking_requests.send_booking_intake_continue_email", return_value=None),
    ):
        res = client.post(
            "/booking-requests/intake",
            json=_intake_payload(item["id"], start, end),
            headers=AUTH,
        )

    assert res.status_code == 201
    assert res.json().get("booking_id")
    stored = db_store["booking_requests"][-1]
    assert stored["customer_auth0_sub"] == SUB
    held = [
        r
        for r in db_store["item_day_status"]
        if r["item_id"] == item["id"] and r["day"] in (start, end)
    ]
    assert {r["status"] for r in held} == {"pending_request"}


def test_intake_ignores_client_supplied_price_when_auth0_configured(
    client, fake_settings, seed_item, seed_day_statuses, db_store
):
    """Price tampering: extra JSON price fields must not become the persisted total."""
    _enable_auth0(fake_settings)
    item = seed_item(cost_per_day=100.0, minimum_day_rental=1, towable=False)
    start, end = _future(5), _future(7)
    seed_day_statuses(
        item["id"],
        [
            (_future(5), "open_for_booking"),
            (_future(6), "open_for_booking"),
            (_future(7), "open_for_booking"),
        ],
    )
    quote = client.post("/booking-requests/quote", json=_quote_payload(item["id"], start, end))
    assert quote.status_code == 200
    expected_total = float(quote.json()["rental_total_with_tax"])
    assert expected_total > 1.0

    with (
        patch(
            "app.deps.verify_auth0_access_token",
            return_value={"sub": SUB},
        ),
        patch("app.routers.booking_requests.send_quote_email", return_value=True),
        patch("app.routers.booking_requests.send_booking_intake_continue_email", return_value=None),
    ):
        res = client.post(
            "/booking-requests/intake",
            json=_intake_payload(
                item["id"],
                start,
                end,
                rental_total_with_tax="0.01",
                discounted_subtotal="0.01",
                base_amount="0.01",
                deposit_amount="0.01",
            ),
            headers=AUTH,
        )

    assert res.status_code == 201
    stored = db_store["booking_requests"][-1]
    assert float(stored["rental_total_with_tax"]) == expected_total
    assert float(stored["discounted_subtotal"]) == float(quote.json()["discounted_subtotal"])
    assert float(stored["rental_total_with_tax"]) != 0.01
