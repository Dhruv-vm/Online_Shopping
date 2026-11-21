"""Price comparison, price alerts, retailer pricing insights and data-quality
monitoring (Phase 3F completion)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.notify import notify_customer
from app.modules.catalogue.models import (
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.price_intel.models import PriceAlert, PriceHistoryTick
from app.modules.price_intel.schemas import (
    PriceAlertItem,
    PriceComparisonOffer,
    PriceComparisonResponse,
    PriceDataQualityResponse,
    RetailerPriceInsight,
)

MAX_ACTIVE_ALERTS_PER_USER = 50


def _public_listing_conditions():
    return (
        ProductListing.is_active.is_(True),
        Retailer.is_active.is_(True),
        Retailer.verification_status == "VERIFIED",
    )


async def _variant(session: AsyncSession, variant_id: uuid.UUID) -> ProductVariant:
    v = (
        await session.execute(
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(ProductVariant.id == variant_id)
        )
    ).scalar_one_or_none()
    if v is None or not v.is_active or not v.product.is_active:
        raise AppException(
            code="VARIANT_NOT_FOUND",
            message="Product variant not found.",
            status_code=404,
        )
    return v


async def best_public_price(session: AsyncSession, variant_id: uuid.UUID) -> int | None:
    return (
        await session.execute(
            select(func.min(ProductListing.selling_price_paise))
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .where(
                ProductListing.variant_id == variant_id, *_public_listing_conditions()
            )
        )
    ).scalar()


async def compare_variant_prices(
    session: AsyncSession, variant_id: uuid.UUID
) -> PriceComparisonResponse:
    v = await _variant(session, variant_id)
    rows = (
        await session.execute(
            select(ProductListing, Retailer, StoreInventory)
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .outerjoin(StoreInventory, StoreInventory.listing_id == ProductListing.id)
            .where(
                ProductListing.variant_id == variant_id, *_public_listing_conditions()
            )
            .order_by(ProductListing.selling_price_paise.asc())
        )
    ).all()
    cheapest = int(rows[0][0].selling_price_paise) if rows else None
    offers = []
    for listing, retailer, inv in rows:
        avail = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
        price = int(listing.selling_price_paise)
        mrp = int(listing.original_price_paise)
        offers.append(
            PriceComparisonOffer(
                listing_id=listing.id,
                retailer_id=retailer.id,
                retailer_name=retailer.name,
                retailer_state=retailer.state,
                selling_price_paise=price,
                mrp_paise=mrp,
                discount_from_mrp_pct=round((mrp - price) * 100.0 / mrp, 2)
                if mrp
                else 0.0,
                available_quantity=avail,
                in_stock=avail > 0,
                is_cheapest=price == cheapest,
                difference_from_cheapest_paise=price - (cheapest or price),
            )
        )
    spread = (int(rows[-1][0].selling_price_paise) - cheapest) if rows else 0
    if not offers:
        explanation = "No verified store currently sells this variant."
    elif len(offers) == 1:
        explanation = f"Only {offers[0].retailer_name} sells this variant right now."
    else:
        explanation = (
            f"{len(offers)} verified stores sell this variant. Prices differ by up to "
            f"₹{spread / 100:,.2f} because each store sets its own price and MRP."
        )
    return PriceComparisonResponse(
        variant_id=v.id,
        product_name=v.product.name,
        variant_name=v.name,
        offers=offers,
        cheapest_price_paise=cheapest,
        price_spread_paise=spread,
        explanation=explanation,
    )


async def _serialize_alerts(
    session: AsyncSession, alerts: list[PriceAlert]
) -> list[PriceAlertItem]:
    out = []
    for a in alerts:
        v = await session.get(
            ProductVariant, a.variant_id, options=[selectinload(ProductVariant.product)]
        )
        out.append(
            PriceAlertItem(
                id=a.id,
                variant_id=a.variant_id,
                product_name=v.product.name if v else "",
                variant_name=v.name if v else "",
                target_price_paise=a.target_price_paise,
                current_best_price_paise=await best_public_price(session, a.variant_id),
                status=a.status,
                triggered_price_paise=a.triggered_price_paise,
                triggered_at=a.triggered_at,
                created_at=a.created_at,
            )
        )
    return out


async def create_price_alert(
    session: AsyncSession, user_id: uuid.UUID, variant_id: uuid.UUID, target: int
) -> PriceAlertItem:
    await _variant(session, variant_id)
    active = (
        await session.execute(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user_id, PriceAlert.status == "ACTIVE")
        )
    ).scalar() or 0
    existing = (
        await session.execute(
            select(PriceAlert)
            .where(
                PriceAlert.user_id == user_id,
                PriceAlert.variant_id == variant_id,
                PriceAlert.status == "ACTIVE",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is None and active >= MAX_ACTIVE_ALERTS_PER_USER:
        raise AppException(
            code="TOO_MANY_ALERTS",
            message=f"You can keep at most {MAX_ACTIVE_ALERTS_PER_USER} active price alerts.",
            status_code=409,
        )
    if existing:
        existing.target_price_paise = target
        alert = existing
    else:
        alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            variant_id=variant_id,
            target_price_paise=target,
        )
        session.add(alert)
    await session.flush()
    await session.refresh(alert)
    # Already at or below target? Trigger immediately so the customer is told now.
    await trigger_price_alerts(session, variant_id)
    await session.refresh(alert)
    return (await _serialize_alerts(session, [alert]))[0]


async def list_price_alerts(
    session: AsyncSession, user_id: uuid.UUID
) -> list[PriceAlertItem]:
    alerts = list(
        (
            await session.execute(
                select(PriceAlert)
                .where(PriceAlert.user_id == user_id, PriceAlert.status != "CANCELLED")
                .order_by(PriceAlert.created_at.desc())
                .limit(100)
            )
        ).scalars()
    )
    return await _serialize_alerts(session, alerts)


async def cancel_price_alert(
    session: AsyncSession, user_id: uuid.UUID, alert_id: uuid.UUID
) -> PriceAlertItem:
    a = await session.get(PriceAlert, alert_id, with_for_update=True)
    if a is None or a.user_id != user_id:
        raise AppException(
            code="ALERT_NOT_FOUND", message="Price alert not found.", status_code=404
        )
    a.status = "CANCELLED"
    await session.flush()
    return (await _serialize_alerts(session, [a]))[0]


async def trigger_price_alerts(session: AsyncSession, variant_id: uuid.UUID) -> int:
    """Notify customers whose target price has been reached by a live listing."""
    best = (
        await session.execute(
            select(ProductListing.id, ProductListing.selling_price_paise)
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .where(
                ProductListing.variant_id == variant_id, *_public_listing_conditions()
            )
            .order_by(ProductListing.selling_price_paise.asc())
            .limit(1)
        )
    ).first()
    if best is None:
        return 0
    listing_id, price = best
    alerts = list(
        (
            await session.execute(
                select(PriceAlert)
                .where(
                    PriceAlert.variant_id == variant_id,
                    PriceAlert.status == "ACTIVE",
                    PriceAlert.target_price_paise >= price,
                )
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )
    if not alerts:
        return 0
    v = await session.get(
        ProductVariant, variant_id, options=[selectinload(ProductVariant.product)]
    )
    now = datetime.now(UTC)
    for a in alerts:
        a.status = "TRIGGERED"
        a.triggered_at = now
        a.triggered_listing_id = listing_id
        a.triggered_price_paise = int(price)
        notify_customer(
            session,
            customer_id=a.user_id,
            title="Price alert: target reached",
            message=(
                f"{v.product.name if v else 'A product you follow'} is now ₹{int(price) / 100:,.2f} "
                f"(your target: ₹{a.target_price_paise / 100:,.2f})."
            ),
            event_type="PRICE_ALERT_TRIGGERED",
        )
    await session.flush()
    return len(alerts)


async def retailer_price_insights(
    session: AsyncSession, retailer: Retailer
) -> list[RetailerPriceInsight]:
    mine = list(
        (
            await session.execute(
                select(ProductListing)
                .options(
                    selectinload(ProductListing.variant).selectinload(
                        ProductVariant.product
                    )
                )
                .where(
                    ProductListing.retailer_id == retailer.id,
                    ProductListing.is_active.is_(True),
                )
                .order_by(ProductListing.created_at.desc())
                .limit(200)
            )
        ).scalars()
    )
    out = []
    for lst in mine:
        competitors = [
            int(p)
            for (p,) in (
                await session.execute(
                    select(ProductListing.selling_price_paise)
                    .join(Retailer, Retailer.id == ProductListing.retailer_id)
                    .where(
                        ProductListing.variant_id == lst.variant_id,
                        ProductListing.retailer_id != retailer.id,
                        *_public_listing_conditions(),
                    )
                )
            ).all()
        ]
        my_price = int(lst.selling_price_paise)
        lowest = min(competitors) if competitors else None
        days = (
            await session.execute(
                select(func.count(func.distinct(PriceHistoryTick.recorded_date))).where(
                    PriceHistoryTick.listing_id == lst.id
                )
            )
        ).scalar() or 0
        alerts = (
            await session.execute(
                select(func.count())
                .select_from(PriceAlert)
                .where(
                    PriceAlert.variant_id == lst.variant_id,
                    PriceAlert.status == "ACTIVE",
                )
            )
        ).scalar() or 0
        out.append(
            RetailerPriceInsight(
                listing_id=lst.id,
                product_name=lst.variant.product.name,
                variant_name=lst.variant.name,
                my_price_paise=my_price,
                competitor_count=len(competitors),
                lowest_competitor_price_paise=lowest,
                my_rank=1 + sum(1 for p in competitors if p < my_price),
                gap_to_lowest_paise=(my_price - lowest) if lowest is not None else None,
                days_of_history=int(days),
                active_price_alerts=int(alerts),
            )
        )
    return out


async def price_data_quality(session: AsyncSession) -> PriceDataQualityResponse:
    week_ago = datetime.now(UTC).date() - timedelta(days=7)
    active_ids = select(ProductListing.id).where(ProductListing.is_active.is_(True))
    active = (
        await session.execute(select(func.count()).select_from(active_ids.subquery()))
    ).scalar() or 0
    without = (
        await session.execute(
            select(func.count()).select_from(
                active_ids.where(
                    ~ProductListing.id.in_(select(PriceHistoryTick.listing_id))
                ).subquery()
            )
        )
    ).scalar() or 0
    with_demo = (
        await session.execute(
            select(func.count(func.distinct(PriceHistoryTick.listing_id))).where(
                PriceHistoryTick.source == "DEMO_SEED",
                PriceHistoryTick.listing_id.in_(active_ids),
            )
        )
    ).scalar() or 0
    live = (
        await session.execute(
            select(func.count()).where(PriceHistoryTick.source == "LIVE")
        )
    ).scalar() or 0
    demo = (
        await session.execute(
            select(func.count()).where(PriceHistoryTick.source == "DEMO_SEED")
        )
    ).scalar() or 0
    stale = (
        await session.execute(
            select(func.count()).select_from(
                active_ids.where(
                    ~ProductListing.id.in_(
                        select(PriceHistoryTick.listing_id).where(
                            PriceHistoryTick.recorded_date >= week_ago
                        )
                    )
                ).subquery()
            )
        )
    ).scalar() or 0
    above_mrp = (
        await session.execute(
            select(func.count()).where(
                ProductListing.is_active.is_(True),
                ProductListing.selling_price_paise
                > ProductListing.original_price_paise,
            )
        )
    ).scalar() or 0
    swings = (
        await session.execute(
            select(func.count()).where(
                and_(
                    PriceHistoryTick.recorded_date >= week_ago,
                    PriceHistoryTick.day_low_paise * 2
                    < PriceHistoryTick.selling_price_paise,
                )
            )
        )
    ).scalar() or 0
    alerts = (
        await session.execute(select(func.count()).where(PriceAlert.status == "ACTIVE"))
    ).scalar() or 0
    return PriceDataQualityResponse(
        active_listings=int(active),
        listings_without_history=int(without),
        listings_with_demo_history=int(with_demo),
        live_ticks=int(live),
        demo_ticks=int(demo),
        stale_listings_7d=int(stale),
        selling_above_mrp=int(above_mrp),
        large_daily_swings=int(swings),
        active_price_alerts=int(alerts),
        generated_at=datetime.now(UTC),
    )
