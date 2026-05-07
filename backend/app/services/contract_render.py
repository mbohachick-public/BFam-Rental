"""Render immutable HTML snapshots for rental agreement + damage schedule (MVP templates)."""

from __future__ import annotations

import html
import hashlib
from decimal import Decimal
from typing import Any

from app.branding import LEGAL_BUSINESS_NAME


DOCUMENT_VERSION = "2026-04-16"

DamageFeeRange = dict[str, str]

# Structured matrix (future: damageType → priceRange → appliedCharge)
# Strings are displayed to customers (ranges, not fixed values).
DAMAGE_FEE_MATRIX: dict[str, DamageFeeRange] = {
    "Tires & wheels": {
        "Flat repair / plug": "$25–$75",
        "Tire replacement": "$150–$400",
        "Wheel / rim damage": "$150–$500",
    },
    "Electrical & lighting": {
        "Wiring / connector repair": "$50–$250",
        "Light replacement / repair": "$25–$150",
    },
    "Hitch / coupler": {
        "Coupler repair / replacement": "$125–$450",
        "Safety chains / hardware": "$25–$200",
        "Jack / crank damage": "$50–$250",
    },
    "Structural / frame / deck": {
        "Bent rail / weld repair": "$150–$1,200",
        "Deck board / surface repair": "$50–$600",
        "Gate / ramp damage": "$150–$900",
    },
    "Dump system (if applicable)": {
        "Hydraulic / lift damage": "$250–$2,500",
        "Battery / charger / pump": "$75–$600",
        "Hoist / hinge / scissor damage": "$250–$2,000",
    },
    "Cleanliness / misuse": {
        "Excessive debris / cleanup": "$50–$300",
        "Concrete / asphalt / contamination": "$150–$1,500",
        "Improper loading / misuse damage": "$150–$2,500",
    },
    "Loss / theft": {
        "Missing straps / accessories": "$25–$250",
        "Theft / total loss": "Up to full replacement cost",
    },
    "Time-based penalties": {
        "Late return": "Additional daily rental rate(s) until returned",
        "No-show after confirmation": "Up to rental charges incurred + admin fee",
        "Loss of use": "Daily rental rate(s) during downtime/repair caused by damage, misuse, or late return",
    },
    "Administrative fee": {
        "Processing / coordination": "$50–$100 per incident",
    },
}


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
    owner = html.escape(LEGAL_BUSINESS_NAME)
    delivery_requested = bool(booking.get("delivery_requested"))
    pickup_from_site_requested = bool(booking.get("pickup_from_site_requested"))
    job_site_raw = str(booking.get("delivery_address") or "").strip()
    job_site = html.escape(job_site_raw)
    fulfill_lines: list[str] = []
    if not delivery_requested and not pickup_from_site_requested:
        fulfill_lines.append("Customer pickup and return")
    if delivery_requested:
        fulfill_lines.append("Delivery to job site")
    if pickup_from_site_requested:
        fulfill_lines.append("Pickup from job site")
    job_site_line = (
        f"<p><strong>Job site address:</strong> {job_site}</p>" if job_site_raw and (delivery_requested or pickup_from_site_requested) else ""
    )
    fulfill = "<ul>" + "".join(f"<li><strong>{html.escape(x)}</strong></li>" for x in fulfill_lines) + "</ul>" + job_site_line
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Rental Agreement</title></head><body>
<h1>Rental Agreement</h1>
<p><strong>Version:</strong> {c["document_version"]}</p>
<p>This Rental Agreement is between {owner} (the &quot;Owner&quot;) and {c["customer_first_name"]} {c["customer_last_name"]} (the &quot;Renter&quot;).</p>
<h2>Equipment</h2>
<p><strong>Item:</strong> {c["item_title"]}</p>
<h2>Rental period</h2>
<p><strong>Rental period:</strong> {c["start_date"]} through {c["end_date"]}</p>
<h2>Fulfillment</h2>
{fulfill}
<h2>Pricing snapshot</h2>
<ul>
<li><strong>Rental total (includes tax where applicable):</strong> {c["rental_total"]}</li>
<li><strong>Security deposit (refundable hold):</strong> {c["deposit_amount"]}</li>
<li><strong>Preferred payment method (request):</strong> {c["payment_preference"]}</li>
<li><strong>Approved payment path (admin):</strong> {c["approved_payment_path"]}</li>
</ul>
<p><em>Delivery and pickup charges are estimates and may be adjusted by {owner} prior to final approval.</em></p>
<h2>Terms (summary)</h2>
<p>Renter agrees to operate the equipment lawfully, return it on time and in the same condition subject to ordinary wear, and pay for damage, misuse, late fees, cleaning, missing items, and loss of use as described in this agreement and the Damage &amp; Fee Schedule Addendum.</p>
<p>Renter acknowledges the equipment is <strong>not released</strong> until payment and deposit requirements are satisfied and the booking is confirmed by {owner}.</p>
<p>Renter acknowledges the equipment is accepted in good working condition unless otherwise noted at pickup or delivery.</p>
<h2>Insurance</h2>
<p>
Renter represents and agrees that they carry valid automobile insurance that covers the towing and operation of the rented equipment.
</p>
<p>
{owner} does not provide insurance coverage for the rented equipment.
</p>
<p>
Renter is solely responsible for any damage, loss, or liability arising from the use of the equipment, regardless of insurance coverage.
</p>
<p>
Proof of insurance may be requested prior to release of the equipment or at any time during the rental period.
</p>
<h2>Prohibited Uses</h2>
<p>Renter agrees <strong>NOT</strong> to use the equipment for any of the following:</p>
<ul>
<li>Overloading the trailer beyond its rated capacity or unevenly loading cargo</li>
<li>Transporting hazardous, illegal, or prohibited materials</li>
<li>Hauling materials that can permanently damage the trailer (including but not limited to concrete, asphalt, corrosive chemicals, or hot materials) without prior approval</li>
<li>Using the trailer in a reckless, unsafe, or unlawful manner</li>
<li>Operating the trailer while under the influence of alcohol or drugs</li>
<li>Allowing any unlicensed or unqualified person to tow or operate the trailer</li>
<li>Using the trailer for commercial purposes not disclosed at the time of booking</li>
<li>Subleasing, lending, or transferring the trailer to any third party</li>
<li>Modifying, altering, or tampering with the trailer or its components</li>
<li>Operating the trailer outside the intended use (including off-road misuse, stunt use, or racing)</li>
<li>Failing to properly secure loads, resulting in damage or safety risk</li>
<li>Continuing to use the trailer after noticing mechanical issues or damage</li>
</ul>
<p>
Violation of any prohibited use may result in additional charges, forfeiture of the security deposit, and renter responsibility for all resulting damage, repair, and loss of use.
</p>
<p><strong>Contact:</strong> {c["customer_email"]} · {c["customer_phone"]}<br/>{c["customer_address"]}</p>
<p><strong>Company (if any):</strong> {c["company_name"]}</p>
</body></html>"""


def render_damage_fee_schedule_html(booking: dict[str, Any], item_title: str) -> str:
    c = _ctx(booking, item_title)
    owner = html.escape(LEGAL_BUSINESS_NAME)
    is_dump = "dump" in str(item_title or "").lower()

    def _row(label: str, range_s: str) -> str:
        return (
            "<tr>"
            f'<td style="padding:8px 10px;border:1px solid #e7e5e4;vertical-align:top;"><strong>{html.escape(label)}</strong></td>'
            f'<td style="padding:8px 10px;border:1px solid #e7e5e4;vertical-align:top;">{html.escape(range_s)}</td>'
            "</tr>"
        )

    cat_blocks: list[str] = []
    for category, rows in DAMAGE_FEE_MATRIX.items():
        if "Dump system" in category and not is_dump:
            continue
        body_rows = "".join(_row(k, v) for k, v in rows.items())
        cat_blocks.append(
            f"<h3>{html.escape(category)}</h3>"
            '<table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:8px 0 16px;">'
            "<thead>"
            "<tr>"
            '<th align="left" style="padding:8px 10px;border:1px solid #e7e5e4;background:#fafaf9;">Type</th>'
            '<th align="left" style="padding:8px 10px;border:1px solid #e7e5e4;background:#fafaf9;">Typical range</th>'
            "</tr>"
            "</thead>"
            f"<tbody>{body_rows}</tbody>"
            "</table>"
        )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Damage Fee Schedule</title></head><body>
<h1>Damage &amp; Fee Schedule Addendum</h1>
<p><strong>Version:</strong> {c["document_version"]}</p>
<p><strong>Equipment:</strong> {c["item_title"]} · <strong>Rental period:</strong> {c["start_date"]} – {c["end_date"]}</p>
<h2>Damage &amp; Fee Schedule Addendum</h2>
<p>
Charges listed are typical ranges. Final charges are based on actual repair or replacement cost plus applicable labor and administrative fees.
</p>
<p>
The security deposit may be used to cover any damage, cleaning, or fees. If costs exceed the deposit, the renter remains responsible for the full amount.
</p>
<p>
Final charges may exceed the security deposit. Renter agrees to pay any remaining balance.
</p>

{"".join(cat_blocks)}

<p>This addendum is part of the rental agreement for the equipment listed above.</p>
</body></html>"""


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
