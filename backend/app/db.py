from supabase import Client, create_client

from app.config import get_settings


def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
