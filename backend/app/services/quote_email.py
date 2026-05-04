"""Send rental quote / booking emails via SMTP (optional)."""

from __future__ import annotations

import html
import logging
import smtplib
from datetime import date
from decimal import Decimal
from email.message import EmailMessage

from app.branding import (
    EMAIL_PUBLIC_LOGO_PATH,
    LEGAL_BUSINESS_NAME,
    PICKUP_FACILITY_ADDRESS,
    PICKUP_STANDARD_TIME_LABEL,
    RENTAL_COORDINATION_EMAIL,
    SERVICE_AREA_TAGLINE,
)
from app.config import Settings

log = logging.getLogger(__name__)

# SMTP2Go (and similar providers) optionally rewrite https:// links for click tracking, which can
# break long tokenized URLs (signing) and Stripe Checkout session links. Append this after opening
# <a ...> per their docs, e.g. <a href="https://..." no-track>
NO_TRACK_A_ATTR = " no-track"


def _plain_signature_lines() -> list[str]:
    return ["", "--", LEGAL_BUSINESS_NAME]


def _email_signature_html() -> str:
    leg = html.escape(LEGAL_BUSINESS_NAME)
    return f'<p style="margin-top:1.5em;font-size:0.9em;color:#57534e">{leg}</p>'


def smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host.strip() and settings.smtp_from.strip())


def _parse_email_address(raw: str) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    if "<" in s and ">" in s:
        start = s.find("<")
        end = s.find(">", start + 1)
        if start >= 0 and end > start:
            inner = s[start + 1 : end].strip()
            return inner if "@" in inner else None
    return s if "@" in s else None


def smtp_account_mailbox(settings: Settings) -> str | None:
    """
    Best mailbox for contact buttons that should target the configured SMTP account.
    Prefers SMTP_USER when it looks like an email, else falls back to SMTP_FROM.
    """
    user = (settings.smtp_user or "").strip()
    if "@" in user:
        return user
    return _parse_email_address(settings.smtp_from)


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


def try_send_email(
    settings: Settings,
    *,
    to_addr: str,
    subject: str,
    plain: str,
    html_body: str,
) -> bool:
    """Send one HTML+plain email; return False if SMTP is unset or send fails."""
    if not smtp_configured(settings):
        log.info("SMTP not configured; skip email to %s", to_addr)
        return False
    try:
        _send_message(settings, to_addr.strip(), subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send email to %s: %s", to_addr, e)
        return False


def send_booking_intake_continue_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    complete_url: str,
) -> bool:
    """After Step 1: backup email with completion link."""
    safe_url = html.escape(complete_url, quote=True)
    subj = f"{LEGAL_BUSINESS_NAME} — Complete your rental request"
    plain_lines = [
        "Thanks — we received your rental request.",
        f"Equipment: {item_title}",
        f"Dates: {start_date} → {end_date}",
        "",
        "Finish your verification and saved payment step here (bookmark this link):",
        complete_url,
        "",
        "This is still a request — it is NOT confirmed until we review and approve it.",
        *_plain_signature_lines(),
    ]
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p><strong>Complete your rental request</strong></p>
<p>{html.escape(item_title)}<br/>
{html.escape(start_date)} → {html.escape(end_date)}</p>
<p><a href="{safe_url}"{NO_TRACK_A_ATTR}>Continue to Step 2</a></p>
<p>This is still a request — it is not a confirmed reservation until we approve it.</p>
{_email_signature_html()}
</body></html>"""
    return try_send_email(settings, to_addr=to_addr, subject=subj, plain="\n".join(plain_lines), html_body=html_body)


def send_booking_pending_review_notice_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
) -> bool:
    """After Step 2: customer knows request is queued for owner review."""
    subj = f"{LEGAL_BUSINESS_NAME} — Rental request received for review"
    plain = "\n".join(
        [
            "We received your completed request.",
            f"Equipment: {item_title}",
            f"Dates: {start_date} → {end_date}",
            "",
            "Our team will review it shortly. Your booking is not confirmed until approved.",
            *_plain_signature_lines(),
        ]
    )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p><strong>Request submitted for review</strong></p>
<p>{html.escape(item_title)}<br/>
{html.escape(start_date)} → {html.escape(end_date)}</p>
<p>We&apos;ll review your request shortly. Your booking is <strong>not</strong> confirmed until you receive approval from us.</p>
{_email_signature_html()}
</body></html>"""
    return try_send_email(settings, to_addr=to_addr, subject=subj, plain=plain, html_body=html_body)


