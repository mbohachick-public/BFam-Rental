"""Build executed PDF packet (MVP: ReportLab text layout from HTML snapshots)."""

from __future__ import annotations

import hashlib
import re
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _strip_html_to_lines(html: str, max_line_chars: int = 95) -> list[str]:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > max_line_chars:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def build_executed_packet_pdf(
    *,
    booking_summary: dict[str, Any],
    rental_agreement_lines: list[str],
    damage_html: str,
    acknowledgments: list[str],
    next_steps: list[str],
    signature_block: dict[str, Any],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=inch * 0.75,
        leftMargin=inch * 0.75,
        topMargin=inch * 0.75,
        bottomMargin=inch * 0.75,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []
    story.append(Paragraph("<b>Executed rental packet</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Booking summary</b>", styles["Heading2"]))
    for k in [
        "Equipment",
        "Rental period",
        "Fulfillment",
        "Pricing snapshot",
        "Status",
    ]:
        v = booking_summary.get(k)
        if v is None:
            continue
        story.append(Paragraph(f"<b>{xml_escape(str(k))}:</b> {xml_escape(str(v))}", styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Equipment</b>", styles["Heading2"]))
    if booking_summary.get("Equipment") is not None:
        story.append(Paragraph(xml_escape(str(booking_summary.get("Equipment"))), styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Rental period</b>", styles["Heading2"]))
    if booking_summary.get("Rental period") is not None:
        story.append(Paragraph(xml_escape(str(booking_summary.get("Rental period"))), styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Fulfillment</b>", styles["Heading2"]))
    if booking_summary.get("Fulfillment") is not None:
        story.append(Paragraph(xml_escape(str(booking_summary.get("Fulfillment"))), styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Pricing snapshot</b>", styles["Heading2"]))
    if booking_summary.get("Pricing snapshot") is not None:
        story.append(Paragraph(xml_escape(str(booking_summary.get("Pricing snapshot"))), styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Rental Agreement</b>", styles["Heading2"]))
    for line in rental_agreement_lines:
        if not str(line).strip():
            story.append(Spacer(1, 8))
            continue
        story.append(Paragraph(xml_escape(str(line)), styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Damage &amp; fee schedule</b>", styles["Heading2"]))
    for line in _strip_html_to_lines(damage_html)[:250]:
        story.append(Paragraph(xml_escape(line), styles["Normal"]))
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            xml_escape(
                "Final charges may exceed the security deposit. Renter agrees to pay any remaining balance."
            ),
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Acknowledgments</b>", styles["Heading2"]))
    for a in acknowledgments:
        story.append(Paragraph(xml_escape(f"• {a}"), styles["Normal"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Electronic signature</b>", styles["Heading2"]))
    for line in [
        f"Signer: {signature_block.get('signer_name')}",
        f"Email: {signature_block.get('signer_email')}",
        f"Company: {signature_block.get('company_name') or '—'}",
        f"Typed signature: {signature_block.get('typed_signature')}",
        f"Signed at (UTC): {signature_block.get('signed_at')}",
        f"IP: {signature_block.get('ip_address') or '—'}",
    ]:
        story.append(Paragraph(xml_escape(line), styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            xml_escape(
                "By typing my name above, I agree that my electronic signature is binding and has the same legal effect as a handwritten signature."
            ),
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Next steps</b>", styles["Heading2"]))
    for s in next_steps:
        story.append(Paragraph(xml_escape(f"• {s}"), styles["Normal"]))
    doc.build(story)
    return buf.getvalue()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
