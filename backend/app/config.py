from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    admin_stub_token: str = "dev-admin-change-me"
    # booking uploads: "supabase" = Storage bucket booking-documents (default); "local" = folder on disk
    booking_documents_storage: str = "supabase"
    booking_documents_local_dir: str = "data/booking-documents"
    # catalog item photos: public bucket item-images (default), or local for dev without Storage
    item_images_storage: str = "supabase"
    item_images_local_dir: str = "data/item-images"
    # Used in JSON links for local file routes (admin opens in new tab with ?admin_token=)
    api_public_url: str = "http://127.0.0.1:8000"
    # Optional SMTP — when set, quote and booking confirmation emails are sent to the customer.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # Optional Auth0: when both are set, POST /booking-requests and /booking-requests/quote require a valid Bearer access token (audience = API identifier).
    auth0_domain: str = ""
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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
