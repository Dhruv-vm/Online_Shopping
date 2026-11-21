import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OrderStatusHistory,
    OutboxEvent,
    OutboxStatus,
    PaymentStatus,
)
from app.modules.payments.client import RazorpayClient
from app.modules.payments.exceptions import (
    ExceedsRefundableBalanceError,
    InvalidPaymentSignatureError,
    PartialCaptureRejectedError,
    PaymentAlreadyConfirmedError,
    PaymentAttemptAmbiguousError,
    PaymentGatewayError,
    PaymentGatewayTimeoutError,
    PaymentNotFoundError,
    PaymentWindowExpiredError,
)
from app.modules.payments.models import (
    CaptureReconciliationStatus,
    CaptureStatus,
    Payment,
    PaymentAttemptStatus,
    PaymentCapture,
    PaymentRefund,
    RefundStatus,
)
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    CreateRefundRequest,
    PaymentInitiateResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    RefundResponse,
)


async def reconcile_rejected_partial_capture_order(
    order: Order,
    reservation_service: ReservationService | None,
    session: AsyncSession | None = None,
) -> bool:
    """Attempts to release the order's reservation hold on rejected partial capture.
    Only marks the order CANCELLED and payment_status FAILED if reservation release succeeds.
    If release fails, marks payment_status REQUIRES_RECONCILIATION and leaves order non-cancelled.
    Uses a savepoint (begin_nested) to safely isolate database-level statement failures (such as
    lock_timeout or postgres aborted transactions) so the outer transaction holding the capture
    ledger, refund intent, and order reconciliation state is not poisoned.
    Returns True if release succeeded or order was already cancelled.
    """
    if order.status == OrderStatus.CANCELLED.value:
        return True

    release_succeeded = False
    effective_session = session or (
        reservation_service.session if reservation_service else None
    )

    if reservation_service and order.reservation_id:
        try:
            if effective_session:
                async with effective_session.begin_nested():
                    await reservation_service.release_reservation(
                        reservation_id=order.reservation_id,
                        reason="PARTIAL_CAPTURE_REJECTED",
                        internal=True,
                    )
            else:
                await reservation_service.release_reservation(
                    reservation_id=order.reservation_id,
                    reason="PARTIAL_CAPTURE_REJECTED",
                    internal=True,
                )
            release_succeeded = True
        except Exception as exc:
            logger.error(
                "Failed to release reservation on partial capture for order %s: %s",
                order.id,
                exc,
            )
            release_succeeded = False

    if release_succeeded:
        order.version += 1
        order.status = OrderStatus.CANCELLED.value
        order.payment_status = PaymentStatus.FAILED.value
    else:
        order.payment_status = PaymentStatus.REQUIRES_RECONCILIATION.value

    return release_succeeded


async def dispatch_automated_refund(
    session: AsyncSession,
    repo: PaymentRepository,
    client: RazorpayClient,
    capture: PaymentCapture,
    reason: str,
) -> PaymentRefund:
    """Helper to create automated refund intent for anomalies and late captures.
    Guarantees capture and refund intent are committed to PostgreSQL before calling external gateway.
    """
    refund_idempotency = f"auto-refund-{capture.id}"
    existing = await repo.get_refund_by_idempotency_key(refund_idempotency)
    if not existing:
        existing = await repo.get_refund_by_idempotency_key(
            f"webhook-auto-refund-{capture.id}"
        )
    if existing:
        return existing

    refund = PaymentRefund(
        capture_id=capture.id,
        payment_id=capture.payment_id,
        order_id=capture.order_id,
        idempotency_key=refund_idempotency,
        amount_paise=capture.amount_paise,
        currency=capture.currency,
        status=RefundStatus.REFUND_REQUESTED.value,
        reason=reason,
    )
    await repo.create_refund(refund)
    # CRITICAL: Commit capture AND refund intent to database BEFORE calling provider!
    await session.commit()

    # Trigger gateway refund outside transaction
    try:
        rzp_refund = await client.create_refund(
            payment_id=capture.provider_payment_id,
            amount_paise=capture.amount_paise,
            idempotency_key=refund_idempotency,
            receipt=f"RFND-{str(refund.id)[:30]}",
            notes={"reason": reason, "capture_id": str(capture.id)},
        )
        locked_refund = await repo.get_refund_by_id(refund.id)
        if locked_refund:
            locked_refund.provider_refund_id = rzp_refund.get("id")
            if rzp_refund.get("status") == "processed":
                locked_refund.status = RefundStatus.REFUND_PROCESSED.value
                locked_refund.processed_at = datetime.now(UTC)
                locked_capture = await repo.get_capture_by_id_for_update(capture.id)
                if locked_capture:
                    locked_capture.status = CaptureStatus.REFUNDED.value
            else:
                locked_refund.status = RefundStatus.REFUND_PENDING.value
                locked_refund.processed_at = None
        await session.commit()
    except PaymentGatewayTimeoutError:
        locked_refund = await repo.get_refund_by_id(refund.id)
        if locked_refund:
            locked_refund.status = RefundStatus.REFUND_PENDING.value
            locked_refund.processed_at = None
        await session.commit()
    except Exception as exc:
        logger.warning(
            "Automated refund failed to dispatch immediately; leaving in REFUND_PENDING: %s",
            str(exc),
        )
        locked_refund = await repo.get_refund_by_id(refund.id)
        if locked_refund:
            locked_refund.status = RefundStatus.REFUND_PENDING.value
            locked_refund.processed_at = None
            locked_refund.error_description = str(exc)
        await session.commit()

    return refund


