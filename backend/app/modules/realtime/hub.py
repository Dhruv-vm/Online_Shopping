"""Real-time hub for the shared marketplace (final functional cycle, Part 4).

Business changes already produce outbox events (transactional, PII-free by the
envelope's rules). Those events reach this per-process hub either from Kafka
(``RealtimeKafkaListener``: a consumer group unique to this API instance, so
every instance sees every event) or, with ``OUTBOX_DISPATCH=direct``, from the
direct dispatcher. The hub forwards a *notice* — ``{type, entity, id}`` only,
never payload data — to the connected users entitled to it; browsers then
refetch through the normal authorised APIs. Private data is therefore never
broadcast and every permission check still happens on the refetch.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)

ALL_TOPICS = [
    "basket.events.orders",
    "basket.events.payments",
    "basket.events.catalogue",
    "basket.events.inventory",
    "basket.events.marketplace",
]
QUEUE_SIZE = 200


@dataclass(eq=False)
class Subscriber:
    user_id: uuid.UUID
    role: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(QUEUE_SIZE))


@dataclass
class Audience:
    everyone: bool = False
    roles: set[str] = field(default_factory=set)
    users: set[uuid.UUID] = field(default_factory=set)

    def includes(self, sub: Subscriber) -> bool:
        return (
            self.everyone
            or sub.role == "admin"
            or sub.role in self.roles
            or sub.user_id in self.users
        )


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


class RealtimeHub:
    def __init__(self) -> None:
        self._subs: set[Subscriber] = set()
        self.published = 0
        self.delivered = 0

    # ----------------------------------------------------------- connections
    def connect(self, user_id: uuid.UUID, role: str) -> Subscriber:
        sub = Subscriber(user_id=user_id, role=role)
        self._subs.add(sub)
        return sub

    def disconnect(self, sub: Subscriber) -> None:
        self._subs.discard(sub)

    @property
    def connections(self) -> int:
        return len(self._subs)

    # -------------------------------------------------------------- audience
    async def _audience(
        self, event_type: str, aggregate_id: uuid.UUID | None, payload: dict
    ) -> Audience:
        """Who may be told that this entity changed (ids only)."""
        prefix = event_type.split(".", 1)[0]
        if prefix in (
            "product",
            "catalogue",
            "listing",
            "variant",
            "inventory",
            "store_inventory",
            "price",
            "sale_stream",
            "offer",
        ):
            return Audience(everyone=True)

        from app.core.database import get_session_factory

        sf = get_session_factory()
        if sf is None:
            return Audience()
        async with sf() as s:
            if prefix in ("order", "payment", "fulfilment"):
                order_id = _uuid(payload.get("order_id")) or aggregate_id
                return await self._order_audience(s, order_id)
            if prefix == "auction":
                from app.modules.auctions.models import BasketAuction

                owner = (
                    await s.execute(
                        select(BasketAuction.user_id).where(
                            BasketAuction.id == aggregate_id
                        )
                    )
                ).scalar_one_or_none()
                return Audience(roles={"retailer"}, users={owner} if owner else set())
            if prefix == "group_buy":
                from app.modules.catalogue.models import Retailer
                from app.modules.community.models import GroupBuyCampaign

                row = (
                    await s.execute(
                        select(Retailer.user_id)
                        .join(
                            GroupBuyCampaign,
                            GroupBuyCampaign.retailer_id == Retailer.id,
                        )
                        .where(GroupBuyCampaign.id == aggregate_id)
                    )
                ).scalar_one_or_none()
                return Audience(roles={"customer"}, users={row} if row else set())
            if prefix == "exchange":
                from app.modules.exchange.models import ExchangeRequest

                owner = (
                    await s.execute(
                        select(ExchangeRequest.user_id).where(
                            ExchangeRequest.id
                            == (_uuid(payload.get("request_id")) or aggregate_id)
                        )
                    )
                ).scalar_one_or_none()
                return Audience(roles={"retailer"}, users={owner} if owner else set())
            if prefix == "demand":
                return Audience(roles={"retailer"})
            if prefix == "negotiation":
                from app.modules.negotiation.models import NegotiationSession

                owner = (
                    await s.execute(
                        select(NegotiationSession.user_id).where(
                            NegotiationSession.id == aggregate_id
                        )
                    )
                ).scalar_one_or_none()
                return Audience(users={owner} if owner else set())
        return Audience()  # unknown: admins only

    async def _order_audience(self, s, order_id: uuid.UUID | None) -> Audience:
        from app.modules.catalogue.models import Retailer
        from app.modules.orders.models import Order, OrderItem

        if order_id is None:
            return Audience()
        owner = (
            await s.execute(select(Order.customer_id).where(Order.id == order_id))
        ).scalar_one_or_none()
        retailer_users = (
            await s.execute(
                select(Retailer.user_id)
                .join(OrderItem, OrderItem.retailer_id == Retailer.id)
                .where(OrderItem.order_id == order_id)
            )
        ).scalars()
        users = {u for u in retailer_users if u}
        if owner:
            users.add(owner)
        return Audience(users=users)

    # ------------------------------------------------------------- publishing
    async def publish(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: Any,
        payload: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> int:
        """Forward a change notice to entitled subscribers. Returns deliveries."""
        self.published += 1
        if not self._subs:
            return 0
        agg = _uuid(aggregate_id)
        try:
            audience = await self._audience(event_type, agg, payload or {})
        except Exception as exc:  # never break event delivery because of push
            logger.warning(
                "Realtime audience lookup failed for %s: %s", event_type, exc
            )
            return 0
        notice = json.dumps(
            {
                "type": event_type,
                "entity": aggregate_type,
                "id": str(agg) if agg else None,
                "at": (occurred_at or datetime.now(UTC)).isoformat(),
            }
        )
        n = 0
        for sub in list(self._subs):
            if not audience.includes(sub):
                continue
            if sub.queue.full():  # slow client: drop the oldest notice
                with contextlib.suppress(asyncio.QueueEmpty):
                    sub.queue.get_nowait()
            sub.queue.put_nowait(notice)
            n += 1
        self.delivered += n
        return n

    async def publish_envelope(self, envelope) -> int:
        return await self.publish(
            envelope.event_type,
            envelope.aggregate_type,
            envelope.aggregate_id,
            dict(envelope.payload or {}),
            envelope.occurred_at,
        )


hub = RealtimeHub()


class RealtimeKafkaListener:
    """Feeds the hub from Kafka with a consumer group unique to this process
    (latest offsets only: live notices, not history)."""

    def __init__(self, config_settings=None) -> None:
        from app.core.config import settings

        self._settings = config_settings or settings
        self._consumer = None
        self._task: asyncio.Task | None = None
        self.group_id = f"basket-realtime-{uuid.uuid4().hex[:12]}"

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer

        from app.core.events.kafka import build_kafka_auth_kwargs

        self._consumer = AIOKafkaConsumer(
            *ALL_TOPICS,
            bootstrap_servers=self._settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            client_id=f"{self._settings.KAFKA_CLIENT_ID}-realtime",
            **build_kafka_auth_kwargs(self._settings),
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run(), name="realtime-kafka")

    async def _run(self) -> None:
        from app.core.events.envelope import EventEnvelope

        async for record in self._consumer:
            try:
                await hub.publish_envelope(EventEnvelope.from_json_bytes(record.value))
            except Exception as exc:
                logger.debug("Realtime: skipped record on %s: %s", record.topic, exc)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        if self._consumer is not None:
            with contextlib.suppress(Exception):
                await self._consumer.stop()