def send_pickup_confirmed_email(
    settings: Settings,
    *,
    to_addr: str,
    greeting_name: str | None,
    item_title: str,
    pickup_date_long: str,
    logo_url: str | None,
) -> bool:
    """
    After admin confirms a booking with customer pickup (no delivery), send facility and time details.
    """
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping pickup instructions to %s", to_addr)
        return False
    greet = (greeting_name or "").strip()
    salutation = f"Dear {greet}," if greet else "Hello,"
    subj = f"{LEGAL_BUSINESS_NAME} — Pickup instructions for your rental"
    esc_item = html.escape(item_title)
    esc_addr = html.escape(PICKUP_FACILITY_ADDRESS)
    esc_time = html.escape(PICKUP_STANDARD_TIME_LABEL)
    esc_when = html.escape(pickup_date_long)
    esc_coord = html.escape(RENTAL_COORDINATION_EMAIL)
    leg = html.escape(LEGAL_BUSINESS_NAME)
    tag = html.escape(SERVICE_AREA_TAGLINE)

    plain = "\n".join(
        [
            salutation,
            "",
            "Your rental is confirmed. Thank you for choosing "
            f"{LEGAL_BUSINESS_NAME}. Because this reservation is for customer pickup "
            "(not delivery), please use the details below.",
            "",
            "Pickup location",
            PICKUP_FACILITY_ADDRESS,
            "",
            "Scheduled pickup",
            f"Standard pickup is {PICKUP_STANDARD_TIME_LABEL} on {pickup_date_long} — "
            "the first day of your rental period. Please arrive on time so we can complete "
            "your paperwork and equipment walk-through.",
            "",
            "Alternate pickup time",
            f"If you need to request a different pickup time, email {RENTAL_COORDINATION_EMAIL} "
            "with your name, the equipment reserved, and your rental dates. We will reply to "
            "confirm whether an alternate time can be accommodated.",
            "",
            "Equipment",
            item_title,
            "",
            f"— {LEGAL_BUSINESS_NAME}",
            SERVICE_AREA_TAGLINE,
        ]
    )

    logo_block = ""
    if logo_url and logo_url.strip():
        esc_u = html.escape(logo_url.strip(), quote=True)
        logo_block = (
            f'<img src="{esc_u}" alt="{leg}" width="220" '
            'style="max-width:220px;height:auto;display:block;margin:0 auto 14px;border:0"/>'
        )

    html_body = f"""\
<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#faf8f3;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf8f3;">
<tr><td align="center" style="padding:28px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #d6d3d1;border-radius:10px;overflow:hidden;">
<tr><td style="background:#1e4d3a;padding:22px 24px;text-align:center;">
{logo_block}
<p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:19px;color:#ffffff;font-weight:600;letter-spacing:0.02em;">{leg}</p>
<p style="margin:8px 0 0;font-family:Arial,sans-serif;font-size:13px;color:#c7ddd4;">Pickup confirmation</p>
</td></tr>
<tr><td style="padding:28px 26px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1c1917;">
<p style="margin:0 0 16px;">{html.escape(salutation)}</p>
<p style="margin:0 0 16px;">Your rental is <strong>confirmed</strong>. Thank you for choosing <strong>{leg}</strong>. Because this reservation is for <strong>customer pickup</strong> (not delivery), please follow the instructions below.</p>
<h2 style="margin:22px 0 10px;font-size:14px;font-weight:700;color:#1e4d3a;text-transform:uppercase;letter-spacing:0.06em;">Pickup location</h2>
<p style="margin:0 0 6px;">{esc_addr}</p>
<h2 style="margin:22px 0 10px;font-size:14px;font-weight:700;color:#1e4d3a;text-transform:uppercase;letter-spacing:0.06em;">Scheduled pickup</h2>
<p style="margin:0 0 6px;">Standard pickup is <strong>{esc_time}</strong> on <strong>{esc_when}</strong> — the first day of your rental period. Please arrive on time so we can complete your paperwork and equipment walk-through.</p>
<h2 style="margin:22px 0 10px;font-size:14px;font-weight:700;color:#1e4d3a;text-transform:uppercase;letter-spacing:0.06em;">Alternate pickup time</h2>
<p style="margin:0 0 6px;">If you need to request a different pickup time, email <a href="mailto:{esc_coord}" style="color:#1e4d3a;font-weight:600;">{esc_coord}</a> with your name, the equipment reserved, and your rental dates. We will reply to confirm whether an alternate time can be accommodated.</p>
<h2 style="margin:22px 0 10px;font-size:14px;font-weight:700;color:#1e4d3a;text-transform:uppercase;letter-spacing:0.06em;">Equipment</h2>
<p style="margin:0 0 6px;"><strong>{esc_item}</strong></p>
<p style="margin:28px 0 0;padding-top:20px;border-top:1px solid #e7e5e4;font-size:0.9em;color:#57534e;">{leg}<br/><span style="font-size:0.95em;">{tag}</span></p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    try:
        _send_message(settings, to_addr.strip(), subj, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send pickup instructions email: %s", e)
        return False


def pickup_email_logo_url(settings: Settings) -> str | None:
    """Absolute URL to the SPA-hosted logo for HTML email (empty FRONTEND_PUBLIC_URL → no image)."""
    base = (settings.frontend_public_url or "").strip().rstrip("/")
    if not base:
        return None
    path = EMAIL_PUBLIC_LOGO_PATH if EMAIL_PUBLIC_LOGO_PATH.startswith("/") else f"/{EMAIL_PUBLIC_LOGO_PATH}"
    return f"{base}{path}"


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
    deposit_amount: Decimal,
    delivery_fee: Decimal = Decimal("0"),
    pickup_fee: Decimal = Decimal("0"),
    delivery_distance_miles: Decimal | None = None,
    pickup_distance_miles: Decimal | None = None,
) -> bool:
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping quote email to %s", to_addr)
        return False
    subject = f"{LEGAL_BUSINESS_NAME} — quote for {item_title}"
    rate_s = f"{sales_tax_rate_percent:f}".rstrip("0").rstrip(".")
    del_lines_plain: list[str] = []
    del_lines_html: list[str] = []
    if delivery_fee and delivery_fee > 0:
        mi = ""
        if delivery_distance_miles is not None:
            mi = f" (~{delivery_distance_miles} mi one-way)"
        del_lines_plain.append(f"Delivery fee{mi}: {_money(delivery_fee)}")
        del_lines_html.append(
            f"<li>Delivery fee{html.escape(mi)}: {_money(delivery_fee)}</li>"
        )
    if pickup_fee and pickup_fee > 0:
        mi = ""
        if pickup_distance_miles is not None:
            mi = f" (~{pickup_distance_miles} mi one-way)"
        del_lines_plain.append(f"Pickup from site fee{mi}: {_money(pickup_fee)}")
        del_lines_html.append(
            f"<li>Pickup from site fee{html.escape(mi)}: {_money(pickup_fee)}</li>"
        )
    plain = "\n".join(
        [
            f"Quote for {item_title}",
            f"Dates: {start_date} → {end_date} ({num_days} days)",
            f"Rental subtotal: {_money(discounted_subtotal)}",
            *del_lines_plain,
            f"Sales tax ({rate_s}%): {_money(sales_tax_amount)}",
            f"Rental total (with tax): {_money(rental_total_with_tax)}",
            f"Deposit (hold): {_money(deposit_amount)}",
            "",
            "This is the amount that will have to be paid before the trailer leaves the lot.",
            *_plain_signature_lines(),
        ]
    )
    html_body = f"""\
