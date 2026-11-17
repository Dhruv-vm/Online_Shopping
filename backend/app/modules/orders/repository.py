import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cart.models import CartItem
from app.modules.identity.models import Address
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import (
    IdempotencyRecord,
    Order,
    OrderStatusHistory,
    OutboxEvent,
)
from app.modules.pricing.models import CheckoutQuote


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_quote_for_update(self, quote_id: uuid.UUID) -> CheckoutQuote | None:
        stmt = (
            select(CheckoutQuote)
            .where(CheckoutQuote.id == quote_id)
            .options(selectinload(CheckoutQuote.items))
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def lock_reservation_for_update(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .options(selectinload(InventoryReservation.items))
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_customer_address(
        self, address_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Address | None:
        stmt = select(Address).where(
            Address.id == address_id,
            Address.user_id == customer_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_idempotency_record(
        self,
        scope: str,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
            (
                (IdempotencyRecord.customer_id == customer_id)
                if customer_id
                else (IdempotencyRecord.guest_token_hash == guest_token_hash)
            ),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_idempotency_record(
        self,
        scope: str,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        idempotency_key: str,
        request_hash: str,
        order_id: uuid.UUID,
        expires_at: datetime,
    ) -> IdempotencyRecord:
        record = IdempotencyRecord(
            id=uuid.uuid4(),
            scope=scope,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            order_id=order_id,
            expires_at=expires_at,
        )
        self.session.add(record)
        return record

    async def get_order_by_quote_id(self, quote_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.quote_id == quote_id)
            .options(selectinload(Order.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_orders(
        self,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        base_filter = (
            (Order.customer_id == customer_id)
            if customer_id
            else (Order.guest_token_hash == guest_token_hash)
        )
        count_stmt = select(func.count(Order.id)).where(base_filter)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(Order)
            .where(base_filter)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        event_type: str,
        schema_version: int,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        event = OutboxEvent(
            id=uuid.uuid4(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            schema_version=schema_version,
            payload=payload,
            status="PENDING",
            retry_count=0,
        )
        self.session.add(event)
        return event

    async def get_cart_items_for_update(self, cart_id: uuid.UUID) -> list[CartItem]:
        stmt = select(CartItem).where(CartItem.cart_id == cart_id).with_for_update()
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def add_order(self, order: Order) -> None:
        self.session.add(order)

    def add_status_history(self, history: OrderStatusHistory) -> None:
        self.session.add(history)

    async def flush(self) -> None:
        await self.session.flush()
