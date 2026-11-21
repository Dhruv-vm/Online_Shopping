"""Sale Stream: live, time-boxed feed of price drops, flash deals and hot sellers."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events.marketplace_events import enqueue_marketplace_event
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    StoreInventory,
)
from app.modules.sale_stream.models import SaleStreamEvent, SaleStreamEventType
from app.modules.sale_stream.schemas import SaleStreamItem, SaleStreamResponse

logger = logging.getLogger(__name__)

PRICE_DROP_MIN_PCT = 5.0
PRICE_DROP_WINDOW = timedelta(hours=24)
FLASH_DEAL_MAX_WINDOW = timedelta(days=7)
HOT_SELLER_MIN_UNITS = 5
HOT_SELLER_WINDOW = timedelta(hours=6)


def _available(listing: ProductListing) -> int:
    inv = listing.inventory
    return max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0


async def _deactivate(session, listing_id, event_type) -> None:
    await session.execute(
        update(SaleStreamEvent)
        .where(
            SaleStreamEvent.listing_id == listing_id,
            SaleStreamEvent.event_type == event_type,
            SaleStreamEvent.status == "ACTIVE",
        )
        .values(status="SUPERSEDED")
    )


async def _emit(session, ev: SaleStreamEvent) -> None:
    await enqueue_marketplace_event(
        session,
        event_type="sale_stream.event_published",
        aggregate_type="sale_stream_event",
        aggregate_id=ev.id,
        payload={
            "event_type": ev.event_type,
            "listing_id": ev.listing_id,
            "deal_price_paise": ev.flash_price_paise,
            "expires_at": ev.expires_at.isoformat(),
        },
    )


async def record_price_drop(
    session: AsyncSession, *, listing: ProductListing, previous_price_paise: int
) -> SaleStreamEvent | None:
    new = int(listing.selling_price_paise)
    if previous_price_paise <= 0 or new >= previous_price_paise:
        return None
    pct = (previous_price_paise - new) * 100.0 / previous_price_paise
    if pct < PRICE_DROP_MIN_PCT:
        return None
    await _deactivate(session, listing.id, SaleStreamEventType.PRICE_DROP.value)
    now = datetime.now(UTC)
    inv = (
        await session.execute(
            select(StoreInventory).where(StoreInventory.listing_id == listing.id)
        )
    ).scalar_one_or_none()
    ev = SaleStreamEvent(
        id=uuid.uuid4(),
        event_type=SaleStreamEventType.PRICE_DROP.value,
        listing_id=listing.id,
        retailer_id=listing.retailer_id,
        old_price_paise=previous_price_paise,
        flash_price_paise=new,
        stock_remaining=max(0, inv.on_hand_quantity - inv.reserved_quantity)
        if inv
        else 0,
        status="ACTIVE",
        starts_at=now,
        expires_at=now + PRICE_DROP_WINDOW,
    )
    session.add(ev)
    await _emit(session, ev)
    return ev


async def record_flash_deal(
    session: AsyncSession, *, discount
) -> SaleStreamEvent | None:
    """Listing-scoped, time-limited offers become FLASH_DEAL entries."""
    from app.modules.pricing.discount_service import DiscountService

    if not discount.listing_id or not discount.valid_to or not discount.is_active:
        return None
    starts = discount.valid_from or datetime.now(UTC)
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=UTC)
    ends = (
        discount.valid_to
        if discount.valid_to.tzinfo
        else discount.valid_to.replace(tzinfo=UTC)
    )
    if ends - starts > FLASH_DEAL_MAX_WINDOW or ends <= datetime.now(UTC):
        return None
    listing = await session.get(ProductListing, discount.listing_id)
    if listing is None:
        return None
    _, deal_price = DiscountService.calculate_unit_discount(
        int(listing.selling_price_paise), [discount]
    )
    if deal_price >= listing.selling_price_paise:
        return None
    await _deactivate(session, listing.id, SaleStreamEventType.FLASH_DEAL.value)
    inv = (
        await session.execute(
            select(StoreInventory).where(StoreInventory.listing_id == listing.id)
        )
    ).scalar_one_or_none()
    ev = SaleStreamEvent(
        id=uuid.uuid4(),
        event_type=SaleStreamEventType.FLASH_DEAL.value,
        listing_id=listing.id,
        retailer_id=listing.retailer_id,
        discount_id=discount.id,
        old_price_paise=int(listing.selling_price_paise),
        flash_price_paise=int(deal_price),
        stock_remaining=max(0, inv.on_hand_quantity - inv.reserved_quantity)
        if inv
        else 0,
        status="ACTIVE",
        starts_at=starts,
        expires_at=ends,
    )
    session.add(ev)
    await _emit(session, ev)
    return ev


async def detect_hot_sellers(session: AsyncSession) -> int:
    """Background job: listings with >= HOT_SELLER_MIN_UNITS sold in 24h."""
    from app.modules.orders.models import Order, OrderItem

    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(OrderItem.listing_id, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.created_at >= now - timedelta(hours=24),
                Order.status.notin_(["CANCELLED", "PENDING_PAYMENT"]),
            )
            .group_by(OrderItem.listing_id)
            .having(func.sum(OrderItem.quantity) >= HOT_SELLER_MIN_UNITS)
        )
    ).all()
    created = 0
    for listing_id, units in rows:
        listing = await session.get(ProductListing, listing_id)
        if listing is None or not listing.is_active:
            continue
        await _deactivate(session, listing_id, SaleStreamEventType.HOT_SELLER.value)
        ev = SaleStreamEvent(
            id=uuid.uuid4(),
            event_type=SaleStreamEventType.HOT_SELLER.value,
            listing_id=listing_id,
            retailer_id=listing.retailer_id,
            old_price_paise=int(listing.original_price_paise),
            flash_price_paise=int(listing.selling_price_paise),
            units_sold_24h=int(units),
            status="ACTIVE",
            starts_at=now,
            expires_at=now + HOT_SELLER_WINDOW,
        )
        session.add(ev)
        await _emit(session, ev)
        created += 1
    return created


async def expire_sale_stream(session: AsyncSession) -> int:
    res = await session.execute(
        update(SaleStreamEvent)
        .where(
            SaleStreamEvent.status == "ACTIVE",
            SaleStreamEvent.expires_at <= datetime.now(UTC),
        )
        .values(status="EXPIRED")
    )
    return res.rowcount or 0


class SaleStreamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def live_feed(
        self,
        *,
        event_type: str | None = None,
        category_slug: str | None = None,
        before: datetime | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> SaleStreamResponse:
        from app.modules.catalogue.models import Retailer

        now = datetime.now(UTC)
        conds = [
            SaleStreamEvent.status == "ACTIVE",
            SaleStreamEvent.starts_at <= now,
            SaleStreamEvent.expires_at > now,
            ProductListing.is_active.is_(True),
            Retailer.is_active.is_(True),
            Retailer.verification_status == "VERIFIED",
            Product.is_active.is_(True),
        ]
        if event_type:
            conds.append(SaleStreamEvent.event_type == event_type)
        if before:
            conds.append(SaleStreamEvent.created_at < before)
        if since:
            conds.append(SaleStreamEvent.created_at > since)
        stmt = (
            select(SaleStreamEvent, ProductListing)
            .join(ProductListing, ProductListing.id == SaleStreamEvent.listing_id)
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .join(ProductVariant, ProductVariant.id == ProductListing.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .options(
                selectinload(ProductListing.inventory),
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.category),
            )
            .where(and_(*conds))
            .order_by(SaleStreamEvent.created_at.desc())
            .limit(limit)
        )
        if category_slug:
            stmt = stmt.join(Category, Category.id == Product.category_id).where(
                Category.slug == category_slug
            )
        rows = (await self.session.execute(stmt)).all()
        items: list[SaleStreamItem] = []
        for ev, listing in rows:
            product = listing.variant.product
            imgs = sorted(
                product.images or [], key=lambda i: (not i.is_primary, i.sort_order)
            )
            exp = (
                ev.expires_at
                if ev.expires_at.tzinfo
                else ev.expires_at.replace(tzinfo=UTC)
            )
            current = int(listing.selling_price_paise)
            deal = int(ev.flash_price_paise)
            items.append(
                SaleStreamItem(
                    id=ev.id,
                    event_type=ev.event_type,
                    listing_id=listing.id,
                    product_id=product.id,
                    product_name=product.name,
                    variant_name=listing.variant.name,
                    image_url=imgs[0].url if imgs else None,
                    retailer_id=listing.retailer_id,
                    retailer_name=listing.retailer.name,
                    category_slug=product.category.slug if product.category else None,
                    old_price_paise=int(ev.old_price_paise),
                    deal_price_paise=deal,
                    current_price_paise=current,
                    discount_pct=round(
                        (ev.old_price_paise - deal) * 100.0 / ev.old_price_paise, 1
                    )
                    if ev.old_price_paise
                    else 0.0,
                    stock_remaining=_available(listing),
                    units_sold_24h=ev.units_sold_24h,
                    starts_at=ev.starts_at,
                    expires_at=ev.expires_at,
                    seconds_remaining=max(0, int((exp - now).total_seconds())),
                    created_at=ev.created_at,
                )
            )
        return SaleStreamResponse(
            items=items,
            next_cursor=items[-1].created_at if len(items) == limit else None,
            server_time=now,
        )
