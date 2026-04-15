"""Send rental quote / booking emails via SMTP (optional)."""

from __future__ import annotations

import html
import logging
import smtplib
from decimal import Decimal
from email.message import EmailMessage

from app.branding import CUSTOMER_BRAND_NAME, LEGAL_BUSINESS_NAME
from app.config import Settings

log = logging.getLogger(__name__)


def _plain_signature_lines() -> list[str]:
    return ["", "--", CUSTOMER_BRAND_NAME, LEGAL_BUSINESS_NAME]


def _email_signature_html() -> str:
    b = html.escape(CUSTOMER_BRAND_NAME)
    leg = html.escape(LEGAL_BUSINESS_NAME)
    return (
        f'<p style="margin-top:1.5em;font-size:0.9em;color:#57534e">{b}<br/>{leg}</p>'
    )


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
    discounted_subtotal: Decimal,
    sales_tax_rate_percent: Decimal,
    sales_tax_amount: Decimal,
    rental_total_with_tax: Decimal,
    sales_tax_source: str,
    deposit_amount: Decimal,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping quote email to %s", to_addr)
        return False
    subject = f"{CUSTOMER_BRAND_NAME} — quote for {item_title}"
    rate_s = f"{sales_tax_rate_percent:f}".rstrip("0").rstrip(".")
    plain = "\n".join(
        [
            f"Quote for {item_title}",
            f"Dates: {start_date} → {end_date} ({num_days} days)",
            f"Rental subtotal: {_money(discounted_subtotal)}",
            f"Sales tax ({rate_s}%): {_money(sales_tax_amount)}",
            f"Rental total (with tax): {_money(rental_total_with_tax)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            f"Tax source: {sales_tax_source}",
            "",
            "This is an estimate. Submit a booking request on the site to proceed.",
            *_plain_signature_lines(),
        ]
    )
    safe_src = html.escape(sales_tax_source)
    html_body = f"""\
<html><body>
<p><strong>Quote for {item_title}</strong></p>
<p>Dates: {start_date} → {end_date} ({num_days} days)</p>
<ul>
<li>Rental subtotal: {_money(discounted_subtotal)}</li>
<li>Sales tax ({html.escape(rate_s)}%): {_money(sales_tax_amount)}</li>
<li>Rental total (with tax): {_money(rental_total_with_tax)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
<p class="muted" style="font-size:0.9em">Tax source: {safe_src}</p>
<p>This is an estimate. Submit a booking request on the site to proceed.</p>
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
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
    discounted_subtotal: Decimal,
    sales_tax_rate_percent: Decimal,
    sales_tax_amount: Decimal,
    rental_total_with_tax: Decimal,
    sales_tax_source: str,
    deposit_amount: Decimal,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping booking confirmation to %s", to_addr)
        return False
    subject = f"{CUSTOMER_BRAND_NAME} — we received your request ({item_title})"
    rate_s = f"{sales_tax_rate_percent:f}".rstrip("0").rstrip(".")
    plain = "\n".join(
        [
            "Thanks — your booking request was received.",
            f"Item: {item_title}",
            f"Dates: {start_date} → {end_date} ({num_days} days)",
            f"Rental subtotal: {_money(discounted_subtotal)}",
            f"Sales tax ({rate_s}%): {_money(sales_tax_amount)}",
            f"Rental total (with tax): {_money(rental_total_with_tax)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            f"Tax source: {sales_tax_source}",
            "",
            "We will follow up when your request is reviewed.",
            *_plain_signature_lines(),
        ]
    )
    safe_src = html.escape(sales_tax_source)
    html_body = f"""\
<html><body>
<p>Thanks — your <strong>booking request</strong> was received.</p>
<p><strong>{item_title}</strong><br/>
{start_date} → {end_date} ({num_days} days)</p>
<ul>
<li>Rental subtotal: {_money(discounted_subtotal)}</li>
<li>Sales tax ({html.escape(rate_s)}%): {_money(sales_tax_amount)}</li>
<li>Rental total (with tax): {_money(rental_total_with_tax)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
<p class="muted" style="font-size:0.9em">Tax source: {safe_src}</p>
<p>We will follow up when your request is reviewed.</p>
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
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
    subject = f"{CUSTOMER_BRAND_NAME} — update on your request ({item_title})"
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
            *_plain_signature_lines(),
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
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send decline email: %s", e)
        return False
