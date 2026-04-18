"""Render immutable HTML snapshots for rental agreement + damage schedule (MVP templates)."""

from __future__ import annotations

import html
import hashlib
from decimal import Decimal
from typing import Any


DOCUMENT_VERSION = "2026-04-16"


def _money(d: object) -> str:
    try:
        v = Decimal(str(d))
    except Exception:
        return str(d)
    return f"${v:,.2f}"


def _ctx(booking: dict[str, Any], item_title: str) -> dict[str, str]:
    fn = html.escape(str(booking.get("customer_first_name") or ""))
    ln = html.escape(str(booking.get("customer_last_name") or ""))
    em = html.escape(str(booking.get("customer_email") or ""))
    ph = html.escape(str(booking.get("customer_phone") or ""))
    addr = html.escape(str(booking.get("customer_address") or ""))
    co = html.escape(str(booking.get("company_name") or "").strip() or "—")
    start = html.escape(str(booking.get("start_date") or ""))
    end = html.escape(str(booking.get("end_date") or ""))
    deliv = html.escape(str(booking.get("delivery_address") or "").strip() or "—")
    pay_pref = html.escape(str(booking.get("payment_method_preference") or "card"))
    approved_path = html.escape(str(booking.get("payment_path") or ""))
    rental = _money(booking.get("rental_total_with_tax") or booking.get("discounted_subtotal") or "0")
    dep = _money(booking.get("deposit_amount") or "0")
    title = html.escape(item_title)
    return {
        "customer_first_name": fn,
        "customer_last_name": ln,
        "customer_email": em,
        "customer_phone": ph,
        "customer_address": addr,
        "company_name": co,
        "start_date": start,
        "end_date": end,
        "item_title": title,
        "delivery_address": deliv,
        "payment_preference": pay_pref,
        "approved_payment_path": approved_path,
        "rental_total": rental,
        "deposit_amount": dep,
        "document_version": html.escape(DOCUMENT_VERSION),
    }


def render_rental_agreement_html(booking: dict[str, Any], item_title: str) -> str:
    c = _ctx(booking, item_title)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Rental Agreement</title></head><body>
<h1>Rental Agreement</h1>
<p><strong>Version:</strong> {c["document_version"]}</p>
<p>This Rental Agreement is between BFam Rentals &amp; Supply (the &quot;Owner&quot;) and {c["customer_first_name"]} {c["customer_last_name"]} (the &quot;Renter&quot;).</p>
<h2>Equipment</h2>
<p><strong>Item:</strong> {c["item_title"]}</p>
<p><strong>Rental period:</strong> {c["start_date"]} through {c["end_date"]}</p>
<p><strong>Fulfillment:</strong> Pickup at the Owner&apos;s agreed location. <strong>Other address on file (if any):</strong> {c["delivery_address"]}</p>
<h2>Pricing snapshot</h2>
<ul>
<li><strong>Rental total (with tax where applicable):</strong> {c["rental_total"]}</li>
<li><strong>Refundable deposit (hold):</strong> {c["deposit_amount"]}</li>
<li><strong>Preferred payment method (request):</strong> {c["payment_preference"]}</li>
<li><strong>Approved payment path (admin):</strong> {c["approved_payment_path"]}</li>
</ul>
<h2>Terms (summary)</h2>
<p>Renter agrees to operate the equipment lawfully, return it on time and in the same condition subject to ordinary wear, and pay for damage, misuse, late fees, cleaning, and missing items as described in the Damage &amp; Fee Schedule Addendum.</p>
<p>Renter acknowledges the equipment is <strong>not released</strong> until payment and deposit requirements are satisfied and the booking is confirmed by BFam Rentals.</p>
<p><strong>Contact:</strong> {c["customer_email"]} · {c["customer_phone"]}<br/>{c["customer_address"]}</p>
<p><strong>Company (if any):</strong> {c["company_name"]}</p>
</body></html>"""


def render_damage_fee_schedule_html(booking: dict[str, Any], item_title: str) -> str:
    c = _ctx(booking, item_title)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Damage Fee Schedule</title></head><body>
<h1>Damage &amp; Fee Schedule Addendum</h1>
<p><strong>Version:</strong> {c["document_version"]}</p>
<p><strong>Equipment:</strong> {c["item_title"]} · <strong>Rental period:</strong> {c["start_date"]} – {c["end_date"]}</p>
<h2>Damage and loss</h2>
<p>Renter is responsible for physical damage, theft, vandalism, tire/wheel damage, hydraulic misuse, and contamination beyond ordinary wear. Charges will be based on reasonable repair or replacement cost plus administrative fees.</p>
<h2>Fees</h2>
<ul>
<li><strong>Late return:</strong> additional daily rental rates until returned.</li>
<li><strong>Cleaning / excessive debris:</strong> reasonable cleaning fee.</li>
<li><strong>No-show / cancellation after confirmation:</strong> per BFam Rentals policy.</li>
</ul>
<p>This addendum is part of the rental agreement for the equipment listed above.</p>
</body></html>"""


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
