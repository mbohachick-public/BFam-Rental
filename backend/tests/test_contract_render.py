"""Rental agreement template content, acknowledgments, and executed PDF sections."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

import pytest

from app.branding import LEGAL_BUSINESS_NAME
from app.services.contract_pdf import build_executed_packet_pdf
from app.services.contract_render import (
    DOCUMENT_VERSION,
    EXECUTED_PACKET_ACKNOWLEDGMENTS,
    is_customer_pickup_fulfillment,
    render_damage_fee_schedule_html,
    render_rental_agreement_html,
    rental_agreement_pdf_body_lines,
)


def _booking(**overrides) -> dict:
    base = {
        "customer_first_name": "Pat",
        "customer_last_name": "Renter",
        "customer_email": "pat@example.com",
        "customer_phone": "5551112222",
        "customer_address": "1 Main St",
        "company_name": None,
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "delivery_requested": False,
        "pickup_from_site_requested": False,
        "delivery_address": None,
        "payment_method_preference": "card",
        "payment_path": "card",
        "rental_total_with_tax": "100.00",
        "deposit_amount": "50.00",
    }
    base.update(overrides)
    return base


def test_document_version_is_2026_06_05():
    assert DOCUMENT_VERSION == "2026-06-05"


def test_rental_agreement_includes_indemnification_section():
    html = render_rental_agreement_html(_booking(), "10′ dump trailer")
    assert "Indemnification and Hold Harmless" in html
    assert "defend, indemnify, and hold harmless" in html


def test_rental_agreement_includes_unattended_trailer_section():
    html = render_rental_agreement_html(_booking(), "10′ dump trailer")
    assert "Unattended Trailer and Security Responsibility" in html
    assert "Chocking wheels when detached" in html


def test_rental_agreement_insurance_requires_proof_before_customer_pickup():
    html = render_rental_agreement_html(_booking(), "10′ dump trailer")
    assert "Proof of valid automobile insurance is required before release of any trailer for customer pickup" in html
    assert "Proof of insurance may be requested" not in html


def test_executed_packet_acknowledgments_include_new_items():
    joined = " ".join(EXECUTED_PACKET_ACKNOWLEDGMENTS)
    assert "indemnify" in joined.lower()
    assert "proof of valid automobile insurance is required" in joined.lower()
    assert "securing the trailer when unattended" in joined.lower()


def test_pdf_body_lines_include_new_sections():
    lines = rental_agreement_pdf_body_lines(owner=LEGAL_BUSINESS_NAME)
    blob = "\n".join(lines)
    assert "Indemnification and Hold Harmless" in blob
    assert "Unattended Trailer and Security Responsibility" in blob
    assert "Proof of valid automobile insurance is required before release" in blob


def test_damage_fee_schedule_still_renders():
    html = render_damage_fee_schedule_html(_booking(), "12′ dump trailer")
    assert "Damage &amp; Fee Schedule Addendum" in html
    assert "Tire replacement" in html
    assert "Dump system" in html


def test_executed_packet_pdf_builds_with_new_section_lines():
    pdf_bytes = build_executed_packet_pdf(
        booking_summary={
            "Equipment": "10′ dump trailer",
            "Rental period": "2026-06-10 through 2026-06-11",
            "Fulfillment": "Customer pickup and return",
            "Pricing snapshot": "Rental total: 100.00",
            "Status": "Executed",
        },
        rental_agreement_lines=["Version: 2026-06-05", ""] + rental_agreement_pdf_body_lines(owner=LEGAL_BUSINESS_NAME),
        damage_html=render_damage_fee_schedule_html(_booking(), "10′ dump trailer"),
        acknowledgments=EXECUTED_PACKET_ACKNOWLEDGMENTS,
        next_steps=["Contact us with questions."],
        signature_block={
            "signer_name": "Pat Renter",
            "signer_email": "pat@example.com",
            "company_name": None,
            "typed_signature": "Pat Renter",
            "signed_at": "2026-06-05T12:00:00+00:00",
            "ip_address": "127.0.0.1",
        },
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_is_customer_pickup_fulfillment():
    assert is_customer_pickup_fulfillment(_booking()) is True
    assert is_customer_pickup_fulfillment(_booking(delivery_requested=True)) is False
    assert is_customer_pickup_fulfillment(_booking(pickup_from_site_requested=True)) is False
