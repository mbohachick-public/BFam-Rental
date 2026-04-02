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
    # booking uploads: "local" = folder on disk; "supabase" = Storage bucket booking-documents
    booking_documents_storage: str = "local"
    booking_documents_local_dir: str = "data/booking-documents"
    # Used in JSON links for local file routes (admin opens in new tab with ?admin_token=)
    api_public_url: str = "http://127.0.0.1:8000"

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
        s = (v or "local").strip().lower()
        if s not in ("local", "supabase"):
            raise ValueError('BOOKING_DOCUMENTS_STORAGE must be "local" or "supabase".')
        return s

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
