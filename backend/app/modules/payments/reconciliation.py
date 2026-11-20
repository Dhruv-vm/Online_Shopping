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
    CaptureReconciliationStatus,
    CaptureStatus,
    Payment,
    PaymentAttemptStatus,
    RefundStatus,
)
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    ReconcilePendingResponse,
    ResolveAmbiguityResponse,
)
from app.modules.payments.service import (
    process_payment_capture_and_fulfillment,
    reconcile_rejected_partial_capture_order,
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
        pending_cutoff_minutes: int = 5,
        order_id: uuid.UUID | None = None,
    ) -> ReconcilePendingResponse:
        """Automated reconciliation for ambiguous attempts, pending payments, and stuck webhook leases."""
        now = datetime.now(UTC)
        cutoff_ambiguous = now - timedelta(minutes=5)
        if pending_cutoff_minutes <= 0:
            cutoff_pending = now + timedelta(seconds=10)
        else:
            cutoff_pending = now - timedelta(minutes=pending_cutoff_minutes)

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

        # 2. Reconcile pending payments older than cutoff (Missed-Webhook Recovery)
        pending_payments = await self.repo.get_pending_payments_for_reconciliation(
            cutoff_datetime=cutoff_pending, limit=batch_size, order_id=order_id
        )
        for payment in pending_payments:
            if not payment.provider_order_id:
                continue
            try:
                rzp_order = await self.client.fetch_order(payment.provider_order_id)
                if rzp_order.get("id") != payment.provider_order_id:
                    continue

                rzp_order_status = rzp_order.get("status")
                if rzp_order_status == "paid":
                    rzp_payments = await self.client.fetch_order_payments(
                        payment.provider_order_id
                    )
                    for p_entity in rzp_payments:
                        capture = await process_payment_capture_and_fulfillment(
                            session=self.session,
                            repo=self.repo,
                            reservation_service=self.reservation_service,
                            order_id=payment.order_id,
                            payment_entity=p_entity,
                            source="RECONCILIATION",
                            payment_id=payment.id,
                            client=self.client,
                        )
                        if capture and capture.is_fulfillment_eligible:
                            locked_order = await self.repo.get_order_by_id(
                                payment.order_id
                            )
                            if (
                                locked_order
                                and locked_order.status == OrderStatus.CONFIRMED.value
                                and locked_order.fulfilling_capture_id == capture.id
                            ):
                                reconciled_payments_count += 1
                elif rzp_order_status in ("attempted", "created"):
                    rzp_payments = await self.client.fetch_order_payments(
                        payment.provider_order_id
                    )
                    for p_entity in rzp_payments:
                        p_status = p_entity.get("status")
                        if p_status == "captured":
                            capture = await process_payment_capture_and_fulfillment(
                                session=self.session,
                                repo=self.repo,
                                reservation_service=self.reservation_service,
                                order_id=payment.order_id,
                                payment_entity=p_entity,
                                source="RECONCILIATION",
                                payment_id=payment.id,
                                client=self.client,
                            )
                            if capture and capture.is_fulfillment_eligible:
                                locked_order = await self.repo.get_order_by_id(
                                    payment.order_id
                                )
                                if (
                                    locked_order
                                    and locked_order.status
                                    == OrderStatus.CONFIRMED.value
                                    and locked_order.fulfilling_capture_id == capture.id
                                ):
                                    reconciled_payments_count += 1
                        elif p_status == "failed":
                            locked_p = await self.repo.get_payment_by_id_for_update(
                                payment.id
                            )
                            if (
                                locked_p
                                and locked_p.status
                                == PaymentAttemptStatus.PENDING.value
                            ):
                                locked_p.status = PaymentAttemptStatus.FAILED.value
                                locked_p.error_code = (
                                    p_entity.get("error_code")
                                    or "GATEWAY_PAYMENT_FAILED"
                                )
                                locked_p.error_description = p_entity.get(
                                    "error_description"
                                )
                                await self.session.commit()
            except Exception as exc:
                logger.error(
                    "Error checking pending payment %s: %s", payment.id, str(exc)
                )

        # 3. Reclaim and process expired webhook leases
        worker_id = f"reconciler-{uuid.uuid4().hex[:8]}"
        claimed_events = await self.repo.claim_pending_webhook_events(
            worker_id=worker_id, batch_size=batch_size, lease_seconds=30
        )
        for event in claimed_events:
            success = await self.webhook_service.process_webhook_event(
                event.id, worker_id=worker_id
            )
            if success:
                reconciled_webhooks_count += 1

        # 4. Reconcile pending / requested refunds older than 2 minutes
        cutoff_refunds = now - timedelta(minutes=2)
        pending_refunds = await self.repo.get_pending_refunds_for_reconciliation(
            cutoff_datetime=cutoff_refunds, limit=batch_size
        )
        for refund in pending_refunds:
            try:
                rzp_rfnd = None
                if refund.provider_refund_id:
                    rzp_rfnd = await self.client.fetch_refund_by_id(
                        refund.provider_refund_id
                    )
                else:
                    capture = await self.repo.get_capture_by_id(refund.capture_id)
                    if capture and capture.provider_payment_id:
                        rfnds = await self.client.fetch_payment_refunds(
                            capture.provider_payment_id
                        )
                        rzp_rfnd = next(
                            (
                                r
                                for r in rfnds
                                if r.get("amount") == refund.amount_paise
                            ),
                            None,
                        )

                if rzp_rfnd:
                    locked_rfnd = await self.repo.get_refund_by_id(refund.id)
                    if locked_rfnd:
                        # Never regress an already processed refund
                        if locked_rfnd.status == RefundStatus.REFUND_PROCESSED.value:
                            continue

                        locked_rfnd.provider_refund_id = rzp_rfnd.get("id")
                        if rzp_rfnd.get("status") == "processed":
                            locked_rfnd.status = RefundStatus.REFUND_PROCESSED.value
                            locked_rfnd.processed_at = datetime.now(UTC)
                            locked_rfnd.error_code = None
                            locked_rfnd.error_description = None
                            await self.session.flush()

                            locked_capture = (
                                await self.repo.get_capture_by_id_for_update(
                                    refund.capture_id
                                )
                            )
                            if locked_capture:
                                processed_sum = await self.repo.get_processed_refunds_sum_for_capture(
                                    locked_capture.id
                                )
                                if processed_sum >= locked_capture.amount_paise:
                                    locked_capture.status = CaptureStatus.REFUNDED.value
                                elif processed_sum > 0:
                                    locked_capture.status = (
                                        CaptureStatus.PARTIALLY_REFUNDED.value
                                    )

                            locked_order = await self.repo.get_order_by_id_for_update(
                                refund.order_id
                            )
                            if locked_order:
                                order_processed_sum = (
                                    await self.repo.get_processed_refunds_sum_for_order(
                                        refund.order_id
                                    )
                                )
                                if (
                                    order_processed_sum
                                    >= locked_order.total_payable_paise
                                ):
                                    locked_order.payment_status = (
                                        PaymentStatus.REFUNDED.value
                                    )
                                elif order_processed_sum > 0:
                                    locked_order.payment_status = (
                                        PaymentStatus.PARTIALLY_REFUNDED.value
                                    )
                        elif rzp_rfnd.get("status") == "failed":
                            if (
                                locked_rfnd.status
                                != RefundStatus.REFUND_PROCESSED.value
                            ):
                                locked_rfnd.status = RefundStatus.REFUND_FAILED.value
                                locked_rfnd.error_code = (
                                    rzp_rfnd.get("error_code") or "PROVIDER_FAILED"
                                )
                                locked_rfnd.error_description = rzp_rfnd.get(
                                    "error_description"
                                )
                    await self.session.commit()
            except Exception as exc:
                logger.error("Error reconciling refund %s: %s", refund.id, str(exc))

        # 5. Reconcile rejected partial captures where reservation release previously failed
        reconciled_partial_captures = await self.reconcile_unresolved_partial_captures(
            limit=batch_size
        )
        reconciled_payments_count += reconciled_partial_captures

        return ReconcilePendingResponse(
            reconciled_payments_count=reconciled_payments_count,
            reconciled_webhooks_count=reconciled_webhooks_count,
            ambiguous_attempts_resolved=ambiguous_resolved_count,
        )

    async def reconcile_unresolved_partial_captures(
        self,
        limit: int = 50,
    ) -> int:
        """Finds non-cancelled orders in REQUIRES_RECONCILIATION that have rejected partial captures,
        and retries reservation release and order cancellation."""
        orders = await self.repo.get_orders_requiring_partial_capture_reconciliation(
            limit=limit
        )
        resolved_count = 0
        for order in orders:
            locked_order = await self.repo.get_order_by_id_for_update(order.id)
            if (
                not locked_order
                or locked_order.status == OrderStatus.CANCELLED.value
                or locked_order.payment_status
                != PaymentStatus.REQUIRES_RECONCILIATION.value
            ):
                continue
            if locked_order.fulfilling_capture_id is not None:
                continue

            success = await reconcile_rejected_partial_capture_order(
                order=locked_order,
                reservation_service=self.reservation_service,
                session=self.session,
            )
            if success:
                history = OrderStatusHistory(
                    order_id=locked_order.id,
                    from_status=locked_order.status,
                    to_status=OrderStatus.CANCELLED.value,
                    reason="PARTIAL_CAPTURE_REJECTED",
                )
                self.session.add(history)

                outbox_event = OutboxEvent(
                    aggregate_type="Order",
                    aggregate_id=locked_order.id,
                    event_type="order.cancelled",
                    schema_version=1,
                    aggregate_version=locked_order.version,
                    payload={
                        "order_id": str(locked_order.id),
                        "order_number": locked_order.order_number,
                        "status": "CANCELLED",
                        "cancel_reason": "PARTIAL_CAPTURE_REJECTED",
                        "aggregate_version": locked_order.version,
                    },
                    status=OutboxStatus.PENDING.value,
                )
                self.session.add(outbox_event)

                # Ensure automated refund exists and is queued/dispatched
                caps = await self.repo.get_captures_for_order(locked_order.id)
                for cap in caps:
                    if (
                        cap.reconciliation_status
                        == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
                    ):
                        await self.webhook_service._trigger_auto_refund(
                            cap, "PARTIAL_CAPTURE_REJECTED"
                        )

                await self.session.commit()
                resolved_count += 1
            else:
                await self.session.rollback()

        return resolved_count

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

            # 1. Release inventory hold first under atomic reservation management
            try:
                if locked_order.reservation_id:
                    await self.reservation_service.release_reservation(
                        reservation_id=locked_order.reservation_id,
                        reason="AMBIGUITY_SLA_EXPIRED",
                        internal=True,
                    )
            except Exception as e:
                logger.error(
                    "Reservation %s could not be released for order %s: %s; blocking payment initiation and deferring cancellation",
                    locked_order.reservation_id,
                    locked_order.id,
                    e,
                )
                locked_order.payment_status = (
                    PaymentStatus.REQUIRES_RECONCILIATION.value
                )
                await self.session.commit()
                continue

            # 2. Only after stock release succeeds, permanently cancel order
            locked_order.version += 1
            locked_order.status = OrderStatus.CANCELLED.value
            locked_order.payment_status = PaymentStatus.FAILED.value

            history = OrderStatusHistory(
                order_id=locked_order.id,
                from_status=OrderStatus.PENDING_PAYMENT.value,
                to_status=OrderStatus.CANCELLED.value,
                reason="AMBIGUITY_SLA_EXPIRED",
            )
            self.session.add(history)

            # 3. Mark any open payment attempts FAILED
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

            # 4. Outbox event
            outbox_event = OutboxEvent(
                aggregate_type="Order",
                aggregate_id=locked_order.id,
                event_type="order.cancelled",
                schema_version=1,
                aggregate_version=locked_order.version,
                payload={
                    "order_id": str(locked_order.id),
                    "order_number": locked_order.order_number,
                    "status": "CANCELLED",
                    "cancel_reason": "AMBIGUITY_SLA_EXPIRED",
                    "aggregate_version": locked_order.version,
                },
                status=OutboxStatus.PENDING.value,
            )
            self.session.add(outbox_event)

            await self.session.commit()
            cancelled_count += 1

        return cancelled_count
