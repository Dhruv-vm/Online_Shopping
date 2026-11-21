"""Shared input validators."""

from __future__ import annotations

from urllib.parse import urlsplit

MAX_MEDIA_URL_LENGTH = 1000


def validate_media_url(value: str | None) -> str | None:
    """Accept only absolute http(s) URLs for images and documents.

    Rejects ``javascript:``, ``data:``, ``file:`` and relative URLs, which could
    otherwise be stored and later rendered into pages (stored XSS / broken media).
    """
    if value is None:
        return None
    url = value.strip()
    if not url:
        return None
    if len(url) > MAX_MEDIA_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_MEDIA_URL_LENGTH} characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        raise ValueError("URL must not contain whitespace or control characters")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ValueError("URL must be an absolute http:// or https:// URL")
    return url
