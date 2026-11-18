from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.events.consumer import BaseKafkaConsumer
from app.core.events.envelope import EventEnvelope
from app.core.events.inbox import OrderSummaryProjection, get_inbox_record
from app.core.events.kafka import EventProducer

logger = logging.getLogger(__name__)

ORDER_PROJECTION_CONSUMER_GROUP = "basket-order-projection"
ORDER_PROJECTION_TOPICS = [
    "basket.events.orders",
    "basket.events.payments",
]


class OrderVersionGapError(Exception):
    """Raised when an incremental order event arrives with an aggregate version gap."""

    pass


class OrderProjectionConsumer(BaseKafkaConsumer):
    """
    Domain consumer maintaining the authoritative OrderSummaryProjection read-model table in PostgreSQL.
    Demonstrates:
    - Strategy A single-ACID transaction deduplication & atomic side-effect execution.
    - Monotonic aggregate version enforcement: stale versions are safely skipped without state regression.
    - Idempotent duplicate processing: equal-version replays produce zero side effects.
    - Irreversible terminal state protection: CONFIRMED and CANCELLED states cannot regress to PENDING.
    - Version gap detection & durable deferral: non-terminal incremental events with version gaps
      are deferred with backoff before falling back to reconciliation.
    - Reconciliation & state reconstitution: delayed preceding events merge missing baseline data
      (e.g., items, totals) rather than being silently dropped, while respecting terminal states.
    - Cross-topic ordering resilience between basket.events.orders and basket.events.payments.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        producer: EventProducer | None = None,
        config_settings: Settings | None = None,
        *,
        consumer_group: str = ORDER_PROJECTION_CONSUMER_GROUP,
        topics: list[str] | None = None,
        consumer_impl: Any | None = None,
        enable_gap_deferral: bool = False,
        max_gap_deferrals: int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            consumer_group=consumer_group,
            topics=topics or ORDER_PROJECTION_TOPICS,
            session_factory=session_factory,
            producer=producer,
            config_settings=config_settings,
            consumer_impl=consumer_impl,
            **kwargs,
        )
        self._enable_gap_deferral = enable_gap_deferral
        self._max_gap_deferrals = max_gap_deferrals

    async def handle_event(self, event: EventEnvelope, session: AsyncSession) -> None:
        """
        Execute domain read-model projection mutation inside the caller's active database transaction.
        """
        order_id = event.aggregate_id
        stmt = (
            select(OrderSummaryProjection)
            .where(OrderSummaryProjection.order_id == order_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        projection = result.scalar_one_or_none()

        event_type = event.event_type.strip().lower()

        if event_type == "order.created":
            await self._handle_order_created(event, projection, session)
        elif event_type == "order.confirmed":
            await self._handle_order_confirmed(event, projection, session)
        elif event_type == "order.cancelled":
            await self._handle_order_cancelled(event, projection, session)
        elif event_type == "payment.succeeded":
            await self._handle_payment_succeeded(event, projection, session)
        else:
            logger.debug(
                "OrderProjectionConsumer ignoring unhandled event type '%s'",
                event.event_type,
            )

    async def _handle_order_created(
        self,
        event: EventEnvelope,
        projection: OrderSummaryProjection | None,
        session: AsyncSession,
    ) -> None:
        payload = event.payload
        items = payload.get("items") or []
        item_count = (
            len(items)
            if isinstance(items, list) and len(items) > 0
            else int(payload.get("item_count", 0))
        )
        total_payable = int(payload.get("total_payable_paise", 0))

        if projection is not None:
            # Out-of-order arrival: projection already exists (e.g. from order.confirmed or payment.succeeded)
            # RECONCILIATION: merge missing baseline fields without regressing terminal status
            reconciled = False
            if projection.item_count == 0 and item_count > 0:
                projection.item_count = item_count
                reconciled = True
            if projection.total_payable_paise == 0 and total_payable > 0:
                projection.total_payable_paise = total_payable
                reconciled = True
            if payload.get("order_number") and projection.order_number.startswith(
                f"ORD-{event.aggregate_id}"
            ):
                projection.order_number = str(payload.get("order_number"))
                reconciled = True

            # Irreversible terminal status protection: NEVER regress CONFIRMED or CANCELLED to PENDING
            if projection.status in ("CONFIRMED", "CANCELLED"):
                logger.info(
                    "Reconciled baseline data from delayed order.created (v%d) for order %s while preserving terminal status '%s'",
                    event.aggregate_version,
                    event.aggregate_id,
                    projection.status,
                )
                return

            if event.aggregate_version <= projection.last_aggregate_version:
                if reconciled:
                    logger.info(
                        "Reconciled missing baseline data for stale order.created (v%d <= v%d) on order %s",
                        event.aggregate_version,
                        projection.last_aggregate_version,
                        event.aggregate_id,
                    )
                return

            # Baseline status update if no terminal transition occurred
            projection.status = payload.get("status", "PENDING_PAYMENT")
            projection.payment_status = payload.get(
                "payment_status", projection.payment_status
            )
            projection.total_payable_paise = (
                total_payable if total_payable > 0 else projection.total_payable_paise
            )
            projection.item_count = (
                item_count if item_count > 0 else projection.item_count
            )
            projection.last_event_type = event.event_type
            projection.last_aggregate_version = event.aggregate_version
        else:
            # In-order normal creation
            new_projection = OrderSummaryProjection(
                order_id=event.aggregate_id,
                order_number=str(
                    payload.get("order_number", f"ORD-{event.aggregate_id}")
                ),
                customer_id=None,  # Customer PII excluded from events by design
                status=str(payload.get("status", "PENDING_PAYMENT")),
                payment_status=str(payload.get("payment_status", "NOT_INITIATED")),
                total_payable_paise=total_payable,
                currency=str(payload.get("currency", "INR")),
                item_count=item_count,
                last_event_type=event.event_type,
                last_aggregate_version=event.aggregate_version,
            )
            session.add(new_projection)

    async def _handle_order_confirmed(
        self,
        event: EventEnvelope,
        projection: OrderSummaryProjection | None,
        session: AsyncSession,
    ) -> None:
        payload = event.payload

        # Gap Detection & Deferral:
        # If order.confirmed (v2+) arrives before order.created (v0), detect the gap.
        if (
            projection is None
            and event.aggregate_version > 1
            and self._enable_gap_deferral
        ):
            await session.flush()
            inbox_rec = await get_inbox_record(
                session, self._consumer_group, event.event_id
            )
            retry_count = inbox_rec.retry_count if inbox_rec else 0
            if retry_count < self._max_gap_deferrals:
                logger.warning(
                    "Aggregate version gap on order %s: received order.confirmed (v%d) but projection does not exist. Deferring attempt %d/%d.",
                    event.aggregate_id,
                    event.aggregate_version,
                    retry_count + 1,
                    self._max_gap_deferrals,
                )
                raise OrderVersionGapError(
                    f"Version gap on order {event.aggregate_id}: incoming v{event.aggregate_version} but projection missing. Deferring."
                )

        if projection is not None:
            # Terminal state protection: CANCELLED order cannot be confirmed
            if projection.status == "CANCELLED":
                logger.warning(
                    "Terminal state protection: refusing to confirm CANCELLED order %s (v%d event)",
                    event.aggregate_id,
                    event.aggregate_version,
                )
                return

            if event.aggregate_version <= projection.last_aggregate_version:
                logger.debug(
                    "Stale or duplicate order.confirmed (v%d <= v%d) for order %s; ignoring",
                    event.aggregate_version,
                    projection.last_aggregate_version,
                    event.aggregate_id,
                )
                return

            projection.status = "CONFIRMED"
            projection.payment_status = "SUCCEEDED"
            if (
                payload.get("total_payable_paise")
                and projection.total_payable_paise == 0
            ):
                projection.total_payable_paise = int(
                    payload.get("total_payable_paise", 0)
                )
            projection.last_event_type = event.event_type
            projection.last_aggregate_version = event.aggregate_version
        else:
            # Out-of-order arrival after deferral window or without deferral
            new_projection = OrderSummaryProjection(
                order_id=event.aggregate_id,
                order_number=str(
                    payload.get("order_number", f"ORD-{event.aggregate_id}")
                ),
                customer_id=None,
                status="CONFIRMED",
                payment_status="SUCCEEDED",
                total_payable_paise=int(payload.get("total_payable_paise", 0)),
                currency=str(payload.get("currency", "INR")),
                item_count=int(payload.get("item_count", 0)),
                last_event_type=event.event_type,
                last_aggregate_version=event.aggregate_version,
            )
            session.add(new_projection)

    async def _handle_order_cancelled(
        self,
        event: EventEnvelope,
        projection: OrderSummaryProjection | None,
        session: AsyncSession,
    ) -> None:
        payload = event.payload
        if projection is not None:
            if event.aggregate_version <= projection.last_aggregate_version:
                logger.debug(
                    "Stale or duplicate order.cancelled (v%d <= v%d) for order %s; ignoring",
                    event.aggregate_version,
                    projection.last_aggregate_version,
                    event.aggregate_id,
                )
                return

            # Irreversible terminal transition
            projection.status = "CANCELLED"
            projection.last_event_type = event.event_type
            projection.last_aggregate_version = event.aggregate_version
        else:
            # Out-of-order arrival before order.created.
            # Cancellation is terminal and does not wait for deferral.
            new_projection = OrderSummaryProjection(
                order_id=event.aggregate_id,
                order_number=str(
                    payload.get("order_number", f"ORD-{event.aggregate_id}")
                ),
                customer_id=None,
                status="CANCELLED",
                payment_status="NOT_INITIATED",
                total_payable_paise=int(payload.get("total_payable_paise", 0)),
                currency=str(payload.get("currency", "INR")),
                item_count=int(payload.get("item_count", 0)),
                last_event_type=event.event_type,
                last_aggregate_version=event.aggregate_version,
            )
            session.add(new_projection)

    async def _handle_payment_succeeded(
        self,
        event: EventEnvelope,
        projection: OrderSummaryProjection | None,
        session: AsyncSession,
    ) -> None:
        payload = event.payload
        if projection is not None:
            projection.payment_status = "SUCCEEDED"
            if event.aggregate_version > projection.last_aggregate_version:
                projection.last_aggregate_version = event.aggregate_version
            projection.last_event_type = event.event_type
        else:
            # Cross-topic resilience: payment.succeeded arrived before order.created
            new_projection = OrderSummaryProjection(
                order_id=event.aggregate_id,
                order_number=f"ORD-{event.aggregate_id}",
                customer_id=None,
                status="PENDING_PAYMENT",
                payment_status="SUCCEEDED",
                total_payable_paise=int(payload.get("amount_paise", 0)),
                currency=str(payload.get("currency", "INR")),
                item_count=0,
                last_event_type=event.event_type,
                last_aggregate_version=event.aggregate_version,
            )
            session.add(new_projection)
