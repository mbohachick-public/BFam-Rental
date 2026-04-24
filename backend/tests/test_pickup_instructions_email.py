"""Pickup instructions email after admin confirms a customer-pickup booking."""

import uuid
from unittest.mock import patch

from app.services.pickup_instructions_email import (
    PICKUP_INSTRUCTIONS_EMAIL_EVENT,
    try_send_pickup_instructions_after_confirm,
)


def test_pickup_instructions_skips_delivery_booking(fake_client, fake_settings, seed_item):
    fake_settings.smtp_host = "smtp.example.com"
    fake_settings.smtp_from = "noreply@example.com"
    item = seed_item(title="Tow dolly")
    bid = str(uuid.uuid4())
    row = {
        "id": bid,
        "item_id": item["id"],
        "start_date": "2026-07-01",
        "delivery_requested": True,
        "customer_email": "a@test.com",
        "customer_first_name": "Alex",
    }
    with patch("app.services.pickup_instructions_email.send_pickup_confirmed_email") as send:
        try_send_pickup_instructions_after_confirm(fake_client, fake_settings, row)
    send.assert_not_called()


def test_pickup_instructions_skips_without_smtp(fake_client, fake_settings, seed_item):
    fake_settings.smtp_host = ""
    fake_settings.smtp_from = ""
    item = seed_item()
    row = {
        "id": str(uuid.uuid4()),
        "item_id": item["id"],
        "start_date": "2026-07-01",
        "delivery_requested": False,
        "customer_email": "a@test.com",
        "customer_first_name": "Alex",
    }
    with patch("app.services.pickup_instructions_email.send_pickup_confirmed_email") as send:
        try_send_pickup_instructions_after_confirm(fake_client, fake_settings, row)
    send.assert_not_called()


def test_pickup_instructions_sends_once_and_logs_event(
    fake_client, fake_settings, db_store, seed_item
):
    fake_settings.smtp_host = "smtp.example.com"
    fake_settings.smtp_from = "noreply@example.com"
    fake_settings.frontend_public_url = "https://rentals.example.com"
    item = seed_item(title="18+2 dovetail trailer")
    bid = str(uuid.uuid4())
    row = {
        "id": bid,
        "item_id": item["id"],
        "start_date": "2026-07-01",
        "delivery_requested": False,
        "customer_email": "renter@example.com",
        "customer_first_name": "Jordan",
    }
    with patch(
        "app.services.pickup_instructions_email.send_pickup_confirmed_email",
        return_value=True,
    ) as send:
        try_send_pickup_instructions_after_confirm(fake_client, fake_settings, row)
        try_send_pickup_instructions_after_confirm(fake_client, fake_settings, row)
    assert send.call_count == 1
    call_kw = send.call_args.kwargs
    assert call_kw["to_addr"] == "renter@example.com"
    assert call_kw["greeting_name"] == "Jordan"
    assert call_kw["item_title"] == "18+2 dovetail trailer"
    assert "July" in call_kw["pickup_date_long"]
    assert call_kw["logo_url"] == "https://rentals.example.com/brand-logo.png"

    ev = [
        e
        for e in db_store.get("booking_events", [])
        if e.get("booking_id") == bid and e.get("event_type") == PICKUP_INSTRUCTIONS_EMAIL_EVENT
    ]
    assert len(ev) == 1
