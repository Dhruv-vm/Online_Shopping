import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cart.models import CartItem
from app.modules.identity.models import Address
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import (
    CustomerNotification,
    IdempotencyRecord,
    Order,
    OrderItem,
    OrderReturn,
    OrderStatusHistory,
    OutboxEvent,
    OutboxStatus,
    ReturnItem,
    ReturnStatusHistory,
    Shipment,
    ShipmentItem,
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

    async def get_reservation_by_id(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation | None:
        stmt = (
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .options(selectinload(InventoryReservation.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_quote_by_id(self, quote_id: uuid.UUID) -> CheckoutQuote | None:
        stmt = (
            select(CheckoutQuote)
            .where(CheckoutQuote.id == quote_id)
            .options(selectinload(CheckoutQuote.items))
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

    async def get_default_customer_address(
        self, customer_id: uuid.UUID
    ) -> Address | None:
        stmt = (
            select(Address)
            .where(
                Address.user_id == customer_id,
                Address.is_default.is_(True),
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        addr = res.scalar_one_or_none()
        if addr:
            return addr
        stmt_fallback = (
            select(Address)
            .where(Address.user_id == customer_id)
            .order_by(Address.created_at.desc())
            .limit(1)
        )
        res_fallback = await self.session.execute(stmt_fallback)
        return res_fallback.scalar_one_or_none()

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
                selectinload(Order.shipments).selectinload(Shipment.items),
                selectinload(Order.returns).selectinload(OrderReturn.items),
                selectinload(Order.returns).selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_id_for_update(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.shipments).selectinload(Shipment.items),
                selectinload(Order.returns).selectinload(OrderReturn.items),
                selectinload(Order.returns).selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_number(self, order_number: str) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.order_number == order_number)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.shipments).selectinload(Shipment.items),
                selectinload(Order.returns).selectinload(OrderReturn.items),
                selectinload(Order.returns).selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_number_and_guest_token_hash(
        self, order_number: str, guest_access_token_hash: str
    ) -> Order | None:
        stmt = (
            select(Order)
            .where(
                Order.order_number == order_number,
                Order.guest_access_token_hash == guest_access_token_hash,
            )
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.shipments).selectinload(Shipment.items),
                selectinload(Order.returns).selectinload(OrderReturn.items),
                selectinload(Order.returns).selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_orders(
        self,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        filters = []
        if customer_id:
            filters.append(Order.customer_id == customer_id)
        elif guest_token_hash:
            filters.append(Order.guest_token_hash == guest_token_hash)
        else:
            return [], 0

        if status:
            filters.append(Order.status == status.strip().upper())
        if from_date:
            filters.append(Order.created_at >= from_date)
        if to_date:
            filters.append(Order.created_at <= to_date)
        if search:
            search_term = f"%{search.strip()}%"
            # Match either order_number or product_title in order items
            subquery = (
                select(OrderItem.order_id)
                .where(OrderItem.product_title.ilike(search_term))
                .scalar_subquery()
            )
            filters.append(
                or_(
                    Order.order_number.ilike(search_term),
                    Order.id.in_(subquery),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count(Order.id)).where(where_clause)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(Order)
            .where(where_clause)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def get_shipment_by_id(self, shipment_id: uuid.UUID) -> Shipment | None:
        stmt = (
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .options(selectinload(Shipment.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_shipment_by_id_for_update(
        self, shipment_id: uuid.UUID
    ) -> Shipment | None:
        stmt = (
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .with_for_update()
            .options(selectinload(Shipment.items))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    def add_shipment(self, shipment: Shipment) -> None:
        self.session.add(shipment)

    def add_shipment_item(self, shipment_item: ShipmentItem) -> None:
        self.session.add(shipment_item)

    async def get_return_by_id(self, return_id: uuid.UUID) -> OrderReturn | None:
        stmt = (
            select(OrderReturn)
            .where(OrderReturn.id == return_id)
            .options(
                selectinload(OrderReturn.items),
                selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_return_by_id_for_update(
        self, return_id: uuid.UUID
    ) -> OrderReturn | None:
        stmt = (
            select(OrderReturn)
            .where(OrderReturn.id == return_id)
            .with_for_update()
            .options(
                selectinload(OrderReturn.items),
                selectinload(OrderReturn.status_history),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_returns_for_order(self, order_id: uuid.UUID) -> list[OrderReturn]:
        stmt = (
            select(OrderReturn)
            .where(OrderReturn.order_id == order_id)
            .options(
                selectinload(OrderReturn.items),
                selectinload(OrderReturn.status_history),
            )
            .order_by(OrderReturn.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def add_return(self, return_order: OrderReturn) -> None:
        self.session.add(return_order)

    def add_return_item(self, return_item: ReturnItem) -> None:
        self.session.add(return_item)

    def add_return_status_history(self, history: ReturnStatusHistory) -> None:
        self.session.add(history)

    async def list_notifications(
        self,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CustomerNotification], int]:
        filters = []
        if customer_id:
            filters.append(CustomerNotification.customer_id == customer_id)
        elif guest_token_hash:
            filters.append(CustomerNotification.guest_token_hash == guest_token_hash)
        else:
            return [], 0

        where_clause = and_(*filters)
        count_stmt = select(func.count(CustomerNotification.id)).where(where_clause)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(CustomerNotification)
            .where(where_clause)
            .order_by(CustomerNotification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def get_unread_notification_count(
        self,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
    ) -> int:
        filters = [CustomerNotification.is_read.is_(False)]
        if customer_id:
            filters.append(CustomerNotification.customer_id == customer_id)
        elif guest_token_hash:
            filters.append(CustomerNotification.guest_token_hash == guest_token_hash)
        else:
            return 0

        stmt = select(func.count(CustomerNotification.id)).where(and_(*filters))
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def mark_notification_as_read(
        self,
        notification_id: uuid.UUID,
        customer_id: uuid.UUID | None,
        guest_token_hash: str | None,
    ) -> CustomerNotification | None:
        filters = [CustomerNotification.id == notification_id]
        if customer_id:
            filters.append(CustomerNotification.customer_id == customer_id)
        elif guest_token_hash:
            filters.append(CustomerNotification.guest_token_hash == guest_token_hash)
        else:
            return None

        stmt = select(CustomerNotification).where(and_(*filters))
        res = await self.session.execute(stmt)
        item = res.scalar_one_or_none()
        if item:
            item.is_read = True
            item.read_at = datetime.now()
        return item

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        event_type: str,
        schema_version: int,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        aggregate_version: int | None = None,
    ) -> OutboxEvent:
        event = OutboxEvent(
            id=uuid.uuid4(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            schema_version=schema_version,
            payload=payload,
            status=OutboxStatus.PENDING.value,
            retry_count=0,
            correlation_id=correlation_id,
            aggregate_version=aggregate_version,
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
