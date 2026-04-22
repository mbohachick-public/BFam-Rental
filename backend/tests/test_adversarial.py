"""Adversarial and abuse-style API tests: auth bypass, webhook abuse, path tricks, and failure modes.

These are not exhaustive penetration tests, but they guard obvious regressions and document behavior.
"""

from __future__ import annotations

import uuid

import pytest
import stripe


# ---------------------------------------------------------------------------
# Stripe webhook: signature, replay, bad metadata
# ---------------------------------------------------------------------------


def _evt(checkout_id: str, event_id: str, session_obj: dict) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": session_obj},
    }


def test_stripe_webhook_invalid_signature_returns_400(client, fake_settings, monkeypatch):
    fake_settings.stripe_webhook_secret = "whsec_test"

    def _boom(*_a, **_k):
        raise stripe.SignatureVerificationError("bad", "sig")

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _boom)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert r.status_code == 400


def test_stripe_webhook_missing_signature_400(client, fake_settings):
    fake_settings.stripe_webhook_secret = "whsec_test"
    r = client.post("/stripe/webhook", content=b"{}")
    assert r.status_code == 400


def test_stripe_webhook_replay_is_idempotent(client, fake_settings, db_store, seed_item, monkeypatch):
    """Duplicate stripe_event_id must be ignored (no double-apply, no 500)."""
    fake_settings.stripe_webhook_secret = "whsec_test"
    fake_settings.stripe_secret_key = "sk_test"
    item = seed_item()
    bid = str(uuid.uuid4())
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
    event_body = _evt(
        "cs_1",
        "evt_replay_1",
        {
            "id": "cs_1",
            "payment_status": "paid",
            "metadata": {"booking_id": bid, "checkout_kind": "rental"},
            "payment_intent": "pi_r1",
        },
    )

    def _construct(payload, sig_header, secret, **_k):
        import json

        if isinstance(payload, bytes):
            assert json.loads(payload) == event_body
        return event_body

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)

    import json

    body = json.dumps(event_body).encode()
    h = {"stripe-signature": "t=0,v1=abc"}
    r1 = client.post("/stripe/webhook", content=body, headers=h)
    assert r1.status_code == 200
    r2 = client.post("/stripe/webhook", content=body, headers=h)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True
    paid = [r for r in db_store["booking_requests"] if r["id"] == bid]
    assert paid[0].get("rental_paid_at")
    ev_rows = db_store.get("stripe_webhook_events", [])
    assert len(ev_rows) == 1
    assert ev_rows[0].get("stripe_event_id") == "evt_replay_1"


def test_stripe_webhook_forged_booking_id_does_not_touch_other_rows(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    """
    Metadata booking_id is trusted once the webhook is authentic.
    A payment for unknown UUID must not crash and must not alter a different booking.
    """
    fake_settings.stripe_webhook_secret = "whsec_test"
    item = seed_item()
    vict = str(uuid.uuid4())
    db_store["booking_requests"].append(
        {
            "id": vict,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": None,
        }
    )
    attacker_id = "00000000-0000-0000-0000-00000000dead"

    def _construct(*_a, **_k):
        return {
            "id": "evt_forged",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_forged",
                    "payment_status": "paid",
                    "metadata": {
                        "booking_id": attacker_id,
                        "checkout_kind": "rental",
                    },
                    "payment_intent": "pi_forged",
                }
            },
        }

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=ok"})
    assert r.status_code == 200
    row = next(x for x in db_store["booking_requests"] if x["id"] == vict)
    assert not row.get("rental_paid_at")


