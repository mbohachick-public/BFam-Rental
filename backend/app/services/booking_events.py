"""Append-only audit rows for booking workflow (optional table until migration runs)."""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client

log = logging.getLogger(__name__)


def log_booking_event(
    client: Client,
    *,
    booking_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        client.table("booking_events").insert(
            {
                "booking_id": booking_id,
                "event_type": event_type,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001 — table may not exist yet
        log.debug("booking_events insert skipped: %s", exc)
