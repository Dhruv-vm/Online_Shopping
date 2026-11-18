import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.cart.dependencies import (
    GUEST_CART_COOKIE_NAME,
    CartContext,
    get_cart_context,
    get_current_user_optional,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.pricing.quote_service import QuoteService
from app.modules.pricing.schemas import (
    QuoteCreateRequest,
    QuoteResponse,
    QuoteValidationResponse,
)

router = APIRouter(tags=["pricing-quotes"])


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
    "/quotes",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate persistent pricing quote from cart",
)
@router.post(
    "/checkout/quote",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate persistent pricing quote from cart (checkout alias)",
)
async def create_quote(
    payload: QuoteCreateRequest,
    cart_ctx: Annotated[CartContext, Depends(get_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuoteResponse:
    quote_service = QuoteService(db)
    quote = await quote_service.generate_quote_from_cart(
        cart=cart_ctx.cart,
        delivery_address_id=payload.delivery_address_id,
        delivery_state=payload.delivery_state,
    )
    return quote_service.format_quote_response(quote)


@router.get(
    "/quotes/{quote_id}",
    response_model=QuoteResponse,
    summary="Retrieve pricing quote by ID",
)
async def get_quote(
    quote_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuoteResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    quote_service = QuoteService(db)
    quote = await quote_service.get_quote_by_id(
        quote_id=quote_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return quote_service.format_quote_response(quote)


@router.post(
    "/quotes/{quote_id}/validate",
    response_model=QuoteValidationResponse,
    summary="Validate quote against current live prices, taxes, and inventory",
)
async def validate_quote(
    quote_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuoteValidationResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    quote_service = QuoteService(db)
    quote = await quote_service.get_quote_by_id(
        quote_id=quote_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return await quote_service.validate_quote(quote)


@router.post(
    "/quotes/{quote_id}/refresh",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Refresh/replace an expired or invalid quote with live catalogue prices",
)
async def refresh_quote(
    quote_id: uuid.UUID,
    cart_ctx: Annotated[CartContext, Depends(get_cart_context)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuoteResponse:
    customer_id, guest_token_hash = _extract_ownership_identifiers(
        request, cart_ctx.user
    )

    quote_service = QuoteService(db)
    old_quote = await quote_service.get_quote_by_id(
        quote_id=quote_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    new_quote = await quote_service.refresh_quote(
        old_quote=old_quote,
        cart=cart_ctx.cart,
    )
    return quote_service.format_quote_response(new_quote)


@router.get(
    "/quotes",
    response_model=list[QuoteResponse],
    summary="List quotes for current authenticated customer",
)
async def list_quotes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuoteResponse]:
    quote_service = QuoteService(db)
    quotes = await quote_service.list_customer_quotes(customer_id=current_user.id)
    return [quote_service.format_quote_response(q) for q in quotes]
