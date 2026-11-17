import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalogue.models import StoreInventory
from app.modules.inventory.models import (
    InventoryReservation,
    ReservationStatus,
)


class ReservationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        reservation_id: uuid.UUID,
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .options(selectinload(InventoryReservation.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_by_quote_id(
        self,
        quote_id: uuid.UUID,
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(
                InventoryReservation.quote_id == quote_id,
                InventoryReservation.status == ReservationStatus.ACTIVE.value,
            )
            .options(selectinload(InventoryReservation.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_idempotency(
        self,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        idempotency_key: str,
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(
                InventoryReservation.idempotency_key == idempotency_key,
                (
                    (InventoryReservation.customer_id == customer_id)
                    if customer_id
                    else (InventoryReservation.guest_token_hash == guest_token_hash)
                ),
            )
            .options(selectinload(InventoryReservation.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def lock_inventories_for_update(
        self,
        listing_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, StoreInventory]:
        """Acquires row-level write locks (FOR UPDATE) in deterministic ascending order of listing_id.

        This guarantees elimination of PostgreSQL deadlock cycles between concurrent transactions.
        """
        if not listing_ids:
            return {}

        # Strictly sort listing_ids in ascending lexicographical order
        sorted_ids = sorted(set(listing_ids))

        stmt = (
            select(StoreInventory)
            .where(StoreInventory.listing_id.in_(sorted_ids))
            .options(selectinload(StoreInventory.listing))
            .with_for_update()
            .order_by(StoreInventory.listing_id.asc())
        )
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return {inv.listing_id: inv for inv in rows}

    async def lock_reservation_for_update(
        self,
        reservation_id: uuid.UUID,
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .with_for_update()
            .options(selectinload(InventoryReservation.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_expired_active_reservations(
        self,
        limit: int = 100,
    ) -> list[InventoryReservation]:
        now = datetime.now(UTC)
        stmt = (
            select(InventoryReservation)
            .where(
                InventoryReservation.status == ReservationStatus.ACTIVE.value,
                InventoryReservation.expires_at < now,
            )
            .options(selectinload(InventoryReservation.items))
            .order_by(InventoryReservation.expires_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
