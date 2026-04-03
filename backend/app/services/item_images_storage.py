"""Catalog item images: Supabase Storage (public bucket) or local disk."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from supabase import Client

from app.config import Settings
from app.services.booking_documents import ext_for_content_type, validate_image_upload

ITEM_IMAGES_BUCKET = "item-images"
MAX_ITEM_IMAGES = 10

_ASSET_NAME_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.(jpg|png|webp)$",
    re.IGNORECASE,
)


def _safe_local_path(settings: Settings, relative: str) -> Path:
    root = Path(settings.item_images_local_dir).resolve()
    parts = [p for p in relative.replace("\\", "/").split("/") if p and p != "."]
    p = root.joinpath(*parts).resolve()
    if not str(p).startswith(str(root)):
        raise ValueError("Invalid path")
    return p


def storage_path_from_item_image_url(url: str) -> str | None:
    """Return storage-relative path `items/{item_id}/{file}` for URLs we created, else None."""
    if not url:
        return None
    parsed = urlparse(url)
    path = unquote(parsed.path or "")
    marker = f"/storage/v1/object/public/{ITEM_IMAGES_BUCKET}/"
    if marker in path:
        return path.split(marker, 1)[1].lstrip("/").split("?", 1)[0]
    if path.startswith("/items/asset-images/"):
        rest = path[len("/items/asset-images/") :].split("?", 1)[0]
        parts = rest.split("/", 1)
        if len(parts) == 2:
            return f"items/{parts[0]}/{parts[1]}"
    return None


def try_delete_item_image_for_url(settings: Settings, client: Client, url: str) -> None:
    rel = storage_path_from_item_image_url(url)
    if not rel:
        return
    if settings.item_images_storage == "local":
        try:
            p = _safe_local_path(settings, rel)
            if p.is_file():
                p.unlink()
        except (ValueError, OSError):
            return
        return
    try:
        client.storage.from_(ITEM_IMAGES_BUCKET).remove([rel])
    except Exception:
        pass


def public_url_for_object(settings: Settings, item_id: str, filename: str) -> str:
    rel = f"items/{item_id}/{filename}"
    if settings.item_images_storage == "local":
        base = settings.api_public_url.rstrip("/")
        return f"{base}/items/asset-images/{item_id}/{filename}"
    base = settings.supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{ITEM_IMAGES_BUCKET}/{rel}"


def save_item_image_bytes(
    settings: Settings,
    client: Client,
    item_id: str,
    data: bytes,
    content_type: str,
) -> str:
    ct = validate_image_upload(content_type, len(data), "Image")
    ext = ext_for_content_type(ct)
    if ext == ".bin":
        ext = ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    rel = f"items/{item_id}/{filename}"
    if settings.item_images_storage == "local":
        dest = _safe_local_path(settings, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return public_url_for_object(settings, item_id, filename)
    client.storage.from_(ITEM_IMAGES_BUCKET).upload(
        rel,
        data,
        file_options={"content-type": ct, "cache-control": "public, max-age=3600"},
    )
    return public_url_for_object(settings, item_id, filename)


def local_asset_file_path(settings: Settings, item_id: str, filename: str) -> Path | None:
    if not _ASSET_NAME_RE.match(filename):
        return None
    rel = f"items/{item_id}/{filename}"
    try:
        p = _safe_local_path(settings, rel)
    except ValueError:
        return None
    return p if p.is_file() else None
