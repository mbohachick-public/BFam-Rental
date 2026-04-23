"""Stripe Checkout + webhook (mocked Stripe SDK; fake Supabase)."""

import hashlib
import uuid
from unittest.mock import MagicMock

import pytest


def test_stripe_webhook_503_when_secret_missing(client):
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=abc"})
    assert r.status_code == 503


def test_public_payment_status_404(client):
    r = client.get("/booking-requests/00000000-0000-0000-0000-000000000099/payment-status")
    assert r.status_code == 404


def test_public_payment_status_ok(client, db_store, seed_item):
    item = seed_item()
    bid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": None,
            "rental_payment_status": "unpaid",
            "deposit_amount": 50.0,
            "deposit_secured_at": None,
        }
    )
    r = client.get(f"/booking-requests/{bid}/payment-status")
    assert r.status_code == 200
    body = r.json()
    assert body["booking_id"] == bid
    assert body["rental_paid"] is False
    assert body["item_title"]
    assert body["deposit_secured"] is False
    assert body["requires_deposit"] is True


def test_stripe_webhook_marks_rental_paid_and_deposit_when_checkout_included_deposit(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    fake_settings.stripe_webhook_secret = "whsec_test"
    item = seed_item()
    bid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbc"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": None,
            "rental_payment_status": "unpaid",
            "deposit_secured_at": None,
        }
    )

    def _construct(*_args, **_kwargs):
        return {
            "id": "evt_deposit_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_dep_1",
                    "payment_status": "paid",
                    "metadata": {
                        "booking_id": bid,
                        "deposit_in_checkout": "1",
                        "deposit_cents": "7500",
                    },
                    "payment_intent": "pi_dep_1",
                }
            },
        }

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=fake"})
    assert r.status_code == 200
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("rental_paid_at")
    assert row.get("deposit_secured_at")
    assert row.get("stripe_deposit_captured_cents") == 7500


def test_stripe_webhook_separate_deposit_checkout_secures_deposit_only(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    """Separate deposit Checkout uses manual capture: session may be `unpaid` with PI `requires_capture`."""
    fake_settings.stripe_webhook_secret = "whsec_test"
    fake_settings.stripe_secret_key = "sk_test_for_pi_retrieve"
    item = seed_item()
    bid = "dddddddd-dddd-dddd-dddd-ddddddddddda"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": "2026-01-01T00:00:00+00:00",
            "rental_payment_status": "paid",
            "deposit_secured_at": None,
        }
    )

    def _pi_retrieve(_pi_id, *_a, **_kw):
        m = MagicMock()
        m.status = "requires_capture"
        m.id = "pi_deposit_only"
        return m

    def _construct(*_args, **_kwargs):
        return {
            "id": "evt_deposit_only_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_dep_only",
                    "payment_status": "unpaid",
                    "metadata": {
                        "booking_id": bid,
                        "checkout_kind": "deposit",
                        "deposit_cents": "7500",
                    },
                    "payment_intent": "pi_deposit_only",
                }
            },
        }

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.PaymentIntent.retrieve", _pi_retrieve)
    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=fake"})
    assert r.status_code == 200
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("deposit_secured_at")
    assert row.get("stripe_deposit_payment_intent_id") == "pi_deposit_only"
    assert row.get("stripe_deposit_captured_cents") in (0, None)
    assert row.get("stripe_payment_intent_id") != "pi_deposit_only"


def test_stripe_webhook_infers_deposit_when_checkout_kind_missing_from_metadata(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    """Deposit-only session amounts must still secure deposit if metadata.checkout_kind is absent."""
    fake_settings.stripe_webhook_secret = "whsec_test"
    item = seed_item()
    bid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeea"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_total_with_tax": 150.0,
            "deposit_amount": 75.0,
            "rental_paid_at": None,
            "rental_payment_status": "unpaid",
            "deposit_secured_at": None,
        }
    )

    def _construct(*_args, **_kwargs):
        return {
            "id": "evt_infer_deposit",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_infer_dep",
                    "payment_status": "Paid",
                    "amount_total": 7500,
                    "metadata": {"booking_id": bid},
                    "payment_intent": "pi_infer_deposit",
                }
            },
        }

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=fake"})
    assert r.status_code == 200
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("deposit_secured_at")
    assert row.get("stripe_deposit_payment_intent_id") == "pi_infer_deposit"
    assert row.get("rental_paid_at") is None


