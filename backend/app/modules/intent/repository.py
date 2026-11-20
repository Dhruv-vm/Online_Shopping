from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.intent.models import (
    CustomerPreferenceProfile,
    IntentMemoryItem,
    RecurringIntention,
)


class IntentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile(
        self, customer_id: uuid.UUID
    ) -> CustomerPreferenceProfile | None:
        stmt = select(CustomerPreferenceProfile).where(
            CustomerPreferenceProfile.customer_id == customer_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_profile(
        self,
        customer_id: uuid.UUID,
        preferred_brands: list[str] | None = None,
        preferred_categories: list[str] | None = None,
        preferred_retailers: list[str] | None = None,
        preferred_price_range: dict[str, Any] | None = None,
        preferred_attributes: dict[str, Any] | None = None,
        shopping_priorities: list[str] | None = None,
        category_preferences: dict[str, Any] | None = None,
        personalization_enabled: bool | None = None,
    ) -> CustomerPreferenceProfile:
        profile = await self.get_profile(customer_id)
        if not profile:
            profile = CustomerPreferenceProfile(
                customer_id=customer_id,
                preferred_brands=preferred_brands or [],
                preferred_categories=preferred_categories or [],
                preferred_retailers=preferred_retailers or [],
                preferred_price_range=preferred_price_range or {},
                preferred_attributes=preferred_attributes or {},
                shopping_priorities=shopping_priorities or [],
                category_preferences=category_preferences or {},
                personalization_enabled=(
                    personalization_enabled
                    if personalization_enabled is not None
                    else False
                ),
            )
            self.session.add(profile)
        else:
            if preferred_brands is not None:
                profile.preferred_brands = preferred_brands
            if preferred_categories is not None:
                profile.preferred_categories = preferred_categories
            if preferred_retailers is not None:
                profile.preferred_retailers = preferred_retailers
            if preferred_price_range is not None:
                profile.preferred_price_range = preferred_price_range
            if preferred_attributes is not None:
                profile.preferred_attributes = preferred_attributes
            if shopping_priorities is not None:
                profile.shopping_priorities = shopping_priorities
            if category_preferences is not None:
                profile.category_preferences = category_preferences
            if personalization_enabled is not None:
                profile.personalization_enabled = personalization_enabled
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def update_consent(
        self, customer_id: uuid.UUID, personalization_enabled: bool
    ) -> CustomerPreferenceProfile:
        profile = await self.get_profile(customer_id)
        if not profile:
            profile = CustomerPreferenceProfile(
                customer_id=customer_id,
                personalization_enabled=personalization_enabled,
            )
            self.session.add(profile)
        else:
            profile.personalization_enabled = personalization_enabled
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_recurring_intentions(
        self, customer_id: uuid.UUID, active_only: bool = False
    ) -> list[RecurringIntention]:
        stmt = (
            select(RecurringIntention)
            .where(RecurringIntention.customer_id == customer_id)
            .order_by(RecurringIntention.created_at.desc())
        )
        if active_only:
            stmt = stmt.where(RecurringIntention.is_active.is_(True))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_recurring_intention_by_id(
        self, intention_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> RecurringIntention | None:
        stmt = select(RecurringIntention).where(RecurringIntention.id == intention_id)
        if customer_id:
            stmt = stmt.where(RecurringIntention.customer_id == customer_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_recurring_intention(
        self,
        customer_id: uuid.UUID,
        title: str,
        category_ids: list[str],
        frequency: str,
        budget_paise: int | None = None,
        notes: str | None = None,
    ) -> RecurringIntention:
        intention = RecurringIntention(
            customer_id=customer_id,
            title=title,
            category_ids=category_ids,
            frequency=frequency,
            budget_paise=budget_paise,
            notes=notes,
            is_active=True,
        )
        self.session.add(intention)
        await self.session.flush()
        await self.session.refresh(intention)
        return intention

    async def update_recurring_intention(
        self,
        intention: RecurringIntention,
        title: str | None = None,
        category_ids: list[str] | None = None,
        frequency: str | None = None,
        budget_paise: int | None = None,
        notes: str | None = None,
        is_active: bool | None = None,
        last_executed_at: datetime.datetime | None = None,
    ) -> RecurringIntention:
        if title is not None:
            intention.title = title
        if category_ids is not None:
            intention.category_ids = category_ids
        if frequency is not None:
            intention.frequency = frequency
        if budget_paise is not None:
            intention.budget_paise = budget_paise
        if notes is not None:
            intention.notes = notes
        if is_active is not None:
            intention.is_active = is_active
        if last_executed_at is not None:
            intention.last_executed_at = last_executed_at
        await self.session.flush()
        await self.session.refresh(intention)
        return intention

    async def delete_recurring_intention(self, intention: RecurringIntention) -> None:
        await self.session.delete(intention)
        await self.session.flush()

    async def get_memories(
        self, customer_id: uuid.UUID, active_only: bool = True
    ) -> list[IntentMemoryItem]:
        stmt = (
            select(IntentMemoryItem)
            .where(IntentMemoryItem.customer_id == customer_id)
            .order_by(IntentMemoryItem.created_at.desc())
        )
        if active_only:
            stmt = stmt.where(IntentMemoryItem.is_active.is_(True))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_memory_by_id(
        self, memory_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> IntentMemoryItem | None:
        stmt = select(IntentMemoryItem).where(IntentMemoryItem.id == memory_id)
        if customer_id:
            stmt = stmt.where(IntentMemoryItem.customer_id == customer_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_memory(
        self,
        customer_id: uuid.UUID,
        memory_type: str,
        key: str,
        value: dict[str, Any] | str,
        summary: str,
        source: str = "CUSTOMER_STATED",
    ) -> IntentMemoryItem:
        item = IntentMemoryItem(
            customer_id=customer_id,
            memory_type=memory_type,
            key=key,
            value=value,
            summary=summary,
            source=source,
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete_memory(self, memory: IntentMemoryItem) -> None:
        await self.session.delete(memory)
        await self.session.flush()

    async def clear_all(self, customer_id: uuid.UUID) -> None:
        """Completely clear all intent memories and recurring intentions, and reset preference profile."""
        await self.session.execute(
            delete(IntentMemoryItem).where(IntentMemoryItem.customer_id == customer_id)
        )
        await self.session.execute(
            delete(RecurringIntention).where(
                RecurringIntention.customer_id == customer_id
            )
        )
        await self.session.execute(
            delete(CustomerPreferenceProfile).where(
                CustomerPreferenceProfile.customer_id == customer_id
            )
        )
        await self.session.flush()
