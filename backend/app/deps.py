from collections.abc import Generator
from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, Query, status
from jwt.exceptions import PyJWKClientConnectionError
from supabase import Client

from app.config import Settings, get_settings
from app.db import get_supabase
from app.services.auth0_jwt import verify_auth0_access_token


def get_supabase_client() -> Generator[Client, None, None]:
    yield get_supabase()


def _csv_lower_set(raw: str) -> set[str]:
    return {x.strip().lower() for x in (raw or "").split(",") if x.strip()}


def _csv_exact_set(raw: str) -> set[str]:
    """Comma-separated values compared exactly (for Auth0 `sub`)."""
    return {x.strip() for x in (raw or "").split(",") if x.strip()}


def _claim_string_values(value: object) -> set[str]:
    if isinstance(value, str):
        return {value.strip().lower()} if value.strip() else set()
    if isinstance(value, list):
        return {str(x).strip().lower() for x in value if x is not None and str(x).strip()}
    return set()


def _emails_from_claims(claims: dict) -> set[str]:
    """Top-level email plus any namespaced * /email claim (common Auth0 Action pattern)."""
    out: set[str] = set()
    em = claims.get("email")
    if isinstance(em, str) and em.strip():
        out.add(em.strip().lower())
    for k, v in claims.items():
        if isinstance(k, str) and k.endswith("/email") and isinstance(v, str) and v.strip():
            out.add(v.strip().lower())
    return out


def _strings_from_role_list(items: list) -> set[str]:
    out: set[str] = set()
    for r in items:
        if isinstance(r, dict):
            n = r.get("name") or r.get("role_name") or r.get("id")
            if n is not None and str(n).strip():
                out.add(str(n).strip().lower())
        elif r is not None and str(r).strip():
            out.add(str(r).strip().lower())
    return out


def _role_strings_from_claims(claims: dict) -> set[str]:
    """permissions, roles, optional explicit claim, plus any * /roles namespaced claim."""
    out: set[str] = set()
    perms = claims.get("permissions")
    if isinstance(perms, list):
        out |= {str(p).lower() for p in perms}
    roles = claims.get("roles")
    if isinstance(roles, list):
        out |= _strings_from_role_list(roles)
    for k, v in claims.items():
        if isinstance(k, str) and k.endswith("/roles") and isinstance(v, list):
            out |= _strings_from_role_list(v)
        elif isinstance(k, str) and k.endswith("/roles"):
            out |= _claim_string_values(v)
    return out


def _auth0_claims_allow_admin(claims: dict, settings: Settings) -> bool:
    subs_want = _csv_exact_set(settings.auth0_admin_subs)
    if subs_want:
        sub = claims.get("sub")
        if isinstance(sub, str) and sub in subs_want:
            return True

    emails_want = _csv_lower_set(settings.auth0_admin_emails)
    if emails_want and emails_want & _emails_from_claims(claims):
        return True

    roles_want = _csv_lower_set(settings.auth0_admin_roles)
    if roles_want:
        if roles_want & _role_strings_from_claims(claims):
            return True
        ck = (settings.auth0_admin_roles_claim or "").strip()
        if ck:
            extra = _claim_string_values(claims.get(ck))
            if roles_want & extra:
                return True

    return False


def require_admin(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    admin_token: str | None = Query(None, description="Stub token for opening file links in a new tab"),
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """
    Allow admin access if X-Admin-Token or admin_token query matches ADMIN_STUB_TOKEN,
    or if Authorization Bearer is a valid Auth0 access token for this API and the user
    is allowed by AUTH0_ADMIN_SUBS / AUTH0_ADMIN_EMAILS / AUTH0_ADMIN_ROLES / AUTH0_ADMIN_ROLES_CLAIM.
    """
    settings = get_settings()
    stub = x_admin_token or admin_token
    if stub and stub == settings.admin_stub_token:
        return

    domain = (settings.auth0_domain or "").strip()
    audience = (settings.auth0_audience or "").strip()
    if (
        domain
        and audience
        and authorization
        and authorization.lower().startswith("bearer ")
    ):
        raw = authorization[7:].strip()
        if raw:
            try:
                claims = verify_auth0_access_token(raw, domain=domain, audience=audience)
            except PyJWKClientConnectionError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Cannot reach Auth0 to verify sign-in (JWKS). "
                        "Allow outbound HTTPS from this API to your AUTH0_DOMAIN and check the domain value."
                    ),
                ) from e
            except pyjwt.PyJWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                ) from None
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Auth0 configuration error",
                ) from None
            allowed = _auth0_claims_allow_admin(claims, settings)
            if allowed:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as admin",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing admin token",
    )


def customer_jwt_claims(
    authorization: Annotated[str | None, Header()] = None,
) -> dict | None:
    """
    When AUTH0_DOMAIN and AUTH0_AUDIENCE are set, require a valid Bearer access token.
    When either is unset, customer JWT auth is disabled (anonymous quote/booking allowed).
    """
    settings = get_settings()
    domain = (settings.auth0_domain or "").strip()
    audience = (settings.auth0_audience or "").strip()
    if not domain or not audience:
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )
    try:
        return verify_auth0_access_token(token, domain=domain, audience=audience)
    except PyJWKClientConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cannot reach Auth0 to verify sign-in (JWKS). "
                "Allow outbound HTTPS from this API to your AUTH0_DOMAIN and check the domain value."
            ),
        ) from e
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 configuration error",
        ) from None


def require_customer_jwt(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """
    For customer-account routes (my bookings, contact prefill). Requires Auth0 env + Bearer token.
    Returns decoded JWT claims. Raises 501 when customer Auth0 is not configured on the API.
    """
    settings = get_settings()
    domain = (settings.auth0_domain or "").strip()
    audience = (settings.auth0_audience or "").strip()
    if not domain or not audience:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Customer account features require AUTH0_DOMAIN and AUTH0_AUDIENCE on the API.",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )
    try:
        return verify_auth0_access_token(token, domain=domain, audience=audience)
    except PyJWKClientConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cannot reach Auth0 to verify sign-in (JWKS). "
                "Allow outbound HTTPS from this API to your AUTH0_DOMAIN and check the domain value."
            ),
        ) from e
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 configuration error",
        ) from None