<html><body>
<p><strong>Quote for {item_title}</strong></p>
<p>Dates: {start_date} → {end_date} ({num_days} days)</p>
<ul>
<li>Rental subtotal: {_money(discounted_subtotal)}</li>
{"".join(del_lines_html)}
<li>Sales tax ({html.escape(rate_s)}%): {_money(sales_tax_amount)}</li>
<li>Rental total (with tax): {_money(rental_total_with_tax)}</li>
<li>Deposit (hold): {_money(deposit_amount)}</li>
</ul>
<p>This is the amount that will have to be paid before the trailer leaves the lot.</p>
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send quote email: %s", e)
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
                f'<a href="{esc_h}"{NO_TRACK_A_ATTR} style="color:#1d4ed8;font-weight:600">{esc_t}</a></td>'
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
        pay_follow_html = f'<p class="muted" style="font-size:0.9em">Reference: <a href="{html.escape(coll_u, quote=True)}"{NO_TRACK_A_ATTR}>{html.escape(coll_u)}</a></p>'
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
            pay_follow_html = f'<p><strong>Payment / next steps</strong><br/><a href="{html.escape(coll_u, quote=True)}"{NO_TRACK_A_ATTR}>Open link</a></p>'

    stripe_footer = ""
    if pp == "card" and (rent_u or dep_u):
        stripe_footer = " You may complete Stripe checkouts in any order unless we tell you otherwise."
    closing = (
        "Equipment is not released until every required step is complete "
        "(signed agreement, payment, and deposit as applicable)."
        + stripe_footer
    )

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
            closing,
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
<p style="font-size:0.95em">Use the checklist above (and any payment details below). Your booking is <strong>not confirmed</strong> until every step is done.</p>
{pay_follow_html}
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send approval email: %s", e)
        return False


