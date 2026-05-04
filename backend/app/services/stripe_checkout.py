"""Create Stripe Checkout Sessions for approved card-path bookings (rental + optional separate deposit)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import stripe
from supabase import Client

from app.config import Settings
from app.schemas import BookingRequestStatus, PaymentPath
from app.services.booking_events import log_booking_event
from app.services.dates import iter_days_inclusive

logger = logging.getLogger(__name__)


def _cents(amount: Decimal) -> int:
    q = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(q)


def create_checkout_session_for_booking(
    client: Client,
    settings: Settings,
    *,
    booking_id: str,
) -> dict[str, Any]:
    """
    Create Stripe Checkout session(s): always a rental session when unpaid; optionally a separate
    deposit session when STRIPE_CHECKOUT_INCLUDE_DEPOSIT and deposit_amount > 0 and deposit unpaid.
    """
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise ValueError("Stripe is not configured (missing STRIPE_SECRET_KEY).")

    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise ValueError("Booking not found")
    row = rows[0]
    st = str(row.get("status") or "")
    if st not in (
        BookingRequestStatus.approved_pending_payment.value,
        BookingRequestStatus.approved_awaiting_signature.value,
    ):
        raise ValueError(
            "Checkout can only be generated for card bookings awaiting signature or awaiting payment.",
        )
    if str(row.get("payment_path") or "") != PaymentPath.card.value:
        raise ValueError("Stripe Checkout is only available for card payment path in Phase 1.")

    total = row.get("rental_total_with_tax")
    if total is None:
        raise ValueError("Booking is missing rental_total_with_tax.")
    amount = Decimal(str(total))
    if amount <= 0:
        raise ValueError("Rental total must be positive.")

    deposit_raw = row.get("deposit_amount")
    deposit_amt = Decimal(str(deposit_raw)) if deposit_raw is not None else Decimal("0")
    if deposit_amt < 0:
        raise ValueError("Deposit amount cannot be negative.")
    include_deposit = bool(settings.stripe_checkout_include_deposit) and deposit_amt > 0

    rental_paid = bool(row.get("rental_paid_at"))
    deposit_secured = bool(row.get("deposit_secured_at"))

    if rental_paid and (not include_deposit or deposit_secured or deposit_amt <= 0):
        raise ValueError(
            "Nothing to generate: rental is already paid and deposit is already secured (or no deposit).",
        )

    item_res = (
        client.table("items").select("title").eq("id", row["item_id"]).limit(1).execute().data or []
    )
    item_title = str(item_res[0].get("title") or "Rental") if item_res else "Rental"
    delivery_fee_raw = row.get("delivery_fee")
    delivery_fee = (
        Decimal(str(delivery_fee_raw)) if delivery_fee_raw is not None else Decimal("0")
    )
    pickup_fee_raw = row.get("pickup_fee")
    pickup_fee = Decimal(str(pickup_fee_raw)) if pickup_fee_raw is not None else Decimal("0")
    start = row.get("start_date")
    end = row.get("end_date")
    try:
        from datetime import date as date_cls

        sd = date_cls.fromisoformat(str(start))
        ed = date_cls.fromisoformat(str(end))
        num_days = len(iter_days_inclusive(sd, ed))
    except Exception:
        num_days = 1

    base = settings.public_app_base_url()
    if not base:
        raise ValueError("APP_BASE_URL or FRONTEND_PUBLIC_URL must be set for Stripe redirects.")

    stripe.api_key = key
    customer_email = str(row.get("customer_email") or "").strip() or None

    line_name = f"{item_title} rental — {num_days} day{'s' if num_days != 1 else ''}"
    if delivery_fee > 0 and pickup_fee > 0:
        line_name = f"{line_name} (includes delivery & pickup from site)"
    elif delivery_fee > 0:
        line_name = f"{line_name} (includes delivery)"
    elif pickup_fee > 0:
        line_name = f"{line_name} (includes pickup from site)"
    deposit_line_name = f"{item_title} — refundable security deposit"

    now = datetime.now(timezone.utc).isoformat()
    upd: dict[str, Any] = {}
    out: dict[str, Any] = {
        "stripe_checkout_session_id": None,
        "stripe_checkout_url": None,
        "stripe_checkout_created_at": None,
        "stripe_deposit_checkout_session_id": None,
        "stripe_deposit_checkout_url": None,
        "stripe_deposit_checkout_created_at": None,
        "amount_cents": _cents(amount),
        "deposit_cents": _cents(deposit_amt) if include_deposit and not deposit_secured else 0,
    }

    base_meta = {
        "booking_id": booking_id,
        "booking_status": st,
        "item_id": str(row["item_id"]),
        "days": str(num_days),
        "customer_email": customer_email or "",
    }

    if not rental_paid:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=customer_email,
            payment_intent_data={
                # Rental balance is charged immediately (no manual capture / hold only).
                "capture_method": "automatic",
            },
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": line_name},
                        "unit_amount": _cents(amount),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{base}/payment-success?booking_id={booking_id}",
            cancel_url=f"{base}/items/{row['item_id']}",
            metadata={
                **base_meta,
                "checkout_kind": "rental",
                "deposit_in_checkout": "0",
                "rental_cents": str(_cents(amount)),
            },
        )
        sid = str(session.id)
        url = str(session.url or "")
        upd["stripe_checkout_session_id"] = sid
        upd["stripe_checkout_url"] = url
        upd["stripe_checkout_created_at"] = now
        out["stripe_checkout_session_id"] = sid
        out["stripe_checkout_url"] = url
        out["stripe_checkout_created_at"] = now
        logger.info(
            "stripe_checkout_rental booking_id=%s session_id=%s cents=%s",
            booking_id,
            sid,
            _cents(amount),
        )

    if include_deposit and not deposit_secured:
        session_d = stripe.checkout.Session.create(
            mode="payment",
            customer_email=customer_email,
            payment_intent_data={
                # Security deposit: authorize only; capture only if you explicitly capture later
                # (e.g. damages). Use cancel/void in admin to release the hold.
                "capture_method": "manual",
            },
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": deposit_line_name},
                        "unit_amount": _cents(deposit_amt),
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{base}/payment-success?booking_id={booking_id}",
            cancel_url=f"{base}/items/{row['item_id']}",
            metadata={
                **base_meta,
                "checkout_kind": "deposit",
                "deposit_cents": str(_cents(deposit_amt)),
                "deposit_capture_mode": "hold",
            },
        )
        dsid = str(session_d.id)
        durl = str(session_d.url or "")
        upd["stripe_deposit_checkout_session_id"] = dsid
        upd["stripe_deposit_checkout_url"] = durl
        upd["stripe_deposit_checkout_created_at"] = now
        out["stripe_deposit_checkout_session_id"] = dsid
        out["stripe_deposit_checkout_url"] = durl
        out["stripe_deposit_checkout_created_at"] = now
        logger.info(
            "stripe_checkout_deposit booking_id=%s session_id=%s cents=%s",
            booking_id,
            dsid,
            _cents(deposit_amt),
        )

    if not upd:
        raise ValueError(
            "Nothing to generate: rental already paid and deposit already secured (or deposit amount is zero).",
        )

    client.table("booking_requests").update(upd).eq("id", booking_id).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="stripe_checkout_created",
        actor_type="system",
        metadata={
            "rental_session_id": out.get("stripe_checkout_session_id"),
            "deposit_session_id": out.get("stripe_deposit_checkout_session_id"),
            "rental_cents": _cents(amount),
            "deposit_cents": out.get("deposit_cents") or 0,
            "separate_deposit_checkout": bool(out.get("stripe_deposit_checkout_session_id")),
            "rental_capture": "automatic",
            "deposit_capture": "hold" if out.get("stripe_deposit_checkout_session_id") else None,
        },
    )

    return out