def test_stripe_webhook_marks_rental_paid(client, fake_settings, db_store, seed_item, monkeypatch):
    fake_settings.stripe_webhook_secret = "whsec_test"
    item = seed_item()
    bid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": None,
            "rental_payment_status": "unpaid",
        }
    )

    def _construct(*_args, **_kwargs):
        return {
            "id": "evt_test_stripe_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_status": "paid",
                    "metadata": {"booking_id": bid, "checkout_kind": "rental"},
                    "payment_intent": "pi_test_1",
                }
            },
        }

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=fake"})
    assert r.status_code == 200
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("rental_paid_at")
    assert row.get("rental_payment_status") == "paid"
    assert row.get("stripe_payment_intent_id") == "pi_test_1"
    assert row.get("deposit_secured_at") is None

    r2 = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=fake"})
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True


def test_admin_stripe_checkout_session(client, admin_headers, fake_settings, db_store, seed_item, monkeypatch):
    fake_settings.stripe_secret_key = "sk_test_fake"
    calls: list[dict] = []

    def _fake_create(**kwargs):
        calls.append(kwargs)
        m = MagicMock()
        n = len(calls)
        m.id = f"cs_test_{n}"
        m.url = f"https://checkout.stripe.com/c/pay/cs_test_{n}"
        return m

    monkeypatch.setattr("app.services.stripe_checkout.stripe.checkout.Session.create", _fake_create)

    item = seed_item()
    bid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 150.0,
            "deposit_amount": 75.0,
            "customer_email": "pay@test.com",
            "rental_paid_at": None,
        }
    )

    r = client.post(f"/admin/booking-requests/{bid}/stripe-checkout-session", headers=admin_headers)
    assert r.status_code == 200
    out = r.json()
    assert out.get("stripe_checkout_email_status") == "skipped_payment_links_in_approval_email"
    assert out["stripe_checkout_session_id"] == "cs_test_1"
    assert "checkout.stripe.com" in (out["stripe_checkout_url"] or "")
    assert out["stripe_deposit_checkout_session_id"] == "cs_test_2"
    assert "checkout.stripe.com" in (out["stripe_deposit_checkout_url"] or "")
    assert len(calls) == 2
    assert len(calls[0].get("line_items") or []) == 1
    assert calls[0].get("payment_intent_data", {}).get("capture_method") == "automatic"
    assert calls[0]["metadata"].get("checkout_kind") == "rental"
    assert calls[0]["metadata"].get("deposit_in_checkout") == "0"
    assert len(calls[1].get("line_items") or []) == 1
    assert calls[1].get("payment_intent_data", {}).get("capture_method") == "manual"
    assert calls[1]["metadata"].get("checkout_kind") == "deposit"
    assert calls[1]["metadata"].get("deposit_capture_mode") == "hold"
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("stripe_checkout_session_id") == "cs_test_1"
    assert row.get("stripe_deposit_checkout_session_id") == "cs_test_2"


def test_admin_stripe_checkout_rental_only_when_deposit_disabled(
    client, admin_headers, fake_settings, db_store, seed_item, monkeypatch
):
    fake_settings.stripe_secret_key = "sk_test_fake"
    fake_settings.stripe_checkout_include_deposit = False
    captured: dict = {}

    def _fake_create(**kwargs):
        captured.update(kwargs)
        m = MagicMock()
        m.id = "cs_test_one"
        m.url = "https://checkout.stripe.com/c/pay/cs_test_one"
        return m

    monkeypatch.setattr("app.services.stripe_checkout.stripe.checkout.Session.create", _fake_create)

    item = seed_item()
    bid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 100.0,
            "deposit_amount": 50.0,
            "customer_email": "x@test.com",
            "rental_paid_at": None,
        }
    )
    r = client.post(f"/admin/booking-requests/{bid}/stripe-checkout-session", headers=admin_headers)
    assert r.status_code == 200
    assert len(captured.get("line_items") or []) == 1
    assert captured["metadata"].get("deposit_in_checkout") == "0"


