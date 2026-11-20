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
