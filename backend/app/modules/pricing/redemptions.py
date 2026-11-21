"""Discount usage accounting (Version 2.0 Phase B4).

``discounts.times_used`` counts the orders currently holding a use of the
discount. A use is reserved when the order is created and released once if the
order is cancelled before payment or its payment window expires. Paid orders
keep their use.

Concurrency: discount rows are locked (``SELECT ... FOR UPDATE``, in id order to
avoid deadlocks) before ``usage_limit`` is checked and ``times_used`` is
incremented, so concurrent orders can never exceed the limit. Release flips
RESERVED → RELEASED in one ``UPDATE ... RETURNING``; a second release (e.g.
cancellation racing payment-window expiry) finds nothing to flip and decrements
nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.pricing.discount_service import discount_is_live
from app.modules.pricing.models import (
    Discount,
    DiscountRedemption,
    DiscountRedemptionStatus,
)


def applied_discount_ids(items: Iterable) -> list[uuid.UUID]:
    """Distinct discount ids priced into a quote's (or order's quote's) lines."""
    ids: set[uuid.UUID] = set()
    for item in items:
        for raw in getattr(item, "applied_discount_ids", None) or []:
            ids.add(uuid.UUID(str(raw)))
    return sorted(ids, key=str)


async def reserve_discount_usage(
    session: AsyncSession, *, discount_ids: list[uuid.UUID], order_id: uuid.UUID
) -> int:
    """Reserve one use of each discount for ``order_id``; raise 409 if any is
    no longer available or its usage limit is reached (the caller's transaction
    then rolls back, so nothing is half-applied)."""
    if not discount_ids:
        return 0
    rows = (
        (
            await session.execute(
                select(Discount)
                .where(Discount.id.in_(discount_ids))
                .order_by(Discount.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    by_id = {d.id: d for d in rows}
    now = datetime.now(UTC)
    for did in discount_ids:
        d = by_id.get(did)
        if d is None or not discount_is_live(d, now, check_usage=False):
            raise AppException(
                code="DISCOUNT_NO_LONGER_AVAILABLE",
                message="A discount in your quote is no longer available. Please refresh your quote.",
                status_code=409,
            )
        if d.usage_limit is not None and d.times_used >= d.usage_limit:
            raise AppException(
                code="DISCOUNT_USAGE_LIMIT_REACHED",
                message="A discount in your quote has reached its usage limit. Please refresh your quote.",
                status_code=409,
            )
    for did in discount_ids:
        by_id[did].times_used += 1
        session.add(
            DiscountRedemption(
                id=uuid.uuid4(),
                discount_id=did,
                order_id=order_id,
                status=DiscountRedemptionStatus.RESERVED.value,
            )
        )
    await session.flush()
    return len(discount_ids)


async def release_discount_usage(
    session: AsyncSession, *, order_id: uuid.UUID, reason: str
) -> int:
    """Release the order's reserved discount uses exactly once. Returns how many
    uses were released (0 if already released or none were reserved)."""
    released = (
        (
            await session.execute(
                update(DiscountRedemption)
                .where(
                    DiscountRedemption.order_id == order_id,
                    DiscountRedemption.status
                    == DiscountRedemptionStatus.RESERVED.value,
                )
                .values(
                    status=DiscountRedemptionStatus.RELEASED.value,
                    released_at=datetime.now(UTC),
                    release_reason=reason[:64],
                )
                .returning(DiscountRedemption.discount_id)
                .execution_options(synchronize_session=False)
            )
        )
        .scalars()
        .all()
    )
    for did in sorted(released, key=str):
        await session.execute(
            update(Discount)
            .where(Discount.id == did)
            .values(times_used=func.greatest(Discount.times_used - 1, 0))
            .execution_options(synchronize_session=False)
        )
    return len(released)