def test_sign_complete_returns_stripe_checkout_url(client, db_store, seed_item):
    raw = "signcomplete-raw-token-test"
    th = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    item = seed_item()
    bid = str(uuid.uuid4())
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "stripe_checkout_url": "https://checkout.stripe.com/c/pay/test_complete",
            "rental_paid_at": None,
        }
    )
    db_store["booking_action_tokens"].append(
        {
            "booking_id": bid,
            "token_hash": th,
            "action_type": "SIGN",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "used_at": "2026-01-01T00:00:00+00:00",
        }
    )
    r = client.get(f"/booking-actions/{raw}/complete")
    assert r.status_code == 200
    j = r.json()
    assert j["booking_id"] == bid
    assert j["stripe_checkout_url"] == "https://checkout.stripe.com/c/pay/test_complete"
    assert j["payment_path"] == "card"
    assert j["rental_balance_paid"] is False


def test_admin_refund_stripe_deposit(client, admin_headers, fake_settings, db_store, seed_item, monkeypatch):
    fake_settings.stripe_secret_key = "sk_test_fake"

    def _fake_refund(**kwargs):
        m = MagicMock()
        m.id = "re_test_deposit_1"
        return m

    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.Refund.create", _fake_refund)

    item = seed_item()
    bid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 100.0,
            "deposit_amount": 50.0,
            "customer_email": "r@test.com",
            "rental_paid_at": "2026-01-02T00:00:00+00:00",
            "deposit_secured_at": "2026-01-02T00:00:00+00:00",
            "stripe_payment_intent_id": "pi_test_refund",
            "stripe_deposit_captured_cents": 5000,
        }
    )
    r = client.post(f"/admin/booking-requests/{bid}/refund-stripe-deposit", headers=admin_headers)
    assert r.status_code == 200
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("deposit_refunded_at")
    assert row.get("stripe_deposit_refund_id") == "re_test_deposit_1"

    r2 = client.post(f"/admin/booking-requests/{bid}/refund-stripe-deposit", headers=admin_headers)
    assert r2.status_code == 400


def test_admin_refund_stripe_deposit_separate_pi(client, admin_headers, fake_settings, db_store, seed_item, monkeypatch):
    """Captured separate deposit: full Refund on the deposit PaymentIntent."""
    fake_settings.stripe_secret_key = "sk_test_fake"
    captured: dict = {}

    def _fake_refund(**kwargs):
        captured.update(kwargs)
        m = MagicMock()
        m.id = "re_test_deposit_sep"
        return m

    def _pi_retrieve(_id, *_a, **_kw):
        m = MagicMock()
        m.status = "succeeded"
        m.id = _id
        return m

    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.PaymentIntent.retrieve", _pi_retrieve)
    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.Refund.create", _fake_refund)

    item = seed_item()
    bid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeef"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 100.0,
            "deposit_amount": 50.0,
            "customer_email": "r@test.com",
            "rental_paid_at": "2026-01-02T00:00:00+00:00",
            "deposit_secured_at": "2026-01-02T00:00:00+00:00",
            "stripe_payment_intent_id": "pi_rental_only",
            "stripe_deposit_payment_intent_id": "pi_deposit_only_ref",
            "stripe_deposit_captured_cents": 5000,
        }
    )
    r = client.post(f"/admin/booking-requests/{bid}/refund-stripe-deposit", headers=admin_headers)
    assert r.status_code == 200
    assert captured.get("payment_intent") == "pi_deposit_only_ref"
    assert "amount" not in captured
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("stripe_deposit_refund_id") == "re_test_deposit_sep"


