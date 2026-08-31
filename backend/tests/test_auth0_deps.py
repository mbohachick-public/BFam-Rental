"""Unit checks for customer JWT dependency (no network)."""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.deps import customer_jwt_claims, optional_customer_jwt_claims


def test_customer_jwt_skipped_when_auth0_not_configured():
    s = MagicMock()
    s.auth0_domain = ""
    s.auth0_audience = ""
    with patch("app.deps.get_settings", return_value=s):
        assert customer_jwt_claims(authorization=None) is None


def test_customer_jwt_requires_bearer_when_configured():
    s = MagicMock()
    s.auth0_domain = "tenant.auth0.com"
    s.auth0_audience = "https://api.example"
    with patch("app.deps.get_settings", return_value=s):
        with pytest.raises(HTTPException) as exc:
            customer_jwt_claims(authorization=None)
        assert exc.value.status_code == 401
        assert "Sign in" in (exc.value.detail or "")


def test_optional_customer_jwt_allows_anonymous_when_configured():
    s = MagicMock()
    s.auth0_domain = "tenant.auth0.com"
    s.auth0_audience = "https://api.example"
    with patch("app.deps.get_settings", return_value=s):
        assert optional_customer_jwt_claims(authorization=None) is None
        assert optional_customer_jwt_claims(authorization="Bearer ") is None


def test_optional_customer_jwt_rejects_invalid_bearer_when_configured():
    s = MagicMock()
    s.auth0_domain = "tenant.auth0.com"
    s.auth0_audience = "https://api.example"
    s.auth0_domain_aliases = ""
    with (
        patch("app.deps.get_settings", return_value=s),
        patch(
            "app.deps.verify_auth0_access_token",
            side_effect=jwt.PyJWTError("bad"),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            optional_customer_jwt_claims(authorization="Bearer not-a-jwt")
        assert exc.value.status_code == 401
