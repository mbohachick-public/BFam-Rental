import base64
import binascii
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_public_origin(v: str) -> str:
    """
    Ensure email and Stripe redirect bases are absolute URLs.
    Env dashboards often omit the scheme (e.g. bohachickrentals.com); email clients then treat
    links as relative and they break. Local dev should keep an explicit http:// URL.
    """
    v = (v or "").strip().rstrip("/")
    if not v:
        return ""
    lower = v.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return v
    if v.startswith("/"):
        return v
    return f"https://{v}"

# `app/config.py` → repository `backend/` (where `.env` with SUPABASE_* usually lives).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DOTENV = _BACKEND_DIR / ".env"


def _jwt_role_unverified(token: str) -> str | None:
    """Return JWT `role` claim without verify (Supabase keys are JWTs). None if not parseable."""
    parts = (token or "").strip().split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64 + pad)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None
    r = data.get("role")
    return str(r) if r is not None else None


def _dotenv_files() -> tuple[str, ...]:
    """
    Load env files so `uvicorn app.main:app` works when the shell cwd is `frontend/` or repo root:
    cwd `.env` first, then `backend/.env` (later wins on duplicate keys).
    """
    paths: list[str] = [".env"]
    if _BACKEND_DOTENV.is_file():
        paths.append(str(_BACKEND_DOTENV))
    return tuple(paths)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_dotenv_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # booking uploads: "supabase" = Storage bucket booking-documents (default); "local" = folder on disk
    booking_documents_storage: str = "supabase"
    booking_documents_local_dir: str = "data/booking-documents"
    # catalog item photos: public bucket item-images (default), or local for dev without Storage
    item_images_storage: str = "supabase"
    item_images_local_dir: str = "data/item-images"
    # Used in JSON links for local booking document routes (admin fetches with Bearer token).
    api_public_url: str = "http://127.0.0.1:8000"
    # Optional SMTP — when set, quote and booking confirmation emails are sent to the customer.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # Optional staff inbox for workflow mail; if empty, SMTP_USER (if email-shaped) or SMTP_FROM is used.
    admin_notification_email: str = ""
    # Optional Auth0: when both are set, POST /booking-requests and /booking-requests/quote require a valid Bearer access token (audience = API identifier).
    auth0_domain: str = ""
    # Optional: comma-separated extra Auth0 hostnames trusted for JWT iss + JWKS (e.g. default tenant
    # dev-xxx.us.auth0.com) when auth0_domain is your custom login host or during migration. Empty = only auth0_domain.
    auth0_domain_aliases: str = ""
    auth0_audience: str = ""
    # Admin via Auth0: comma-separated role names matched against JWT permissions, roles, or AUTH0_ADMIN_ROLES_CLAIM (default role name: admin).
    auth0_admin_roles: str = "admin"
    # Optional exact JWT claim key (e.g. https://your.app/roles) whose value is a string or string array.
    auth0_admin_roles_claim: str = ""
    # Optional comma-separated emails; access token must include an email claim (add via Auth0 Action if missing).
    auth0_admin_emails: str = ""
    # Optional comma-separated Auth0 user ids (JWT "sub", e.g. auth0|abc123) — works when the access token has no roles/email claims.
    auth0_admin_subs: str = ""
    # Sales tax: live GET when SALES_TAX_RATE_URL is set (substitute {zip} or {ZIP}, or ?postal_code= is appended). No caching.
    # Missouri DOR does not publish a simple public JSON rate API; use a proxy you host that reads official tables, or set fallback for dev.
    sales_tax_rate_url: str = ""
    sales_tax_fallback_percent: str = ""
    sales_tax_default_postal_code: str = ""
    sales_tax_http_timeout_sec: float = 8.0
    # Optional: set e.g. https://pay.example.com/booking/{booking_id} — filled on admin approve.
    payment_collection_url_template: str = ""
    # Customer signing links in emails: origin of the Vite app (no trailing slash).
    frontend_public_url: str = "http://localhost:5173"
    signing_token_ttl_days: int = 14
    # Executed agreement PDFs written by the API (relative to backend cwd or absolute).
    contract_packets_dir: str = "data/contract-packets"
    # Stripe Checkout (rental); webhook uses raw body + STRIPE_WEBHOOK_SECRET.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # When true, Checkout adds a second line item for deposit_amount and webhook sets deposit_secured_at on success.
    stripe_checkout_include_deposit: bool = True
    # Success/cancel redirects for Checkout (SPA origin, no trailing slash). Defaults to frontend_public_url.
    app_base_url: str = ""
    # Google Distance Matrix (server-side only) for delivery mileage when delivery is enabled.
    google_maps_api_key: str = ""
    google_maps_http_timeout_sec: float = 12.0

    @field_validator("supabase_url")
    @classmethod
    def supabase_url_shape(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return v
        parsed = urlparse(v)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https"):
            raise ValueError("SUPABASE_URL must start with https:// (or http:// for local dev).")
        if not host:
            raise ValueError(
                "SUPABASE_URL must look like https://YOUR-PROJECT-REF.supabase.co (Project Settings → API)."
            )
        if "your_project" in host or host.startswith("replace"):
            raise ValueError(
                "SUPABASE_URL is still a placeholder. Copy the real Project URL from Supabase (Project Settings → API)."
            )
        return v.rstrip("/")

    @field_validator("supabase_service_role_key")
    @classmethod
    def supabase_service_role_key_bypasses_rls(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return v
        role = _jwt_role_unverified(v)
        if role == "anon":
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY is set to the anon (public) API key. "
                "The API will hit RLS errors on inserts/updates. Use the **service_role** "
                "secret from Supabase → Project Settings → API (not the anon key)."
            )
        if role is not None and role != "service_role":
            raise ValueError(
                f"SUPABASE_SERVICE_ROLE_KEY JWT role is {role!r}; expected 'service_role' "
                "for server-side access (bypasses RLS). Copy the service_role key from "
                "Supabase → Project Settings → API."
            )
        return v

    @field_validator("booking_documents_storage")
    @classmethod
    def booking_storage_mode(cls, v: str) -> str:
        s = (v or "supabase").strip().lower()
        if s not in ("local", "supabase"):
            raise ValueError('BOOKING_DOCUMENTS_STORAGE must be "local" or "supabase".')
        return s

    @field_validator("item_images_storage")
    @classmethod
    def item_images_storage_mode(cls, v: str) -> str:
        s = (v or "supabase").strip().lower()
        if s not in ("local", "supabase"):
            raise ValueError('ITEM_IMAGES_STORAGE must be "local" or "supabase".')
        return s

    @field_validator("frontend_public_url", "app_base_url")
    @classmethod
    def public_browser_origin(cls, v: str) -> str:
        v = _normalize_public_origin(v)
        if not v:
            return ""
        if "index.html" in v.lower():
            raise ValueError(
                "FRONTEND_PUBLIC_URL and APP_BASE_URL must be the site origin only "
                "(e.g. https://www.example.com), not a path to index.html."
            )
        parsed = urlparse(v)
        path = (parsed.path or "").rstrip("/")
        if path:
            raise ValueError(
                "FRONTEND_PUBLIC_URL and APP_BASE_URL must not include a URL path "
                "(use https://www.example.com, not a subdirectory)."
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def public_app_base_url(self) -> str:
        """Origin for Stripe success/cancel URLs (customer browser)."""
        u = (self.app_base_url or self.frontend_public_url or "").strip().rstrip("/")
        return u


@lru_cache
def get_settings() -> Settings:
    return Settings()
