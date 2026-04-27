"""Transactional email HTML must opt out of ESP link rewriting (e.g. SMTP2Go click tracking)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.quote_email import send_booking_approved_email


def test_approval_email_includes_no_track_on_action_links() -> None:
    settings = MagicMock()
    settings.smtp_host = "smtp.example.com"
    settings.smtp_from = "ops@example.com"
    settings.smtp_user = ""
    settings.smtp_password = ""
    settings.smtp_use_tls = True
    with patch("app.services.quote_email._send_message") as send:
        ok = send_booking_approved_email(
            settings,
            to_addr="renter@example.com",
            item_title="Trailer",
            start_date="2026-04-01",
            end_date="2026-04-03",
            rental_total_with_tax=Decimal("100.00"),
            deposit_amount=Decimal("50.00"),
            payment_collection_url=None,
            signing_url="https://app.example.com/booking-actions/rawtok/sign",
            rental_checkout_url="https://checkout.stripe.com/c/pay/cs_test_a",
            deposit_checkout_url="https://checkout.stripe.com/c/pay/cs_test_b",
            payment_path="card",
        )
    assert ok is True
    assert send.called
    _s, _to, _subj, _plain, html = send.call_args[0]
    assert " no-track" in html
    assert 'href="https://app.example.com/booking-actions/rawtok/sign"' in html
    assert "cs_test_a" in html and "cs_test_b" in html
