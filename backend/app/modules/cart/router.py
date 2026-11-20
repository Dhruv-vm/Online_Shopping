import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import AppException
from app.modules.cart.dependencies import (
    CartContext,
    clear_guest_cart_cookie,
    get_cart_context,
)
from app.modules.cart.schemas import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartMergeRequest,
    CartMergeResponse,
    CartResponse,
)
from app.modules.cart.service import CartService
from app.modules.identity.dependencies import (
    get_current_active_user,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.substitutes.schemas import (
    CartItemReplaceRequest,
    CartItemReplaceResponse,
    SubstituteListResponse,
    SubstituteType,
)
from app.modules.substitutes.service import SubstituteService

cart_router = APIRouter(prefix="/cart", tags=["Cart"])


@cart_router.get(
    "",
    response_model=CartResponse,
    summary="Get active cart for customer or guest",
)
async def get_cart(
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartResponse:
    items = await ctx.service.repo.get_cart_items(ctx.cart.id)
    return ctx.service.format_cart_response(ctx.cart, items)


@cart_router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf_token)],
    summary="Add an item listing to cart",
)
async def add_item_to_cart(
    body: CartItemAddRequest,
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartResponse:
    return await ctx.service.add_item(
        cart_id=ctx.cart.id,
        listing_id=body.listing_id,
        quantity=body.quantity,
    )


@cart_router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update item quantity in cart",
)
async def update_cart_item(
    item_id: uuid.UUID,
    body: CartItemUpdateRequest,
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartResponse:
    return await ctx.service.update_item_quantity(
        cart_id=ctx.cart.id,
        item_id=item_id,
        quantity=body.quantity,
    )


@cart_router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Remove an item from cart",
)
async def remove_cart_item(
    item_id: uuid.UUID,
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartResponse:
    return await ctx.service.remove_item(
        cart_id=ctx.cart.id,
        item_id=item_id,
    )


@cart_router.delete(
    "",
    response_model=CartResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Clear all items in cart",
)
async def clear_cart(
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartResponse:
    return await ctx.service.clear_cart(cart_id=ctx.cart.id)


@cart_router.get(
    "/items/{item_id}/substitutes",
    response_model=SubstituteListResponse,
    summary="Get substitute recommendations for an item in the active cart",
)
async def get_cart_item_substitutes(
    item_id: uuid.UUID,
    ctx: Annotated[CartContext, Depends(get_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    type: Annotated[
        SubstituteType | None,
        Query(description="Filter by substitute category"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=20, description="Maximum number of substitutes"),
    ] = 10,
    in_stock_only: Annotated[
        bool,
        Query(description="Only return verified in-stock substitutes"),
    ] = True,
) -> SubstituteListResponse:
    # Ensure item belongs to active cart
    item = await ctx.service.repo.get_cart_item_by_id(item_id)
    if not item or item.cart_id != ctx.cart.id:
        raise AppException(
            code="ITEM_NOT_FOUND",
            message="Cart item not found.",
            status_code=404,
        )

    sub_service = SubstituteService(db)
    return await sub_service.get_substitutes_for_listing(
        listing_id=item.listing_id,
        filter_type=type,
        limit=limit,
        in_stock_only=in_stock_only,
        customer_id=ctx.cart.customer_id,
    )


@cart_router.post(
    "/items/{item_id}/replace",
    response_model=CartItemReplaceResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf_token)],
    summary="Replace a cart item with an intelligent substitute",
)
async def replace_cart_item(
    item_id: uuid.UUID,
    body: CartItemReplaceRequest,
    ctx: Annotated[CartContext, Depends(get_cart_context)],
) -> CartItemReplaceResponse:
    updated_cart, old_id, new_id = await ctx.service.replace_item(
        cart_id=ctx.cart.id,
        item_id=item_id,
        new_listing_id=body.new_listing_id,
        quantity=body.quantity,
    )
    return CartItemReplaceResponse(
        cart=updated_cart,
        replaced_item_id=old_id,
        new_item_id=new_id,
        message="Item successfully replaced in your basket.",
    )


@cart_router.post(
    "/merge",
    response_model=CartMergeResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Merge guest cart into authenticated customer cart",
)
async def merge_guest_cart(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: CartMergeRequest | None = None,
) -> CartMergeResponse:
    service = CartService(db)

    guest_token = (
        body.guest_token
        if body and body.guest_token
        else (
            request.cookies.get("basket_guest_cart")
            or request.headers.get("X-Guest-Cart-Token")
        )
    )

    merged_cart, migrated_count, warnings = await service.merge_guest_cart(
        customer_id=current_user.id,
        guest_token=guest_token,
    )

    # Clear guest cookie
    clear_guest_cart_cookie(response)

    return CartMergeResponse(
        cart=merged_cart,
        migrated_items_count=migrated_count,
        warnings=warnings,
    )
