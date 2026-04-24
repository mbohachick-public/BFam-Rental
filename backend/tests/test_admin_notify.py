"""Admin workflow notification emails."""

from unittest.mock import patch

from app.services.admin_notify import (
    ADMIN_EMAIL_APPROVAL_EVENT,
    ADMIN_EMAIL_CONFIRM_EVENT,
    _admin_recipient,
    booking_row_ready_for_confirm,
    try_notify_admin_approval_needed,
    try_notify_admin_confirm_needed,
)


def test_booking_row_ready_for_confirm_true():
    row = {
        "status": "approved_pending_payment",
        "rental_paid_at": "2026-04-01T00:00:00",
        "rental_payment_status": "paid",
        "deposit_amount": 0,
        "deposit_secured_at": None,
        "agreement_signed_at": "2026-04-01T00:00:00",
    }
    assert booking_row_ready_for_confirm(row) is True


def test_booking_row_ready_for_confirm_needs_deposit():
    row = {
        "status": "approved_pending_payment",
        "rental_paid_at": "2026-04-01T00:00:00",
        "rental_payment_status": "paid",
        "deposit_amount": 50.0,
        "deposit_secured_at": None,
        "agreement_signed_at": "2026-04-01T00:00:00",
    }
    assert booking_row_ready_for_confirm(row) is False


def test_admin_recipient_prefers_explicit_then_smtp_user_then_from(fake_settings):
    fake_settings.admin_notification_email = "explicit@example.com"
    fake_settings.smtp_user = "user@example.com"
    fake_settings.smtp_from = "Other <from@example.com>"
    assert _admin_recipient(fake_settings) == "explicit@example.com"

    fake_settings.admin_notification_email = ""
    assert _admin_recipient(fake_settings) == "user@example.com"

    fake_settings.smtp_user = "apikey_not_an_email"
    assert _admin_recipient(fake_settings) == "from@example.com"

    fake_settings.smtp_from = "BFam Rentals <inbox@example.org>"
    assert _admin_recipient(fake_settings) == "inbox@example.org"


def test_try_notify_approval_sends_once(fake_client, fake_settings, db_store, seed_item):
    fake_settings.smtp_host = "smtp.example.com"
    fake_settings.smtp_from = "from@example.com"
    fake_settings.admin_notification_email = "admin@example.com"
    fake_settings.frontend_public_url = "http://localhost:5173"
    item = seed_item()
    db_store["booking_requests"].append(
        {
            "id": "b1111111-1111-1111-1111-111111111111",
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "requested",
            "customer_first_name": "A",
            "customer_last_name": "B",
            "customer_email": "c@test.com",
            "drivers_license_path": "b1111111-1111-1111-1111-111111111111/dl.jpg",
            "license_plate_path": None,
            "deposit_amount": 0,
        }
    )
    with patch("app.services.admin_notify.try_send_email", return_value=True) as send:
        try_notify_admin_approval_needed(fake_client, fake_settings, "b1111111-1111-1111-1111-111111111111")
        try_notify_admin_approval_needed(fake_client, fake_settings, "b1111111-1111-1111-1111-111111111111")
    assert send.call_count == 1
    ev = [e for e in db_store.get("booking_events", []) if e.get("event_type") == ADMIN_EMAIL_APPROVAL_EVENT]
    assert len(ev) == 1


def test_try_notify_approval_uses_smtp_user_when_admin_email_unset(
    fake_client, fake_settings, db_store, seed_item
):
    fake_settings.smtp_host = "smtp.example.com"
    fake_settings.smtp_from = "noreply@example.com"
    fake_settings.smtp_user = "ops@example.com"
    fake_settings.admin_notification_email = ""
    fake_settings.frontend_public_url = "http://localhost:5173"
    item = seed_item()
    db_store["booking_requests"].append(
        {
            "id": "b3333333-3333-3333-3333-333333333333",
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "requested",
            "customer_first_name": "A",
            "customer_last_name": "B",
            "customer_email": "c@test.com",
            "drivers_license_path": "b3333333-3333-3333-3333-333333333333/dl.jpg",
            "license_plate_path": None,
            "deposit_amount": 0,
        }
    )
    with patch("app.services.admin_notify.try_send_email", return_value=True) as send:
        try_notify_admin_approval_needed(fake_client, fake_settings, "b3333333-3333-3333-3333-333333333333")
    send.assert_called_once()
    assert send.call_args.kwargs["to_addr"] == "ops@example.com"


def test_try_notify_confirm_sends_once(fake_client, fake_settings, db_store, seed_item):
    fake_settings.smtp_host = "smtp.example.com"
    fake_settings.smtp_from = "from@example.com"
    fake_settings.admin_notification_email = "admin@example.com"
    fake_settings.frontend_public_url = "http://localhost:5173"
    item = seed_item()
    db_store["booking_requests"].append(
        {
            "id": "b2222222-2222-2222-2222-222222222222",
            "item_id": item["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "status": "approved_pending_payment",
            "rental_paid_at": "2026-04-01T00:00:00",
            "rental_payment_status": "paid",
            "deposit_amount": 0,
            "deposit_secured_at": None,
            "agreement_signed_at": "2026-04-01T00:00:00",
        }
    )
    with patch("app.services.admin_notify.try_send_email", return_value=True) as send:
        try_notify_admin_confirm_needed(fake_client, fake_settings, "b2222222-2222-2222-2222-222222222222")
        try_notify_admin_confirm_needed(fake_client, fake_settings, "b2222222-2222-2222-2222-222222222222")
    assert send.call_count == 1
    ev = [e for e in db_store.get("booking_events", []) if e.get("event_type") == ADMIN_EMAIL_CONFIRM_EVENT]
    assert len(ev) == 1
