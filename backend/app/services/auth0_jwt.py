"""Verify Auth0-issued RS256 access tokens using JWKS."""

from __future__ import annotations

import ssl

import certifi
import jwt
from jwt import PyJWKClient

# Short-lived cache; PyJWKClient fetches JWKS on first use per process.
_jwks_clients: dict[str, PyJWKClient] = {}

# macOS / some Python installs lack a usable default CA bundle for urllib;
# PyJWKClient uses urlopen and fails with CERTIFICATE_VERIFY_FAILED without this.
_jwks_ssl = ssl.create_default_context(cafile=certifi.where())


def _normalize_domain(domain: str) -> str:
    d = (domain or "").strip().rstrip("/")
    if d.startswith("https://"):
        d = d[len("https://") :]
    if d.startswith("http://"):
        d = d[len("http://") :]
    return d


def issuer_for_domain(domain: str) -> str:
    d = _normalize_domain(domain)
    return f"https://{d}/"


def jwks_url_for_domain(domain: str) -> str:
    return issuer_for_domain(domain) + ".well-known/jwks.json"


def verify_auth0_access_token(token: str, *, domain: str, audience: str) -> dict:
    """
    Decode and validate an access token. Raises jwt.PyJWTError subclasses on failure.
    """
    d = _normalize_domain(domain)
    if not d or not (audience or "").strip():
        raise ValueError("auth0 domain and audience are required")
    aud = audience.strip()
    # Token `aud` may differ from env by trailing slash; always allow both variants.
    base_aud = aud.rstrip("/")
    aud_candidates = tuple(dict.fromkeys([aud, base_aud, f"{base_aud}/"] if base_aud else [aud]))
    iss = issuer_for_domain(d)
    iss_candidates = tuple(dict.fromkeys([iss, iss.rstrip("/")]))
    jwks_url = jwks_url_for_domain(d)
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(jwks_url, ssl_context=_jwks_ssl)
    jwks_client = _jwks_clients[jwks_url]
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=aud_candidates,
        issuer=iss_candidates,
        leeway=60,
    )
