import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
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

    async def initiate_payment(
        self,
        order_id: uuid.UUID,
        idempotency_key: str,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> PaymentInitiateResponse:
        """Initiates a payment attempt using the pre-gateway two-transaction pattern."""
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
        captured_at_ts = pay_data.get("created_at") or int(
            datetime.now(UTC).timestamp()
        )
        captured_at = datetime.fromtimestamp(captured_at_ts, tz=UTC)
        acquirer_ref = (
            pay_data.get("acquirer_data", {}).get("rrn")
            or pay_data.get("acquirer_data", {}).get("upi_transaction_id")
            or pay_data.get("acquirer_data", {}).get("bank_transaction_id")
        )

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

        # Currency validation
        if captured_currency != order.currency:
            existing_capture = await self.repo.get_capture_by_provider_payment_id(
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=req.razorpay_payment_id,
            )
            if not existing_capture:
                currency_anomaly = PaymentCapture(
                    payment_id=payment.id,
                    order_id=order.id,
                    provider="RAZORPAY_SANDBOX",
                    provider_payment_id=req.razorpay_payment_id,
                    provider_order_id=req.razorpay_order_id,
                    amount_paise=captured_amount_paise,
                    currency=captured_currency,
                    status=CaptureStatus.CAPTURED.value,
                    method=pay_data.get("method"),
                    acquirer_reference=acquirer_ref,
                    is_fulfillment_eligible=False,
                    reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
                    captured_at=captured_at,
                )
                await self.repo.create_capture(currency_anomaly)
                await self._queue_automated_refund(
                    capture=currency_anomaly,
                    reason="CURRENCY_MISMATCH",
                )
            raise AppException(
                code="CURRENCY_MISMATCH",
                message="Captured payment currency does not match order currency",
                status_code=400,
            )

        # If order is already confirmed:
        if order.status == OrderStatus.CONFIRMED.value:
            existing_capture = await self.repo.get_capture_by_provider_payment_id(
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=req.razorpay_payment_id,
            )
            if existing_capture and order.fulfilling_capture_id == existing_capture.id:
                # Idempotent return
                return PaymentVerifyResponse(
                    status=order.status,
                    payment_status=order.payment_status,
                    order_id=order.id,
                    order_number=order.order_number,
                    fulfilling_capture_id=order.fulfilling_capture_id,
                    amount_paid_paise=order.total_payable_paise,
                    confirmed_at=order.updated_at,
                )

            # Distinct second capture for already confirmed order: record as OVERPAYMENT_ANOMALY & auto-refund
            if not existing_capture:
                anomaly_capture = PaymentCapture(
                    payment_id=payment.id,
                    order_id=order.id,
                    provider="RAZORPAY_SANDBOX",
                    provider_payment_id=req.razorpay_payment_id,
                    provider_order_id=req.razorpay_order_id,
                    amount_paise=captured_amount_paise,
                    currency=captured_currency,
                    status=CaptureStatus.CAPTURED.value,
                    method=pay_data.get("method"),
                    acquirer_reference=acquirer_ref,
                    is_fulfillment_eligible=False,
                    reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
                    captured_at=captured_at,
                )
                await self.repo.create_capture(anomaly_capture)
                await self._queue_automated_refund(
                    capture=anomaly_capture,
                    reason="OVERPAYMENT_DUPLICATE_CAPTURE",
                )
            raise PaymentAlreadyConfirmedError(
                "Order already confirmed; duplicate payment captured as anomaly and refunded."
            )

        # If order was cancelled (e.g. 75-minute SLA expiry or user cancelled):
        if order.status == OrderStatus.CANCELLED.value:
            existing_capture = await self.repo.get_capture_by_provider_payment_id(
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=req.razorpay_payment_id,
            )
            if not existing_capture:
                late_capture = PaymentCapture(
                    payment_id=payment.id,
                    order_id=order.id,
                    provider="RAZORPAY_SANDBOX",
                    provider_payment_id=req.razorpay_payment_id,
                    provider_order_id=req.razorpay_order_id,
                    amount_paise=captured_amount_paise,
                    currency=captured_currency,
                    status=CaptureStatus.CAPTURED.value,
                    method=pay_data.get("method"),
                    acquirer_reference=acquirer_ref,
                    is_fulfillment_eligible=False,
                    reconciliation_status=CaptureReconciliationStatus.LATE_CAPTURE_ANOMALY.value,
                    captured_at=captured_at,
                )
                await self.repo.create_capture(late_capture)
                await self._queue_automated_refund(
                    capture=late_capture,
                    reason="LATE_CAPTURE_AFTER_ORDER_CANCELLATION",
                )
            raise AppException(
                code="ORDER_CANCELLED",
                message="Order is cancelled; captured payment was recorded as an anomaly and refunded.",
                status_code=400,
            )

        # Check for partial capture
        if captured_amount_paise < order.total_payable_paise:
            existing_capture = await self.repo.get_capture_by_provider_payment_id(
                provider="RAZORPAY_SANDBOX",
                provider_payment_id=req.razorpay_payment_id,
            )
            if not existing_capture:
                partial_capture = PaymentCapture(
                    payment_id=payment.id,
                    order_id=order.id,
                    provider="RAZORPAY_SANDBOX",
                    provider_payment_id=req.razorpay_payment_id,
                    provider_order_id=req.razorpay_order_id,
                    amount_paise=captured_amount_paise,
                    currency=captured_currency,
                    status=CaptureStatus.CAPTURED.value,
                    method=pay_data.get("method"),
                    acquirer_reference=acquirer_ref,
                    is_fulfillment_eligible=False,
                    reconciliation_status=CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value,
                    captured_at=captured_at,
                )
                await self.repo.create_capture(partial_capture)
            else:
                partial_capture = existing_capture

            # Underpayment: reject capture for fulfillment
            payment.status = PaymentAttemptStatus.FAILED.value
            payment.error_code = "PARTIAL_CAPTURE_REJECTED"

            # Attempt reservation release if order is not yet CANCELLED
            if order.status != OrderStatus.CANCELLED.value:
                release_succeeded = False
                if self.reservation_service and order.reservation_id:
                    try:
                        await self.reservation_service.release_reservation(
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
                    order.status = OrderStatus.CANCELLED.value
                    order.payment_status = PaymentStatus.FAILED.value
                else:
                    # Never mark CANCELLED if release failed! Keep in REQUIRES_RECONCILIATION
                    order.payment_status = PaymentStatus.REQUIRES_RECONCILIATION.value

            # Durably commit partial capture, order status, and payment attempt before refund / raising error
            await self.session.commit()

            # Make refund dispatch independent of whether inventory release succeeds
            # Ensure durable capture and refund intent are committed
            await self._queue_automated_refund(
                capture=partial_capture,
                reason="PARTIAL_CAPTURE_REJECTED",
            )
            raise PartialCaptureRejectedError()

        # Normal successful capture:
        # 1. Insert capture with is_fulfillment_eligible = TRUE
        capture = PaymentCapture(
            payment_id=payment.id,
            order_id=order.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=req.razorpay_payment_id,
            provider_order_id=req.razorpay_order_id,
            amount_paise=captured_amount_paise,
            currency=captured_currency,
            status=CaptureStatus.CAPTURED.value,
            method=pay_data.get("method"),
            acquirer_reference=acquirer_ref,
            is_fulfillment_eligible=True,
            reconciliation_status=CaptureReconciliationStatus.NORMAL.value,
            captured_at=captured_at,
        )
        await self.repo.create_capture(capture)

        # 2. Set fulfilling_capture_id on orders (single source of truth!)
        order.fulfilling_capture_id = capture.id
        order.status = OrderStatus.CONFIRMED.value
        order.payment_status = PaymentStatus.SUCCEEDED.value

        # Record order status history
        history = OrderStatusHistory(
            order_id=order.id,
            from_status=OrderStatus.PENDING_PAYMENT.value,
            to_status=OrderStatus.CONFIRMED.value,
            reason="PAYMENT_CAPTURED_CONFIRMED",
        )
        self.session.add(history)

        # 3. Update payment attempt status
        payment.status = PaymentAttemptStatus.SUCCEEDED.value
        payment.provider_payment_id = req.razorpay_payment_id
        payment.method = pay_data.get("method")

        # 4. Confirm inventory reservation and permanently deduct on_hand stock
        await self.reservation_service.confirm_reservation(
            reservation_id=order.reservation_id,
            internal=True,
        )

        # 5. Outbox event (Zero PII payload)
        outbox_event = OutboxEvent(
            aggregate_type="Order",
            aggregate_id=order.id,
            event_type="order.confirmed",
            schema_version=1,
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "fulfilling_capture_id": str(capture.id),
                "total_payable_paise": order.total_payable_paise,
                "currency": order.currency,
            },
            status=OutboxStatus.PENDING.value,
        )
        order_status = order.status
        order_payment_status = order.payment_status
        order_id_val = order.id
        order_number_val = order.order_number
        fulfilling_capture_id_val = order.fulfilling_capture_id
        confirmed_at_val = datetime.now(UTC)

        self.session.add(outbox_event)
        await self.session.commit()

        return PaymentVerifyResponse(
            status=order_status,
            payment_status=order_payment_status,
            order_id=order_id_val,
            order_number=order_number_val,
            fulfilling_capture_id=fulfilling_capture_id_val,
            amount_paid_paise=captured_amount_paise,
            confirmed_at=confirmed_at_val,
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
        refund_idempotency = f"auto-refund-{capture.id}"
        existing = await self.repo.get_refund_by_idempotency_key(refund_idempotency)
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
        await self.repo.create_refund(refund)
        # CRITICAL: Commit capture AND refund intent to database BEFORE calling provider!
        await self.session.commit()

        # Trigger gateway refund outside transaction
        try:
            rzp_refund = await self.client.create_refund(
                payment_id=capture.provider_payment_id,
                amount_paise=capture.amount_paise,
                idempotency_key=refund_idempotency,
                receipt=f"RFND-{str(refund.id)[:30]}",
                notes={"reason": reason, "capture_id": str(capture.id)},
            )
            locked_refund = await self.repo.get_refund_by_id(refund.id)
            if locked_refund:
                locked_refund.provider_refund_id = rzp_refund.get("id")
                if rzp_refund.get("status") == "processed":
                    locked_refund.status = RefundStatus.REFUND_PROCESSED.value
                    locked_refund.processed_at = datetime.now(UTC)
                    locked_capture = await self.repo.get_capture_by_id_for_update(
                        capture.id
                    )
                    if locked_capture:
                        locked_capture.status = CaptureStatus.REFUNDED.value
                else:
                    locked_refund.status = RefundStatus.REFUND_PENDING.value
                    locked_refund.processed_at = None
            await self.session.commit()
        except Exception as exc:
            logger.warning(
                "Automated refund failed to dispatch immediately; leaving in REFUND_PENDING: %s",
                str(exc),
            )
            locked_refund = await self.repo.get_refund_by_id(refund.id)
            if locked_refund:
                locked_refund.status = RefundStatus.REFUND_PENDING.value
                locked_refund.processed_at = None
                locked_refund.error_description = str(exc)
            await self.session.commit()

        return refund
