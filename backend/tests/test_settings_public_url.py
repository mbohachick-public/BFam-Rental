"""Settings normalization for browser-facing URLs (emails, Stripe redirects)."""

from __future__ import annotations

import base64
import json

from app.config import Settings


def _minimal_service_role_jwt() -> str:
    h = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    return f"{h}.{p}.sig"


def _settings(**kwargs: str) -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key=_minimal_service_role_jwt(),
        **kwargs,
    )


def test_frontend_public_url_prepends_https_for_bare_host() -> None:
    s = _settings(frontend_public_url="bohachickrentals.com")
    assert s.frontend_public_url == "https://bohachickrentals.com"


def test_frontend_public_url_preserves_explicit_http() -> None:
    s = _settings(frontend_public_url="http://localhost:5173")
    assert s.frontend_public_url == "http://localhost:5173"


def test_frontend_public_url_strips_trailing_slash() -> None:
    s = _settings(frontend_public_url="https://app.example.com/")
    assert s.frontend_public_url == "https://app.example.com"


def test_app_base_url_bare_host_gets_https() -> None:
    s = _settings(frontend_public_url="http://localhost:5173", app_base_url="pay.example.com")
    assert s.app_base_url == "https://pay.example.com"
