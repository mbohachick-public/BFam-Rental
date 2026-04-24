"""Email admins when booking workflow actions are required (approval or final confirm)."""

from __future__ import annotations

import html
import logging
from decimal import Decimal

from supabase import Client

from app.branding import LEGAL_BUSINESS_NAME
from app.config import Settings
from app.schemas import BookingRequestStatus
from app.services.booking_events import log_booking_event
from app.services.quote_email import try_send_email

log = logging.getLogger(__name__)

ADMIN_EMAIL_APPROVAL_EVENT = "admin_email_approval_needed_sent"
ADMIN_EMAIL_CONFIRM_EVENT = "admin_email_confirm_ready_sent"

_PRE_CONFIRM_STATUSES = frozenset(
    {
        BookingRequestStatus.approved_pending_payment.value,
        BookingRequestStatus.approved_pending_check_clearance.value,
    }
)

_APPROVAL_STATUSES = frozenset(
    {
        BookingRequestStatus.requested.value,
        BookingRequestStatus.pending.value,
        BookingRequestStatus.under_review.value,
    }
)


def _parse_smtp_from_address(from_header: str) -> str | None:
    """Return a single mailbox from SMTP_FROM (handles ``Name <addr@host>``)."""
    s = (from_header or "").strip()
    if not s:
        return None
    if "<" in s and ">" in s:
        inner = s[s.index("<") + 1 : s.index(">")].strip()
        return inner if "@" in inner else None
    return s if "@" in s else None


def _admin_recipient(settings: Settings) -> str | None:
    """
    Inbox for staff workflow mail. Explicit ADMIN_NOTIFICATION_EMAIL wins; otherwise use the
    same mailbox as SMTP (many hosts use an email-shaped SMTP_USER, or SMTP_FROM is the ops address).
    """
    explicit = (settings.admin_notification_email or "").strip()
    if explicit:
        return explicit
    user = (settings.smtp_user or "").strip()
    if "@" in user:
        return user
    return _parse_smtp_from_address(settings.smtp_from)


