"""Issue, apply and consume customer-specific price awards (see PriceAward)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pricing.models import PriceAward, PriceAwardStatus

DEFAULT_AWARD_TTL = timedelta(hours=48)


async def issue_award(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    listing_id: uuid.UUID,
    unit_price_paise: int,
    max_quantity: int,
    source: str,
    source_id: uuid.UUID,
    ttl: timedelta = DEFAULT_AWARD_TTL,
) -> PriceAward:
    """Create an ACTIVE award, revoking earlier ACTIVE awards from the same source."""
    await session.execute(
        update(PriceAward)
        .where(
            PriceAward.customer_id == customer_id,
            PriceAward.listing_id == listing_id,
            PriceAward.source == source,
            PriceAward.status == PriceAwardStatus.ACTIVE.value,
        )
        .values(status=PriceAwardStatus.REVOKED.value)
    )
    award = PriceAward(
        id=uuid.uuid4(),
        customer_id=customer_id,
        listing_id=listing_id,
        unit_price_paise=int(unit_price_paise),
        max_quantity=int(max_quantity),
        source=source,
        source_id=source_id,
        status=PriceAwardStatus.ACTIVE.value,
        expires_at=datetime.now(UTC) + ttl,
    )
    session.add(award)
    return award


async def best_award_for_line(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID | None,
    listing_id: uuid.UUID,
    quantity: int,
) -> PriceAward | None:
    """Lowest-priced ACTIVE, unexpired award that covers the whole line quantity."""
    if customer_id is None:
        return None
    now = datetime.now(UTC)
    stmt = (
        select(PriceAward)
        .where(
            PriceAward.customer_id == customer_id,
            PriceAward.listing_id == listing_id,
            PriceAward.status == PriceAwardStatus.ACTIVE.value,
            PriceAward.expires_at > now,
            PriceAward.max_quantity >= quantity,
        )
        .order_by(PriceAward.unit_price_paise.asc(), PriceAward.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def consume_awards_for_quote(
    session: AsyncSession, *, quote_id: uuid.UUID, order_id: uuid.UUID
) -> int:
    """Mark awards applied to a consumed quote as USED (single-use guarantee)."""
    res = await session.execute(
        update(PriceAward)
        .where(
            PriceAward.quote_id == quote_id,
            PriceAward.status == PriceAwardStatus.ACTIVE.value,
        )
        .values(
            status=PriceAwardStatus.USED.value,
            order_id=order_id,
            used_at=datetime.now(UTC),
        )
        .returning(PriceAward.id, PriceAward.source)
    )
    used = res.all()
    group_award_ids = [aid for aid, source in used if source == "GROUP_BUY"]
    if group_award_ids:
        from app.modules.community.models import GroupBuyMember

        await session.execute(
            update(GroupBuyMember)
            .where(GroupBuyMember.award_id.in_(group_award_ids))
            .values(status="PURCHASED", order_id=order_id)
        )
    return len(used)


async def expire_stale_awards(session: AsyncSession) -> int:
    res = await session.execute(
        update(PriceAward)
        .where(
            PriceAward.status == PriceAwardStatus.ACTIVE.value,
            PriceAward.expires_at <= datetime.now(UTC),
        )
        .values(status=PriceAwardStatus.EXPIRED.value)
    )
    return res.rowcount or 0
