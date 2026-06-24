"""Create Stripe SetupIntents so customers can save a card before admin approval."""

from __future__ import annotations

import stripe

from app.config import Settings


def stripe_payment_collection_enabled(settings: Settings) -> bool:
    return bool((settings.stripe_secret_key or "").strip())


def create_booking_setup_intent(settings: Settings, *, booking_id: str, customer_email: str | None) -> dict:
    """Return SetupIntent id + client_secret; metadata tags the booking row."""
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise ValueError("Stripe is not configured on the API.")
    stripe.api_key = key
    meta = {"booking_id": booking_id}
    params: dict = {"usage": "off_session", "metadata": meta, "payment_method_types": ["card"]}
    em = (customer_email or "").strip()
    if em:
        # SetupIntent does not accept customer_email; use a Stripe Customer id.
        existing = stripe.Customer.list(email=em, limit=1)
        rows = getattr(existing, "data", None) or []
        if rows:
            params["customer"] = rows[0].id
        else:
            cust = stripe.Customer.create(email=em, metadata=meta)
            params["customer"] = cust.id
    intent = stripe.SetupIntent.create(**params)
    return {
        "id": intent.id,
        "client_secret": intent.client_secret,
    }


def assert_payment_method_for_booking(
    settings: Settings,
    *,
    booking_id: str,
    setup_intent_id: str | None,
    payment_method_id: str,
) -> None:
    """Reject payment methods not produced by this booking's SetupIntent."""
    sid = (setup_intent_id or "").strip()
    if not sid:
        raise ValueError("Save your card on the completion page before submitting.")
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise ValueError("Stripe is not configured on the API.")
    stripe.api_key = key
    intent = stripe.SetupIntent.retrieve(sid)
    meta_bid = (intent.metadata or {}).get("booking_id")
    if str(meta_bid) != str(booking_id):
        raise ValueError("Payment method is not linked to this booking.")
    if intent.status != "succeeded":
        raise ValueError("Card setup is incomplete. Save your payment method again.")
    intent_pm = intent.payment_method
    if not isinstance(intent_pm, str) or intent_pm != payment_method_id:
        raise ValueError("Payment method does not match the card saved for this booking.")
