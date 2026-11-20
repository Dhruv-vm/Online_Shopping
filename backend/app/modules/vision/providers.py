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
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Text recognised by a provider plus the provider's own confidence scores.

    Confidence values are passed through exactly as reported (0..1); they are
    never estimated by BASKET. Missing scores stay ``None``.
    """

    text: str
    confidence: float | None = None
    line_confidence: dict[str, float] = field(default_factory=dict)


class OCRProvider(Protocol):
    name: str

    async def extract_text(self, image_base64: str, content_type: str) -> str: ...

    async def extract(self, image_base64: str, content_type: str) -> OCRResult: ...


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

    async def extract(self, image_base64: str, content_type: str) -> OCRResult:
        return OCRResult(text=await self.extract_text(image_base64, content_type))


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
        body = resp.json() or {}
        text = body.get("text")
        if not isinstance(text, str):
            raise AppException(
                code="OCR_PROVIDER_ERROR",
                message="The OCR service returned no text.",
                status_code=502,
            )
        self._last_body = body
        return text

    async def extract(self, image_base64: str, content_type: str) -> OCRResult:
        text = await self.extract_text(image_base64, content_type)
        body = getattr(self, "_last_body", {}) or {}

        def _score(v) -> float | None:
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None
            return f if 0.0 <= f <= 1.0 else None

        lines: dict[str, float] = {}
        for entry in body.get("lines") or []:
            if isinstance(entry, dict) and isinstance(entry.get("text"), str):
                sc = _score(entry.get("confidence"))
                if sc is not None:
                    lines[entry["text"].strip()] = sc
        return OCRResult(
            text=text, confidence=_score(body.get("confidence")), line_confidence=lines
        )


def get_ocr_provider() -> OCRProvider:
    if (settings.OCR_PROVIDER or "").lower() == "http" and settings.OCR_PROVIDER_URL:
        key = (
            settings.OCR_PROVIDER_API_KEY.get_secret_value()
            if settings.OCR_PROVIDER_API_KEY
            else None
        )
        return HttpOCRProvider(settings.OCR_PROVIDER_URL, key)
    return UnconfiguredOCRProvider()