def test_stripe_webhook_deposit_unpaid_needs_pi_retrieve_failure_is_safe(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    """
    If the session looks unpaid+deposit but PaymentIntent cannot be read, we must not 500.
    """
    fake_settings.stripe_webhook_secret = "whsec_test"
    fake_settings.stripe_secret_key = "sk_test"
    item = seed_item()
    bid = str(uuid.uuid4())
    db_store["booking_requests"].append(
        {
            "id": bid,
            "item_id": item["id"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "status": "approved_pending_payment",
            "rental_paid_at": "2026-01-01T00:00:00+00:00",
            "deposit_secured_at": None,
        }
    )

    def _construct(*_a, **_k):
        return {
            "id": "evt_nopi",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_dep",
                    "payment_status": "unpaid",
                    "metadata": {
                        "booking_id": bid,
                        "checkout_kind": "deposit",
                    },
                    "payment_intent": "pi_mystery",
                }
            },
        }

    def _pi_boom(_id, *_a, **_kw):
        raise stripe.StripeError("simulated network failure")

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    monkeypatch.setattr("app.routers.stripe_webhook.stripe.PaymentIntent.retrieve", _pi_boom)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=ok"})
    assert r.status_code == 200
    row = next(x for x in db_store["booking_requests"] if x["id"] == bid)
    assert not row.get("deposit_secured_at")


# ---------------------------------------------------------------------------
# Public unauthenticated token surfaces
# ---------------------------------------------------------------------------


def test_public_payment_status_suspicious_id_is_not_sql_error(client):
    from urllib.parse import quote

    rid = quote("x' OR 1=1--", safe="")
    r = client.get(f"/booking-requests/{rid}/payment-status")
    # Literal id string has no row → 404, not 5xx
    assert r.status_code == 404


def test_public_payment_status_unicode_in_path_404_not_500(client):
    path_id = "aaaaaaaa-bbbb-bccc-dddd-\u200ceeeeeeeeeeee"
    r = client.get(f"/booking-requests/{path_id}/payment-status")
    assert r.status_code == 404


def test_booking_sign_very_long_token_does_not_crash_404(client, monkeypatch):
    token = "a" * 50_000
    r = client.get(f"/booking-actions/{token}/sign")
    # Invalid token → 404, not 500; resolver hashes without allocating huge string issues
    assert r.status_code in (404, 410, 500)
    if r.status_code == 500:
        pytest.fail("very long path token caused server error; expected 4xx")
    assert r.status_code in (404, 410)


# ---------------------------------------------------------------------------
# Admin: weak tokens never authorize (documented in test_edge_cases too)
# ---------------------------------------------------------------------------


def test_admin_bearer_tampered_token_rejected(client, fake_settings, monkeypatch):
    fake_settings.auth0_domain = "tenant.auth0.com"
    fake_settings.auth0_audience = "https://api.test/"

    def _nope(*_a, **_k):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    monkeypatch.setattr("app.deps.verify_auth0_access_token", _nope)
    r = client.get("/admin/items", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Webhook: malformed JSON
# ---------------------------------------------------------------------------


def test_stripe_webhook_invalid_json_400(client, fake_settings):
    fake_settings.stripe_webhook_secret = "whsec_test"
    r = client.post(
        "/stripe/webhook",
        content=b"not json {{{",
        headers={"stripe-signature": "t=0,v1=x"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# API stress: very large filter params (no crash)
# ---------------------------------------------------------------------------


def test_items_list_extremely_long_search_param_ok(client, seed_item):
    seed_item()
    r = client.get("/items", params={"q": "A" * 20_000})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Webhook: inner handler exception propagates 500 (documented for Stripe retries)
# ---------------------------------------------------------------------------


def test_stripe_webhook_handler_runtime_error_returns_500(
    client, fake_settings, db_store, seed_item, monkeypatch
):
    """If the verified handler raises, the route returns 500 (Stripe may retry the event)."""
    fake_settings.stripe_webhook_secret = "whsec_test"
    from app.routers import stripe_webhook as wh

    def _construct(*_a, **_k):
        return {
            "id": "evt_500_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_500",
                    "payment_status": "paid",
                    "metadata": {"booking_id": "nope", "checkout_kind": "rental"},
                    "payment_intent": "pi_x",
                }
            },
        }

    def _shim(client_inner, _obj):
        raise RuntimeError("intentional handler failure")

    monkeypatch.setattr("app.routers.stripe_webhook.stripe.Webhook.construct_event", _construct)
    monkeypatch.setattr(wh, "_handle_checkout_session_completed", _shim)
    r = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=0,v1=ok"})
    assert r.status_code == 500
