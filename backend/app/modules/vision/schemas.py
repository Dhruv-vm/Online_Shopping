import base64
import binascii
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


class ParseListRequest(BaseModel):
    """Send a photo (`image_base64` + `content_type`) or the typed/corrected list (`text`)."""

    image_base64: str | None = Field(None, max_length=7_200_000)
    content_type: Literal["image/jpeg", "image/png", "image/webp"] | None = None
    text: str | None = Field(None, min_length=2, max_length=4000)

    @model_validator(mode="after")
    def _one_source(self):
        if bool(self.image_base64) == bool(self.text):
            raise ValueError("Provide exactly one of image_base64 or text")
        if self.image_base64:
            if not self.content_type:
                raise ValueError("content_type is required with image_base64")
            try:
                raw = base64.b64decode(self.image_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("image_base64 is not valid base64") from None
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError("Image must be 5 MB or smaller")
            if not raw.startswith(_MAGIC[self.content_type]) or (
                self.content_type == "image/webp" and raw[8:12] != b"WEBP"
            ):
                raise ValueError("File content does not match content_type")
        return self


class MatchCandidate(BaseModel):
    listing_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    retailer_name: str
    price_paise: int
    in_stock: bool


class ParsedListItem(BaseModel):
    line: str
    name: str
    interpreted_as: str
    size: str | None
    quantity: int
    candidates: list[MatchCandidate]
    suggested_listing_id: uuid.UUID | None


class ParseListResponse(BaseModel):
    source: Literal["OCR", "TEXT"]
    provider: str | None
    raw_text: str
    items: list[ParsedListItem]
    unmatched_count: int


class BuildCartItem(BaseModel):
    listing_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=10)


class BuildCartRequest(BaseModel):
    items: list[BuildCartItem] = Field(..., min_length=1, max_length=30)


class BuildCartResponse(BaseModel):
    cart_id: uuid.UUID
    added: int
    skipped: list[dict]
