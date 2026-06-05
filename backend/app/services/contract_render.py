"""Render immutable HTML snapshots for rental agreement + damage schedule (MVP templates)."""

from __future__ import annotations

import html
import hashlib
from decimal import Decimal
from typing import Any

from app.branding import LEGAL_BUSINESS_NAME


DOCUMENT_VERSION = "2026-06-05"

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


def is_customer_pickup_fulfillment(booking: dict[str, Any]) -> bool:
    """Renter picks up and returns the trailer (not delivery or pickup-from-site service)."""
    return not bool(booking.get("delivery_requested")) and not bool(booking.get("pickup_from_site_requested"))


def _fulfillment_lines(booking: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if is_customer_pickup_fulfillment(booking):
        lines.append("Customer pickup and return")
    if bool(booking.get("delivery_requested")):
        lines.append("Delivery to job site")
    if bool(booking.get("pickup_from_site_requested")):
        lines.append("Pickup from job site")
    return lines


def _insurance_section_html(owner: str) -> str:
    return f"""<h2>Insurance</h2>
<p>
Renter represents and agrees that they carry valid automobile insurance that covers the towing and operation of the rented equipment.
</p>
<p>
{owner} does not provide insurance coverage for the rented equipment.
</p>
<p>
Proof of valid automobile insurance is required before release of any trailer for customer pickup. {owner} may refuse rental, cancel a reservation, or withhold release of equipment if satisfactory proof of insurance is not provided.
</p>
<p>
Renter represents and agrees that the insurance information provided is accurate, valid, and in force during the rental period.
</p>
<p>
Renter agrees to notify {owner} immediately if insurance coverage is cancelled, expired, suspended, or otherwise unavailable during the rental period.
</p>
<p>
Renter acknowledges that automobile liability while towing generally follows the tow vehicle and that Renter remains responsible for safe towing, lawful operation, property damage, bodily injury, damage to the rented equipment, theft, loss, misuse, and any amounts not covered by insurance.
</p>"""


def _indemnification_section_html(owner: str) -> str:
    return f"""<h2>Indemnification and Hold Harmless</h2>
<p>
To the fullest extent permitted by law, Renter agrees to defend, indemnify, and hold harmless {owner}, its members, managers, officers, employees, agents, successors, and assigns from and against any and all claims, demands, lawsuits, liabilities, damages, losses, judgments, fines, penalties, costs, and expenses, including reasonable attorney fees, arising out of or related to:
</p>
<ul>
<li>Renter&apos;s possession, towing, loading, unloading, operation, storage, transportation, maintenance, or use of the equipment;</li>
<li>Injury to persons, including death;</li>
<li>Damage to property;</li>
<li>Cargo loss;</li>
<li>Violations of law;</li>
<li>Negligent or improper towing, loading, or operation of the equipment;</li>
<li>Any breach of this Rental Agreement by Renter.</li>
</ul>
<p>
This obligation applies whether the claim is brought by the Renter, a passenger, a third party, a governmental entity, or any other person.
</p>
<p>
This indemnification obligation shall survive the expiration or termination of the rental period.
</p>
<p>
Nothing in this provision shall require Renter to indemnify {owner} for damages caused solely by {owner}&apos;s gross negligence or willful misconduct.
</p>"""


def _unattended_trailer_section_html() -> str:
    return """<h2>Unattended Trailer and Security Responsibility</h2>
<p>
Renter shall not leave the trailer unattended unless it is properly secured against movement, theft, vandalism, and unauthorized use.
</p>
<p>
When unattended, Renter must use reasonable safeguards, including as applicable:
</p>
<ul>
<li>Parking on stable and level ground;</li>
<li>Setting the tow vehicle parking brake when attached;</li>
<li>Chocking wheels when detached or when conditions require;</li>
<li>Locking or securing the coupler when detached;</li>
<li>Keeping the trailer in a safe and lawful location;</li>
<li>Avoiding storage in areas where theft, vandalism, flooding, traffic impact, or property damage risk is elevated.</li>
</ul>
<p>
Renter remains responsible for theft, vandalism, collision, rollaway, property damage, bodily injury, fines, towing, recovery costs, impound charges, and all losses occurring while the trailer is in Renter&apos;s possession, custody, or control.
</p>"""


def _prohibited_uses_section_html() -> str:
    return """<h2>Prohibited Uses</h2>
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
</p>"""


EXECUTED_PACKET_ACKNOWLEDGMENTS: list[str] = [
    "I have reviewed and agree to the Rental Agreement, including pricing, deposit terms, and responsibilities for damage and loss.",
    "I have reviewed and acknowledge the Damage & Fee Schedule Addendum.",
    "I understand I am financially responsible for any damage, loss, misuse, or loss of use of the equipment during the rental period, including amounts exceeding the security deposit.",
    "I understand the equipment will not be released until payment and deposit requirements are satisfied and the booking is confirmed.",
    "I agree to defend, indemnify, and hold harmless Bohachick Rentals & Supply LLC as stated in this Rental Agreement.",
    "I understand proof of valid automobile insurance is required before release of any trailer for customer pickup.",
    "I understand I am responsible for securing the trailer when unattended and remain responsible for losses, theft, vandalism, rollaway, damage, injury, towing, recovery, and impound costs while the trailer is in my possession, custody, or control.",
]


def rental_agreement_pdf_body_lines(*, owner: str) -> list[str]:
    """Plain-text rental agreement body for executed PDF (matches HTML legal sections)."""
    return [
        "Insurance",
        "Renter represents and agrees that they carry valid automobile insurance that covers the towing and operation of the rented equipment.",
        f"{owner} does not provide insurance coverage for the rented equipment.",
        f"Proof of valid automobile insurance is required before release of any trailer for customer pickup. {owner} may refuse rental, cancel a reservation, or withhold release of equipment if satisfactory proof of insurance is not provided.",
        "Renter represents and agrees that the insurance information provided is accurate, valid, and in force during the rental period.",
        f"Renter agrees to notify {owner} immediately if insurance coverage is cancelled, expired, suspended, or otherwise unavailable during the rental period.",
        "Renter acknowledges that automobile liability while towing generally follows the tow vehicle and that Renter remains responsible for safe towing, lawful operation, property damage, bodily injury, damage to the rented equipment, theft, loss, misuse, and any amounts not covered by insurance.",
        "",
        "Indemnification and Hold Harmless",
        f"To the fullest extent permitted by law, Renter agrees to defend, indemnify, and hold harmless {owner}, its members, managers, officers, employees, agents, successors, and assigns from and against any and all claims, demands, lawsuits, liabilities, damages, losses, judgments, fines, penalties, costs, and expenses, including reasonable attorney fees, arising out of or related to:",
        "• Renter's possession, towing, loading, unloading, operation, storage, transportation, maintenance, or use of the equipment;",
        "• Injury to persons, including death;",
        "• Damage to property;",
        "• Cargo loss;",
        "• Violations of law;",
        "• Negligent or improper towing, loading, or operation of the equipment;",
        "• Any breach of this Rental Agreement by Renter.",
        "This obligation applies whether the claim is brought by the Renter, a passenger, a third party, a governmental entity, or any other person.",
        "This indemnification obligation shall survive the expiration or termination of the rental period.",
        f"Nothing in this provision shall require Renter to indemnify {owner} for damages caused solely by {owner}'s gross negligence or willful misconduct.",
        "",
        "Unattended Trailer and Security Responsibility",
        "Renter shall not leave the trailer unattended unless it is properly secured against movement, theft, vandalism, and unauthorized use.",
        "When unattended, Renter must use reasonable safeguards, including as applicable:",
        "• Parking on stable and level ground;",
        "• Setting the tow vehicle parking brake when attached;",
        "• Chocking wheels when detached or when conditions require;",
        "• Locking or securing the coupler when detached;",
        "• Keeping the trailer in a safe and lawful location;",
        "• Avoiding storage in areas where theft, vandalism, flooding, traffic impact, or property damage risk is elevated.",
        "Renter remains responsible for theft, vandalism, collision, rollaway, property damage, bodily injury, fines, towing, recovery costs, impound charges, and all losses occurring while the trailer is in Renter's possession, custody, or control.",
        "",
        "Prohibited Uses",
        "Renter agrees NOT to use the equipment for any of the following:",
        "• Overloading the trailer beyond its rated capacity or unevenly loading cargo",
        "• Transporting hazardous, illegal, or prohibited materials",
        "• Hauling materials that can permanently damage the trailer (including but not limited to concrete, asphalt, corrosive chemicals, or hot materials) without prior approval",
        "• Using the trailer in a reckless, unsafe, or unlawful manner",
        "• Operating the trailer while under the influence of alcohol or drugs",
        "• Allowing any unlicensed or unqualified person to tow or operate the trailer",
        "• Using the trailer for commercial purposes not disclosed at the time of booking",
        "• Subleasing, lending, or transferring the trailer to any third party",
        "• Modifying, altering, or tampering with the trailer or its components",
        "• Operating the trailer outside the intended use (including off-road misuse, stunt use, or racing)",
        "• Failing to properly secure loads, resulting in damage or safety risk",
        "• Continuing to use the trailer after noticing mechanical issues or damage",
        "Violation of any prohibited use may result in additional charges, forfeiture of the security deposit, and renter responsibility for all resulting damage, repair, and loss of use.",
    ]


def render_rental_agreement_html(booking: dict[str, Any], item_title: str) -> str:
    c = _ctx(booking, item_title)
    owner = html.escape(LEGAL_BUSINESS_NAME)
    job_site_raw = str(booking.get("delivery_address") or "").strip()
    job_site = html.escape(job_site_raw)
    delivery_requested = bool(booking.get("delivery_requested"))
    pickup_from_site_requested = bool(booking.get("pickup_from_site_requested"))
    fulfill_lines = _fulfillment_lines(booking)
    job_site_line = (
        f"<p><strong>Job site address:</strong> {job_site}</p>"
        if job_site_raw and (delivery_requested or pickup_from_site_requested)
        else ""
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
{_insurance_section_html(owner)}
{_indemnification_section_html(owner)}
{_unattended_trailer_section_html()}
{_prohibited_uses_section_html()}
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