def _rental_start_date_long(start_date: str) -> str:
    try:
        d = date.fromisoformat(str(start_date)[:10])
        return d.strftime("%A, %B %d, %Y")
    except ValueError:
        return str(start_date)


def _fulfillment_next_steps_plain_html(
    *,
    start_date: str,
    delivery_requested: bool,
    pickup_from_site_requested: bool,
    delivery_address: str | None,
) -> tuple[list[str], str]:
    """Paragraphs for how the customer gets / returns equipment (plain lines + one HTML block)."""
    esc_coord = html.escape(RENTAL_COORDINATION_EMAIL)
    addr_clean = (delivery_address or "").strip()
    esc_addr = html.escape(addr_clean) if addr_clean else None
    start_long = _rental_start_date_long(start_date)
    esc_start = html.escape(start_long)
    esc_fac = html.escape(PICKUP_FACILITY_ADDRESS)
    esc_time = html.escape(PICKUP_STANDARD_TIME_LABEL)

    plain_chunks: list[str] = []
    html_chunks: list[str] = []

    if delivery_requested:
        loc = f" Address on file: {addr_clean}" if addr_clean else ""
        plain_chunks.extend([
            "DELIVERY",
            f"We will deliver the equipment to your job site for the rental start ({start_long}).{loc}",
            f"To coordinate timing or site access, email {RENTAL_COORDINATION_EMAIL} with your name, the equipment reserved, and your rental dates.",
            "",
        ])
        html_chunks.append(
            "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;color:#1e4d3a;\">Delivery</h2>"
            "<p style=\"margin:0 0 10px;\">We will <strong>deliver</strong> the equipment to your job site for the rental start "
            f"(<strong>{esc_start}</strong>)."
            + (f" Address on file: <strong>{esc_addr}</strong>." if esc_addr else "")
            + "</p>"
            f'<p style="margin:0 0 10px;">To coordinate timing or site access, email <a href="mailto:{esc_coord}">{esc_coord}</a> '
            "with your name, the equipment reserved, and your rental dates.</p>"
        )
    else:
        plain_chunks.extend([
            "CUSTOMER PICKUP (FACILITY)",
            f"Pickup location: {PICKUP_FACILITY_ADDRESS}",
            "",
            "Scheduled pickup",
            f"Standard pickup is {PICKUP_STANDARD_TIME_LABEL} on {start_long} — the first day of your rental period. "
            "Please arrive on time so we can complete your paperwork and equipment walk-through.",
            "",
            "Alternate pickup time",
            f"If you need a different pickup time, email {RENTAL_COORDINATION_EMAIL} with your name, the equipment reserved, and your rental dates.",
            "",
        ])
        html_chunks.append(
            "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;color:#1e4d3a;\">Customer pickup (facility)</h2>"
            f"<p style=\"margin:0 0 6px;\"><strong>{esc_fac}</strong></p>"
            "<h3 style=\"margin:14px 0 6px;font-size:13px;font-weight:600;color:#334155;\">Scheduled pickup</h3>"
            f"<p style=\"margin:0 0 10px;\">Standard pickup is <strong>{esc_time}</strong> on <strong>{esc_start}</strong> — "
            "the first day of your rental period. Please arrive on time so we can complete your paperwork and equipment walk-through.</p>"
            "<h3 style=\"margin:14px 0 6px;font-size:13px;font-weight:600;color:#334155;\">Alternate pickup time</h3>"
            f'<p style="margin:0 0 10px;">Email <a href="mailto:{esc_coord}">{esc_coord}</a> with your name, the equipment reserved, and your rental dates.</p>'
        )

    if pickup_from_site_requested:
        loc = f" Address on file: {addr_clean}" if addr_clean else ""
        plain_chunks.extend([
            "END OF RENTAL — PICKUP FROM YOUR SITE",
            "We will pick up the equipment from your job site after the rental period."
            f"{loc} Please have the equipment accessible.",
            f"Email {RENTAL_COORDINATION_EMAIL} to coordinate the pickup window.",
            "",
        ])
        html_chunks.append(
            "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;color:#1e4d3a;\">End of rental — pickup from your site</h2>"
            "<p style=\"margin:0 0 10px;\">We will <strong>pick up</strong> the equipment from your job site after the rental period."
            + (f" Address on file: <strong>{esc_addr}</strong>." if esc_addr else "")
            + " Please have the equipment accessible.</p>"
            f'<p style="margin:0 0 10px;">Email <a href="mailto:{esc_coord}">{esc_coord}</a> to coordinate the pickup window.</p>'
        )

    return plain_chunks, "".join(html_chunks)


