"""Send rental quote / booking emails via SMTP (optional)."""

from __future__ import annotations

import html
import logging
import smtplib
from decimal import Decimal
from email.message import EmailMessage

from app.branding import LEGAL_BUSINESS_NAME
from app.config import Settings

log = logging.getLogger(__name__)


def _plain_signature_lines() -> list[str]:
    return ["", "--", LEGAL_BUSINESS_NAME]


def _email_signature_html() -> str:
    leg = html.escape(LEGAL_BUSINESS_NAME)
    return f'<p style="margin-top:1.5em;font-size:0.9em;color:#57534e">{leg}</p>'


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
    subject = f"{LEGAL_BUSINESS_NAME} — quote for {item_title}"
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
    subject = f"{LEGAL_BUSINESS_NAME} — we received your request ({item_title})"
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


def _approval_steps_progress_html(steps: list[tuple[str, str | None]]) -> str:
    """Email-safe horizontal stepper: N circles + labels (title, optional URL)."""
    n = len(steps)
    if n == 0:
        return ""
    w = max(24, min(33, 100 // n))
    num_cells: list[str] = []
    lab_cells: list[str] = []
    for i, (title, href) in enumerate(steps, start=1):
        num_cells.append(
            f'<td align="center" valign="top" style="padding:10px 4px;width:{w}%">'
            f'<div style="display:inline-block;width:40px;height:40px;line-height:40px;'
            f'border-radius:50%;background:#1e293b;color:#fff;font-weight:bold;font-family:Arial,sans-serif;font-size:16px">'
            f"{i}</div></td>"
        )
        esc_t = html.escape(title)
        if href:
            esc_h = html.escape(href, quote=True)
            lab_cells.append(
                f'<td align="center" valign="top" style="padding:6px 4px;font-size:13px;'
                f'font-family:Arial,sans-serif;color:#334155;line-height:1.35">'
                f'<a href="{esc_h}" style="color:#1d4ed8;font-weight:600">{esc_t}</a></td>'
            )
        else:
            lab_cells.append(
                f'<td align="center" valign="top" style="padding:6px 4px;font-size:13px;'
                f'font-family:Arial,sans-serif;color:#334155;line-height:1.35">{esc_t}</td>'
            )
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:560px;margin:0 auto 8px">
<tr>{"".join(num_cells)}</tr>
<tr>{"".join(lab_cells)}</tr>
</table>
<p style="text-align:center;margin:0 0 18px;font-family:Arial,sans-serif;font-size:17px;color:#0f172a">
<strong>Your checklist: {n} step{"s" if n != 1 else ""}</strong>
</p>
"""


def send_booking_approved_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    rental_total_with_tax: Decimal,
    deposit_amount: Decimal,
    payment_collection_url: str | None,
    signing_url: str | None = None,
    rental_checkout_url: str | None = None,
    deposit_checkout_url: str | None = None,
    payment_path: str | None = None,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping approval notice to %s", to_addr)
        return False
    subject = f"{LEGAL_BUSINESS_NAME} — next steps for your rental ({item_title})"
    pp = (payment_path or "").strip().lower()
    rent_u = (rental_checkout_url or "").strip() or None
    dep_u = (deposit_checkout_url or "").strip() or None
    coll_u = (payment_collection_url or "").strip() or None

    steps: list[tuple[str, str | None]] = []
    if signing_url and signing_url.strip():
        steps.append(("Sign your rental agreement", signing_url.strip()))
    if rent_u:
        steps.append(("Pay rental total (with tax)", rent_u))
    elif pp != "card" and coll_u:
        steps.append(("Payment instructions", coll_u))
    if dep_u:
        steps.append(("Pay refundable security deposit", dep_u))

    n = len(steps)
    stepper_html = _approval_steps_progress_html(steps)

    plain_step_lines: list[str] = []
    for i, (label, href) in enumerate(steps, start=1):
        plain_step_lines.append(f"STEP {i} of {n} — {label}")
        if href:
            plain_step_lines.append(href)
        plain_step_lines.append("")

    pay_follow_plain: list[str] = []
    pay_follow_html = ""
    if pp == "card" and not rent_u and coll_u:
        pay_follow_plain = ["", "Additional reference link:", coll_u, ""]
        pay_follow_html = f'<p class="muted" style="font-size:0.9em">Reference: <a href="{html.escape(coll_u, quote=True)}">{html.escape(coll_u)}</a></p>'
    elif pp == "card" and not rent_u and not coll_u:
        pay_follow_plain = [
            "",
            f"Card checkout links will be added by {LEGAL_BUSINESS_NAME} if Stripe is not yet configured on our side.",
            "",
        ]
        pay_follow_html = '<p class="muted" style="font-size:0.9em">If no payment links appear above, our team will follow up with a secure Stripe link.</p>'
    elif coll_u and not rent_u and pp != "card":
        if not any(s[0] == "Payment instructions" for s in steps):
            pay_follow_plain = ["", "Payment / next steps:", coll_u, ""]
            pay_follow_html = f'<p><strong>Payment / next steps</strong><br/><a href="{html.escape(coll_u, quote=True)}">Open link</a></p>'

    plain = "\n".join(
        [
            "Your rental request was approved for the dates below.",
            f"Item: {item_title}",
            f"Dates: {start_date} → {end_date}",
            f"Rental total (with tax): {_money(rental_total_with_tax)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            "",
            f"You have {n} step(s) to complete (see numbered checklist in the HTML version of this email).",
            "",
            *plain_step_lines,
            *pay_follow_plain,
            "Equipment is not released until every step above is complete. You may complete Stripe checkouts in any order unless we tell you otherwise.",
            *_plain_signature_lines(),
        ]
    )
    safe_title = html.escape(item_title)
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p>Your <strong>rental request was approved</strong> for the dates below.</p>
<p><strong>{safe_title}</strong><br/>
{html.escape(start_date)} → {html.escape(end_date)}</p>
<ul>
<li>Rental total (with tax): {_money(rental_total_with_tax)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
{stepper_html}
<p style="font-size:0.95em">Use the links in the checklist above. Your booking is <strong>not confirmed</strong> until every step is done.</p>
{pay_follow_html}
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send approval email: %s", e)
        return False


def send_signature_completed_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    next_status: str,
    pdf_path: str | None,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping signature confirmation to %s", to_addr)
        return False
    subject = f"{LEGAL_BUSINESS_NAME} — agreement signed ({item_title})"
    pdf_note = f"\nExecuted packet saved at: {pdf_path}\n" if pdf_path else ""
    pay_plain = [
        "",
        "Payment links were included in your approval email (same thread). Complete any remaining steps there,",
        "or open “My rentals” on our site after signing in if you use the same email address.",
        "",
    ]
    pay_html = """\
<p class="muted" style="font-size:0.95em">Use the <strong>Stripe links in your approval email</strong> for rental and deposit (if applicable), or visit <strong>My rentals</strong> while signed in.</p>"""

    plain = "\n".join(
        [
            "Your signed rental agreement has been recorded.",
            f"Item: {item_title}",
            f"Booking status: {next_status}",
            *pay_plain,
            pdf_note,
            *_plain_signature_lines(),
        ]
    )
    safe_title = html.escape(item_title)
    html_body = f"""\
<html><body>
<p><strong>Agreement signed</strong></p>
<p>Your rental agreement for <strong>{safe_title}</strong> has been recorded.</p>
<p>Status: {html.escape(next_status)}</p>
{pay_html}
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send signature confirmation email: %s", e)
        return False


def send_stripe_checkout_ready_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    rental_checkout_url: str | None,
    deposit_checkout_url: str | None,
    rental_total_with_tax: Decimal | None = None,
    deposit_amount: Decimal | None = None,
) -> str:
    """
    Email customer with one or two Stripe Checkout links (rental total vs security deposit).

    Returns a short status token for admin UI: ``sent``, ``skipped_no_smtp``,
    ``skipped_no_payment_links``, or ``failed_smtp:…`` (truncated).
    """
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping Stripe checkout email to %s", to_addr)
        return "skipped_no_smtp"
    rent_u = (rental_checkout_url or "").strip() or None
    dep_u = (deposit_checkout_url or "").strip() or None
    if not rent_u and not dep_u:
        log.warning("Stripe checkout email skipped: no payment URLs for booking email %s", to_addr)
        return "skipped_no_payment_links"
    has_both = bool(rent_u and dep_u)
    subject = (
        f"{LEGAL_BUSINESS_NAME} — pay rental & deposit ({item_title})"
        if has_both
        else f"{LEGAL_BUSINESS_NAME} — payment link ({item_title})"
    )
    dep = deposit_amount if deposit_amount is not None and deposit_amount > 0 else None
    amt_lines: list[str] = []
    amt_html_parts: list[str] = []
    if rental_total_with_tax is not None:
        amt_lines.append(f"Rental total (with tax): {_money(rental_total_with_tax)}")
        amt_html_parts.append(
            f"<p>Rental total (with tax): <strong>{html.escape(_money(rental_total_with_tax))}</strong></p>"
        )
    if dep is not None:
        amt_lines.append(f"Refundable security deposit: {_money(dep)}")
        amt_html_parts.append(
            f"<p>Refundable security deposit: <strong>{html.escape(_money(dep))}</strong></p>"
        )
    amounts_plain = "\n".join(amt_lines) if amt_lines else ""
    amounts_html = "".join(amt_html_parts)
    safe_title = html.escape(item_title)

    plain_blocks: list[str] = [
        f"Your rental agreement is signed for {item_title}.",
        "",
        "Use the secure Stripe Checkout links below. Each link is for a separate charge — complete every link that applies to your booking.",
        "",
        amounts_plain,
        "",
    ]
    html_blocks: list[str] = [
        f"<p>Your agreement is signed for <strong>{safe_title}</strong>.</p>",
        "<p>Use the <strong>separate</strong> Stripe links below. Each link pays a different part of your booking.</p>",
        amounts_html,
    ]
    if rent_u:
        plain_blocks.extend(
            [
                "— RENTAL BALANCE (rental total with tax) —",
                rent_u,
                "",
            ]
        )
        esc_r = html.escape(rent_u, quote=True)
        html_blocks.append(
            f'<p><strong>1) Rental balance</strong> (rental total with tax)</p><p><a href="{esc_r}">Open rental payment (Stripe)</a></p>'
        )
    if dep_u:
        plain_blocks.extend(
            [
                "— SECURITY DEPOSIT (refundable per your rental agreement) —",
                dep_u,
                "",
            ]
        )
        esc_d = html.escape(dep_u, quote=True)
        html_blocks.append(
            f'<p><strong>2) Security deposit</strong> (refundable per agreement)</p><p><a href="{esc_d}">Open deposit payment (Stripe)</a></p>'
        )
    plain_blocks.extend(
        [
            f"Pay rental first or deposit first — either order is fine unless {LEGAL_BUSINESS_NAME} tells you otherwise.",
            "",
            f"Questions? Reply to this email or contact {LEGAL_BUSINESS_NAME}.",
            *_plain_signature_lines(),
        ]
    )
    html_blocks.append(
        '<p class="muted" style="font-size:0.9em">You may complete the two checkouts in any order unless we instructed otherwise.</p>'
        if has_both
        else ""
    )
    html_blocks.append(_email_signature_html())
    plain = "\n".join(plain_blocks)
    html_body = f"<html><body><p><strong>Payment links</strong></p>{''.join(html_blocks)}</body></html>"
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return "sent"
    except Exception as e:
        log.warning("Failed to send Stripe checkout email: %s", e)
        msg = str(e).replace("\n", " ").strip() or type(e).__name__
        tail = msg[:180] if len(msg) > 180 else msg
        return f"failed_smtp:{tail}"


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
    subject = f"{LEGAL_BUSINESS_NAME} — update on your request ({item_title})"
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
