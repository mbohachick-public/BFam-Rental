"""Stripe webhooks — raw body + signature verification (no JWT)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from app.config import get_settings
from app.deps import get_supabase_client
from app.services.booking_events import log_booking_event
from app.services.stripe_checkout import _cents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])


def _event_already_processed(client: Client, stripe_event_id: str) -> bool:
    existing = (
        client.table("stripe_webhook_events")
        .select("id")
        .eq("stripe_event_id", stripe_event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        logger.info("stripe_webhook_duplicate event_id=%s", stripe_event_id)
        return True
    return False


def _insert_processed_event(
    client: Client, *, stripe_event_id: str, event_type: str, booking_id: str | None
) -> None:
    client.table("stripe_webhook_events").insert(
        {
            "stripe_event_id": stripe_event_id,
            "event_type": event_type,
            "booking_id": booking_id,
        }
    ).execute()


def _checkout_session_paid(session: dict) -> bool:
    ps = str(session.get("payment_status") or "").strip().lower()
    return ps in ("paid", "no_payment_required")


def _payment_intent_status_value(pi_obj) -> str | None:
    if isinstance(pi_obj, dict):
        return str(pi_obj.get("status") or "") or None
    if pi_obj is None:
        return None
    s = getattr(pi_obj, "status", None)
    return str(s) if s is not None else None


def _session_payment_intent_authorized_for_manual_deposit(session: dict) -> bool:
    """
    For checkout sessions created with payment_intent_data.capture_method=manual, Stripe
    may leave session.payment_status as `unpaid` while the card is authorized. In that
    case the underlying PaymentIntent status is `requires_capture`.
    """
    if _checkout_session_paid(session):
        return False
    ps = str(session.get("payment_status") or "").strip().lower()
    if ps not in ("unpaid", ""):
        return False
    pi_field = session.get("payment_intent")
    if isinstance(pi_field, dict) and _payment_intent_status_value(pi_field) == "requires_capture":
        return True
    if isinstance(pi_field, dict) and pi_field.get("id"):
        pi_id = str(pi_field["id"])
    else:
        pi_id = _payment_intent_id(session)
    if not pi_id:
        return False
    try:
        pi = stripe.PaymentIntent.retrieve(pi_id)
    except stripe.StripeError:
        logger.exception("stripe_webhook_deposit_retrieve_pi_failed session_id=%s", session.get("id"))
        return False
    return _payment_intent_status_value(pi) == "requires_capture"


def _deposit_checkout_satisfied(session: dict) -> bool:
    if _checkout_session_paid(session):
        return True
    return _session_payment_intent_authorized_for_manual_deposit(session)


def _infer_checkout_kind_from_amounts(client: Client, booking_id: str, session: dict) -> str | None:
    """
    When Session metadata omits checkout_kind (older sessions, API quirks), infer from
    amount_total vs booking rental total and deposit so deposit payments still set deposit_secured_at.
    Returns 'deposit', 'rental', 'legacy_combo', or None.
    """
    raw_total = session.get("amount_total")
    if raw_total is None:
        return None
    try:
        total_cents = int(raw_total)
    except (TypeError, ValueError):
        return None
    res = (
        client.table("booking_requests")
        .select("rental_total_with_tax,deposit_amount")
        .eq("id", booking_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not res:
        return None
    row = res[0]
    rental_raw = row.get("rental_total_with_tax")
    if rental_raw is None:
        return None
    rental_cents = _cents(Decimal(str(rental_raw)))
    dep_raw = row.get("deposit_amount")
    dep_amt = Decimal(str(dep_raw)) if dep_raw is not None else Decimal("0")
    dep_cents = _cents(dep_amt) if dep_amt > 0 else 0
    if dep_cents > 0 and total_cents == dep_cents:
        return "deposit"
    if total_cents == rental_cents:
        return "rental"
    if dep_cents > 0 and total_cents == rental_cents + dep_cents:
        return "legacy_combo"
    return None


def _payment_intent_id(session: dict) -> str | None:
    pi = session.get("payment_intent")
    if pi is None:
        return None
    if isinstance(pi, str):
        return pi
    if isinstance(pi, dict) and pi.get("id"):
        return str(pi["id"])
    return None


def _handle_rental_checkout_completed(client: Client, session: dict) -> None:
    meta = session.get("metadata") or {}
    booking_id = (meta.get("booking_id") or "").strip()
    if not booking_id:
        logger.error("stripe_webhook_missing_booking_id session_id=%s", session.get("id"))
        return
    if not _checkout_session_paid(session):
        logger.info(
            "stripe_webhook_session_not_paid session_id=%s payment_status=%s",
            session.get("id"),
            session.get("payment_status"),
        )
        return

    now = datetime.now(timezone.utc).isoformat()
    pi = _payment_intent_id(session)
    upd: dict = {
        "rental_paid_at": now,
        "rental_payment_status": "paid",
        "stripe_payment_intent_id": pi,
    }
    client.table("booking_requests").update(upd).eq("id", booking_id).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_rental_paid",
        actor_type="system",
        metadata={
            "stripe_session_id": str(session.get("id") or ""),
            "stripe_payment_intent_id": pi,
            "checkout_kind": "rental",
        },
    )
    logger.info("stripe_webhook_rental_paid booking_id=%s", booking_id)


def _handle_deposit_checkout_completed(client: Client, session: dict) -> None:
    meta = session.get("metadata") or {}
    booking_id = (meta.get("booking_id") or "").strip()
    if not booking_id:
        logger.error("stripe_webhook_missing_booking_id session_id=%s", session.get("id"))
        return
    if not _deposit_checkout_satisfied(session):
        logger.info(
            "stripe_webhook_deposit_session_not_satisfied session_id=%s payment_status=%s",
            session.get("id"),
            session.get("payment_status"),
        )
        return
    now = datetime.now(timezone.utc).isoformat()
    pi = _payment_intent_id(session)
    if not pi and isinstance(session.get("payment_intent"), dict):
        pi = str((session.get("payment_intent") or {}).get("id") or "") or None
    dep_cents = 0
    try:
        dep_cents = int(str(meta.get("deposit_cents") or "0").strip() or "0")
    except ValueError:
        dep_cents = 0
    if dep_cents <= 0:
        br0 = (
            client.table("booking_requests")
            .select("deposit_amount")
            .eq("id", booking_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if br0 and br0[0].get("deposit_amount") is not None:
            dep_cents = _cents(Decimal(str(br0[0]["deposit_amount"])))
    is_hold = _session_payment_intent_authorized_for_manual_deposit(session) and not _checkout_session_paid(
        session
    )
    upd: dict = {
        "deposit_secured_at": now,
        "stripe_deposit_payment_intent_id": pi,
    }
    if is_hold:
        # Card authorized only; no capture. Release via PaymentIntent.cancel from admin.
        upd["stripe_deposit_captured_cents"] = 0
    elif dep_cents > 0:
        upd["stripe_deposit_captured_cents"] = dep_cents
    client.table("booking_requests").update(upd).eq("id", booking_id).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_deposit_paid",
        actor_type="system",
        metadata={
            "stripe_session_id": str(session.get("id") or ""),
            "stripe_payment_intent_id": pi,
            "checkout_kind": "deposit",
            "deposit_cents": dep_cents,
            "deposit_hold": is_hold,
        },
    )
    logger.info(
        "stripe_webhook_deposit_secured booking_id=%s hold=%s",
        booking_id,
        is_hold,
    )


def _handle_legacy_combined_checkout_completed(client: Client, session: dict) -> None:
    """Single Checkout with rental + deposit line items (metadata deposit_in_checkout=1)."""
    meta = session.get("metadata") or {}
    booking_id = (meta.get("booking_id") or "").strip()
    if not booking_id:
        logger.error("stripe_webhook_missing_booking_id session_id=%s", session.get("id"))
        return
    if not _checkout_session_paid(session):
        return
    now = datetime.now(timezone.utc).isoformat()
    pi = _payment_intent_id(session)
    upd: dict = {
        "rental_paid_at": now,
        "rental_payment_status": "paid",
        "stripe_payment_intent_id": pi,
        "deposit_secured_at": now,
    }
    dep_cents = 0
    try:
        dep_cents = int(str(meta.get("deposit_cents") or "0").strip() or "0")
    except ValueError:
        dep_cents = 0
    if dep_cents <= 0:
        br0 = (
            client.table("booking_requests")
            .select("deposit_amount")
            .eq("id", booking_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if br0 and br0[0].get("deposit_amount") is not None:
            dep_cents = _cents(Decimal(str(br0[0]["deposit_amount"])))
    if dep_cents > 0:
        upd["stripe_deposit_captured_cents"] = dep_cents
    client.table("booking_requests").update(upd).eq("id", booking_id).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_rental_paid",
        actor_type="system",
        metadata={
            "stripe_session_id": str(session.get("id") or ""),
            "stripe_payment_intent_id": pi,
            "deposit_in_checkout": True,
            "legacy_combined_checkout": True,
        },
    )
    logger.info("stripe_webhook_legacy_combined_paid booking_id=%s", booking_id)


def _handle_checkout_session_completed(client: Client, session: dict) -> None:
    meta = session.get("metadata") or {}
    booking_id = (meta.get("booking_id") or "").strip()
    kind = (meta.get("checkout_kind") or "").strip().lower()
    deposit_in_combo = str(meta.get("deposit_in_checkout") or "").strip().lower() in ("1", "true", "yes")

    if booking_id and not kind and not deposit_in_combo:
        inferred = _infer_checkout_kind_from_amounts(client, booking_id, session)
        if inferred == "deposit":
            kind = "deposit"
            logger.info(
                "stripe_webhook_inferred_checkout_kind session_id=%s booking_id=%s kind=deposit",
                session.get("id"),
                booking_id,
            )
        elif inferred == "rental":
            kind = "rental"
            logger.info(
                "stripe_webhook_inferred_checkout_kind session_id=%s booking_id=%s kind=rental",
                session.get("id"),
                booking_id,
            )
        elif inferred == "legacy_combo":
            deposit_in_combo = True
            logger.info(
                "stripe_webhook_inferred_checkout_kind session_id=%s booking_id=%s kind=legacy_combo",
                session.get("id"),
                booking_id,
            )

    if kind == "deposit":
        _handle_deposit_checkout_completed(client, session)
    elif kind == "rental":
        _handle_rental_checkout_completed(client, session)
    elif deposit_in_combo:
        _handle_legacy_combined_checkout_completed(client, session)
    else:
        _handle_rental_checkout_completed(client, session)


def _handle_checkout_failed(client: Client, session: dict, *, payment_status: str) -> None:
    meta = session.get("metadata") or {}
    booking_id = (meta.get("booking_id") or "").strip()
    if not booking_id:
        return
    kind = (meta.get("checkout_kind") or "").strip().lower()
    if kind == "deposit":
        log_booking_event(
            client,
            booking_id=booking_id,
            event_type="stripe_deposit_checkout_failed",
            actor_type="system",
            metadata={"payment_status": payment_status},
        )
        return
    res = client.table("booking_requests").select("rental_paid_at").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows or rows[0].get("rental_paid_at"):
        return
    client.table("booking_requests").update({"rental_payment_status": "failed"}).eq("id", booking_id).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_checkout_failed",
        actor_type="system",
        metadata={"payment_status": payment_status},
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, client: Client = Depends(get_supabase_client)):
    settings = get_settings()
    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook not configured.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        logger.warning("stripe_webhook_missing_signature")
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=secret)
    except ValueError as e:
        logger.warning("stripe_webhook_invalid_payload err=%s", e)
        raise HTTPException(status_code=400, detail="Invalid payload") from e
    except stripe.SignatureVerificationError as e:
        logger.warning("stripe_webhook_bad_signature err=%s", e)
        raise HTTPException(status_code=400, detail="Invalid signature") from e

    event_dict = event if isinstance(event, dict) else event.to_dict()
    event_id = str(event_dict.get("id") or "")
    event_type = str(event_dict.get("type") or "")
    data_obj = (event_dict.get("data") or {}).get("object") or {}

    booking_id_for_log: str | None = None
    if isinstance(data_obj.get("metadata"), dict):
        booking_id_for_log = (data_obj["metadata"].get("booking_id") or "").strip() or None

    if _event_already_processed(client, event_id):
        return {"received": True, "duplicate": True}

    sk = (settings.stripe_secret_key or "").strip()
    if sk:
        stripe.api_key = sk

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_session_completed(client, data_obj)
        elif event_type == "checkout.session.async_payment_succeeded":
            _handle_checkout_session_completed(client, data_obj)
        elif event_type == "checkout.session.async_payment_failed":
            _handle_checkout_failed(client, data_obj, payment_status="async_failed")
        elif event_type == "payment_intent.payment_failed":
            logger.info("stripe_webhook_payment_intent_failed ignored_phase1")
        else:
            logger.debug("stripe_webhook_unhandled_type type=%s", event_type)
        _insert_processed_event(
            client,
            stripe_event_id=event_id,
            event_type=event_type,
            booking_id=booking_id_for_log,
        )
    except Exception:
        logger.exception("stripe_webhook_processing_failed type=%s event_id=%s", event_type, event_id)
        raise HTTPException(status_code=500, detail="Webhook processing failed") from None

    return {"received": True}
