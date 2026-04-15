from __future__ import annotations

from pathlib import Path

BOOKING_DOCUMENTS_BUCKET = "booking-documents"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _normalize_content_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.split(";")[0].strip().lower()


def normalize_booking_image_content_type(content_type: str | None, label: str) -> str:
    """Allowed image MIME only (no size check). Used when presigning before upload."""
    ct = _normalize_content_type(content_type)
    if not ct or ct not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"{label} must be an image (JPEG, PNG, or WebP).",
        )
    return ct


def content_type_for_storage_path(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext)


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