def send_customer_booking_fully_complete_email(
    settings: Settings,
    *,
    to_addr: str,
    item_title: str,
    start_date: str,
    end_date: str,
    rental_total_with_tax: Decimal | None,
    deposit_amount: Decimal | None,
    delivery_requested: bool = False,
    pickup_from_site_requested: bool = False,
    delivery_address: str | None = None,
    greeting_name: str | None = None,
) -> bool:
    """
    One customer email after the rental agreement is signed and Stripe rental (and deposit, if any) are satisfied.
    Confirms the booking is complete and includes delivery / pickup next steps.
    """
    if not smtp_configured(settings):
        log.info("SMTP not configured; skipping booking-complete email to %s", to_addr)
        return False
    subject = f"{LEGAL_BUSINESS_NAME} — booking confirmed: your next steps"
    base = html.escape((settings.frontend_public_url or "").strip().rstrip("/") or "")
    my_rentals_line = ""
    my_rentals_html = ""
    if base:
        mr = f"{base}/my-rentals"
        my_rentals_line = f"\nBooking status: {mr}\n"
        my_rentals_html = (
            f'<p class="muted" style="font-size:0.95em">'
            f'<a href="{html.escape(mr, quote=True)}"{NO_TRACK_A_ATTR}>My rentals</a>'
            f" — sign in with the same email to view this booking.</p>"
        )
    safe_title = html.escape(item_title)
    amt_lines: list[str] = []
    amt_html: list[str] = []
    if rental_total_with_tax is not None:
        amt_lines.append(f"Rental total paid (with tax): {_money(rental_total_with_tax)}")
        amt_html.append(f"<li>Rental total (with tax): {_money(rental_total_with_tax)}</li>")
    dep_dec: Decimal | None = None
    if deposit_amount is not None:
        try:
            dep_dec = Decimal(str(deposit_amount))
        except Exception:
            dep_dec = None
    if dep_dec is not None and dep_dec > 0:
        amt_lines.append(f"Security deposit (hold): {_money(dep_dec)}")
        amt_html.append(f"<li>Security deposit (hold): {_money(dep_dec)}</li>")

    greet = (greeting_name or "").strip()
    salutation_plain = f"Dear {greet}," if greet else "Hello,"
    salutation_html = html.escape(salutation_plain)

    plain_fulfill, fulfill_html = _fulfillment_next_steps_plain_html(
        start_date=start_date,
        delivery_requested=delivery_requested,
        pickup_from_site_requested=pickup_from_site_requested,
        delivery_address=delivery_address,
    )

    plain = "\n".join(
        [
            salutation_plain,
            "",
            "Your booking is confirmed.",
            "",
            "All required steps are complete: your rental agreement is signed and your rental payment (and security deposit, if applicable) have been submitted successfully through Stripe.",
            "You do not need to take further action for paperwork or payment.",
            "",
            f"Item: {item_title}",
            f"Dates: {start_date} → {end_date}",
            *amt_lines,
            "",
            "— NEXT STEPS —",
            *plain_fulfill,
            my_rentals_line.rstrip(),
            *_plain_signature_lines(),
        ]
    )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#0f172a">
