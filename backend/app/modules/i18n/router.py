import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import AppException
from app.modules.i18n.lexicon import SUPPORTED_LANGUAGES
from app.modules.i18n.schemas import (
    LanguageItem,
    LanguagePreferenceRequest,
    LanguagePreferenceResponse,
    LanguagesResponse,
    NormalizedQueryResponse,
    TranslationsResponse,
    TranslationUpsertRequest,
)
from app.modules.i18n.service import (
    TranslationService,
    normalize_query,
    validate_language,
)
from app.modules.identity.dependencies import (
    get_current_user,
    require_admin,
    verify_csrf_token,
)
from app.modules.identity.models import User

router = APIRouter(
    prefix="/i18n",
    tags=["Bharat Multilingual"],
    dependencies=[Depends(verify_csrf_token)],
)
admin_router = APIRouter(
    prefix="/admin/i18n",
    tags=["Bharat Multilingual (Admin)"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


@router.get("/languages", response_model=LanguagesResponse)
async def list_languages() -> LanguagesResponse:
    return LanguagesResponse(
        languages=[
            LanguageItem(
                code=c, name=m["name"], native_name=m["native"], script=m["script"]
            )
            for c, m in SUPPORTED_LANGUAGES.items()
        ]
    )


@router.get("/normalize", response_model=NormalizedQueryResponse)
async def normalize(
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> NormalizedQueryResponse:
    normalized, lang, translated = normalize_query(q)
    return NormalizedQueryResponse(
        original=q, normalized=normalized, detected_language=lang, translated=translated
    )


@router.get("/translations", response_model=TranslationsResponse)
async def get_translations(
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: Literal["product", "category", "offer"],
    lang: Annotated[str, Query(min_length=2, max_length=8)],
    ids: Annotated[
        str,
        Query(
            min_length=1, max_length=4000, description="Comma-separated UUIDs (max 100)"
        ),
    ],
) -> TranslationsResponse:
    try:
        uuids = [uuid.UUID(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise AppException(
            code="INVALID_IDS",
            message="ids must be comma-separated UUIDs.",
            status_code=422,
        ) from None
    if len(uuids) > 100:
        raise AppException(
            code="TOO_MANY_IDS", message="At most 100 ids.", status_code=422
        )
    data = await TranslationService(db).bulk_get(
        entity_type=entity_type, entity_ids=uuids, language=lang
    )
    return TranslationsResponse(
        entity_type=entity_type, language=lang, translations=data
    )


@router.get("/preference", response_model=LanguagePreferenceResponse)
async def get_preference(
    user: Annotated[User, Depends(get_current_user)],
) -> LanguagePreferenceResponse:
    return LanguagePreferenceResponse(language=user.preferred_language or "en")


@router.put("/preference", response_model=LanguagePreferenceResponse)
async def set_preference(
    payload: LanguagePreferenceRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LanguagePreferenceResponse:
    user.preferred_language = validate_language(payload.language)
    await db.flush()
    return LanguagePreferenceResponse(language=user.preferred_language)


@admin_router.put("/translations", status_code=204)
async def upsert_translation(
    payload: TranslationUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> None:
    await TranslationService(db).upsert(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        language=payload.language,
        fields=dict(payload.fields),
        actor_id=admin.id,
    )
