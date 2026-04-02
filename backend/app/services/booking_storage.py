"""Persist booking uploads: local filesystem (dev) or Supabase Storage (production)."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from supabase import Client

from app.config import Settings, get_settings
from app.services.booking_documents import BOOKING_DOCUMENTS_BUCKET


def _supabase_upload(client: Client, object_path: str, data: bytes, content_type: str) -> None:
    client.storage.from_(BOOKING_DOCUMENTS_BUCKET).upload(
        object_path,
        data,
        file_options={"content-type": content_type},
    )


def _supabase_signed_url(client: Client, object_path: str, expires_in: int = 3600) -> str | None:
    try:
        res = client.storage.from_(BOOKING_DOCUMENTS_BUCKET).create_signed_url(
            object_path, expires_in
        )
    except Exception:
        return None
    if isinstance(res, dict):
        return res.get("signedURL") or res.get("signed_url")
    if isinstance(res, str):
        return res
    su = getattr(res, "signed_url", None) or getattr(res, "signedURL", None)
    return str(su) if su else None


def save_booking_document(
    settings: Settings,
    client: Client,
    object_path: str,
    data: bytes,
    content_type: str,
) -> None:
    if settings.booking_documents_storage == "local":
        root = Path(settings.booking_documents_local_dir)
        dest = (root / object_path).resolve()
        root_resolved = root.resolve()
        if not str(dest).startswith(str(root_resolved)):
            raise ValueError("Invalid storage path")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return
    _supabase_upload(client, object_path, data, content_type)


def admin_document_view_urls(settings: Settings, client: Client, row: dict) -> tuple[str | None, str | None]:
    """URLs for admin to open documents (browser-friendly)."""
    rid = row["id"]
    dl_p = row.get("drivers_license_path")
    lp_p = row.get("license_plate_path")
    base = settings.api_public_url.rstrip("/")
    if settings.booking_documents_storage == "local":
        return (
            f"{base}/admin/booking-requests/{rid}/files/drivers-license" if dl_p else None,
            f"{base}/admin/booking-requests/{rid}/files/license-plate" if lp_p else None,
        )
    return (
        _supabase_signed_url(client, dl_p) if dl_p else None,
        _supabase_signed_url(client, lp_p) if lp_p else None,
    )


def _safe_local_file(settings: Settings, relative_path: str) -> Path:
    root = Path(settings.booking_documents_local_dir).resolve()
    p = (root / relative_path.replace("\\", "/")).resolve()
    if not str(p).startswith(str(root)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")
    return p


def admin_booking_file_response(
    client: Client,
    request_id: str,
    file_key: str,
) -> FileResponse | RedirectResponse:
    settings = get_settings()
    if file_key == "drivers-license":
        col = "drivers_license_path"
    elif file_key == "license-plate":
        col = "license_plate_path"
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown file")

    res = (
        client.table("booking_requests")
        .select(col)
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    rel = rows[0].get(col)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if settings.booking_documents_storage == "local":
        fs_path = _safe_local_file(settings, rel)
        if not fs_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")
        media, _ = mimetypes.guess_type(fs_path.name)
        return FileResponse(
            fs_path,
            media_type=media or "application/octet-stream",
            filename=fs_path.name,
        )

    url = _supabase_signed_url(client, rel)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not sign storage URL. Check Supabase Storage bucket configuration.",
        )
    return RedirectResponse(url, status_code=307)