<p><strong>Booking confirmed</strong></p>
<p style="margin:0 0 8px;">{salutation_html}</p>
<p style="margin:0 0 12px;">Your booking is <strong>confirmed</strong>.</p>
<p style="margin:0 0 12px;">All required steps are complete: your <strong>rental agreement</strong> is signed and your <strong>rental payment</strong> (and <strong>security deposit</strong>, if applicable) have been submitted successfully through Stripe.</p>
<p style="margin:0 0 18px;">You do not need to take further action for paperwork or payment.</p>
<p><strong>{safe_title}</strong><br/>
{html.escape(start_date)} → {html.escape(end_date)}</p>
<ul style="margin:8px 0 16px;">
{"".join(amt_html)}
</ul>
<p style="margin:16px 0 8px;font-weight:700;">Next steps</p>
{fulfill_html}
{my_rentals_html}
{_email_signature_html()}
</body></html>"""
    try:
        _send_message(settings, to_addr, subject, plain, html_body)
        return True
    except Exception as e:
        log.warning("Failed to send booking-complete email: %s", e)
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
            f'<p><strong>1) Rental balance</strong> (rental total with tax)</p>'
            f'<p><a href="{esc_r}"{NO_TRACK_A_ATTR}>Open rental payment (Stripe)</a></p>'
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
            f'<p><strong>2) Security deposit</strong> (refundable per agreement)</p>'
            f'<p><a href="{esc_d}"{NO_TRACK_A_ATTR}>Open deposit payment (Stripe)</a></p>'
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