def _booking_event_exists(client: Client, booking_id: str, event_type: str) -> bool:
    try:
        res = (
            client.table("booking_events")
            .select("id")
            .eq("booking_id", booking_id)
            .eq("event_type", event_type)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        log.debug("booking_events check skipped: %s", exc)
        return False


def booking_row_ready_for_confirm(row: dict) -> bool:
    """Same gates as admin confirm (without mutating)."""
    st = str(row.get("status") or "")
    if st not in _PRE_CONFIRM_STATUSES:
        return False
    rp = str(row.get("rental_payment_status") or "").strip().lower()
    if not row.get("rental_paid_at") and rp != "paid":
        return False
    dep_need = False
    try:
        d0 = row.get("deposit_amount")
        dep_need = d0 is not None and Decimal(str(d0)) > 0
    except Exception:
        dep_need = row.get("deposit_amount") is not None
    if dep_need and not row.get("deposit_secured_at"):
        return False
    if not row.get("agreement_signed_at"):
        return False
    return True


def _admin_bookings_url(settings: Settings, booking_id: str) -> str:
    base = (settings.frontend_public_url or "").strip().rstrip("/")
    return f"{base}/admin/bookings/{booking_id}"


def _fetch_booking(client: Client, booking_id: str) -> dict | None:
    res = client.table("booking_requests").select("*").eq("id", booking_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def _fetch_item_title(client: Client, item_id: str) -> str:
    res = client.table("items").select("title").eq("id", item_id).limit(1).execute()
    rows = res.data or []
    return str(rows[0].get("title") or "Rental item") if rows else "Rental item"


def try_notify_admin_approval_needed(client: Client, settings: Settings, booking_id: str) -> None:
    from app.services.quote_email import smtp_configured

    if not smtp_configured(settings):
        return
    to = _admin_recipient(settings)
    if not to:
        log.warning(
            "Admin approval email skipped: SMTP is set but no staff inbox "
            "(set ADMIN_NOTIFICATION_EMAIL or use an email-shaped SMTP_USER / SMTP_FROM address)."
        )
        return
    if _booking_event_exists(client, booking_id, ADMIN_EMAIL_APPROVAL_EVENT):
        return
    row = _fetch_booking(client, booking_id)
    if not row:
        return
    st = str(row.get("status") or "")
    if st not in _APPROVAL_STATUSES:
        return
    if not row.get("drivers_license_path"):
        return
    item_title = _fetch_item_title(client, str(row["item_id"]))
    start = str(row.get("start_date") or "")
    end = str(row.get("end_date") or "")
    who = " ".join(
        x
        for x in (
            row.get("customer_first_name"),
            row.get("customer_last_name"),
        )
        if x
    ).strip() or "—"
    url = _admin_bookings_url(settings, booking_id)
    subj = f"{LEGAL_BUSINESS_NAME} — booking needs your approval"
    plain = "\n".join(
        [
            "A customer submitted a booking request that needs approval.",
            f"Item: {item_title}",
            f"Dates: {start} → {end}",
            f"Customer: {who}",
            "",
            f"Open admin: {url}",
            "",
            f"-- {LEGAL_BUSINESS_NAME}",
        ]
    )
    safe_url = html.escape(url, quote=True)
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p><strong>Booking needs approval</strong></p>
<p>{html.escape(item_title)}<br/>
{html.escape(start)} → {html.escape(end)}<br/>
Customer: {html.escape(who)}</p>
<p><a href="{safe_url}">Open booking in admin</a></p>
</body></html>"""
    if try_send_email(settings, to_addr=to, subject=subj, plain=plain, html_body=html_body):
        log_booking_event(
            client,
            booking_id=booking_id,
            event_type=ADMIN_EMAIL_APPROVAL_EVENT,
            actor_type="system",
        )


def try_notify_admin_confirm_needed(client: Client, settings: Settings, booking_id: str) -> None:
    from app.services.quote_email import smtp_configured

    if not smtp_configured(settings):
        return
    to = _admin_recipient(settings)
    if not to:
        log.warning(
            "Admin confirm-ready email skipped: SMTP is set but no staff inbox "
            "(set ADMIN_NOTIFICATION_EMAIL or use an email-shaped SMTP_USER / SMTP_FROM address)."
        )
        return
    if _booking_event_exists(client, booking_id, ADMIN_EMAIL_CONFIRM_EVENT):
        return
    row = _fetch_booking(client, booking_id)
    if not row or not booking_row_ready_for_confirm(row):
        return
    item_title = _fetch_item_title(client, str(row["item_id"]))
    start = str(row.get("start_date") or "")
    end = str(row.get("end_date") or "")
    url = _admin_bookings_url(settings, booking_id)
    subj = f"{LEGAL_BUSINESS_NAME} — booking ready to confirm"
    plain = "\n".join(
        [
            "Rental payment, deposit (if required), and agreement are complete.",
            "Confirm the booking in admin to finalize the reservation.",
            f"Item: {item_title}",
            f"Dates: {start} → {end}",
            "",
            f"Open admin: {url}",
            "",
            f"-- {LEGAL_BUSINESS_NAME}",
        ]
    )
    safe_url = html.escape(url, quote=True)
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p><strong>Booking is ready to confirm</strong></p>
<p>Rental payment, deposit (if applicable), and signed agreement are satisfied.</p>
<p>{html.escape(item_title)}<br/>
{html.escape(start)} → {html.escape(end)}</p>
<p><a href="{safe_url}">Open booking in admin</a></p>
</body></html>"""
    if try_send_email(settings, to_addr=to, subject=subj, plain=plain, html_body=html_body):
        log_booking_event(
            client,
            booking_id=booking_id,
            event_type=ADMIN_EMAIL_CONFIRM_EVENT,
            actor_type="system",
        )
