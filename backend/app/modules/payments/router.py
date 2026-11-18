import hashlib
import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.modules.cart.dependencies import (
    GUEST_CART_COOKIE_NAME,
    get_current_user_optional,
)
from app.modules.identity.models import User
from app.modules.inventory.dependencies import verify_internal_service_key
from app.modules.payments.reconciliation import ReconciliationService
from app.modules.payments.schemas import (
    CreateRefundRequest,
    PaymentInitiateResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    ReconcilePendingRequest,
    ReconcilePendingResponse,
    RefundResponse,
    ResolveAmbiguityRequest,
    ResolveAmbiguityResponse,
    WebhookIngestResponse,
)
from app.modules.payments.service import PaymentService
from app.modules.payments.webhook import WebhookService

router = APIRouter(tags=["payments"])
internal_router = APIRouter(prefix="/internal/payments", tags=["internal-payments"])


def _extract_ownership_identifiers(
    request: Request,
    user: User | None,
) -> tuple[uuid.UUID | None, str | None]:
    customer_id = user.id if user else None
    guest_token_hash = None
    if not customer_id:
        guest_token = request.cookies.get(
            GUEST_CART_COOKIE_NAME
        ) or request.headers.get("X-Guest-Cart-Token")
        if guest_token:
            guest_token_hash = hashlib.sha256(guest_token.encode()).hexdigest()
    return customer_id, guest_token_hash


@router.post(
    "/orders/{order_id}/payments",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a payment attempt for an order",
)
async def initiate_payment(
    order_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PaymentInitiateResponse:
    effective_key = idempotency_key or str(uuid.uuid4())

    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = PaymentService(db)
    return await service.initiate_payment(
        order_id=order_id,
        idempotency_key=effective_key,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )


@router.post(
    "/orders/{order_id}/payments/verify",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify payment signature and confirm order fulfillment",
)
async def verify_payment(
    order_id: uuid.UUID,
    payload: PaymentVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentVerifyResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = PaymentService(db)
    return await service.verify_payment(
        order_id=order_id,
        req=payload,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )


@router.post(
    "/orders/{order_id}/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a partial or full refund against a capture",
)
async def create_refund(
    order_id: uuid.UUID,
    payload: CreateRefundRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RefundResponse:
    # Check internal auth header or customer session
    internal_key = request.headers.get("X-Internal-Service-Key") or request.headers.get(
        "X-Internal-Token"
    )
    is_internal = False
    if internal_key and settings.INTERNAL_SERVICE_KEY:
        if hmac.compare_digest(
            internal_key, settings.INTERNAL_SERVICE_KEY.get_secret_value()
        ):
            is_internal = True

    customer_id = None
    guest_token_hash = None
    if not is_internal:
        user = await get_current_user_optional(request, db)
        customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    effective_key = idempotency_key or str(uuid.uuid4())
    service = PaymentService(db)
    return await service.create_refund(
        order_id=order_id,
        req=payload,
        idempotency_key=effective_key,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )


@router.post(
    "/payments/webhook",
    response_model=WebhookIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Durable Razorpay webhook receiver",
)
async def receive_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_razorpay_signature: Annotated[
        str | None, Header(alias="x-razorpay-signature")
    ] = None,
    x_razorpay_event_id: Annotated[
        str | None, Header(alias="x-razorpay-event-id")
    ] = None,
) -> WebhookIngestResponse:
    raw_body = await request.body()
    webhook_service = WebhookService(db)
    response = await webhook_service.ingest_webhook(
        raw_body_bytes=raw_body,
        signature_header=x_razorpay_signature,
        event_id_header=x_razorpay_event_id,
    )

    # Trigger async processing if newly ingested
    if response.status == "ok":
        # Process the newly ingested event immediately for responsiveness
        event = await webhook_service.repo.get_webhook_event_by_provider_event(
            "RAZORPAY", response.event_id
        )
        if event:
            await webhook_service.process_webhook_event(event.id)

    return response


@internal_router.post(
    "/reconcile-pending",
    response_model=ReconcilePendingResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconcile pending/ambiguous payments and reclaim stuck webhooks",
)
async def reconcile_pending(
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ReconcilePendingRequest | None = None,
    _internal_auth: None = Depends(verify_internal_service_key),
) -> ReconcilePendingResponse:
    batch_size = payload.batch_size if payload else 50
    max_age_minutes = payload.max_age_minutes if payload else 1440
    service = ReconciliationService(db)
    return await service.reconcile_pending(
        batch_size=batch_size,
        max_age_minutes=max_age_minutes,
    )


@internal_router.post(
    "/{payment_id}/resolve-ambiguity",
    response_model=ResolveAmbiguityResponse,
    status_code=status.HTTP_200_OK,
    summary="Manual operational review resolution for ambiguous payments",
)
async def resolve_ambiguity(
    payment_id: uuid.UUID,
    payload: ResolveAmbiguityRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _internal_auth: None = Depends(verify_internal_service_key),
    x_operator_id: Annotated[str, Header(alias="X-Operator-Id")] = "operator",
    x_operator_reason: Annotated[
        str, Header(alias="X-Operator-Reason")
    ] = "manual-review",
) -> ResolveAmbiguityResponse:
    service = ReconciliationService(db)
    return await service.resolve_ambiguity_manual(
        payment_id=payment_id,
        action=payload.action,
        provider_order_id=payload.provider_order_id,
        operator_id=x_operator_id,
        operator_reason=x_operator_reason,
    )


@internal_router.post(
    "/sla-escalation",
    status_code=status.HTTP_200_OK,
    summary="Trigger the 75-minute terminal SLA escalation job",
)
async def run_sla_escalation(
    db: Annotated[AsyncSession, Depends(get_db)],
    _internal_auth: None = Depends(verify_internal_service_key),
    limit: int = 50,
) -> dict[str, int]:
    service = ReconciliationService(db)
    count = await service.execute_75m_sla_escalation_job(limit=limit)
    return {"cancelled_orders_count": count}
