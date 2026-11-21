"""Backend-verified Basket Mission completion (final cycle, Part 10).

A mission is COMPLETED only when a *paid* order of the same customer, created
after the mission was sent to the cart, contains every selected item's listing.
The customer cannot mark it completed; it completes once (the status check makes
a second paid order a no-op). No rewards are attached: reward missions need
product rules and approval first.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.notify import notify_customer
from app.modules.missions.models import ShoppingMission
from app.modules.orders.models import Order, OrderItem, PaymentStatus

OPEN = ("ACTIVE", "SAVED")


async def purchased_listing_ids(
    session: AsyncSession, customer_id: uuid.UUID, since
) -> set[uuid.UUID]:
    """Listings the customer bought in paid orders created at/after ``since``."""
    if since is None:
        return set()
    rows = await session.execute(
        select(OrderItem.listing_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.customer_id == customer_id,
            Order.payment_status == PaymentStatus.SUCCEEDED.value,
            Order.created_at >= since,
        )
    )
    return {r for (r,) in rows}


async def complete_missions_for_order(session: AsyncSession, order: Order) -> int:
    """Called after a payment is captured. Returns how many missions completed."""
    if (
        order.customer_id is None
        or order.payment_status != PaymentStatus.SUCCEEDED.value
    ):
        return 0  # only a paid order can complete a mission
    missions = (
        (
            await session.execute(
                select(ShoppingMission)
                .options(selectinload(ShoppingMission.items))
                .where(
                    ShoppingMission.customer_id == order.customer_id,
                    ShoppingMission.status.in_(OPEN),
                    ShoppingMission.carted_at.is_not(None),
                    ShoppingMission.carted_at <= order.created_at,
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    if not missions:
        return 0
    in_order = {i.listing_id for i in order.items}
    done = 0
    for m in missions:
        selected = {i.listing_id for i in m.items if i.is_selected}
        if selected and selected <= in_order:
            m.status = "COMPLETED"
            m.completed_at = datetime.now(UTC)
            m.completed_order_id = order.id
            notify_customer(
                session,
                customer_id=m.customer_id,
                title="Shopping mission completed",
                message=f"'{m.title}' is complete: order {order.order_number} has all of its items.",
                event_type="MISSION_COMPLETED",
            )
            done += 1
    return done
