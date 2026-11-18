import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import (
    OrderStatus,
    OrderStatusHistory,
    OutboxEvent,
    OutboxStatus,
    PaymentStatus,
)
from app.modules.payments.client import RazorpayClient
from app.modules.payments.models import (
    Payment,
    PaymentAttemptStatus,
)
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    ReconcilePendingResponse,
    ResolveAmbiguityResponse,
)
from app.modules.payments.webhook import WebhookService


class ReconciliationService:
    """Service handling background reconciliation, manual ambiguity resolution, and the 75m terminal SLA."""

    def __init__(
        self,
        session: AsyncSession,
        client: RazorpayClient | None = None,
    ):
        self.session = session
        self.repo = PaymentRepository(session)
        self.client = client or RazorpayClient()
        self.reservation_service = ReservationService(session)
        self.webhook_service = WebhookService(session, self.client)

    async def reconcile_pending(
        self,
        batch_size: int = 50,
        max_age_minutes: int = 1440,
    ) -> ReconcilePendingResponse:
        """Automated reconciliation for ambiguous attempts, pending payments, and stuck webhook leases."""
        now = datetime.now(UTC)
        cutoff_ambiguous = now - timedelta(minutes=5)
        cutoff_pending = now - timedelta(minutes=5)

        ambiguous_resolved_count = 0
        reconciled_payments_count = 0
        reconciled_webhooks_count = 0

        # 1. Resolve ambiguous CREATION_AMBIGUOUS attempts via Razorpay receipt search
        ambiguous_payments = await self.repo.get_expired_ambiguous_payments(
            cutoff_datetime=cutoff_ambiguous, limit=batch_size
        )
        for payment in ambiguous_payments:
            order = await self.repo.get_order_by_id(payment.order_id)
            if not order:
                continue
            receipt = f"{order.order_number}-{payment.attempt_number}"[:40]
            try:
                orders_list = await self.client.fetch_orders_by_receipt(receipt=receipt)
                matching = next(
                    (
                        o
                        for o in orders_list
                        if o.get("amount") == payment.amount_paise
                        and o.get("receipt") == receipt
                    ),
                    None,
                )
                if matching:
                    locked_p = await self.repo.get_payment_by_id_for_update(payment.id)
                    if locked_p:
                        locked_p.provider_order_id = matching["id"]
                        locked_p.status = PaymentAttemptStatus.PENDING.value
                    locked_o = await self.repo.get_order_by_id_for_update(order.id)
                    if locked_o:
                        locked_o.payment_status = PaymentStatus.PENDING.value
                    await self.session.commit()
                    ambiguous_resolved_count += 1
            except Exception as exc:
                logger.error(
                    "Error reconciling ambiguous payment %s: %s", payment.id, str(exc)
                )

        # 2. Reconcile pending payments older than 5 minutes
        pending_payments = await self.repo.get_pending_payments_for_reconciliation(
            cutoff_datetime=cutoff_pending, limit=batch_size
        )
        for payment in pending_payments:
            if not payment.provider_order_id:
                continue
            try:
                rzp_order = await self.client.fetch_order(payment.provider_order_id)
                if rzp_order.get("status") == "paid":
                    # Order paid on gateway; verify or update
                    reconciled_payments_count += 1
            except Exception as exc:
                logger.error(
                    "Error checking pending payment %s: %s", payment.id, str(exc)
                )

        # 3. Reclaim and process expired webhook leases
        claimed_events = await self.repo.claim_pending_webhook_events(
            worker_id="reconciler-worker", batch_size=batch_size, lease_seconds=30
        )
        for event in claimed_events:
            success = await self.webhook_service.process_webhook_event(event.id)
            if success:
                reconciled_webhooks_count += 1

        return ReconcilePendingResponse(
            reconciled_payments_count=reconciled_payments_count,
            reconciled_webhooks_count=reconciled_webhooks_count,
            ambiguous_attempts_resolved=ambiguous_resolved_count,
        )

    async def resolve_ambiguity_manual(
        self,
        payment_id: uuid.UUID,
        action: str,
        provider_order_id: str | None = None,
        operator_id: str = "operator",
        operator_reason: str = "manual-review",
    ) -> ResolveAmbiguityResponse:
        """Manual operational review endpoint for CREATION_AMBIGUOUS payment attempts."""
        payment = await self.repo.get_payment_by_id_for_update(payment_id)
        if not payment:
            raise AppException(
                code="PAYMENT_NOT_FOUND", message="Payment not found", status_code=404
            )

        if payment.status not in (
            PaymentAttemptStatus.CREATING.value,
            PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
        ):
            raise AppException(
                code="PAYMENT_NOT_AMBIGUOUS",
                message=f"Payment status is '{payment.status}'; only ambiguous attempts can be manually resolved.",
                status_code=400,
            )

        order = await self.repo.get_order_by_id_for_update(payment.order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        now = datetime.now(UTC)
        metadata = dict(payment.metadata_json or {})
        metadata["manual_resolution"] = {
            "action": action,
            "operator_id": operator_id,
            "operator_reason": operator_reason,
            "resolved_at": now.isoformat(),
        }
        payment.metadata_json = metadata

        if action == "CONFIRM_ABSENT":
            payment.status = PaymentAttemptStatus.FAILED.value
            payment.error_code = "OPERATOR_CONFIRMED_ABSENT"
            payment.error_description = operator_reason
            order.payment_status = PaymentStatus.FAILED.value
            status_result = PaymentAttemptStatus.FAILED.value
        elif action == "LINK_PROVIDER_ORDER":
            if not provider_order_id:
                raise AppException(
                    code="MISSING_PROVIDER_ORDER_ID",
                    message="provider_order_id is required when action is LINK_PROVIDER_ORDER",
                    status_code=400,
                )
            # Verify order exists on gateway
            rzp_order = await self.client.fetch_order(provider_order_id)
            if rzp_order.get("amount") != payment.amount_paise:
                raise AppException(
                    code="AMOUNT_MISMATCH",
                    message="Gateway order amount does not match local payment attempt amount",
                    status_code=400,
                )
            payment.provider_order_id = provider_order_id
            payment.status = PaymentAttemptStatus.PENDING.value
            order.payment_status = PaymentStatus.PENDING.value
            status_result = PaymentAttemptStatus.PENDING.value
        else:
            raise AppException(
                code="INVALID_ACTION",
                message="Invalid resolution action",
                status_code=400,
            )

        await self.session.commit()

        return ResolveAmbiguityResponse(
            payment_id=payment.id,
            status=status_result,
            action_taken=action,
            resolved_at=now,
        )

    async def execute_75m_sla_escalation_job(self, limit: int = 50) -> int:
        """Terminal 75-minute SLA job: permanently cancels order, fails attempts, releases reservation once."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=75)

        orders = await self.repo.get_orders_for_sla_expiry(
            cutoff_datetime=cutoff, limit=limit
        )
        cancelled_count = 0

        for order in orders:
            locked_order = await self.repo.get_order_by_id_for_update(order.id)
            if (
                not locked_order
                or locked_order.status != OrderStatus.PENDING_PAYMENT.value
            ):
                continue
            if locked_order.fulfilling_capture_id is not None:
                continue

            # 1. Permanently cancel order
            locked_order.status = OrderStatus.CANCELLED.value
            locked_order.payment_status = PaymentStatus.FAILED.value

            history = OrderStatusHistory(
                order_id=locked_order.id,
                from_status=OrderStatus.PENDING_PAYMENT.value,
                to_status=OrderStatus.CANCELLED.value,
                reason="AMBIGUITY_SLA_EXPIRED",
            )
            self.session.add(history)

            # 2. Mark any open payment attempts FAILED
            stmt = (
                select(Payment)
                .where(
                    Payment.order_id == locked_order.id,
                    Payment.status.in_(
                        [
                            PaymentAttemptStatus.CREATING.value,
                            PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
                            PaymentAttemptStatus.PENDING.value,
                            PaymentAttemptStatus.AUTHORIZED.value,
                        ]
                    ),
                )
                .with_for_update()
            )
            res = await self.session.execute(stmt)
            for payment in res.scalars().all():
                payment.status = PaymentAttemptStatus.FAILED.value
                payment.error_code = "OPERATIONAL_SLA_EXPIRED"
                payment.error_description = (
                    "Manual review SLA expired at 75m; quarantined stock released"
                )

            # 3. Release inventory hold exactly once
            try:
                await self.reservation_service.release_reservation(
                    reservation_id=locked_order.reservation_id,
                    reason="AMBIGUITY_SLA_EXPIRED",
                    internal=True,
                )
            except Exception as e:
                logger.warning(
                    f"Reservation {locked_order.reservation_id} could not be released for order {locked_order.id}: {e}"
                )

            # 4. Outbox event
            outbox_event = OutboxEvent(
                aggregate_type="Order",
                aggregate_id=locked_order.id,
                event_type="order.cancelled",
                schema_version=1,
                payload={
                    "order_id": str(locked_order.id),
                    "order_number": locked_order.order_number,
                    "status": "CANCELLED",
                    "cancel_reason": "AMBIGUITY_SLA_EXPIRED",
                },
                status=OutboxStatus.PENDING.value,
            )
            self.session.add(outbox_event)
            await self.session.commit()
            cancelled_count += 1

        return cancelled_count
