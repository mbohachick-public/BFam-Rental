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
