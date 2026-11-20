"""OCR / vision provider interface for Handwritten List to Basket (Phase 3I).

No OCR or multimodal vision service is configured for this project. The default
provider therefore refuses with OCR_PROVIDER_UNAVAILABLE instead of inventing
text. A generic HTTP adapter is provided for integrating a real service:

  OCR_PROVIDER=http
  OCR_PROVIDER_URL=https://<your-ocr-service>/v1/extract
  OCR_PROVIDER_API_KEY=<secret>

It POSTs {"image_base64", "content_type", "languages"} and expects {"text": "..."}.
The adapter has NOT been verified against a live service.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class OCRProvider(Protocol):
    name: str

    async def extract_text(self, image_base64: str, content_type: str) -> str: ...


class UnconfiguredOCRProvider:
    name = "unconfigured"

    async def extract_text(self, image_base64: str, content_type: str) -> str:
        raise AppException(
            code="OCR_PROVIDER_UNAVAILABLE",
            message=(
                "Handwriting recognition is not configured on this server. "
                "Type or paste your list instead (send `text`)."
            ),
            status_code=503,
        )


class HttpOCRProvider:
    name = "http"

    def __init__(self, url: str, api_key: str | None, timeout: float = 20.0) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    async def extract_text(self, image_base64: str, content_type: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.url,
                    json={
                        "image_base64": image_base64,
                        "content_type": content_type,
                        "languages": ["en", "hi", "ta", "te", "kn", "bn", "mr", "gu"],
                    },
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.warning("OCR provider request failed: %s", type(exc).__name__)
            raise AppException(
                code="OCR_PROVIDER_ERROR",
                message="The OCR service is unreachable.",
                status_code=502,
            ) from None
        if resp.status_code != 200:
            raise AppException(
                code="OCR_PROVIDER_ERROR",
                message="The OCR service returned an error.",
                status_code=502,
            )
        text = (resp.json() or {}).get("text")
        if not isinstance(text, str):
            raise AppException(
                code="OCR_PROVIDER_ERROR",
                message="The OCR service returned no text.",
                status_code=502,
            )
        return text


def get_ocr_provider() -> OCRProvider:
    if (settings.OCR_PROVIDER or "").lower() == "http" and settings.OCR_PROVIDER_URL:
        key = (
            settings.OCR_PROVIDER_API_KEY.get_secret_value()
            if settings.OCR_PROVIDER_API_KEY
            else None
        )
        return HttpOCRProvider(settings.OCR_PROVIDER_URL, key)
    return UnconfiguredOCRProvider()
