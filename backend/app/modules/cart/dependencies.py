import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import AppException
from app.modules.cart.models import Cart
from app.modules.cart.service import CartService
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import decode_access_token

GUEST_CART_COOKIE_NAME = "basket_guest_cart"
GUEST_CART_MAX_AGE_SECONDS = 30 * 86400  # 30 days


def set_guest_cart_cookie(response: Response, guest_token: str) -> None:
    response.set_cookie(
        key=GUEST_CART_COOKIE_NAME,
        value=guest_token,
        max_age=GUEST_CART_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


def clear_guest_cart_cookie(response: Response) -> None:
    response.delete_cookie(
        key=GUEST_CART_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


async def get_current_user_optional(
    request: Request,
    db: AsyncSession,
) -> User | None:
    """Extract authenticated user if valid token present, otherwise None."""
    token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
        repo = IdentityRepository(db)

        # Check session revocation if sid present
        sid_str = payload.get("sid")
        if sid_str:
            session_id = uuid.UUID(sid_str)
            session = await repo.get_session_by_id(session_id)
            if not session or session.is_revoked:
                return None

        user = await repo.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


@dataclass
class CartContext:
    cart: Cart
    service: CartService
    guest_token: str | None
    is_new_guest_token: bool
    user: User | None


# Only customer accounts (and signed-out guests) may build a basket and check
# out. Retailer and administrator sessions are business sessions; letting them
# place customer orders would mix seller and buyer identities on one order.
SHOPPER_ROLES = frozenset({"customer"})


def ensure_can_shop(user: User | None) -> None:
    if user is not None and user.role not in SHOPPER_ROLES:
        raise AppException(
            code="BUSINESS_ACCOUNT_CANNOT_SHOP",
            message=(
                "Retailer and administrator accounts cannot place customer orders. "
                "Sign in with a customer account to shop."
            ),
            status_code=403,
        )


async def _build_cart_context(
    request: Request, response: Response, db: AsyncSession, *, shopping: bool
) -> CartContext:
    service = CartService(db)
    user = await get_current_user_optional(request, db)
    if shopping:
        ensure_can_shop(user)

    guest_token = request.cookies.get(GUEST_CART_COOKIE_NAME) or request.headers.get(
        "X-Guest-Cart-Token"
    )

    customer_id = user.id if user else None
    cart, effective_token, is_new = await service.get_or_create_cart(
        customer_id=customer_id,
        guest_token=guest_token if not customer_id else None,
    )

    if is_new and effective_token and not customer_id:
        set_guest_cart_cookie(response, effective_token)

    return CartContext(
        cart=cart,
        service=service,
        guest_token=effective_token,
        is_new_guest_token=is_new,
        user=user,
    )


async def get_cart_context(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartContext:
    """Cart context for read-only use (any session may view its cart)."""
    return await _build_cart_context(request, response, db, shopping=False)


async def get_shopping_cart_context(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartContext:
    """Cart context for changing the basket or checking out: shoppers only."""
    return await _build_cart_context(request, response, db, shopping=True)
