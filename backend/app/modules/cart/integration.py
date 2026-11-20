"""Transactional cart helpers for Phase 3 flows (no intermediate commits)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.catalogue.models import ProductListing

MAX_CART_LINE_QTY = 10


async def set_customer_cart_lines(
    session: AsyncSession,
    customer_id: uuid.UUID,
    lines: list[tuple[uuid.UUID, int]],
    *,
    remove_listing_ids: list[uuid.UUID] | None = None,
) -> Cart:
    """Ensure each (listing, quantity) is in the customer's ACTIVE cart with exactly
    that quantity, optionally removing other listings first; supersedes quotes."""
    repo = CartRepository(session)
    cart = await repo.get_active_cart_by_customer_id(customer_id)
    if cart is None:
        cart = await repo.create_cart(customer_id=customer_id)
    items = {
        i.listing_id: i
        for i in (
            await session.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        ).scalars()
    }
    for lid in remove_listing_ids or []:
        if lid in items:
            await session.delete(items.pop(lid))
    for listing_id, qty in lines:
        qty = max(1, min(int(qty), MAX_CART_LINE_QTY))
        if listing_id in items:
            items[listing_id].quantity = qty
            continue
        listing = await session.get(ProductListing, listing_id)
        session.add(
            CartItem(
                id=uuid.uuid4(),
                cart_id=cart.id,
                listing_id=listing_id,
                variant_id=listing.variant_id,
                retailer_id=listing.retailer_id,
                quantity=qty,
            )
        )
    from app.modules.pricing.models import CheckoutQuote, QuoteStatus

    for q in (
        await session.execute(
            select(CheckoutQuote).where(
                CheckoutQuote.cart_id == cart.id,
                CheckoutQuote.status == QuoteStatus.ACTIVE.value,
            )
        )
    ).scalars():
        q.status = QuoteStatus.SUPERSEDED.value
    await session.flush()
    return cart
