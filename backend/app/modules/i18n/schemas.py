import uuid
from typing import Literal

from pydantic import BaseModel, Field


class LanguageItem(BaseModel):
    code: str
    name: str
    native_name: str
    script: str


class LanguagesResponse(BaseModel):
    default: str = "en"
    languages: list[LanguageItem]


class LanguagePreferenceRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=8)


class LanguagePreferenceResponse(BaseModel):
    language: str


class NormalizedQueryResponse(BaseModel):
    original: str
    normalized: str
    detected_language: str
    translated: bool


class TranslationUpsertRequest(BaseModel):
    entity_type: Literal["product", "category", "offer"]
    entity_id: uuid.UUID
    language: str = Field(..., min_length=2, max_length=8)
    fields: dict[Literal["name", "description"], str] = Field(..., min_length=1)


class TranslationsResponse(BaseModel):
    entity_type: str
    language: str
    translations: dict[str, dict[str, str]]
