from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.intent.models import (
    CustomerPreferenceProfile,
    IntentMemoryItem,
    RecurringIntention,
)
from app.modules.intent.repository import IntentRepository
from app.modules.intent.schemas import (
    CustomerPreferenceProfileRequest,
    CustomerPreferenceProfileResponse,
    IntentMemoryItemCreateRequest,
    IntentMemoryItemResponse,
    IntentOverviewResponse,
    IntentSuggestionResponse,
    PersonalizationConsentResponse,
    RecurringIntentionCreateRequest,
    RecurringIntentionResponse,
    RecurringIntentionUpdateRequest,
)

logger = logging.getLogger("basket_intent_service")


class IntentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IntentRepository(session)

    @staticmethod
    def _map_profile(
        profile: CustomerPreferenceProfile,
    ) -> CustomerPreferenceProfileResponse:
        return CustomerPreferenceProfileResponse(
            id=profile.id,
            customer_id=profile.customer_id,
            preferred_brands=profile.preferred_brands or [],
            preferred_categories=profile.preferred_categories or [],
            preferred_retailers=profile.preferred_retailers or [],
            preferred_price_range=profile.preferred_price_range or {},
            preferred_attributes=profile.preferred_attributes or {},
            shopping_priorities=profile.shopping_priorities or [],
            category_preferences=profile.category_preferences or {},
            personalization_enabled=profile.personalization_enabled,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _map_intention(intention: RecurringIntention) -> RecurringIntentionResponse:
        return RecurringIntentionResponse(
            id=intention.id,
            customer_id=intention.customer_id,
            title=intention.title,
            category_ids=intention.category_ids or [],
            frequency=intention.frequency,
            budget_paise=intention.budget_paise,
            notes=intention.notes,
            is_active=intention.is_active,
            last_executed_at=intention.last_executed_at,
            created_at=intention.created_at,
            updated_at=intention.updated_at,
        )

    @staticmethod
    def _map_memory(memory: IntentMemoryItem) -> IntentMemoryItemResponse:
        return IntentMemoryItemResponse(
            id=memory.id,
            customer_id=memory.customer_id,
            memory_type=memory.memory_type,
            key=memory.key,
            value=memory.value or {},
            summary=memory.summary,
            source=memory.source,
            is_active=memory.is_active,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )

    async def get_overview(self, customer_id: uuid.UUID) -> IntentOverviewResponse:
        profile = await self.repo.get_profile(customer_id)
        intentions = await self.repo.get_recurring_intentions(customer_id)
        memories = await self.repo.get_memories(customer_id)

        mapped_profile = self._map_profile(profile) if profile else None
        mapped_intentions = [self._map_intention(i) for i in intentions]
        mapped_memories = [self._map_memory(m) for m in memories]

        active_count = sum(1 for i in intentions if i.is_active)
        personalization_enabled = profile.personalization_enabled if profile else False

        return IntentOverviewResponse(
            profile=mapped_profile,
            recurring_intentions=mapped_intentions,
            memories=mapped_memories,
            active_intentions_count=active_count,
            total_memories_count=len(memories),
            personalization_enabled=personalization_enabled,
        )

    async def get_profile(
        self, customer_id: uuid.UUID
    ) -> CustomerPreferenceProfileResponse:
        profile = await self.repo.get_profile(customer_id)
        if not profile:
            profile = await self.repo.upsert_profile(
                customer_id=customer_id,
                personalization_enabled=False,
            )
            await self.session.flush()
        return self._map_profile(profile)

    async def update_profile(
        self, customer_id: uuid.UUID, req: CustomerPreferenceProfileRequest
    ) -> CustomerPreferenceProfileResponse:
        profile = await self.repo.upsert_profile(
            customer_id=customer_id,
            preferred_brands=req.preferred_brands,
            preferred_categories=req.preferred_categories,
            preferred_retailers=req.preferred_retailers,
            preferred_price_range=req.preferred_price_range,
            preferred_attributes=req.preferred_attributes,
            shopping_priorities=req.shopping_priorities,
            category_preferences=req.category_preferences,
            personalization_enabled=req.personalization_enabled,
        )
        await self.session.flush()
        res = self._map_profile(profile)
        await self.session.commit()
        return res

    async def update_consent(
        self, customer_id: uuid.UUID, enabled: bool
    ) -> PersonalizationConsentResponse:
        profile = await self.repo.update_consent(
            customer_id=customer_id, personalization_enabled=enabled
        )
        await self.session.flush()
        msg = (
            "Personalized recommendations enabled based on your intent memory."
            if enabled
            else "Personalized recommendations disabled. Future recommendations will be neutral."
        )
        res = PersonalizationConsentResponse(
            personalization_enabled=profile.personalization_enabled,
            updated_at=profile.updated_at or datetime.datetime.now(datetime.UTC),
            message=msg,
        )
        await self.session.commit()
        return res

    async def list_recurring_intentions(
        self, customer_id: uuid.UUID, active_only: bool = False
    ) -> list[RecurringIntentionResponse]:
        intentions = await self.repo.get_recurring_intentions(
            customer_id, active_only=active_only
        )
        return [self._map_intention(i) for i in intentions]

    async def create_recurring_intention(
        self, customer_id: uuid.UUID, req: RecurringIntentionCreateRequest
    ) -> RecurringIntentionResponse:
        intention = await self.repo.create_recurring_intention(
            customer_id=customer_id,
            title=req.title.strip(),
            category_ids=req.category_ids,
            frequency=req.frequency.upper(),
            budget_paise=req.budget_paise,
            notes=req.notes.strip() if req.notes else None,
        )
        await self.session.flush()
        res = self._map_intention(intention)
        await self.session.commit()
        return res

    async def update_recurring_intention(
        self,
        customer_id: uuid.UUID,
        intention_id: uuid.UUID,
        req: RecurringIntentionUpdateRequest,
    ) -> RecurringIntentionResponse:
        intention = await self.repo.get_recurring_intention_by_id(
            intention_id=intention_id, customer_id=customer_id
        )
        if not intention:
            raise AppException(
                code="INTENTION_NOT_FOUND",
                message="Recurring shopping intention not found.",
                status_code=404,
            )

        updated = await self.repo.update_recurring_intention(
            intention=intention,
            title=req.title.strip() if req.title is not None else None,
            category_ids=req.category_ids,
            frequency=req.frequency.upper() if req.frequency is not None else None,
            budget_paise=req.budget_paise,
            notes=req.notes.strip() if req.notes is not None else None,
            is_active=req.is_active,
        )
        await self.session.flush()
        res = self._map_intention(updated)
        await self.session.commit()
        return res

    async def toggle_recurring_intention_status(
        self, customer_id: uuid.UUID, intention_id: uuid.UUID, is_active: bool
    ) -> RecurringIntentionResponse:
        intention = await self.repo.get_recurring_intention_by_id(
            intention_id=intention_id, customer_id=customer_id
        )
        if not intention:
            raise AppException(
                code="INTENTION_NOT_FOUND",
                message="Recurring shopping intention not found.",
                status_code=404,
            )

        updated = await self.repo.update_recurring_intention(
            intention=intention, is_active=is_active
        )
        await self.session.flush()
        res = self._map_intention(updated)
        await self.session.commit()
        return res

    async def delete_recurring_intention(
        self, customer_id: uuid.UUID, intention_id: uuid.UUID
    ) -> None:
        intention = await self.repo.get_recurring_intention_by_id(
            intention_id=intention_id, customer_id=customer_id
        )
        if not intention:
            raise AppException(
                code="INTENTION_NOT_FOUND",
                message="Recurring shopping intention not found.",
                status_code=404,
            )
        await self.repo.delete_recurring_intention(intention)
        await self.session.commit()

    async def list_memories(
        self, customer_id: uuid.UUID
    ) -> list[IntentMemoryItemResponse]:
        memories = await self.repo.get_memories(customer_id)
        return [self._map_memory(m) for m in memories]

    async def create_memory(
        self, customer_id: uuid.UUID, req: IntentMemoryItemCreateRequest
    ) -> IntentMemoryItemResponse:
        memory = await self.repo.create_memory(
            customer_id=customer_id,
            memory_type=req.memory_type.upper(),
            key=req.key.strip(),
            value=req.value,
            summary=req.summary.strip(),
            source=req.source,
        )
        await self.session.flush()
        res = self._map_memory(memory)
        await self.session.commit()
        return res

    async def delete_memory(self, customer_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        memory = await self.repo.get_memory_by_id(
            memory_id=memory_id, customer_id=customer_id
        )
        if not memory:
            raise AppException(
                code="MEMORY_NOT_FOUND",
                message="Intent memory item not found.",
                status_code=404,
            )
        await self.repo.delete_memory(memory)
        await self.session.commit()

    async def clear_all_memories(self, customer_id: uuid.UUID) -> None:
        await self.repo.clear_all(customer_id)
        await self.session.commit()

    async def get_suggestions(
        self, customer_id: uuid.UUID, category_id: uuid.UUID | None = None
    ) -> IntentSuggestionResponse:
        profile = await self.repo.get_profile(customer_id)
        if not profile or not profile.personalization_enabled:
            return IntentSuggestionResponse(
                suggested_brands=[],
                suggested_priorities=[],
                suggested_budget_paise=None,
                suggested_categories=[],
                applicable_intentions=[],
                personalization_enabled=False,
                explanation="Personalization is disabled in your intent settings.",
            )

        intentions = await self.repo.get_recurring_intentions(
            customer_id, active_only=True
        )
        applicable_intentions: list[RecurringIntention] = []
        suggested_budget = None

        if category_id:
            cat_str = str(category_id)
            applicable_intentions = [
                i for i in intentions if cat_str in (i.category_ids or [])
            ]
        else:
            applicable_intentions = intentions

        if applicable_intentions:
            budgets = [i.budget_paise for i in applicable_intentions if i.budget_paise]
            if budgets:
                suggested_budget = budgets[0]
        elif profile.preferred_price_range:
            suggested_budget = profile.preferred_price_range.get("max_paise")

        explanation_parts = []
        if profile.preferred_brands:
            explanation_parts.append(
                f"matches your preferred brands: {', '.join(profile.preferred_brands[:3])}"
            )
        if profile.shopping_priorities:
            explanation_parts.append(
                f"prioritizes {', '.join(profile.shopping_priorities[:2])}"
            )

        explanation = (
            f"Personalized based on your saved shopping memory: {'; '.join(explanation_parts)}."
            if explanation_parts
            else "Tailored suggestions based on your active shopping intent memory."
        )

        return IntentSuggestionResponse(
            suggested_brands=profile.preferred_brands or [],
            suggested_priorities=profile.shopping_priorities or [],
            suggested_budget_paise=suggested_budget,
            suggested_categories=profile.preferred_categories or [],
            applicable_intentions=[
                self._map_intention(i) for i in applicable_intentions
            ],
            personalization_enabled=True,
            explanation=explanation,
        )
