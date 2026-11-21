"""In-app customer notifications used by Phase 3 features."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


def notify_customer(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    title: str,
    message: str,
    event_type: str,
) -> None:
    from app.modules.orders.models import CustomerNotification

    session.add(
        CustomerNotification(
            id=uuid.uuid4(),
            customer_id=customer_id,
            title=title[:255],
            message=message,
            event_type=event_type[:64],
        )
    )


async def notify_retailer_users(
    session: AsyncSession,
    *,
    retailer_ids,
    title: str,
    message: str,
    event_type: str,
) -> int:
    """In-app notice to the owner account of each retailer (no customer data)."""
    from sqlalchemy import select

    from app.modules.catalogue.models import Retailer

    ids = {r for r in retailer_ids if r}
    if not ids:
        return 0
    users = (
        await session.execute(
            select(Retailer.user_id).where(
                Retailer.id.in_(ids), Retailer.user_id.is_not(None)
            )
        )
    ).scalars()
    n = 0
    for uid in set(users):
        notify_customer(
            session,
            customer_id=uid,
            title=title,
            message=message,
            event_type=event_type,
        )
        n += 1
    return n


async def notify_retailers_serving(
    session: AsyncSession,
    *,
    pincode: str | None,
    title: str,
    message: str,
    event_type: str,
) -> int:
    """Notify every active, verified retailer whose service area covers `pincode`."""
    from sqlalchemy import select

    from app.core.pincode import retailer_serves
    from app.modules.catalogue.models import Retailer

    rows = (
        await session.execute(
            select(Retailer.id, Retailer.service_pincodes).where(
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
                Retailer.user_id.is_not(None),
            )
        )
    ).all()
    ids = [rid for rid, pins in rows if retailer_serves(pins, pincode)]
    return await notify_retailer_users(
        session, retailer_ids=ids, title=title, message=message, event_type=event_type
    )
