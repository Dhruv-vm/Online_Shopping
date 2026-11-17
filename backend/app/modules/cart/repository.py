import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cart.models import Cart, CartItem
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
)


class CartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_cart_by_customer_id(
        self, customer_id: uuid.UUID, for_update: bool = False
    ) -> Cart | None:
        stmt = select(Cart).where(
            Cart.customer_id == customer_id, Cart.status == "ACTIVE"
        )
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_cart_by_guest_token_hash(
        self, guest_token_hash: str, for_update: bool = False
    ) -> Cart | None:
        stmt = select(Cart).where(
            Cart.guest_token_hash == guest_token_hash, Cart.status == "ACTIVE"
        )
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_cart_by_id(
        self, cart_id: uuid.UUID, for_update: bool = False
    ) -> Cart | None:
        stmt = select(Cart).where(Cart.id == cart_id)
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_cart_items(self, cart_id: uuid.UUID) -> list[CartItem]:
        stmt = (
            select(CartItem)
            .where(CartItem.cart_id == cart_id)
            .order_by(CartItem.created_at.asc())
            .options(
                selectinload(CartItem.listing).selectinload(ProductListing.inventory),
                selectinload(CartItem.listing).selectinload(ProductListing.retailer),
                selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(CartItem.retailer),
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_cart(
        self,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        currency: str = "INR",
        expires_at: datetime | None = None,
    ) -> Cart:
        cart = Cart(
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            currency=currency,
            status="ACTIVE",
            expires_at=expires_at,
        )
        self.session.add(cart)
        await self.session.flush()
        return cart

    async def get_cart_item(
        self, cart_id: uuid.UUID, listing_id: uuid.UUID, for_update: bool = False
    ) -> CartItem | None:
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.listing_id == listing_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_cart_item_by_id(
        self, item_id: uuid.UUID, for_update: bool = False
    ) -> CartItem | None:
        stmt = select(CartItem).where(CartItem.id == item_id)
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_cart_item(
        self,
        cart_id: uuid.UUID,
        listing_id: uuid.UUID,
        variant_id: uuid.UUID,
        retailer_id: uuid.UUID,
        quantity: int,
    ) -> CartItem:
        item = CartItem(
            cart_id=cart_id,
            listing_id=listing_id,
            variant_id=variant_id,
            retailer_id=retailer_id,
            quantity=quantity,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_cart_item_quantity(
        self, item: CartItem, quantity: int
    ) -> CartItem:
        item.quantity = quantity
        await self.session.flush()
        return item

    async def remove_cart_item(self, item: CartItem) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def clear_cart(self, cart_id: uuid.UUID) -> None:
        stmt = delete(CartItem).where(CartItem.cart_id == cart_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_cart_merged(self, cart: Cart) -> None:
        cart.status = "MERGED"
        await self.session.flush()

    async def get_listing_with_details(
        self, listing_id: uuid.UUID
    ) -> ProductListing | None:
        stmt = (
            select(ProductListing)
            .where(ProductListing.id == listing_id)
            .options(
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.inventory),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
