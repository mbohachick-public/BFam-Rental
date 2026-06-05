"""Create signing tokens + document snapshots; complete customer signature."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from supabase import Client

from app.branding import LEGAL_BUSINESS_NAME
from app.config import Settings
from app.schemas import BookingRequestStatus, PaymentPath
from app.services.admin_notify import try_finalize_booking_after_obligations_complete, try_notify_admin_confirm_needed
from app.services.booking_events import log_booking_event
from app.services.contract_pdf import build_executed_packet_pdf, sha256_bytes
from app.services.contract_render import (
    DOCUMENT_VERSION,
    EXECUTED_PACKET_ACKNOWLEDGMENTS,
    render_damage_fee_schedule_html,
    render_rental_agreement_html,
    rental_agreement_pdf_body_lines,
    sha256_hex,
)


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _expires_at(settings: Settings) -> str:
    days = max(1, int(settings.signing_token_ttl_days))
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def signing_url(settings: Settings, raw_token: str) -> str:
    base = (settings.frontend_public_url or "").rstrip("/")
    return f"{base}/booking-actions/{raw_token}/sign"


def clear_signing_artifacts_for_booking(client: Client, booking_id: str) -> None:
    """Remove prior unsigned SIGN tokens and agreement snapshots (regenerate / re-approve)."""
    try:
        client.table("booking_action_tokens").delete().eq("booking_id", booking_id).execute()
    except Exception:
        pass
    try:
        client.table("booking_documents").delete().eq("booking_id", booking_id).execute()
    except Exception:
        pass


def create_signing_package(
    client: Client,
    settings: Settings,
    *,
    booking_id: str,
    booking_row: dict[str, Any],
    item_title: str,
    payment_path: PaymentPath,
) -> str:
    """
    Insert agreement + damage HTML snapshots, a fresh SIGN token, return raw token string.
    Caller updates booking status to approved_awaiting_signature.
    """
    clear_signing_artifacts_for_booking(client, booking_id)
    row = {**booking_row, "payment_path": payment_path.value}
    agr = render_rental_agreement_html(row, item_title)
    dmg = render_damage_fee_schedule_html(row, item_title)
    client.table("booking_documents").insert(
        {
            "booking_id": booking_id,
            "document_type": "RENTAL_AGREEMENT",
            "document_version": DOCUMENT_VERSION,
            "title": "Rental Agreement",
            "html_snapshot": agr,
            "pdf_path": None,
            "sha256_hash": sha256_hex(agr),
        }
    ).execute()
    client.table("booking_documents").insert(
        {
            "booking_id": booking_id,
            "document_type": "DAMAGE_FEE_SCHEDULE",
            "document_version": DOCUMENT_VERSION,
            "title": "Damage & Fee Schedule",
            "html_snapshot": dmg,
            "pdf_path": None,
            "sha256_hash": sha256_hex(dmg),
        }
    ).execute()
    raw = secrets.token_urlsafe(32)
    client.table("booking_action_tokens").insert(
        {
            "booking_id": booking_id,
            "token_hash": _token_hash(raw),
            "action_type": "SIGN",
            "expires_at": _expires_at(settings),
            "used_at": None,
        }
    ).execute()
    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="signing_package_created",
        actor_type="system",
        metadata={"document_version": DOCUMENT_VERSION},
    )
    return raw


def load_token_row_by_raw(client: Client, raw_token: str) -> dict[str, Any] | None:
    th = _token_hash(raw_token)
    res = (
        client.table("booking_action_tokens")
        .select("*")
        .eq("token_hash", th)
        .eq("action_type", "SIGN")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def resolve_sign_token(client: Client, raw_token: str) -> dict[str, Any] | None:
    th = _token_hash(raw_token)
    res = (
        client.table("booking_action_tokens")
        .select("*")
        .eq("token_hash", th)
        .eq("action_type", "SIGN")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    tok = rows[0]
    if tok.get("used_at"):
        return {"error": "used", "token_row": tok}
    exp = tok.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                return {"error": "expired", "token_row": tok}
        except Exception:
            pass
    return {"token_row": tok}


def load_signing_page_payload(
    client: Client, booking_id: str
) -> dict[str, Any] | None:
    br = (
        client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute().data
        or []
    )
    if not br:
        return None
    booking = br[0]
    if str(booking.get("status") or "") != BookingRequestStatus.approved_awaiting_signature.value:
        return None
    docs = (
        client.table("booking_documents")
        .select("document_type,html_snapshot,title")
        .eq("booking_id", booking_id)
        .execute()
        .data
        or []
    )
    agr = next((d for d in docs if d.get("document_type") == "RENTAL_AGREEMENT"), None)
    dmg = next((d for d in docs if d.get("document_type") == "DAMAGE_FEE_SCHEDULE"), None)
    if not agr or not dmg:
        return None
    item_res = (
        client.table("items").select("title").eq("id", booking["item_id"]).limit(1).execute().data
        or []
    )
    item_title = str(item_res[0].get("title") or "Rental item") if item_res else "Rental item"
    return {
        "booking": booking,
        "item_title": item_title,
        "agreement_html": agr.get("html_snapshot") or "",
        "damage_html": dmg.get("html_snapshot") or "",
    }


def complete_customer_signature(
    client: Client,
    settings: Settings,
    *,
    raw_token: str,
    signer_name: str,
    signer_email: str | None,
    company_name: str | None,
    typed_signature: str,
    acknowledgments: dict[str, bool],
    ip_address: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    resolved = resolve_sign_token(client, raw_token)
    if resolved is None:
        return {"error": "not_found"}
    if "error" in resolved:
        return {"error": resolved["error"]}
    tok = resolved["token_row"]
    booking_id = str(tok["booking_id"])
    payload = load_signing_page_payload(client, booking_id)
    if not payload:
        return {"error": "invalid_state"}
    booking = payload["booking"]
    expected_email = str(booking.get("customer_email") or "").strip().lower()
    provided_raw = (signer_email or "").strip()
    provided_lower = provided_raw.lower()
    if expected_email:
        if not provided_lower:
            email_for_record = str(booking.get("customer_email") or "").strip()
        elif provided_lower != expected_email:
            return {"error": "email_mismatch"}
        else:
            email_for_record = provided_raw
    else:
        if not provided_lower:
            return {"error": "email_required"}
        email_for_record = provided_raw

    existing = (
        client.table("booking_signatures").select("id").eq("booking_id", booking_id).execute().data
        or []
    )
    if existing:
        return {"error": "already_signed"}

    now = datetime.now(timezone.utc).isoformat()
    next_status = BookingRequestStatus.approved_pending_payment.value
    sig_ins = (
        client.table("booking_signatures")
        .insert(
            {
                "booking_id": booking_id,
                "signer_name": signer_name.strip(),
                "signer_email": email_for_record,
                "company_name": (company_name or "").strip() or None,
                "typed_signature": typed_signature.strip(),
                "signed_at": now,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "agreement_version": DOCUMENT_VERSION,
                "damage_schedule_version": DOCUMENT_VERSION,
                "acknowledged_terms": acknowledgments,
                "signature_audit_json": {
                    "submitted_at": now,
                    "signatureIpAddress": ip_address,
                    "user_agent": user_agent,
                },
            }
        )
        .execute()
    )
    sig_rows = sig_ins.data or []
    sig_id = str(sig_rows[0]["id"]) if sig_rows else ""

    pdf_rel = f"{booking_id}/{sig_id}.pdf"
    root = Path(settings.contract_packets_dir)
    out_path = root / booking_id / f"{sig_id}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    delivery_requested = bool(booking.get("delivery_requested"))
    pickup_from_site_requested = bool(booking.get("pickup_from_site_requested"))
    job_site = str(booking.get("delivery_address") or "").strip()
    fulfill_parts: list[str] = []
    if not delivery_requested and not pickup_from_site_requested:
        fulfill_parts.append("Customer pickup and return")
    if delivery_requested:
        fulfill_parts.append("Delivery to job site")
    if pickup_from_site_requested:
        fulfill_parts.append("Pickup from job site")
    fulfillment = "; ".join(fulfill_parts) if fulfill_parts else "—"
    if job_site and (delivery_requested or pickup_from_site_requested):
        fulfillment = f"{fulfillment}; job site address: {job_site}"

    rental_total = str(booking.get("rental_total_with_tax") or "")
    deposit_amt = str(booking.get("deposit_amount") or "")
    pricing = (
        f"Rental total (includes tax where applicable): {rental_total or '—'}; "
        f"Security deposit (refundable hold): {deposit_amt or '—'}; "
        "Delivery and pickup charges are estimates and may be adjusted by Bohachick Rentals & Supply LLC prior to final approval."
    )

    summary = {
        "Equipment": payload["item_title"],
        "Rental period": f"{booking.get('start_date')} through {booking.get('end_date')}",
        "Fulfillment": fulfillment,
        "Pricing snapshot": pricing,
        "Status": "Executed",
    }
    # Executed packet should reflect final required checkboxes (no duplicates).
    acks = list(EXECUTED_PACKET_ACKNOWLEDGMENTS)
    next_steps = [
        "Check your email for pickup or delivery instructions before heading out.",
        "Equipment is not released until payment, deposit, and confirmation requirements are complete.",
        "Contact Bohachick Rentals & Supply LLC if anything looks incorrect.",
    ]

    renter_name = signer_name.strip()
    owner = str(LEGAL_BUSINESS_NAME)
    start = str(booking.get("start_date") or "")
    end = str(booking.get("end_date") or "")
    eq = str(payload.get("item_title") or "")
    job_site_line = ""
    if job_site and (delivery_requested or pickup_from_site_requested):
        job_site_line = f"Job site address: {job_site}"

    rental_agreement_lines = [
        f"Version: {DOCUMENT_VERSION}",
        "",
        "Parties",
        f"Owner: {owner}",
        f"Renter: {renter_name}",
        "",
        "Equipment",
        f"Equipment item: {eq}",
        "",
        "Rental Period",
        f"{start} through {end}",
        "",
        "Fulfillment",
        fulfillment.split("; job site address:")[0].strip(),
        job_site_line,
        "",
        "Pricing Snapshot",
        f"Rental total: {rental_total or '—'} (includes tax where applicable)",
        f"Security deposit: {deposit_amt or '—'} (refundable hold)",
        "Delivery and pickup charges are estimates and may be adjusted by Bohachick Rentals & Supply LLC prior to final approval.",
        "",
        "Terms Summary",
        "Renter agrees to operate the equipment lawfully, return it on time and in the same condition subject to ordinary wear, and pay for damage, misuse, late fees, cleaning, missing items, and loss of use as described in this agreement and the Damage & Fee Schedule Addendum.",
        "Renter is responsible for loss of use of the equipment during repair periods caused by damage, misuse, late return, or failure to return the equipment in acceptable condition.",
        "Renter acknowledges the equipment is accepted in good working condition unless otherwise noted at pickup or delivery.",
        "",
    ] + rental_agreement_pdf_body_lines(owner=owner)
    pdf_bytes = build_executed_packet_pdf(
        booking_summary=summary,
        rental_agreement_lines=rental_agreement_lines,
        damage_html=payload["damage_html"],
        acknowledgments=acks,
        next_steps=next_steps,
        signature_block={
            "signer_name": signer_name.strip(),
            "signer_email": email_for_record,
            "company_name": (company_name or "").strip() or None,
            "typed_signature": typed_signature.strip(),
            "signed_at": now,
            "ip_address": ip_address,
        },
    )
    out_path.write_bytes(pdf_bytes)
    pdf_hash = sha256_bytes(pdf_bytes)

    client.table("booking_documents").insert(
        {
            "booking_id": booking_id,
            "document_type": "EXECUTED_PACKET",
            "document_version": DOCUMENT_VERSION,
            "title": "Executed rental packet",
            "html_snapshot": None,
            "pdf_path": str(out_path.resolve()),
            "sha256_hash": pdf_hash,
        }
    ).execute()

    client.table("booking_requests").update(
        {
            "status": next_status,
            "agreement_signed_at": now,
        }
    ).eq("id", booking_id).execute()

    client.table("booking_action_tokens").update({"used_at": now}).eq("id", tok["id"]).execute()

    log_booking_event(
        client,
        booking_id=booking_id,
        event_type="customer_signed",
        actor_type="customer",
        metadata={"signer_email": email_for_record},
    )
    try_finalize_booking_after_obligations_complete(client, settings, booking_id)
    try_notify_admin_confirm_needed(client, settings, booking_id)
    return {
        "ok": True,
        "next_status": next_status,
        "booking_id": booking_id,
        "pdf_path": str(out_path.resolve()),
    }
