"""Pull Stripe Checkout Session state into booking_requests when webhooks were missed (e.g. local dev)."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import stripe
from supabase import Client

from app.config import Settings

logger = logging.getLogger(__name__)


def _session_to_dict(sess: Any) -> dict:
    if isinstance(sess, dict):
        return sess
    to_d = getattr(sess, "to_dict", None)
    if callable(to_d):
        return to_d()
    raise TypeError("Unexpected Stripe session type")


def sync_booking_checkout_sessions_from_stripe(
    client: Client,
    settings: Settings,
    *,
    booking_id: str,
) -> dict[str, Any]:
    """
    For each Checkout session id stored on the booking, retrieve Stripe and, if the session
    is paid, run the same completion handler as the webhook.

    Returns a dict with ``actions`` (list of short strings) for logging / admin UI.
    """
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise ValueError("Stripe is not configured (missing STRIPE_SECRET_KEY).")

    res = (
        client.table("booking_requests")
        .select(
            "stripe_checkout_session_id,stripe_deposit_checkout_session_id,"
            "rental_paid_at,deposit_secured_at,deposit_amount"
        )
        .eq("id", booking_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not res:
        raise ValueError("Booking not found")
    row = res[0]

    dep_raw = row.get("deposit_amount")
    try:
        needs_deposit = dep_raw is not None and Decimal(str(dep_raw)) > 0
    except Exception:
        needs_deposit = True

    stripe.api_key = key
    actions: list[str] = []
    # Lazy import avoids circular import with app.routers.stripe_webhook at package load time.
    from app.routers.stripe_webhook import _deposit_checkout_satisfied, _handle_checkout_session_completed

    rental_sid = str(row.get("stripe_checkout_session_id") or "").strip()
    if rental_sid and not row.get("rental_paid_at"):
        sess = stripe.checkout.Session.retrieve(rental_sid)
        d = _session_to_dict(sess)
        ps = str(d.get("payment_status") or "").strip().lower()
        if ps in ("paid", "no_payment_required"):
            _handle_checkout_session_completed(client, d)
            actions.append("rental_checkout_applied")
            logger.info("stripe_reconcile_rental booking_id=%s session_id=%s", booking_id, rental_sid)
        else:
            actions.append(f"rental_checkout_skipped_payment_status={ps or 'empty'}")

    deposit_sid = str(row.get("stripe_deposit_checkout_session_id") or "").strip()
    if deposit_sid and needs_deposit and not row.get("deposit_secured_at"):
        sess_d = stripe.checkout.Session.retrieve(deposit_sid, expand=["payment_intent"])
        dd = _session_to_dict(sess_d)
        if _deposit_checkout_satisfied(dd):
            _handle_checkout_session_completed(client, dd)
            actions.append("deposit_checkout_applied")
            logger.info("stripe_reconcile_deposit booking_id=%s session_id=%s", booking_id, deposit_sid)
        else:
            ps = str(dd.get("payment_status") or "").strip().lower()
            actions.append(f"deposit_checkout_skipped_payment_status={ps or 'empty'}")

    if not actions:
        actions.append("nothing_to_sync")

    return {"booking_id": booking_id, "actions": actions}
