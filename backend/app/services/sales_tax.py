"""
Live sales tax rate lookup for quotes and bookings (no caching).

Configure either:
- SALES_TAX_RATE_URL: HTTPS GET template with {zip} or {ZIP}, or a URL that accepts ?postal_code=
  Response JSON must include one of: rate_percent, combined_rate_percent, total_rate_percent,
  sales_tax_percent (all as percent e.g. 8.475), or rate (decimal 0.08475 or percent).
- SALES_TAX_FALLBACK_PERCENT: used when URL is unset (dev/tests; document for production).

SALES_TAX_DEFAULT_POSTAL_CODE: used for quote when tax_postal_code is omitted (and required when URL is set).
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


def normalize_postal_code(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    m = _ZIP_RE.search(s)
    if m:
        return m.group(1)
    if len(s) >= 5 and s[:5].isdigit():
        return s[:5]
    return None


def extract_zip_from_address(address: str) -> str | None:
    return normalize_postal_code(address)


def resolve_postal_for_tax(
    *,
    explicit_zip: str | None,
    customer_address: str | None,
    default_zip: str,
) -> str:
    z = normalize_postal_code(explicit_zip)
    if z:
        return z
    z = extract_zip_from_address(customer_address or "")
    if z:
        return z
    z = normalize_postal_code(default_zip)
    if z:
        return z
    raise ValueError(
        "A ZIP code is required for sales tax. Pass tax_postal_code on the quote, include ZIP in "
        "your address when booking, or set SALES_TAX_DEFAULT_POSTAL_CODE on the API."
    )


def _parse_rate_percent_from_json(data: dict[str, Any]) -> Decimal:
    for key in ("rate_percent", "combined_rate_percent", "total_rate_percent", "sales_tax_percent"):
        if key in data and data[key] is not None:
            return Decimal(str(data[key]))
    if "rate" in data and data["rate"] is not None:
        r = Decimal(str(data["rate"]))
        return r * Decimal("100") if r <= Decimal("1") else r
    raise ValueError(
        "Tax API JSON must include rate_percent, combined_rate_percent, or rate (decimal or percent)"
    )


def _build_tax_url(url_template: str, zip_code: str) -> str:
    if "{zip}" in url_template or "{ZIP}" in url_template:
        return url_template.replace("{zip}", zip_code).replace("{ZIP}", zip_code)
    sep = "&" if "?" in url_template else "?"
    return f"{url_template}{sep}postal_code={quote(zip_code)}"


def fetch_rate_from_government_url(url_template: str, zip_code: str, *, timeout_sec: float) -> Decimal:
    """Single GET; no caching. Raises on HTTP or parse errors."""
    url = _build_tax_url(url_template, zip_code)
    with httpx.Client(timeout=timeout_sec) as client:
        res = client.get(url, headers={"Accept": "application/json"})
        res.raise_for_status()
        try:
            data = res.json()
        except json.JSONDecodeError as e:
            raise ValueError("Sales tax response was not valid JSON") from e
    if not isinstance(data, dict):
        raise ValueError("Tax API must return a JSON object")
    return _parse_rate_percent_from_json(data)


def lookup_sales_tax_rate_percent(
    settings: Settings,
    *,
    postal_code: str,
) -> tuple[Decimal, str]:
    """
    Returns (rate_percent, source_description). Always a fresh lookup when URL is configured.
    If the live URL fails (HTTP error, non-JSON, bad shape) but SALES_TAX_FALLBACK_PERCENT is set,
    uses the fallback and logs a warning (common when SALES_TAX_RATE_URL is exported in the shell
    but points at HTML or a dead endpoint while .env comments it out).
    """
    url = (settings.sales_tax_rate_url or "").strip()
    fb = (settings.sales_tax_fallback_percent or "").strip()

    if url:
        try:
            rate = fetch_rate_from_government_url(
                url,
                postal_code,
                timeout_sec=float(settings.sales_tax_http_timeout_sec),
            )
            return rate, f"GET {url.split('?')[0]} (postal_code={postal_code})"
        except (httpx.HTTPError, ValueError) as e:
            if fb:
                log.warning(
                    "Sales tax live URL failed (%s: %s); using SALES_TAX_FALLBACK_PERCENT",
                    type(e).__name__,
                    e,
                )
                return Decimal(fb), (
                    f"SALES_TAX_FALLBACK_PERCENT (live lookup failed: {type(e).__name__})"
                )
            raise

    if fb:
        return Decimal(fb), "SALES_TAX_FALLBACK_PERCENT (configure SALES_TAX_RATE_URL for live lookup)"

    raise ValueError(
        "Sales tax is not configured. Set SALES_TAX_RATE_URL for a government JSON endpoint "
        "or SALES_TAX_FALLBACK_PERCENT for development."
    )


def compute_sales_tax_amount(taxable_rental_subtotal: Decimal, rate_percent: Decimal) -> Decimal:
    """Tax on rental only; deposit is excluded."""
    if taxable_rental_subtotal < 0 or rate_percent < 0:
        raise ValueError("invalid amounts")
    raw = taxable_rental_subtotal * (rate_percent / Decimal("100"))
    return raw.quantize(Decimal("0.01"))
