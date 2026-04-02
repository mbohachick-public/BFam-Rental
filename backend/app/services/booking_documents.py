from __future__ import annotations

from supabase import Client

BOOKING_DOCUMENTS_BUCKET = "booking-documents"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _normalize_content_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.split(";")[0].strip().lower()


def validate_image_upload(content_type: str | None, size: int, label: str) -> str:
    ct = _normalize_content_type(content_type)
    if not ct or ct not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"{label} must be an image (JPEG, PNG, or WebP).",
        )
    if size <= 0:
        raise ValueError(f"{label} file is empty.")
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"{label} must be at most 10 MB.")
    return ct


def ext_for_content_type(content_type: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
        content_type, ".bin"
    )
