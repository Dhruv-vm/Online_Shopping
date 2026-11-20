"""Bharat Multilingual: query normalisation, translations, language preference."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.i18n.lexicon import (
    SUPPORTED_LANGUAGES,
    TERM_INDEX,
    detect_script_language,
)
from app.modules.i18n.models import ContentTranslation

ENTITY_TYPES = {"product", "category", "offer"}
FIELDS = {"name", "description"}
_TOKEN_RE = re.compile(r"[\wऀ-ൿ]+", re.UNICODE)


def normalize_query(q: str | None) -> tuple[str, str, bool]:
    """Return (normalised_english_query, detected_language, was_translated)."""
    if not q or not q.strip():
        return "", "en", False
    raw = q.strip()
    detected = detect_script_language(raw)
    out: list[str] = []
    changed = False
    for token in _TOKEN_RE.findall(raw):
        mapped = TERM_INDEX.get(token.casefold())
        if mapped:
            out.append(mapped)
            changed = True
        else:
            out.append(token)
    if not changed:
        return raw, detected, False
    # De-duplicate while preserving order
    seen: set[str] = set()
    words = [w for w in " ".join(out).split() if not (w in seen or seen.add(w))]
    return " ".join(words), detected, True


def validate_language(lang: str) -> str:
    code = (lang or "").strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        raise AppException(
            code="UNSUPPORTED_LANGUAGE",
            message=f"Language '{lang}' is not supported.",
            status_code=422,
            details={"supported": sorted(SUPPORTED_LANGUAGES)},
        )
    return code


class TranslationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        language: str,
        fields: dict[str, str],
        actor_id: uuid.UUID | None,
    ) -> None:
        if entity_type not in ENTITY_TYPES:
            raise AppException(
                code="INVALID_ENTITY_TYPE",
                message=f"entity_type must be one of {sorted(ENTITY_TYPES)}",
                status_code=422,
            )
        language = validate_language(language)
        if language == "en":
            raise AppException(
                code="INVALID_LANGUAGE",
                message="English is the source language; edit the entity directly.",
                status_code=422,
            )
        await self._assert_entity_exists(entity_type, entity_id)
        for field, value in fields.items():
            if field not in FIELDS:
                raise AppException(
                    code="INVALID_FIELD",
                    message=f"field must be one of {sorted(FIELDS)}",
                    status_code=422,
                )
            stmt = pg_insert(ContentTranslation).values(
                id=uuid.uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                language=language,
                field=field,
                value=value.strip(),
                updated_by_user_id=actor_id,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_content_translation",
                set_={
                    "value": stmt.excluded.value,
                    "updated_by_user_id": stmt.excluded.updated_by_user_id,
                },
            )
            await self.session.execute(stmt)

    async def _assert_entity_exists(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> None:
        from app.modules.catalogue.models import Category, Product
        from app.modules.pricing.models import Discount

        model = {"product": Product, "category": Category, "offer": Discount}[
            entity_type
        ]
        if await self.session.get(model, entity_id) is None:
            raise AppException(
                code="ENTITY_NOT_FOUND",
                message=f"{entity_type} not found.",
                status_code=404,
            )

    async def bulk_get(
        self, *, entity_type: str, entity_ids: list[uuid.UUID], language: str
    ) -> dict[str, dict[str, str]]:
        language = validate_language(language)
        if language == "en" or not entity_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ContentTranslation).where(
                    ContentTranslation.entity_type == entity_type,
                    ContentTranslation.language == language,
                    ContentTranslation.entity_id.in_(entity_ids),
                )
            )
        ).scalars()
        out: dict[str, dict[str, str]] = {}
        for r in rows:
            out.setdefault(str(r.entity_id), {})[r.field] = r.value
        return out
