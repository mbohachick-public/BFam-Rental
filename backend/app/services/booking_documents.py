from __future__ import annotations

from pathlib import Path

BOOKING_DOCUMENTS_BUCKET = "booking-documents"
MAX_IMAGE_BYTES = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_BOOKING_UPLOAD_TYPES = ALLOWED_IMAGE_TYPES | frozenset({"application/pdf"})
PDF_MAGIC = b"%PDF"
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_RIFF = b"RIFF"
WEBP_WEBP = b"WEBP"


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


def normalize_booking_document_upload_content_type(content_type: str | None, label: str) -> str:
    """Image or PDF (Step 2 driver license / insurance completion uploads)."""
    ct = _normalize_content_type(content_type)
    if not ct or ct not in ALLOWED_BOOKING_UPLOAD_TYPES:
        raise ValueError(f"{label} must be JPEG, PNG, WebP, or PDF.")
    return ct


def content_type_for_storage_path(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(ext)


def validate_customer_booking_document(content_type: str | None, size: int, label: str) -> str:
    ct = _normalize_content_type(content_type)
    if not ct or ct not in ALLOWED_BOOKING_UPLOAD_TYPES:
        raise ValueError(f"{label} must be JPEG, PNG, WebP, or PDF.")
    if size <= 0:
        raise ValueError(f"{label} file is empty.")
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"{label} must be at most 10 MB.")
    return ct


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
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(content_type, ".bin")


def sniff_image_magic(data: bytes) -> str | None:
    if len(data) >= 3 and data[:3] == JPEG_MAGIC[:3]:
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == PNG_MAGIC:
        return "image/png"
    if len(data) >= 12 and data[:4] == WEBP_RIFF and data[8:12] == WEBP_WEBP:
        return "image/webp"
    return None


def sniff_booking_document_content_type(path: str, data: bytes) -> str | None:
    """Infer content type from magic bytes, then suffix."""
    magic = sniff_image_magic(data)
    if magic:
        return magic
    if len(data) >= len(PDF_MAGIC) and data[: len(PDF_MAGIC)] == PDF_MAGIC:
        return "application/pdf"
    return content_type_for_storage_path(path)
