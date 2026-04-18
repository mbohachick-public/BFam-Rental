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
    agreement_html: str,
    damage_html: str,
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
    for k, v in booking_summary.items():
        story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Normal"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Rental agreement (text extract)</b>", styles["Heading2"]))
    for line in _strip_html_to_lines(agreement_html)[:400]:
        story.append(Paragraph(xml_escape(line), styles["Normal"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Damage &amp; fee schedule (text extract)</b>", styles["Heading2"]))
    for line in _strip_html_to_lines(damage_html)[:400]:
        story.append(Paragraph(xml_escape(line), styles["Normal"]))
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
    doc.build(story)
    return buf.getvalue()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
