"""Basket Price Intelligence: history capture and discount authenticity."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.modules.catalogue.models import ProductListing, Retailer
from app.modules.price_intel.models import PriceHistoryTick
from app.modules.price_intel.schemas import (
    PriceIntelligenceResponse,
    PricePoint,
)

logger = logging.getLogger(__name__)

MIN_DAYS_FOR_VERDICT = 7
GENUINE_DISCOUNT_THRESHOLD = 0.05  # >=5% below own 30-day average
MRP_INFLATION_THRESHOLD = 0.10  # MRP raised >=10% within 30 days


async def record_price_tick(
    session: AsyncSession,
    *,
    listing_id: uuid.UUID,
    selling_price_paise: int,
    mrp_paise: int,
    on: date | None = None,
) -> None:
    """Idempotent daily upsert; keeps the latest price and the day's low."""
    day = on or datetime.now(UTC).date()
    stmt = pg_insert(PriceHistoryTick).values(
        id=uuid.uuid4(),
        listing_id=listing_id,
        recorded_date=day,
        selling_price_paise=int(selling_price_paise),
        day_low_paise=int(selling_price_paise),
        mrp_paise=int(mrp_paise),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_tick_listing_day",
        set_={
            "selling_price_paise": stmt.excluded.selling_price_paise,
            "mrp_paise": stmt.excluded.mrp_paise,
            "day_low_paise": func.least(
                PriceHistoryTick.day_low_paise, stmt.excluded.day_low_paise
            ),
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)


async def snapshot_all_active_listings(session: AsyncSession) -> int:
    """Daily background snapshot so listings with no price change still have history."""
    rows = (
        await session.execute(
            select(
                ProductListing.id,
                ProductListing.selling_price_paise,
                ProductListing.original_price_paise,
            ).where(ProductListing.is_active.is_(True))
        )
    ).all()
    for lid, sp, mrp in rows:
        await record_price_tick(
            session, listing_id=lid, selling_price_paise=sp, mrp_paise=mrp
        )
    return len(rows)


def _avg(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


class PriceIntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_listing_intelligence(
        self, listing_id: uuid.UUID, days: int = 90
    ) -> PriceIntelligenceResponse:
        listing = (
            await self.session.execute(
                select(ProductListing)
                .options(selectinload(ProductListing.retailer))
                .where(ProductListing.id == listing_id)
            )
        ).scalar_one_or_none()
        retailer: Retailer | None = listing.retailer if listing else None
        if (
            listing is None
            or not listing.is_active
            or retailer is None
            or not retailer.is_active
            or retailer.verification_status != "VERIFIED"
        ):
            raise AppException(
                code="LISTING_NOT_FOUND", message="Listing not found.", status_code=404
            )

        today = datetime.now(UTC).date()
        since = today - timedelta(days=days - 1)
        ticks = list(
            (
                await self.session.execute(
                    select(PriceHistoryTick)
                    .where(
                        PriceHistoryTick.listing_id == listing_id,
                        PriceHistoryTick.recorded_date >= since,
                    )
                    .order_by(PriceHistoryTick.recorded_date.asc())
                )
            ).scalars()
        )

        current = int(listing.selling_price_paise)
        current_mrp = int(listing.original_price_paise)
        lows = [t.day_low_paise for t in ticks] + [current]
        closes = [t.selling_price_paise for t in ticks]
        d30 = today - timedelta(days=30)
        prior_30 = [
            t.selling_price_paise for t in ticks if d30 <= t.recorded_date < today
        ]
        mrp_recent = [t.mrp_paise for t in ticks if t.recorded_date >= d30]
        mrp_older = [t.mrp_paise for t in ticks if t.recorded_date < d30]

        lowest = min(lows)
        highest = max(closes + [current])
        avg_30 = _avg(prior_30)
        avg_90 = _avg(closes)
        distinct_days = len({t.recorded_date for t in ticks})

        vs_avg_pct = round((current - avg_30) * 100.0 / avg_30, 2) if avg_30 else None
        discount_from_mrp_pct = (
            round((current_mrp - current) * 100.0 / current_mrp, 2)
            if current_mrp
            else 0.0
        )
        mrp_inflated = bool(
            mrp_recent
            and mrp_older
            and max(mrp_recent) >= min(mrp_older) * (1 + MRP_INFLATION_THRESHOLD)
            and discount_from_mrp_pct >= 10
        )

        if distinct_days < MIN_DAYS_FOR_VERDICT:
            badge, reason = (
                "INSUFFICIENT_HISTORY",
                f"Only {distinct_days} day(s) of price history; at least {MIN_DAYS_FOR_VERDICT} are needed.",
            )
        elif mrp_inflated:
            badge, reason = (
                "MRP_INFLATED",
                "MRP was raised within the last 30 days; the advertised discount may be overstated.",
            )
        elif avg_30 and current <= avg_30 * (1 - GENUINE_DISCOUNT_THRESHOLD):
            badge, reason = (
                "GENUINE_DISCOUNT",
                f"Current price is {abs(vs_avg_pct or 0):.1f}% below its own 30-day average.",
            )
        else:
            badge, reason = (
                "NO_SPECIAL_DISCOUNT",
                "Current price is in line with its recent average.",
            )

        return PriceIntelligenceResponse(
            listing_id=listing.id,
            currency="INR",
            window_days=days,
            current_price_paise=current,
            current_mrp_paise=current_mrp,
            lowest_price_paise=lowest,
            highest_price_paise=highest,
            average_price_30d_paise=avg_30,
            average_price_90d_paise=avg_90,
            current_vs_30d_average_pct=vs_avg_pct,
            discount_from_mrp_pct=discount_from_mrp_pct,
            is_lowest_in_window=current <= lowest,
            days_of_history=distinct_days,
            badge=badge,
            badge_reason=reason,
            history=[
                PricePoint(
                    date=t.recorded_date,
                    price_paise=t.selling_price_paise,
                    day_low_paise=t.day_low_paise,
                    mrp_paise=t.mrp_paise,
                )
                for t in ticks
            ],
        )
