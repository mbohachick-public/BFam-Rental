from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, Query, status
from supabase import Client

from app.config import get_settings
from app.db import get_supabase


def get_supabase_client() -> Generator[Client, None, None]:
    yield get_supabase()


def require_admin_stub(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    admin_token: str | None = Query(None, description="Stub token for opening file links in a new tab"),
) -> None:
    settings = get_settings()
    token = x_admin_token or admin_token
    if not token or token != settings.admin_stub_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )
