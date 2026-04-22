"""Stripe refund for security deposit (separate deposit PaymentIntent or legacy combined capture)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import stripe
from supabase import Client

from app.config import Settings
from app.services.booking_events import log_booking_event

logger = logging.getLogger(__name__)


def refund_stripe_deposit_for_booking(
    client: Client,
    settings: Settings,
    *,
    booking_id: str,
) -> dict[str, Any]:
    """
    Release the security deposit: for a **separate** deposit PaymentIntent, if the amount is
    only **authorized** (manual capture, status ``requires_capture``), **cancel** the
    PaymentIntent to void the hold. If the deposit was **captured** (or legacy flow), create a
    full **refund** on that PaymentIntent. For legacy **combined** checkout, partial refund on the
    rental PaymentIntent using ``stripe_deposit_captured_cents``.
    """
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise ValueError("Stripe is not configured (missing STRIPE_SECRET_KEY).")

    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise ValueError("Booking not found")
    row = rows[0]

    if row.get("deposit_refunded_at"):
        raise ValueError("Deposit has already been refunded via Stripe.")

    dep_pi = (row.get("stripe_deposit_payment_intent_id") or "").strip()
    rental_pi = (row.get("stripe_payment_intent_id") or "").strip()

    stripe.api_key = key
    rid: str
    now = datetime.now(timezone.utc).isoformat()
    amount_cents: int | None = None

    try:
        if dep_pi:
            pi_obj = stripe.PaymentIntent.retrieve(dep_pi)
            pi_status = str(
                getattr(pi_obj, "status", None)
                or (pi_obj.get("status") if isinstance(pi_obj, dict) else "")
            )

            if pi_status == "requires_capture":
                # Card hold (manual capture) — no charge yet; void the authorization, do not create a Refund.
                try:
                    stripe.PaymentIntent.cancel(dep_pi)
                except stripe.InvalidRequestError as e:
                    em = (getattr(e, "message", None) or str(e) or "").lower()
                    if "canceled" not in em and "has already been" not in em and "fully refunded" not in em:
                        raise
                rid = f"void:{dep_pi}"
                amount_cents = None
            elif pi_status == "canceled":
                raise ValueError(
                    "This security deposit was already voided in Stripe. If the booking still shows "
                    "a deposit, use “Sync payment from Stripe” to refresh.",
                )
            else:
                ref = stripe.Refund.create(
                    payment_intent=dep_pi,
                    reason="requested_by_customer",
                    metadata={"booking_id": booking_id, "refund_kind": "deposit"},
                )
                rid = str(ref.id)
                amount_cents = getattr(ref, "amount", None)
        else:
            cap_raw = row.get("stripe_deposit_captured_cents")
            try:
                deposit_cents = int(cap_raw) if cap_raw is not None else 0
            except (TypeError, ValueError):
                deposit_cents = 0
            if deposit_cents <= 0 or not rental_pi:
                raise ValueError(
                    "No Stripe deposit payment found. Deposit refunds apply after the customer "
                    "pays the deposit Checkout (or legacy combined checkout).",
                )
            ref = stripe.Refund.create(
                payment_intent=rental_pi,
                amount=deposit_cents,
                reason="requested_by_customer",
                metadata={"booking_id": booking_id, "refund_kind": "deposit"},
            )
            rid = str(ref.id)
            amount_cents = deposit_cents
    except stripe.InvalidRequestError as e:
        logger.warning("stripe_deposit_refund_invalid booking_id=%s err=%s", booking_id, e)
        msg = getattr(e, "user_message", None) or getattr(e, "message", None) or str(e)
        raise ValueError(msg) from e
    except stripe.StripeError as e:
        logger.exception("stripe_deposit_refund_failed booking_id=%s", booking_id)
        msg = getattr(e, "user_message", None) or getattr(e, "message", None) or str(e)
        raise ValueError(msg) from e

    client.table("booking_requests").update(
        {
            "deposit_refunded_at": now,
            "stripe_deposit_refund_id": rid,
        }
    ).eq("id", booking_id).execute()

    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_deposit_refunded",
        actor_type="admin",
        metadata={
            "stripe_refund_id": rid,
            "amount_cents": amount_cents,
            "payment_intent_id": dep_pi or rental_pi,
            "separate_deposit_pi": bool(dep_pi),
            "release_kind": "void_authorization" if (dep_pi and rid.startswith("void:")) else "refund",
        },
    )
    logger.info(
        "stripe_deposit_refunded booking_id=%s refund_id=%s",
        booking_id,
        rid,
    )
    return {
        "stripe_deposit_refund_id": rid,
        "amount_cents": amount_cents,
        "deposit_refunded_at": now,
    }