async def process_payment_capture_and_fulfillment(
    session: AsyncSession,
    repo: PaymentRepository,
    reservation_service: ReservationService,
    order_id: uuid.UUID,
    payment_entity: dict[str, Any],
    source: str,
    payment_id: uuid.UUID | None = None,
    client: RazorpayClient | None = None,
) -> PaymentCapture | None:
    """Universal, transactionally safe payment-capture & fulfillment path shared across
    webhooks, payment verification, and background reconciliation.
    Follows strict universal lock hierarchy: orders -> payments -> captures.
    Uses SAVEPOINT isolation around reservation confirmation to protect against statement aborts.
    """
    provider_payment_id = payment_entity.get("id")
    provider_order_id = payment_entity.get("order_id")
    amount_paise = int(payment_entity.get("amount", 0))
    currency = payment_entity.get("currency", "INR")
    provider_status = payment_entity.get("status")
    method = payment_entity.get("method")
    acquirer_ref = (
        payment_entity.get("acquirer_data", {}).get("rrn")
        or payment_entity.get("acquirer_data", {}).get("upi_transaction_id")
        or payment_entity.get("acquirer_data", {}).get("bank_transaction_id")
    )
    captured_at_ts = payment_entity.get("created_at") or int(
        datetime.now(UTC).timestamp()
    )
    captured_at = datetime.fromtimestamp(captured_at_ts, tz=UTC)

    if not provider_payment_id:
        logger.warning(
            "Payment entity missing provider payment id; skipping fulfillment"
        )
        return None

    # 1. Universal lock hierarchy: lock Order FOR UPDATE first
    order = await repo.get_order_by_id_for_update(order_id)
    if not order:
        logger.error("Order %s not found during payment fulfillment", order_id)
        return None

    # 2. Universal lock hierarchy: lock Payment attempt FOR UPDATE next
    payment = None
    if payment_id:
        payment = await repo.get_payment_by_id_for_update(payment_id)
    elif provider_order_id:
        payment = await repo.get_payment_by_provider_order_id_for_update(
            provider_order_id
        )
    if not payment:
        payment = await repo.get_latest_payment_for_order_for_update(order.id)

    if not payment:
        payment = Payment(
            id=uuid.uuid4(),
            order_id=order.id,
            customer_id=order.customer_id,
            guest_token_hash="guest_fallback" if order.is_guest else None,
            provider="RAZORPAY_SANDBOX",
            provider_order_id=provider_order_id,
            provider_payment_id=provider_payment_id,
            idempotency_key=f"{source.lower()}_{provider_payment_id}",
            attempt_number=1,
            amount_paise=amount_paise,
            currency=currency,
            status=PaymentAttemptStatus.PENDING.value,
        )
        await repo.create_payment(payment)

    # Validate provider order ID matching
    if (
        payment.provider_order_id
        and provider_order_id
        and payment.provider_order_id != provider_order_id
    ):
        logger.error(
            "Payment attempt provider_order_id %s mismatch with provider payment order %s",
            payment.provider_order_id,
            provider_order_id,
        )
        return None

    # Status check: only 'captured' payments can fulfill orders
    if provider_status != "captured":
        logger.info(
            "Provider payment %s is in status '%s'; skipping fulfillment",
            provider_payment_id,
            provider_status,
        )
        if (
            provider_status == "failed"
            and payment.status != PaymentAttemptStatus.SUCCEEDED.value
        ):
            payment.status = PaymentAttemptStatus.FAILED.value
            payment.error_code = (
                payment_entity.get("error_code") or "GATEWAY_PAYMENT_FAILED"
            )
            payment.error_description = payment_entity.get("error_description")
            await session.commit()
        return None

    # 3. Check existing capture in payment ledger
    existing_capture = await repo.get_capture_by_provider_payment_id(
        provider="RAZORPAY_SANDBOX",
        provider_payment_id=provider_payment_id,
    )
    if existing_capture:
        if (
            order.fulfilling_capture_id == existing_capture.id
            and order.status == OrderStatus.CONFIRMED.value
        ):
            # Idempotent replay: already fulfilled
            return existing_capture

        if (
            existing_capture.reconciliation_status
            == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
        ):
            await reconcile_rejected_partial_capture_order(
                order=order,
                reservation_service=reservation_service,
                session=session,
            )
            await session.commit()
            if client:
                await dispatch_automated_refund(
                    session,
                    repo,
                    client,
                    existing_capture,
                    "PARTIAL_CAPTURE_REJECTED",
                )
            return existing_capture

        # If existing capture is eligible and order is not yet confirmed, reuse it to complete fulfillment
        if (
            existing_capture.is_fulfillment_eligible
            and order.status != OrderStatus.CONFIRMED.value
            and order.fulfilling_capture_id is None
        ):
            capture = existing_capture
        else:
            return existing_capture
    else:
        capture = None

    # 4. If no capture was previously recorded, validate eligibility and anomalies
    if capture is None:
        # Currency mismatch check
        if currency != order.currency:
            currency_anomaly = PaymentCapture(
                payment_id=payment.id,
                order_id=order.id,
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=provider_payment_id,
                provider_order_id=provider_order_id,
                amount_paise=amount_paise,
                currency=currency,
                status=CaptureStatus.CAPTURED.value,
                method=method,
                acquirer_reference=acquirer_ref,
                is_fulfillment_eligible=False,
                reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
                captured_at=captured_at,
            )
            await repo.create_capture(currency_anomaly)
            await session.commit()
            await session.refresh(currency_anomaly)
            if client:
                await dispatch_automated_refund(
                    session, repo, client, currency_anomaly, "CURRENCY_MISMATCH"
                )
            return currency_anomaly

        # Duplicate capture on already confirmed order
        if order.status == OrderStatus.CONFIRMED.value:
            anomaly_capture = PaymentCapture(
                payment_id=payment.id,
                order_id=order.id,
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=provider_payment_id,
                provider_order_id=provider_order_id,
                amount_paise=amount_paise,
                currency=currency,
                status=CaptureStatus.CAPTURED.value,
                method=method,
                acquirer_reference=acquirer_ref,
                is_fulfillment_eligible=False,
                reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
                captured_at=captured_at,
            )
            await repo.create_capture(anomaly_capture)
            await session.commit()
            await session.refresh(anomaly_capture)
            if client:
                await dispatch_automated_refund(
                    session,
                    repo,
                    client,
                    anomaly_capture,
                    "OVERPAYMENT_DUPLICATE_CAPTURE",
                )
            return anomaly_capture

        # Late capture on cancelled order
        if order.status == OrderStatus.CANCELLED.value:
            late_capture = PaymentCapture(
                payment_id=payment.id,
                order_id=order.id,
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=provider_payment_id,
                provider_order_id=provider_order_id,
                amount_paise=amount_paise,
                currency=currency,
                status=CaptureStatus.CAPTURED.value,
                method=method,
                acquirer_reference=acquirer_ref,
                is_fulfillment_eligible=False,
                reconciliation_status=CaptureReconciliationStatus.LATE_CAPTURE_ANOMALY.value,
                captured_at=captured_at,
            )
            await repo.create_capture(late_capture)
            await session.commit()
            await session.refresh(late_capture)
            if client:
                await dispatch_automated_refund(
                    session,
                    repo,
                    client,
                    late_capture,
                    "LATE_CAPTURE_AFTER_ORDER_CANCELLATION",
                )
            return late_capture

        # Partial capture underpayment check
        if amount_paise < order.total_payable_paise:
            partial_capture = PaymentCapture(
                payment_id=payment.id,
                order_id=order.id,
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=provider_payment_id,
                provider_order_id=provider_order_id,
                amount_paise=amount_paise,
                currency=currency,
                status=CaptureStatus.CAPTURED.value,
                method=method,
                acquirer_reference=acquirer_ref,
                is_fulfillment_eligible=False,
                reconciliation_status=CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value,
                captured_at=captured_at,
            )
            await repo.create_capture(partial_capture)
            payment.status = PaymentAttemptStatus.FAILED.value
            payment.error_code = "PARTIAL_CAPTURE_REJECTED"

            await reconcile_rejected_partial_capture_order(
                order=order,
                reservation_service=reservation_service,
                session=session,
            )
            await session.commit()
            await session.refresh(partial_capture)
            if client:
                await dispatch_automated_refund(
                    session,
                    repo,
                    client,
                    partial_capture,
                    "PARTIAL_CAPTURE_REJECTED",
                )
            return partial_capture

        # Overpayment check (amount > total_payable_paise)
        if amount_paise > order.total_payable_paise:
            overpayment_capture = PaymentCapture(
                payment_id=payment.id,
                order_id=order.id,
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=provider_payment_id,
                provider_order_id=provider_order_id,
                amount_paise=amount_paise,
                currency=currency,
                status=CaptureStatus.CAPTURED.value,
                method=method,
                acquirer_reference=acquirer_ref,
                is_fulfillment_eligible=False,
                reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
                captured_at=captured_at,
            )
            await repo.create_capture(overpayment_capture)
            await session.commit()
            await session.refresh(overpayment_capture)
            if client:
                await dispatch_automated_refund(
                    session,
                    repo,
                    client,
                    overpayment_capture,
                    "OVERPAYMENT_ANOMALY",
                )
            return overpayment_capture

        # Full valid eligible capture
        capture = PaymentCapture(
            payment_id=payment.id,
            order_id=order.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=provider_payment_id,
            provider_order_id=provider_order_id,
            amount_paise=amount_paise,
            currency=currency,
            status=CaptureStatus.CAPTURED.value,
            method=method,
            acquirer_reference=acquirer_ref,
            is_fulfillment_eligible=True,
            reconciliation_status=CaptureReconciliationStatus.NORMAL.value,
            captured_at=captured_at,
        )
        await repo.create_capture(capture)
        await session.flush()

    # 5. Savepoint-isolated reservation confirmation & order fulfillment
    reservation_confirmed = False
    try:
        async with session.begin_nested():
            await reservation_service.confirm_reservation(
                reservation_id=order.reservation_id,
                internal=True,
            )
        reservation_confirmed = True
    except Exception as exc:
        logger.error(
            "Reservation confirmation failed for order %s on capture %s: %s",
            order.id,
            capture.id,
            exc,
        )
        reservation_confirmed = False

    if reservation_confirmed:
        order.fulfilling_capture_id = capture.id
        from_status = order.status
        order.version += 1
        order.status = OrderStatus.CONFIRMED.value
        order.payment_status = PaymentStatus.SUCCEEDED.value
        for item in order.items:
            if item.fulfillment_status == OrderStatus.PENDING_PAYMENT.value:
                item.fulfillment_status = OrderStatus.CONFIRMED.value

        history = OrderStatusHistory(
            order_id=order.id,
            from_status=from_status,
            to_status=OrderStatus.CONFIRMED.value,
            reason=f"{source}_PAYMENT_CAPTURED",
        )
        session.add(history)

        payment.status = PaymentAttemptStatus.SUCCEEDED.value
        payment.provider_payment_id = provider_payment_id
        payment.method = method

        outbox_event = OutboxEvent(
            aggregate_type="Order",
            aggregate_id=order.id,
            event_type="order.confirmed",
            schema_version=1,
            aggregate_version=order.version,
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "fulfilling_capture_id": str(capture.id),
                "total_payable_paise": order.total_payable_paise,
                "currency": order.currency,
                "aggregate_version": order.version,
            },
            status=OutboxStatus.PENDING.value,
        )
        session.add(outbox_event)
        from app.core.notify import notify_retailer_users

        await notify_retailer_users(
            session,
            retailer_ids=[i.retailer_id for i in order.items],
            title=f"New paid order {order.order_number}",
            message="Payment is confirmed. Open Orders to pack and dispatch it.",
            event_type="retailer.order_paid",
        )
        await session.commit()
        await session.refresh(order)
        await session.refresh(capture)
        return capture
    else:
        # Reservation confirmation statement failed.
        # Capture is durably saved in PostgreSQL, but order is NOT fulfilled.
        # Order enters REQUIRES_RECONCILIATION so operator or recovery job can act safely.
        order.payment_status = PaymentStatus.REQUIRES_RECONCILIATION.value
        await session.commit()
        await session.refresh(order)
        await session.refresh(capture)
        return capture


