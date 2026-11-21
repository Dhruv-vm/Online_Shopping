"""Outbox helper for Phase 3 marketplace lifecycle events.

Events are written to ``outbox_events`` in the caller's transaction and relayed
by the outbox publisher to the ``basket.events.marketplace`` topic. They are
published contracts for downstream consumers (notifications, analytics); the
platform itself keeps PostgreSQL as the source of truth.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

MARKETPLACE_EVENT_PREFIXES = (
    "demand.",
    "group_buy.",
    "exchange.",
    "negotiation.",
    "auction.",
    "sale_stream.",
    "price.",
    # Final cycle (live updates): retailer fulfilment steps and offer changes.
    # Kept off the order topic so the order projection's version sequence is
    # untouched.
    "fulfilment.",
    "offer.",
)


async def enqueue_marketplace_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    from app.modules.orders.models import OutboxEvent, OutboxStatus

    if not event_type.startswith(MARKETPLACE_EVENT_PREFIXES):
        raise ValueError(f"Not a marketplace event type: {event_type}")
    session.add(
        OutboxEvent(
            id=uuid.uuid4(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            schema_version=1,
            payload={
                k: (str(v) if isinstance(v, uuid.UUID) else v)
                for k, v in payload.items()
            },
            status=OutboxStatus.PENDING.value,
            retry_count=0,
            aggregate_version=int(time.time()),
        )
    )
