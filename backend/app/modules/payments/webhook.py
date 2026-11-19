import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.logging import logger
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import (
    OrderStatus,
    PaymentStatus,
)
from app.modules.payments.client import RazorpayClient
from app.modules.payments.exceptions import (
    InvalidWebhookSignatureError,
    MissingWebhookSignatureError,
)
from app.modules.payments.models import (
    CaptureStatus,
    PaymentAttemptStatus,
    PaymentCapture,
    PaymentRefund,
    RefundStatus,
    WebhookEvent,
    WebhookEventStatus,
)
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import WebhookIngestResponse
from app.modules.payments.service import (
    dispatch_automated_refund,
    process_payment_capture_and_fulfillment,
)


def sanitize_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize inbound payload to remove sensitive card / banking credentials."""
    sanitized = json.loads(json.dumps(payload))
    payment = sanitized.get("payload", {}).get("payment", {}).get("entity", {})
    if "card" in payment and isinstance(payment["card"], dict):
        card = payment["card"]
        card.pop("cvv", None)
        card.pop("pin", None)
        card.pop("token", None)
    return sanitized


class WebhookService:
    """Service implementing the Three-Phase Claim-and-Process Webhook Architecture."""

    def __init__(
        self,
        session: AsyncSession,
        client: RazorpayClient | None = None,
    ):
        self.session = session
        self.repo = PaymentRepository(session)
        self.client = client or RazorpayClient()
        self.reservation_service = ReservationService(session)

    async def ingest_webhook(
        self,
        raw_body_bytes: bytes,
        signature_header: str | None,
        event_id_header: str | None = None,
    ) -> WebhookIngestResponse:
        """Phase 1: Ingestion. Verifies HMAC, deduplicates event, commits PENDING receipt."""
        if not signature_header:
            raise MissingWebhookSignatureError()

        if not self.client.verify_webhook_signature(raw_body_bytes, signature_header):
            raise InvalidWebhookSignatureError()

        try:
            payload = json.loads(raw_body_bytes.decode("utf-8"))
        except Exception as exc:
            raise AppException(
                code="INVALID_JSON", message="Malformed webhook body", status_code=400
            ) from exc

        event_id = event_id_header or payload.get("id") or payload.get("event_id")
        if not event_id or not str(event_id).strip():
            raise AppException(
                code="MISSING_WEBHOOK_EVENT_ID",
                message="Valid provider event ID is required in header or payload for deduplication",
                status_code=400,
            )
        event_id = str(event_id).strip()
        event_type = payload.get("event", "unknown")

        # Deduplication check
        existing = await self.repo.get_webhook_event_by_provider_event(
            "RAZORPAY", event_id
        )
        if existing:
            return WebhookIngestResponse(
                status="ignored", event_id=event_id, reason="ALREADY_INGESTED"
            )

        sanitized_payload = sanitize_webhook_payload(payload)

        event = WebhookEvent(
            provider="RAZORPAY",
            provider_event_id=event_id,
            event_type=event_type,
            payload=sanitized_payload,
            status=WebhookEventStatus.PENDING.value,
        )
        try:
            await self.repo.create_webhook_event(event)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.info(
                "Concurrent duplicate webhook ingestion race resolved for event '%s'",
                event_id,
            )
            return WebhookIngestResponse(
                status="ignored", event_id=event_id, reason="ALREADY_INGESTED"
            )

        return WebhookIngestResponse(status="ok", event_id=event_id)

    async def process_webhook_event(self, event_id: uuid.UUID, worker_id: str) -> bool:
        """Phase 2: Business execution for a single claimed webhook event.
        Requires active durable worker lease ownership."""
        if not worker_id or not str(worker_id).strip():
            raise AppException(
                code="MISSING_WORKER_ID",
                message="worker_id is required to process webhook event",
                status_code=400,
            )
        worker_id = str(worker_id).strip()

        now = datetime.now(UTC)
        stmt = (
            select(WebhookEvent)
            .where(
                WebhookEvent.id == event_id,
                WebhookEvent.claimed_by == worker_id,
                WebhookEvent.status == WebhookEventStatus.PROCESSING.value,
                WebhookEvent.claim_expires_at > now,
            )
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            logger.warning(
                "Worker %s cannot process webhook event %s; missing or expired claim",
                worker_id,
                event_id,
            )
            return False

        event_type = event.event_type
        payload = event.payload

        try:
            if event_type in ("payment.captured", "order.paid"):
                await self._handle_payment_captured(payload)
            elif event_type == "payment.failed":
                await self._handle_payment_failed(payload)
            elif event_type == "refund.processed":
                await self._handle_refund_processed(payload)
            elif event_type == "refund.failed":
                await self._handle_refund_failed(payload)
            else:
                logger.info("Ignoring unhandled webhook event type: %s", event_type)

            # Ensure a worker whose lease expires during processing cannot mark the event complete after losing ownership
            now_end = datetime.now(UTC)
            update_stmt = (
                update(WebhookEvent)
                .where(
                    WebhookEvent.id == event_id,
                    WebhookEvent.claimed_by == worker_id,
                    WebhookEvent.status == WebhookEventStatus.PROCESSING.value,
                    WebhookEvent.claim_expires_at > now_end,
                )
                .values(
                    status=WebhookEventStatus.PROCESSED.value,
                    processed_at=now_end,
                    claimed_by=None,
                    claim_expires_at=None,
                )
            )
            update_res = await self.session.execute(update_stmt)
            if update_res.rowcount == 0:
                logger.warning(
                    "Worker %s lost lease for webhook event %s before completion",
                    worker_id,
                    event_id,
                )
                await self.session.rollback()
                return False

            await self.session.commit()
            return True
        except Exception as exc:
            logger.error(
                "Error processing webhook event %s: %s",
                event_id,
                str(exc),
                exc_info=True,
            )
            await self.session.rollback()

            now_err = datetime.now(UTC)
            fail_stmt = (
                update(WebhookEvent)
                .where(
                    WebhookEvent.id == event_id,
                    WebhookEvent.claimed_by == worker_id,
                    WebhookEvent.status == WebhookEventStatus.PROCESSING.value,
                    WebhookEvent.claim_expires_at > now_err,
                )
                .values(
                    error_message=str(exc),
                    status=case(
                        (
                            WebhookEvent.retry_count >= 5,
                            WebhookEventStatus.FAILED.value,
                        ),
                        else_=WebhookEventStatus.PENDING.value,
                    ),
                    claimed_by=None,
                    claim_expires_at=None,
                )
            )
            await self.session.execute(fail_stmt)
            await self.session.commit()
            return False

    async def _handle_payment_captured(self, payload: dict[str, Any]) -> None:
        """Processes payment.captured / order.paid webhook events following downward lock hierarchy."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        provider_payment_id = payment_entity.get("id")
        provider_order_id = payment_entity.get("order_id")

        if not provider_payment_id and not provider_order_id:
            order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})
            provider_order_id = order_entity.get("id")

        if not provider_order_id and not provider_payment_id:
            logger.warning(
                "payment.captured webhook payload missing payment and order id"
            )
            return

        # Locate payment and order
        payment = None
        order = None
        if provider_order_id:
            payment = await self.repo.get_payment_by_provider_order_id(
                provider_order_id
            )
        if not payment:
            # Check notes for order_id or payment_id
            notes = payment_entity.get("notes", {})
            if notes.get("order_id"):
                try:
                    order_uuid = uuid.UUID(notes["order_id"])
                    order = await self.repo.get_order_by_id_for_update(order_uuid)
                except Exception:
                    pass

        if payment and not order:
            order = await self.repo.get_order_by_id_for_update(payment.order_id)

        if not order:
            logger.error(
                "Unable to match payment.captured event to an existing BASKET order (provider_order_id=%s)",
                provider_order_id,
            )
            return

        if not provider_payment_id and provider_order_id:
            rzp_payments = await self.client.fetch_order_payments(provider_order_id)
            for p_item in rzp_payments:
                await process_payment_capture_and_fulfillment(
                    session=self.session,
                    repo=self.repo,
                    reservation_service=self.reservation_service,
                    order_id=order.id,
                    payment_entity=p_item,
                    source="WEBHOOK",
                    payment_id=payment.id if payment else None,
                    client=self.client,
                )
            return

        await process_payment_capture_and_fulfillment(
            session=self.session,
            repo=self.repo,
            reservation_service=self.reservation_service,
            order_id=order.id,
            payment_entity=payment_entity,
            source="WEBHOOK",
            payment_id=payment.id if payment else None,
            client=self.client,
        )

    async def _handle_payment_failed(self, payload: dict[str, Any]) -> None:
        """Handles payment.failed event safely; ignores if order is already confirmed."""
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        provider_order_id = payment_entity.get("order_id")
        if not provider_order_id:
            return

        payment = await self.repo.get_payment_by_provider_order_id(provider_order_id)
        if not payment:
            return

        order = await self.repo.get_order_by_id_for_update(payment.order_id)
        if not order:
            return

        # Invariant: Never allow an older/stale failed event to regress a confirmed order or succeeded payment!
        if (
            order.status == OrderStatus.CONFIRMED.value
            or order.fulfilling_capture_id is not None
        ):
            logger.info(
                "Ignoring payment.failed webhook for already confirmed order %s",
                order.id,
            )
            return

        if payment.status in (
            PaymentAttemptStatus.SUCCEEDED.value,
            PaymentAttemptStatus.PARTIALLY_REFUNDED.value,
            PaymentAttemptStatus.REFUNDED.value,
        ):
            logger.info(
                "Ignoring payment.failed webhook for already succeeded payment %s",
                payment.id,
            )
            return

        if payment.status in (
            PaymentAttemptStatus.CREATING.value,
            PaymentAttemptStatus.PENDING.value,
        ):
            payment.status = PaymentAttemptStatus.FAILED.value
            payment.error_code = payment_entity.get("error_code")
            payment.error_description = payment_entity.get("error_description")
            payment.provider_payment_id = payment_entity.get("id")

    async def _handle_refund_processed(self, payload: dict[str, Any]) -> None:
        """Handles refund.processed event to update payment_refunds and order payment status."""
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        provider_refund_id = refund_entity.get("id")
        if not provider_refund_id:
            return

        stmt = select(PaymentRefund).where(
            PaymentRefund.provider_refund_id == provider_refund_id
        )
        res = await self.session.execute(stmt)
        refund = res.scalar_one_or_none()
        if not refund:
            return

        # Duplicate refund.processed is an idempotent no-op
        if refund.status == RefundStatus.REFUND_PROCESSED.value:
            logger.info(
                "Duplicate refund.processed event for already processed refund %s (provider_refund_id=%s)",
                refund.id,
                provider_refund_id,
            )
            return

        refund.status = RefundStatus.REFUND_PROCESSED.value
        refund.processed_at = datetime.now(UTC)
        refund.error_code = None
        refund.error_description = None
        await self.session.flush()

        capture = await self.repo.get_capture_by_id_for_update(refund.capture_id)
        if capture:
            processed_sum = await self.repo.get_processed_refunds_sum_for_capture(
                capture.id
            )
            if processed_sum >= capture.amount_paise:
                capture.status = CaptureStatus.REFUNDED.value
            elif processed_sum > 0:
                capture.status = CaptureStatus.PARTIALLY_REFUNDED.value
            else:
                capture.status = CaptureStatus.CAPTURED.value

        order = await self.repo.get_order_by_id_for_update(refund.order_id)
        if order:
            order_processed_sum = await self.repo.get_processed_refunds_sum_for_order(
                refund.order_id
            )
            if order_processed_sum >= order.total_payable_paise:
                order.payment_status = PaymentStatus.REFUNDED.value
            elif order_processed_sum > 0:
                order.payment_status = PaymentStatus.PARTIALLY_REFUNDED.value

    async def _handle_refund_failed(self, payload: dict[str, Any]) -> None:
        """Handles refund.failed event to mark refund FAILED without regressing capture status.
        Never regresses an already processed refund."""
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        provider_refund_id = refund_entity.get("id")
        if not provider_refund_id:
            return

        stmt = select(PaymentRefund).where(
            PaymentRefund.provider_refund_id == provider_refund_id
        )
        res = await self.session.execute(stmt)
        refund = res.scalar_one_or_none()
        if not refund:
            return

        # Never transition REFUND_PROCESSED back to REFUND_FAILED
        if refund.status == RefundStatus.REFUND_PROCESSED.value:
            logger.info(
                "Ignoring stale refund.failed event for already processed refund %s (provider_refund_id=%s)",
                refund.id,
                provider_refund_id,
            )
            return

        # Duplicate refund.failed is an idempotent no-op
        if refund.status == RefundStatus.REFUND_FAILED.value:
            logger.info(
                "Duplicate refund.failed event for already failed refund %s (provider_refund_id=%s)",
                refund.id,
                provider_refund_id,
            )
            return

        refund.status = RefundStatus.REFUND_FAILED.value
        refund.error_code = refund_entity.get("error_code") or "PROVIDER_REFUND_FAILED"
        refund.error_description = (
            refund_entity.get("error_description") or "Refund rejected by gateway"
        )

    async def _trigger_auto_refund(self, capture: PaymentCapture, reason: str) -> None:
        await dispatch_automated_refund(
            session=self.session,
            repo=self.repo,
            client=self.client,
            capture=capture,
            reason=reason,
        )
