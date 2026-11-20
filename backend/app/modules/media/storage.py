"""Validated media storage.

Uploads arrive as base64 JSON (no multipart dependency), are checked for an
allowed type, matching file signature and size, then written with a random
name. Only the "local" backend exists today; when storage is disabled the API
answers 503 MEDIA_STORAGE_UNAVAILABLE instead of pretending to succeed.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.core.exceptions import AppException

IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}
DOCUMENT_TYPES = {**IMAGE_TYPES, "application/pdf": (".pdf", (b"%PDF-",))}


class Base64Upload(BaseModel):
    content_base64: str = Field(..., min_length=8, max_length=7_200_000)
    content_type: str = Field(..., max_length=64)

    @model_validator(mode="after")
    def _decode_check(self):
        try:
            base64.b64decode(self.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("content_base64 is not valid base64") from None
        return self


def _validate(upload: Base64Upload, allowed: dict) -> tuple[bytes, str]:
    if upload.content_type not in allowed:
        raise AppException(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Allowed types: {', '.join(sorted(allowed))}.",
            status_code=415,
        )
    raw = base64.b64decode(upload.content_base64, validate=True)
    if len(raw) > settings.MEDIA_MAX_BYTES:
        raise AppException(
            code="FILE_TOO_LARGE",
            message=f"Files must be {settings.MEDIA_MAX_BYTES // (1024 * 1024)} MB or smaller.",
            status_code=413,
        )
    ext, magics = allowed[upload.content_type]
    if not any(raw.startswith(m) for m in magics) or (
        upload.content_type == "image/webp" and raw[8:12] != b"WEBP"
    ):
        raise AppException(
            code="FILE_CONTENT_MISMATCH",
            message="File content does not match its declared type.",
            status_code=422,
        )
    return raw, ext


def storage_available() -> bool:
    return (settings.MEDIA_STORAGE or "").lower() == "local"


PRIVATE_PREFIX = "private://"


def save_upload(
    upload: Base64Upload, *, folder: str, documents: bool = False, private: bool = False
) -> str:
    """Store a validated upload. Returns a public URL, or ``private://...`` for
    files that must never be served publicly (verification documents)."""
    if not storage_available():
        raise AppException(
            code="MEDIA_STORAGE_UNAVAILABLE",
            message="File storage is not configured on this server.",
            status_code=503,
        )
    raw, ext = _validate(upload, DOCUMENT_TYPES if documents else IMAGE_TYPES)
    safe_folder = "".join(c for c in folder if c.isalnum() or c in "-_") or "misc"
    name = f"{uuid.uuid4().hex}{ext}"
    root = Path(settings.MEDIA_PRIVATE_ROOT if private else settings.MEDIA_ROOT)
    target_dir = root / safe_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / name).write_bytes(raw)
    if private:
        return f"{PRIVATE_PREFIX}{safe_folder}/{name}"
    return f"{settings.MEDIA_PUBLIC_BASE_URL.rstrip('/')}/{safe_folder}/{name}"


def private_path(reference: str) -> Path | None:
    """Resolve a ``private://`` reference to a file path inside the private root."""
    if not reference.startswith(PRIVATE_PREFIX):
        return None
    root = Path(settings.MEDIA_PRIVATE_ROOT).resolve()
    candidate = (root / reference[len(PRIVATE_PREFIX) :]).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate
