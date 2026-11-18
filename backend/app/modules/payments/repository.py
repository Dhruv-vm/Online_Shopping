import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import Order
from app.modules.payments.models import (
    Payment,
    PaymentAttemptStatus,
    PaymentCapture,
    PaymentRefund,
    RefundStatus,
    WebhookEvent,
    WebhookEventStatus,
)


class PaymentRepository:
    """Repository handling database operations for payments, captures, refunds, and webhooks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_order_by_id_for_update(self, order_id: uuid.UUID) -> Order | None:
        """Lock order row following universal lock hierarchy: orders -> payments -> captures."""
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_payment_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_payment_by_id_for_update(
        self, payment_id: uuid.UUID
    ) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_payment_by_order_and_idempotency(
        self, order_id: uuid.UUID, idempotency_key: str
    ) -> Payment | None:
        stmt = select(Payment).where(
            Payment.order_id == order_id,
            Payment.idempotency_key == idempotency_key,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_payment_by_provider_order_id(
        self, provider_order_id: str
    ) -> Payment | None:
        stmt = select(Payment).where(Payment.provider_order_id == provider_order_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_or_ambiguous_attempt_for_order(
        self, order_id: uuid.UUID
    ) -> Payment | None:
        stmt = (
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status.in_(
                    [
                        PaymentAttemptStatus.CREATING.value,
                        PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
                        PaymentAttemptStatus.PENDING.value,
                        PaymentAttemptStatus.AUTHORIZED.value,
                    ]
                ),
            )
            .order_by(Payment.attempt_number.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_payment_for_order(self, order_id: uuid.UUID) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.attempt_number.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_attempt_for_order(self, order_id: uuid.UUID) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.attempt_number.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_next_attempt_number(self, order_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(Payment.attempt_number), 0)).where(
            Payment.order_id == order_id
        )
        res = await self.session.execute(stmt)
        max_num = res.scalar_one()
        return max_num + 1

    async def create_payment(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_capture_by_provider_payment_id(
        self, provider: str, provider_payment_id: str
    ) -> PaymentCapture | None:
        stmt = select(PaymentCapture).where(
            PaymentCapture.provider == provider,
            PaymentCapture.provider_payment_id == provider_payment_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_capture_by_id(self, capture_id: uuid.UUID) -> PaymentCapture | None:
        stmt = select(PaymentCapture).where(PaymentCapture.id == capture_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_capture_by_id_for_update(
        self, capture_id: uuid.UUID
    ) -> PaymentCapture | None:
        stmt = (
            select(PaymentCapture)
            .where(PaymentCapture.id == capture_id)
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_captures_for_order(self, order_id: uuid.UUID) -> list[PaymentCapture]:
        stmt = (
            select(PaymentCapture)
            .where(PaymentCapture.order_id == order_id)
            .order_by(PaymentCapture.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_capture(self, capture: PaymentCapture) -> PaymentCapture:
        self.session.add(capture)
        await self.session.flush()
        return capture

    async def get_refund_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentRefund | None:
        stmt = select(PaymentRefund).where(
            PaymentRefund.idempotency_key == idempotency_key
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_refund_by_id(self, refund_id: uuid.UUID) -> PaymentRefund | None:
        stmt = select(PaymentRefund).where(PaymentRefund.id == refund_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_refunds_sum_for_capture(self, capture_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.sum(PaymentRefund.amount_paise), 0)).where(
            PaymentRefund.capture_id == capture_id,
            PaymentRefund.status.in_(
                [
                    RefundStatus.REFUND_REQUESTED.value,
                    RefundStatus.REFUND_PENDING.value,
                    RefundStatus.REFUND_PROCESSED.value,
                ]
            ),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def create_refund(self, refund: PaymentRefund) -> PaymentRefund:
        self.session.add(refund)
        await self.session.flush()
        return refund

    async def get_webhook_event_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> WebhookEvent | None:
        stmt = select(WebhookEvent).where(
            WebhookEvent.provider == provider,
            WebhookEvent.provider_event_id == provider_event_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_webhook_event(self, event: WebhookEvent) -> WebhookEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def claim_pending_webhook_events(
        self, worker_id: str, batch_size: int = 10, lease_seconds: int = 30
    ) -> list[WebhookEvent]:
        """Claim a batch of pending or expired-lease webhook events with SKIP LOCKED."""
        now = datetime.now(UTC)
        lease_expiry = now + timedelta(seconds=lease_seconds)

        subquery = (
            select(WebhookEvent.id)
            .where(
                (WebhookEvent.status == WebhookEventStatus.PENDING.value)
                | (
                    (WebhookEvent.status == WebhookEventStatus.PROCESSING.value)
                    & (WebhookEvent.claim_expires_at < now)
                )
            )
            .order_by(WebhookEvent.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )

        claim_stmt = (
            update(WebhookEvent)
            .where(WebhookEvent.id.in_(subquery))
            .values(
                status=WebhookEventStatus.PROCESSING.value,
                claimed_by=worker_id,
                claim_expires_at=lease_expiry,
                retry_count=WebhookEvent.retry_count + 1,
                updated_at=now,
            )
            .returning(WebhookEvent)
        )

        res = await self.session.execute(claim_stmt)
        return list(res.scalars().all())

    async def get_expired_ambiguous_payments(
        self, cutoff_datetime: datetime, limit: int = 50
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(
                Payment.status == PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
                Payment.created_at <= cutoff_datetime,
            )
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_pending_payments_for_reconciliation(
        self, cutoff_datetime: datetime, limit: int = 50
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(
                Payment.status.in_(
                    [
                        PaymentAttemptStatus.PENDING.value,
                        PaymentAttemptStatus.AUTHORIZED.value,
                    ]
                ),
                Payment.created_at <= cutoff_datetime,
            )
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_orders_for_sla_expiry(
        self, cutoff_datetime: datetime, limit: int = 50
    ) -> list[Order]:
        """Fetch orders eligible for 75-minute SLA cancellation."""
        stmt = (
            select(Order)
            .where(
                Order.status == "PENDING_PAYMENT",
                or_(
                    Order.created_at <= cutoff_datetime,
                    Order.payment_window_expires_at <= cutoff_datetime,
                ),
            )
            .order_by(Order.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
