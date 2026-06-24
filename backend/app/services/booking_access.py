"""Step 2 booking access: signed email token + Auth0 sub ownership."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from supabase import Client

from app.config import Settings, get_settings


def step2_token_hash(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def issue_step2_token_fields(
    settings: Settings | None = None,
) -> tuple[dict[str, str], str]:
    """Return DB columns + raw token (show raw token only to the customer once)."""
    stg = settings or get_settings()
    days = max(1, int(stg.step2_token_ttl_days))
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    return (
        {
            "step2_token_hash": step2_token_hash(raw),
            "step2_token_expires_at": expires.isoformat(),
        },
        raw,
    )


def step2_token_valid(booking_row: dict[str, Any], raw_token: str | None) -> bool:
    raw = (raw_token or "").strip()
    if not raw:
        return False
    stored = (booking_row.get("step2_token_hash") or "").strip()
    if not stored or stored != step2_token_hash(raw):
        return False
    exp_raw = booking_row.get("step2_token_expires_at")
    if not exp_raw:
        return True
    try:
        exp = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) <= exp
    except Exception:
        return False


def assert_step2_access(
    booking_row: dict[str, Any],
    *,
    customer_claims: dict | None,
    step_token: str | None,
) -> None:
    """
    Allow Step 2 when:
    - JWT sub matches a non-empty booking customer_auth0_sub, or
    - valid step2 email token is presented (required when sub is not yet bound).
    """
    booking_sub = str(booking_row.get("customer_auth0_sub") or "").strip()
    claims_sub = ""
    if customer_claims:
        raw = customer_claims.get("sub")
        claims_sub = str(raw).strip() if raw else ""

    if claims_sub and booking_sub and claims_sub != booking_sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this booking.",
        )

    if claims_sub and booking_sub and claims_sub == booking_sub:
        return

    if step2_token_valid(booking_row, step_token):
        return

    if (step_token or "").strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this booking. Use the completion link from your email.",
        )

    settings = get_settings()
    auth_on = bool((settings.auth0_domain or "").strip() and (settings.auth0_audience or "").strip())
    if auth_on and not claims_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required, or open the completion link from your email.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized for this booking. Use the completion link from your email.",
    )


def maybe_bind_customer_sub(
    client: Client,
    booking_id: str,
    booking_row: dict[str, Any],
    customer_claims: dict | None,
) -> None:
    """Attach Auth0 sub to anonymous intake rows on first authenticated Step 2 touch."""
    if not customer_claims:
        return
    sub = str(customer_claims.get("sub") or "").strip()
    if not sub:
        return
    existing = str(booking_row.get("customer_auth0_sub") or "").strip()
    if existing:
        if existing != sub:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this booking.",
            )
        return
    client.table("booking_requests").update({"customer_auth0_sub": sub}).eq("id", booking_id).execute()
    booking_row["customer_auth0_sub"] = sub


def complete_path_with_token(booking_id: str, raw_token: str) -> str:
    from urllib.parse import quote

    return f"/booking/{booking_id}/complete?t={quote(raw_token, safe='')}"


def complete_url_with_token(settings: Settings, booking_id: str, raw_token: str) -> str:
    from urllib.parse import quote

    base = (settings.frontend_public_url or "").strip().rstrip("/")
    return f"{base}/booking/{booking_id}/complete?t={quote(raw_token, safe='')}"


def assert_payment_status_access(
    booking_row: dict[str, Any],
    *,
    customer_claims: dict | None,
    step_token: str | None,
    sign_token_valid: bool,
) -> None:
    """Thank-you page: require Step 2 token, signing token, or matching customer JWT."""
    if step2_token_valid(booking_row, step_token):
        return
    if sign_token_valid:
        return
    booking_sub = str(booking_row.get("customer_auth0_sub") or "").strip()
    claims_sub = ""
    if customer_claims:
        raw = customer_claims.get("sub")
        claims_sub = str(raw).strip() if raw else ""
    if claims_sub and booking_sub and claims_sub == booking_sub:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to view payment status for this booking.",
    )
