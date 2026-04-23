"""Delivery distance (Google Distance Matrix) and fee from admin delivery_settings."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

METERS_PER_MILE = Decimal("1609.344")


def default_delivery_settings_row() -> dict[str, Any]:
    return {
        "id": 1,
        "enabled": False,
        "origin_address": "",
        "price_per_mile": 0.0,
        "minimum_fee": 0.0,
        "free_miles": 0.0,
        "max_delivery_miles": None,
    }


def load_delivery_settings_row(client) -> dict[str, Any]:
    try:
        res = client.table("delivery_settings").select("*").eq("id", 1).limit(1).execute()
        rows = res.data or []
        if rows:
            return dict(rows[0])
    except Exception as e:
        log.warning("delivery_settings load failed: %s", e)
    return default_delivery_settings_row()


def fee_from_miles(miles: Decimal, row: dict[str, Any]) -> Decimal:
    """Billable miles after free_miles, then max(minimum, miles * rate)."""
    free = Decimal(str(row.get("free_miles") or 0))
    rate = Decimal(str(row.get("price_per_mile") or 0))
    minimum = Decimal(str(row.get("minimum_fee") or 0))
    billable = miles - free
    if billable < 0:
        billable = Decimal("0")
    raw = billable * rate
    out = raw if raw > minimum else minimum
    return out.quantize(Decimal("0.01"))


def fetch_road_distance_miles(settings: Settings, *, origin: str, destination: str) -> Decimal:
    """
    Driving distance in miles via Google Distance Matrix API.
    Requires GOOGLE_MAPS_API_KEY and non-empty origin/destination strings.
    """
    key = (settings.google_maps_api_key or "").strip()
    if not key:
        raise ValueError("Google Maps API key is not configured (GOOGLE_MAPS_API_KEY).")
    o = (origin or "").strip()
    d = (destination or "").strip()
    if not o or not d:
        raise ValueError("Origin and destination addresses are required for delivery distance.")

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": o,
        "destinations": d,
        "units": "imperial",
        "key": key,
    }
    with httpx.Client(timeout=settings.google_maps_http_timeout_sec) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    status = str(data.get("status") or "")
    if status != "OK":
        raise ValueError(
            f"Distance Matrix error: {status} ({data.get('error_message', '')})".strip()
        )

    rows = data.get("rows") or []
    if not rows:
        raise ValueError("No route rows returned.")
    elements = rows[0].get("elements") or []
    if not elements:
        raise ValueError("No route elements returned.")
    el = elements[0]
    el_status = str(el.get("status") or "")
    if el_status != "OK":
        raise ValueError(f"Route not found: {el_status}")

    dist = el.get("distance") or {}
    meters = dist.get("value")
    if meters is None:
        raise ValueError("Distance value missing in API response.")
    miles = (Decimal(str(meters)) / METERS_PER_MILE).quantize(Decimal("0.01"))
    return miles


def compute_delivery_charge(
    client,
    settings: Settings,
    *,
    item_delivery_available: bool,
    delivery_requested: bool,
    delivery_address: str | None,
) -> tuple[Decimal, Decimal | None]:
    """
    Returns (delivery_fee, road_miles or None).
    When not requested or item has no delivery, returns (0, None).
    """
    if not delivery_requested:
        return Decimal("0"), None
    if not item_delivery_available:
        raise ValueError("This item does not offer delivery.")
    addr = (delivery_address or "").strip()
    if not addr:
        raise ValueError("Delivery address is required when delivery is requested.")

    row = load_delivery_settings_row(client)
    if not bool(row.get("enabled")):
        raise ValueError("Delivery is not enabled. Contact the rental office.")

    origin = str(row.get("origin_address") or "").strip()
    if not origin:
        raise ValueError("Delivery origin is not configured (admin → Delivery settings).")

    miles = fetch_road_distance_miles(settings, origin=origin, destination=addr)
    max_m = row.get("max_delivery_miles")
    if max_m is not None:
        cap = Decimal(str(max_m))
        if miles > cap:
            raise ValueError(
                f"Delivery address is outside the maximum service distance ({cap} miles). "
                "Contact the rental office."
            )

    fee = fee_from_miles(miles, row)
    return fee, miles