def test_admin_release_stripe_deposit_separate_pi_hold(
    client, admin_headers, fake_settings, db_store, seed_item, monkeypatch
):
    """Authorization-only deposit: void via PaymentIntent.cancel, not Refund.create."""
    fake_settings.stripe_secret_key = "sk_test_fake"
    calls: list[str] = []

    def _pi_retrieve(_id, *_a, **_kw):
        m = MagicMock()
        m.status = "requires_capture"
        m.id = _id
        return m

    def _pi_cancel(_id, *_a, **_kw):
        calls.append("cancel:" + str(_id))
        m = MagicMock()
        m.id = _id
        m.status = "canceled"
        return m

    def _refund_shoud_not_run(**_kwargs):
        raise AssertionError("Refund should not be used for an uncaptured hold")

    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.PaymentIntent.retrieve", _pi_retrieve)
    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.PaymentIntent.cancel", _pi_cancel)
    monkeypatch.setattr("app.services.stripe_deposit_refund.stripe.Refund.create", _refund_shoud_not_run)

    item = seed_item()
    bid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeed"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 100.0,
            "deposit_amount": 50.0,
            "customer_email": "r@test.com",
            "rental_paid_at": "2026-01-02T00:00:00+00:00",
            "deposit_secured_at": "2026-01-02T00:00:00+00:00",
            "stripe_payment_intent_id": "pi_rental_only",
            "stripe_deposit_payment_intent_id": "pi_deposit_hold",
            "stripe_deposit_captured_cents": 0,
        }
    )
    r = client.post(f"/admin/booking-requests/{bid}/refund-stripe-deposit", headers=admin_headers)
    assert r.status_code == 200
    assert calls == ["cancel:pi_deposit_hold"]
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert str(row.get("stripe_deposit_refund_id", "")).startswith("void:pi_deposit_hold")


def test_admin_sync_stripe_checkout_applies_rental_and_deposit(
    client, admin_headers, fake_settings, db_store, seed_item, monkeypatch
):
    fake_settings.stripe_secret_key = "sk_test_fake"
    item = seed_item()
    bid = "ffffffff-ffff-ffff-ffff-fffffffffffa"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "approved_pending_payment",
            "payment_path": "card",
            "rental_total_with_tax": 100.0,
            "deposit_amount": 50.0,
            "stripe_checkout_session_id": "cs_rental_x",
            "stripe_deposit_checkout_session_id": "cs_dep_y",
            "rental_paid_at": None,
            "deposit_secured_at": None,
            "rental_payment_status": "unpaid",
        }
    )

    def _retrieve(sid, *_a, **_kw):
        m = MagicMock()
        if sid == "cs_rental_x":
            m.to_dict = lambda: {
                "id": sid,
                "payment_status": "paid",
                "payment_intent": "pi_rent",
                "metadata": {"booking_id": bid, "checkout_kind": "rental"},
            }
        else:
            m.to_dict = lambda: {
                "id": sid,
                "payment_status": "unpaid",
                "payment_intent": {"id": "pi_dep", "status": "requires_capture", "object": "payment_intent"},
                "metadata": {"booking_id": bid, "checkout_kind": "deposit", "deposit_cents": "5000"},
            }
        return m

    monkeypatch.setattr(
        "app.services.stripe_payment_reconcile.stripe.checkout.Session.retrieve",
        _retrieve,
    )

    r = client.post(f"/admin/booking-requests/{bid}/sync-stripe-checkout", headers=admin_headers)
    assert r.status_code == 200
    out = r.json()
    assert "rental_checkout_applied" in out["actions"]
    assert "deposit_checkout_applied" in out["actions"]
    row = next(rw for rw in db_store["booking_requests"] if rw["id"] == bid)
    assert row.get("rental_paid_at")
    assert row.get("deposit_secured_at")
    assert row.get("stripe_deposit_payment_intent_id") == "pi_dep"


def test_admin_stripe_checkout_rejects_non_card(client, admin_headers, db_store, seed_item):
    item = seed_item()
    bid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "approved_pending_payment",
            "payment_path": "legacy_non_card",
            "rental_total_with_tax": 50.0,
            "customer_email": "a@test.com",
        }
    )
    r = client.post(f"/admin/booking-requests/{bid}/stripe-checkout-session", headers=admin_headers)
    assert r.status_code == 400
