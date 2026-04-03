"""Send rental quote / booking emails via SMTP (optional)."""

from __future__ import annotations

import html
import logging
import smtplib
from decimal import Decimal
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger(__name__)


def smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host.strip() and settings.smtp_from.strip())


def _money(d: Decimal) -> str:
    return f"${d:,.2f}"


def _send_message(settings: Settings, to_addr: str, subject: str, plain: str, html: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from.strip()
    msg["To"] = to_addr
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.smtp_host.strip(), int(settings.smtp_port), timeout=45) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        user = settings.smtp_user.strip()
        if user:
            smtp.login(user, settings.smtp_password)
        smtp.send_message(msg)


def send_quote_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    num_days: int,
    base_amount: Decimal,
    discount_percent: Decimal,
    discounted_subtotal: Decimal,
    deposit_amount: Decimal,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping quote email to %s", to_addr)
        return False
    subject = f"BFam Rental — quote for {item_title}"
    plain = "\n".join(
        [
            f"Quote for {item_title}",
            f"Dates: {start_date} → {end_date} ({num_days} days)",
            f"Base rental: {_money(base_amount)}",
            f"Duration discount: {discount_percent}%",
            f"Rental after discount: {_money(discounted_subtotal)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            "",
            "This is an estimate. Submit a booking request on the site to proceed.",
        ]
    )
    html = f"""\
<html><body>
<p><strong>Quote for {item_title}</strong></p>
<p>Dates: {start_date} → {end_date} ({num_days} days)</p>
<ul>
<li>Base rental: {_money(base_amount)}</li>
<li>Duration discount: {discount_percent}%</li>
<li>Rental after discount: {_money(discounted_subtotal)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
<p>This is an estimate. Submit a booking request on the site to proceed.</p>
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html)
        return True
    except Exception as e:
        log.warning("Failed to send quote email: %s", e)
        return False


def send_booking_received_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    num_days: int,
    base_amount: Decimal,
    discount_percent: Decimal,
    discounted_subtotal: Decimal,
    deposit_amount: Decimal,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping booking confirmation to %s", to_addr)
        return False
    subject = f"BFam Rental — we received your request ({item_title})"
    plain = "\n".join(
        [
            "Thanks — your booking request was received.",
            f"Item: {item_title}",
            f"Dates: {start_date} → {end_date} ({num_days} days)",
            f"Base rental: {_money(base_amount)}",
            f"Duration discount: {discount_percent}%",
            f"Rental after discount: {_money(discounted_subtotal)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            "",
            "We will follow up when your request is reviewed.",
        ]
    )
    html = f"""\
<html><body>
<p>Thanks — your <strong>booking request</strong> was received.</p>
<p><strong>{item_title}</strong><br/>
{start_date} → {end_date} ({num_days} days)</p>
<ul>
<li>Base rental: {_money(base_amount)}</li>
<li>Duration discount: {discount_percent}%</li>
<li>Rental after discount: {_money(discounted_subtotal)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
<p>We will follow up when your request is reviewed.</p>
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html)
        return True
    except Exception as e:
        log.warning("Failed to send booking confirmation email: %s", e)
        return False


def send_booking_declined_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    reason: str,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping decline notice to %s", to_addr)
        return False
    subject = f"BFam Rental — update on your request ({item_title})"
    plain = "\n".join(
        [
            "We are unable to approve your rental request for the dates below.",
            f"Item: {item_title}",
            f"Requested period: {start_date} → {end_date}",
            "",
            "Reason:",
            reason,
            "",
            "Those dates are open again for other requests. If you have questions, reply to this email or contact us.",
        ]
    )
    safe_reason = html.escape(reason)
    safe_title = html.escape(item_title)
    html_body = f"""\
<html><body>
<p>We are unable to approve your <strong>rental request</strong> for the dates below.</p>
<p><strong>{safe_title}</strong><br/>
Requested period: {html.escape(start_date)} → {html.escape(end_date)}</p>
<p><strong>Reason</strong></p>
<p style="white-space:pre-wrap">{safe_reason}</p>
<p>Those dates are open again for other requests. If you have questions, contact us.</p>
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send decline email: %s", e)
        return False
