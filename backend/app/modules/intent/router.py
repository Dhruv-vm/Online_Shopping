from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.identity.dependencies import (
    get_current_active_user,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.intent.schemas import (
    CustomerPreferenceProfileRequest,
    CustomerPreferenceProfileResponse,
    IntentMemoryItemCreateRequest,
    IntentMemoryItemResponse,
    IntentOverviewResponse,
    IntentSuggestionResponse,
    PersonalizationConsentRequest,
    PersonalizationConsentResponse,
    RecurringIntentionCreateRequest,
    RecurringIntentionResponse,
    RecurringIntentionStatusRequest,
    RecurringIntentionUpdateRequest,
)
from app.modules.intent.service import IntentService

intent_router = APIRouter(prefix="/intent", tags=["Basket Intent Memory"])


@intent_router.get(
    "/overview",
    response_model=IntentOverviewResponse,
    summary="Get complete intent memory overview for authenticated customer",
)
async def get_intent_overview(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntentOverviewResponse:
    service = IntentService(db)
    return await service.get_overview(customer_id=current_user.id)


@intent_router.get(
    "/profile",
    response_model=CustomerPreferenceProfileResponse,
    summary="Get customer shopping preference profile",
)
async def get_preference_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerPreferenceProfileResponse:
    service = IntentService(db)
    return await service.get_profile(customer_id=current_user.id)


@intent_router.put(
    "/profile",
    response_model=CustomerPreferenceProfileResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update customer shopping preference profile",
)
async def update_preference_profile(
    req: CustomerPreferenceProfileRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerPreferenceProfileResponse:
    service = IntentService(db)
    return await service.update_profile(customer_id=current_user.id, req=req)


@intent_router.patch(
    "/consent",
    response_model=PersonalizationConsentResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update customer personalization consent",
)
async def update_personalization_consent(
    req: PersonalizationConsentRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PersonalizationConsentResponse:
    service = IntentService(db)
    return await service.update_consent(
        customer_id=current_user.id, enabled=req.personalization_enabled
    )


@intent_router.get(
    "/recurring",
    response_model=list[RecurringIntentionResponse],
    summary="List recurring shopping intentions for customer",
)
async def list_recurring_intentions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[bool, Query()] = False,
) -> list[RecurringIntentionResponse]:
    service = IntentService(db)
    return await service.list_recurring_intentions(
        customer_id=current_user.id, active_only=active_only
    )


@intent_router.post(
    "/recurring",
    response_model=RecurringIntentionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf_token)],
    summary="Create a new recurring shopping intention",
)
async def create_recurring_intention(
    req: RecurringIntentionCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecurringIntentionResponse:
    service = IntentService(db)
    return await service.create_recurring_intention(
        customer_id=current_user.id, req=req
    )


@intent_router.put(
    "/recurring/{intention_id}",
    response_model=RecurringIntentionResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update a recurring shopping intention",
)
async def update_recurring_intention(
    intention_id: uuid.UUID,
    req: RecurringIntentionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecurringIntentionResponse:
    service = IntentService(db)
    return await service.update_recurring_intention(
        customer_id=current_user.id, intention_id=intention_id, req=req
    )


@intent_router.patch(
    "/recurring/{intention_id}/status",
    response_model=RecurringIntentionResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Pause or reactivate a recurring shopping intention",
)
async def toggle_recurring_intention_status(
    intention_id: uuid.UUID,
    req: RecurringIntentionStatusRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecurringIntentionResponse:
    service = IntentService(db)
    return await service.toggle_recurring_intention_status(
        customer_id=current_user.id,
        intention_id=intention_id,
        is_active=req.is_active,
    )


@intent_router.delete(
    "/recurring/{intention_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf_token)],
    summary="Delete a recurring shopping intention",
)
async def delete_recurring_intention(
    intention_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = IntentService(db)
    await service.delete_recurring_intention(
        customer_id=current_user.id, intention_id=intention_id
    )


@intent_router.get(
    "/memories",
    response_model=list[IntentMemoryItemResponse],
    summary="List individual intent memory cards",
)
async def list_memories(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[IntentMemoryItemResponse]:
    service = IntentService(db)
    return await service.list_memories(customer_id=current_user.id)


@intent_router.post(
    "/memories",
    response_model=IntentMemoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf_token)],
    summary="Add an individual intent memory card",
)
async def create_memory(
    req: IntentMemoryItemCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntentMemoryItemResponse:
    service = IntentService(db)
    return await service.create_memory(customer_id=current_user.id, req=req)


@intent_router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf_token)],
    summary="Delete an individual intent memory card",
)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = IntentService(db)
    await service.delete_memory(customer_id=current_user.id, memory_id=memory_id)


@intent_router.delete(
    "/clear-all",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf_token)],
    summary="Clear all customer shopping intent memories and recurring intentions",
)
async def clear_all_memories(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = IntentService(db)
    await service.clear_all_memories(customer_id=current_user.id)


@intent_router.get(
    "/suggestions",
    response_model=IntentSuggestionResponse,
    summary="Get intent-based suggestions for mission planning or product exploration",
)
async def get_intent_suggestions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: Annotated[uuid.UUID | None, Query()] = None,
) -> IntentSuggestionResponse:
    service = IntentService(db)
    return await service.get_suggestions(
        customer_id=current_user.id, category_id=category_id
    )