class PaymentService:
    """Core payment gateway service for initiation, verification, and refunds."""

    def __init__(
        self,
        session: AsyncSession,
        client: RazorpayClient | None = None,
    ):
        self.session = session
        self.repo = PaymentRepository(session)
        self.client = client or RazorpayClient()
        self.reservation_service = ReservationService(session)

    async def _reusable_keyless_attempt(
        self, order_id: uuid.UUID, amount_paise: int, currency: str
    ) -> Payment | None:
        """For a request without an Idempotency-Key, return the order's open PENDING
        attempt (same amount and currency) instead of creating another Razorpay
        order. The caller holds the order row lock (SELECT ... FOR UPDATE)."""

        def reusable(p: Payment | None) -> bool:
            return (
                p is not None
                and p.status == PaymentAttemptStatus.PENDING.value
                and bool(p.provider_order_id)
                and p.amount_paise == amount_paise
                and p.currency == currency
            )

        active = await self.repo.get_active_or_ambiguous_attempt_for_order(order_id)
        if active is None:
            return None
        if active.status == PaymentAttemptStatus.CREATION_AMBIGUOUS.value:
            raise PaymentAttemptAmbiguousError()
        if active.status == PaymentAttemptStatus.CREATING.value:
            # Another request is creating the provider order right now: wait for it.
            active_id = active.id
            for _ in range(50):
                await asyncio.sleep(0.05)
                await self.session.rollback()
                active = await self.repo.get_payment_by_id(active_id)
                if (
                    active is None
                    or active.status != PaymentAttemptStatus.CREATING.value
                ):
                    break
            else:
                raise PaymentAttemptAmbiguousError(
                    "Concurrent payment attempt is currently in progress"
                )
            if reusable(active):
                return active
            # The rollbacks above released the order lock: take it again and re-check
            # before the caller creates a new attempt.
            await self.repo.get_order_by_id_for_update(order_id)
            active = await self.repo.get_active_or_ambiguous_attempt_for_order(order_id)
            if active is not None and active.status in (
                PaymentAttemptStatus.CREATING.value,
                PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
            ):
                raise PaymentAttemptAmbiguousError()
        return active if reusable(active) else None

    async def initiate_payment(
        self,
        order_id: uuid.UUID,
        idempotency_key: str | None,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> PaymentInitiateResponse:
        """Initiates a payment attempt using the pre-gateway two-transaction pattern.

        Without an ``idempotency_key`` the order's open PENDING attempt is reused, so
        repeated "Pay" clicks never create a second Razorpay order."""
        # ----------------------------------------------------------------------
        # TRANSACTION 1: Validate order and persist local CREATING payment attempt
        # ----------------------------------------------------------------------
        order = await self.repo.get_order_by_id_for_update(order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        order_id_val = order.id
        order_number_val = order.order_number
        order_customer_id = order.customer_id
        order_guest_token_hash = order.guest_token_hash
        order_status = order.status
        order_total_payable = order.total_payable_paise
        order_currency = order.currency
        order_expires_at = order.payment_window_expires_at

        # Ownership enforcement
        if customer_id is None and guest_token_hash is None:
            raise AppException(
                code="AUTHENTICATION_REQUIRED",
                message="Authentication or guest session is required",
                status_code=401,
            )
        if customer_id and order_customer_id != customer_id:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )
        if guest_token_hash and (
            order_guest_token_hash != guest_token_hash or order_customer_id is not None
        ):
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        # Order state validation
        if order_status == OrderStatus.CONFIRMED.value:
            raise PaymentAlreadyConfirmedError()
        if order_status == OrderStatus.CANCELLED.value:
            raise AppException(
                code="ORDER_NOT_PAYABLE",
                message="Cannot initiate payment on cancelled order",
                status_code=409,
            )
        if order.payment_status == PaymentStatus.REQUIRES_RECONCILIATION.value:
            raise PaymentAttemptAmbiguousError(
                "Order payment status requires reconciliation before retrying payment initiation"
            )

        # Checkout window expiry validation
        now = datetime.now(UTC)
        exp = order_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp <= now:
            raise PaymentWindowExpiredError()

        if idempotency_key is None:
            reusable = await self._reusable_keyless_attempt(
                order_id, order_total_payable, order_currency
            )
            if reusable is not None:
                return PaymentInitiateResponse(
                    payment_id=reusable.id,
                    order_id=order_id_val,
                    order_number=order_number_val,
                    provider=reusable.provider,
                    provider_order_id=reusable.provider_order_id,
                    razorpay_key_id=self.client.key_id,
                    amount_paise=reusable.amount_paise,
                    currency=reusable.currency,
                    status=reusable.status,
                    attempt_number=reusable.attempt_number,
                    payment_window_expires_at=order_expires_at,
                )
            idempotency_key = f"auto-{uuid.uuid4()}"

        # Check existing payment attempt with identical idempotency key
        existing_attempt = await self.repo.get_payment_by_order_and_idempotency(
            order_id, idempotency_key
        )
        if not existing_attempt:
            active_attempt = await self.repo.get_active_or_ambiguous_attempt_for_order(
                order_id
            )
            if active_attempt and active_attempt.idempotency_key == idempotency_key:
                existing_attempt = active_attempt

        if existing_attempt:
            if existing_attempt.status == PaymentAttemptStatus.SUCCEEDED.value:
                raise PaymentAlreadyConfirmedError()
            if existing_attempt.status == PaymentAttemptStatus.CREATION_AMBIGUOUS.value:
                raise PaymentAttemptAmbiguousError()
            if existing_attempt.status == PaymentAttemptStatus.CREATING.value:
                # Concurrent request in progress with same idempotency key: wait for completion
                for _ in range(50):
                    await asyncio.sleep(0.05)
                    await self.session.rollback()
                    refreshed = await self.repo.get_payment_by_order_and_idempotency(
                        order_id, idempotency_key
                    )
                    if (
                        refreshed
                        and refreshed.status == PaymentAttemptStatus.PENDING.value
                        and refreshed.provider_order_id
                    ):
                        return PaymentInitiateResponse(
                            payment_id=refreshed.id,
                            order_id=order_id_val,
                            order_number=order_number_val,
                            provider=refreshed.provider,
                            provider_order_id=refreshed.provider_order_id,
                            razorpay_key_id=self.client.key_id,
                            amount_paise=refreshed.amount_paise,
                            currency=refreshed.currency,
                            status=refreshed.status,
                            attempt_number=refreshed.attempt_number,
                            payment_window_expires_at=order_expires_at,
                        )
                    if (
                        refreshed
                        and refreshed.status != PaymentAttemptStatus.CREATING.value
                    ):
                        break
                raise PaymentAttemptAmbiguousError()

            if existing_attempt.status == PaymentAttemptStatus.FAILED.value:
                raise AppException(
                    code="PAYMENT_ATTEMPT_FAILED",
                    message="Cannot reuse an idempotency key from a permanently failed payment attempt. Please use a new key.",
                    status_code=409,
                )
            if (
                existing_attempt.status == PaymentAttemptStatus.PENDING.value
                and existing_attempt.provider_order_id
            ):
                # Idempotent replay of existing valid pending attempt
                return PaymentInitiateResponse(
                    payment_id=existing_attempt.id,
                    order_id=order_id_val,
                    order_number=order_number_val,
                    provider=existing_attempt.provider,
                    provider_order_id=existing_attempt.provider_order_id,
                    razorpay_key_id=self.client.key_id,
                    amount_paise=existing_attempt.amount_paise,
                    currency=existing_attempt.currency,
                    status=existing_attempt.status,
                    attempt_number=existing_attempt.attempt_number,
                    payment_window_expires_at=order_expires_at,
                )

        # Check if there is an active in-flight or ambiguous attempt for this order with a different idempotency key
        active_attempt = await self.repo.get_active_or_ambiguous_attempt_for_order(
            order_id
        )
        if active_attempt and active_attempt.idempotency_key != idempotency_key:
            if active_attempt.status in (
                PaymentAttemptStatus.CREATING.value,
                PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
            ):
                raise PaymentAttemptAmbiguousError()

        attempt_number = await self.repo.get_next_attempt_number(order_id)
        receipt = f"{order_number_val}-{attempt_number}"[:40]

        payment = Payment(
            order_id=order_id_val,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            provider="RAZORPAY_SANDBOX",
            idempotency_key=idempotency_key,
            attempt_number=attempt_number,
            amount_paise=order_total_payable,
            currency=order_currency,
            status=PaymentAttemptStatus.CREATING.value,
            metadata_json={"receipt": receipt},
        )
        try:
            await self.repo.create_payment(payment)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # A concurrent transaction inserted the payment attempt with this idempotency key
            for _ in range(50):
                await asyncio.sleep(0.05)
                await self.session.rollback()
                existing = await self.repo.get_payment_by_order_and_idempotency(
                    order_id, idempotency_key
                )
                if (
                    existing
                    and existing.status == PaymentAttemptStatus.PENDING.value
                    and existing.provider_order_id
                ):
                    return PaymentInitiateResponse(
                        payment_id=existing.id,
                        order_id=order_id_val,
                        order_number=order_number_val,
                        provider=existing.provider,
                        provider_order_id=existing.provider_order_id,
                        razorpay_key_id=self.client.key_id,
                        amount_paise=existing.amount_paise,
                        currency=existing.currency,
                        status=existing.status,
                        attempt_number=existing.attempt_number,
                        payment_window_expires_at=order_expires_at,
                    )
                if existing and existing.status != PaymentAttemptStatus.CREATING.value:
                    break
            raise PaymentAttemptAmbiguousError(
                "Concurrent payment attempt is currently in progress"
            ) from None

        # ----------------------------------------------------------------------
        # STEP 2: Call Razorpay API outside the local PostgreSQL transaction
        # ----------------------------------------------------------------------
        try:
            rzp_order = await self.client.create_order(
                amount_paise=order_total_payable,
                currency=order_currency,
                receipt=receipt,
                notes={
                    "order_id": str(order_id_val),
                    "order_number": order_number_val,
                    "payment_id": str(payment.id),
                    "attempt_number": str(attempt_number),
                },
            )
            provider_order_id = rzp_order.get("id")
            if not provider_order_id:
                raise PaymentGatewayError("Razorpay response missing order ID")
        except PaymentGatewayTimeoutError:
            # Mark attempt CREATION_AMBIGUOUS and flag order for reconciliation
            locked_payment = await self.repo.get_payment_by_id_for_update(payment.id)
            if locked_payment:
                locked_payment.status = PaymentAttemptStatus.CREATION_AMBIGUOUS.value
            locked_order = await self.repo.get_order_by_id_for_update(order_id_val)
            if locked_order:
                locked_order.payment_status = (
                    PaymentStatus.REQUIRES_RECONCILIATION.value
                )
            await self.session.commit()
            raise
        except PaymentGatewayError:
            locked_payment = await self.repo.get_payment_by_id_for_update(payment.id)
            if locked_payment:
                locked_payment.status = PaymentAttemptStatus.FAILED.value
                locked_payment.error_code = "GATEWAY_ERROR"
            await self.session.commit()
            raise

        # ----------------------------------------------------------------------
        # TRANSACTION 2: Associate provider order ID and transition to PENDING
        # ----------------------------------------------------------------------
        locked_payment = await self.repo.get_payment_by_id_for_update(payment.id)
        if not locked_payment:
            raise PaymentNotFoundError()
        locked_payment.provider_order_id = provider_order_id
        locked_payment.status = PaymentAttemptStatus.PENDING.value

        locked_order = await self.repo.get_order_by_id_for_update(order_id_val)
        if locked_order:
            locked_order.payment_status = PaymentStatus.PENDING.value

        payment_id_res = locked_payment.id
        provider_res = locked_payment.provider
        amount_res = locked_payment.amount_paise
        currency_res = locked_payment.currency
        status_res = locked_payment.status
        attempt_num_res = locked_payment.attempt_number

        await self.session.commit()

        return PaymentInitiateResponse(
            payment_id=payment_id_res,
            order_id=order_id_val,
            order_number=order_number_val,
            provider=provider_res,
            provider_order_id=provider_order_id,
            razorpay_key_id=self.client.key_id,
            amount_paise=amount_res,
            currency=currency_res,
            status=status_res,
            attempt_number=attempt_num_res,
            payment_window_expires_at=order_expires_at,
        )

    async def verify_payment(
        self,
        order_id: uuid.UUID,
        req: PaymentVerifyRequest,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> PaymentVerifyResponse:
        """Verifies payment signature, captures server-side if authorized, and fulfills order."""
        # 1. Cryptographic client signature verification
        is_valid_sig = self.client.verify_payment_signature(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature,
        )
        if not is_valid_sig:
            raise InvalidPaymentSignatureError()

        # 2. Fetch authoritative provider status from Razorpay
        pay_data = await self.client.fetch_payment(req.razorpay_payment_id)
        if pay_data.get("order_id") != req.razorpay_order_id:
            raise AppException(
                code="PAYMENT_ORDER_MISMATCH",
                message="Payment provider order does not match verification request",
                status_code=400,
            )

        provider_status = pay_data.get("status")
        # If authorized, execute server-side capture
        if provider_status == "authorized":
            captured_resp = await self.client.capture_payment(
                payment_id=req.razorpay_payment_id,
                amount_paise=pay_data["amount"],
                currency=pay_data.get("currency", "INR"),
            )
            pay_data = captured_resp
            provider_status = pay_data.get("status")

        if provider_status != "captured":
            raise AppException(
                code="PAYMENT_NOT_CAPTURED",
                message=f"Payment status is '{provider_status}'; only 'captured' payments can fulfill orders.",
                status_code=400,
            )

        captured_amount_paise = int(pay_data["amount"])
        captured_currency = pay_data.get("currency", "INR")

        # 3. Transactional fulfillment execution
        # Lock order following universal lock hierarchy: orders -> payments -> captures -> res -> inv
        order = await self.repo.get_order_by_id_for_update(order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        # Ownership check
        if customer_id is None and guest_token_hash is None:
            raise AppException(
                code="AUTHENTICATION_REQUIRED",
                message="Authentication or guest session is required",
                status_code=401,
            )
        if customer_id and order.customer_id != customer_id:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )
        if guest_token_hash and (
            order.guest_token_hash != guest_token_hash or order.customer_id is not None
        ):
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        if req.payment_id:
            payment = await self.repo.get_payment_by_id_for_update(req.payment_id)
        else:
            payment = await self.repo.get_payment_by_provider_order_id(
                req.razorpay_order_id
            )
        if not payment or payment.order_id != order.id:
            raise PaymentNotFoundError("Payment attempt does not belong to this order")

        if (
            payment.provider_order_id
            and payment.provider_order_id != req.razorpay_order_id
        ):
            raise AppException(
                code="PAYMENT_ORDER_MISMATCH",
                message="Payment attempt provider order does not match verification request",
                status_code=400,
            )

        capture = await process_payment_capture_and_fulfillment(
            session=self.session,
            repo=self.repo,
            reservation_service=self.reservation_service,
            order_id=order.id,
            payment_entity=pay_data,
            source="VERIFY",
            payment_id=payment.id,
            client=self.client,
        )
        if not capture:
            raise AppException(
                code="PAYMENT_FULFILLMENT_FAILED",
                message="Payment could not be fulfilled",
                status_code=400,
            )

        if (
            capture.reconciliation_status
            == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
        ):
            raise PartialCaptureRejectedError()
        elif (
            capture.reconciliation_status
            == CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value
        ):
            if captured_currency != order.currency:
                raise AppException(
                    code="CURRENCY_MISMATCH",
                    message="Captured payment currency does not match order currency",
                    status_code=400,
                )
            if (
                order.status == OrderStatus.CONFIRMED.value
                and order.fulfilling_capture_id != capture.id
            ):
                raise PaymentAlreadyConfirmedError(
                    "Order already confirmed; duplicate payment captured as anomaly and refunded."
                )
            raise AppException(
                code="OVERPAYMENT_ANOMALY",
                message="Payment amount exceeds order payable amount",
                status_code=400,
            )
        elif (
            capture.reconciliation_status
            == CaptureReconciliationStatus.LATE_CAPTURE_ANOMALY.value
        ):
            raise AppException(
                code="ORDER_CANCELLED",
                message="Order is cancelled; captured payment was recorded as an anomaly and refunded.",
                status_code=400,
            )

        if (
            order.payment_status == PaymentStatus.REQUIRES_RECONCILIATION.value
            and order.fulfilling_capture_id is None
        ):
            raise AppException(
                code="RESERVATION_CONFIRMATION_FAILED",
                message="Payment captured but inventory confirmation failed; requires reconciliation",
                status_code=500,
            )

        return PaymentVerifyResponse(
            status=order.status,
            payment_status=order.payment_status,
            order_id=order.id,
            order_number=order.order_number,
            fulfilling_capture_id=order.fulfilling_capture_id,
            amount_paid_paise=captured_amount_paise,
            confirmed_at=order.updated_at,
        )

    async def create_refund(
        self,
        order_id: uuid.UUID,
        req: CreateRefundRequest,
        idempotency_key: str,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        is_internal: bool = False,
    ) -> RefundResponse:
        """Issues a partial or full refund against a specific capture row under row lock."""
        order = await self.repo.get_order_by_id_for_update(order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND", message="Order not found", status_code=404
            )

        if not is_internal:
            if customer_id is None and guest_token_hash is None:
                raise AppException(
                    code="AUTHENTICATION_REQUIRED",
                    message="Authentication or guest session is required",
                    status_code=401,
                )
            if customer_id and order.customer_id != customer_id:
                raise AppException(
                    code="ORDER_NOT_FOUND", message="Order not found", status_code=404
                )
            if guest_token_hash and (
                order.guest_token_hash != guest_token_hash
                or order.customer_id is not None
            ):
                raise AppException(
                    code="ORDER_NOT_FOUND", message="Order not found", status_code=404
                )

        target_capture_id = req.capture_id or order.fulfilling_capture_id
        if not target_capture_id:
            raise AppException(
                code="CAPTURE_NOT_FOUND",
                message="No fulfilling capture found for this order",
                status_code=404,
            )

        capture = await self.repo.get_capture_by_id_for_update(target_capture_id)
        if not capture or capture.order_id != order.id:
            raise AppException(
                code="CAPTURE_NOT_FOUND",
                message="Capture not found for this order",
                status_code=404,
            )

        # Check idempotency
        existing_refund = await self.repo.get_refund_by_idempotency_key(idempotency_key)
        if existing_refund:
            return RefundResponse(
                refund_id=existing_refund.id,
                capture_id=existing_refund.capture_id,
                payment_id=existing_refund.payment_id,
                order_id=existing_refund.order_id,
                provider_refund_id=existing_refund.provider_refund_id,
                amount_paise=existing_refund.amount_paise,
                currency=existing_refund.currency,
                status=existing_refund.status,
            )

        # Atomic balance validation under row lock (sum active requested, pending, processed)
        active_sum = await self.repo.get_active_refunds_sum_for_capture(capture.id)
        if active_sum + req.amount_paise > capture.amount_paise:
            raise ExceedsRefundableBalanceError()

        refund = PaymentRefund(
            capture_id=capture.id,
            payment_id=capture.payment_id,
            order_id=order.id,
            idempotency_key=idempotency_key,
            amount_paise=req.amount_paise,
            currency=capture.currency,
            status=RefundStatus.REFUND_REQUESTED.value,
            reason=req.reason,
        )
        await self.repo.create_refund(refund)
        await self.session.commit()

        # Call Razorpay API outside transaction
        provider_refund_id = None
        refund_status = RefundStatus.REFUND_PENDING.value
        try:
            rzp_refund = await self.client.create_refund(
                payment_id=capture.provider_payment_id,
                amount_paise=req.amount_paise,
                idempotency_key=idempotency_key,
                receipt=f"RFND-{str(refund.id)[:30]}",
                notes={
                    "refund_id": str(refund.id),
                    "order_id": str(order_id),
                    "capture_id": str(capture.id),
                },
            )
            provider_refund_id = rzp_refund.get("id")
            refund_status = (
                RefundStatus.REFUND_PROCESSED.value
                if rzp_refund.get("status") == "processed"
                else RefundStatus.REFUND_PENDING.value
            )
        except PaymentGatewayTimeoutError as exc:
            logger.warning(
                "Refund request timed out; outcome uncertain, leaving in REFUND_PENDING: %s",
                exc,
            )
            locked_refund = await self.repo.get_refund_by_id(refund.id)
            if locked_refund:
                locked_refund.status = RefundStatus.REFUND_PENDING.value
                locked_refund.processed_at = None
                locked_refund.error_description = f"Gateway timeout: {exc}"
                await self.session.commit()
            return RefundResponse(
                refund_id=refund.id,
                capture_id=refund.capture_id,
                payment_id=refund.payment_id,
                order_id=refund.order_id,
                provider_refund_id=None,
                amount_paise=refund.amount_paise,
                currency=refund.currency,
                status=RefundStatus.REFUND_PENDING.value,
            )
        except PaymentGatewayError as exc:
            locked_refund = await self.repo.get_refund_by_id(refund.id)
            if locked_refund:
                locked_refund.status = RefundStatus.REFUND_FAILED.value
                locked_refund.processed_at = None
                locked_refund.error_code = "GATEWAY_REFUND_FAILED"
                locked_refund.error_description = str(exc)
                await self.session.commit()
            raise

        # Update refund status and order payment status
        locked_refund = await self.repo.get_refund_by_id(refund.id)
        if locked_refund:
            locked_refund.provider_refund_id = provider_refund_id
            locked_refund.status = refund_status
            if refund_status == RefundStatus.REFUND_PROCESSED.value:
                locked_refund.processed_at = datetime.now(UTC)
            else:
                locked_refund.processed_at = None
        await self.session.flush()

        # Calculate confirmed processed refund totals ONLY
        processed_sum = await self.repo.get_processed_refunds_sum_for_capture(
            capture.id
        )
        locked_capture = await self.repo.get_capture_by_id_for_update(capture.id)
        if locked_capture:
            if processed_sum >= locked_capture.amount_paise:
                locked_capture.status = CaptureStatus.REFUNDED.value
            elif processed_sum > 0:
                locked_capture.status = CaptureStatus.PARTIALLY_REFUNDED.value
            else:
                locked_capture.status = CaptureStatus.CAPTURED.value

        order_processed_sum = await self.repo.get_processed_refunds_sum_for_order(
            order_id
        )
        locked_order = await self.repo.get_order_by_id_for_update(order_id)
        if locked_order:
            if order_processed_sum >= locked_order.total_payable_paise:
                locked_order.payment_status = PaymentStatus.REFUNDED.value
            elif order_processed_sum > 0:
                locked_order.payment_status = PaymentStatus.PARTIALLY_REFUNDED.value

        await self.session.commit()

        return RefundResponse(
            refund_id=refund.id,
            capture_id=refund.capture_id,
            payment_id=refund.payment_id,
            order_id=refund.order_id,
            provider_refund_id=provider_refund_id,
            amount_paise=refund.amount_paise,
            currency=refund.currency,
            status=refund_status,
        )

    async def _queue_automated_refund(
        self,
        capture: PaymentCapture,
        reason: str,
    ) -> PaymentRefund:
        """Helper to create automated refund intent for anomalies and late captures.
        Guarantees capture and refund intent are committed to PostgreSQL before calling external gateway.
        """
        return await dispatch_automated_refund(
            session=self.session,
            repo=self.repo,
            client=self.client,
            capture=capture,
            reason=reason,
        )
