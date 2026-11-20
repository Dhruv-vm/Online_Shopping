"""Transactional outbox events for catalogue and inventory changes.

Every change that alters what a shopper sees in search (product data, listing
price or visibility, stock levels) must enqueue a ``product.updated`` /
``product.deleted`` event in the *same* database transaction as the change.
The outbox publisher relays it to Kafka (``basket.events.catalogue``) and the
OpenSearch consumer rebuilds the product document from PostgreSQL.

Before this module existed no catalogue or inventory events were produced at
all, so the OpenSearch consumer subscribed to topics nothing wrote to and the
search index drifted from the database after every sale.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PRODUCT_UPDATED = "product.updated"
PRODUCT_DELETED = "product.deleted"


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def enqueue_product_events(
    session: AsyncSession,
    product_ids: Iterable[Any],
    *,
    reason: str,
    event_type: str = PRODUCT_UPDATED,
) -> int:
    """Add outbox rows for the given products to the current transaction."""
    from app.modules.orders.models import OutboxEvent, OutboxStatus

    # De-duplicate against rows not yet flushed in this unit of work. Duplicates
    # that slip past this are harmless: the consumer rebuilds from PostgreSQL.
    pending: set[tuple[str, uuid.UUID]] = {
        (obj.event_type, obj.aggregate_id)
        for obj in session.new
        if isinstance(obj, OutboxEvent) and obj.aggregate_type == "product"
    }
    added = 0
    for raw in product_ids:
        pid = _as_uuid(raw)
        if pid is None or (event_type, pid) in pending:
            continue
        pending.add((event_type, pid))
        session.add(
            OutboxEvent(
                id=uuid.uuid4(),
                aggregate_type="product",
                aggregate_id=pid,
                event_type=event_type,
                schema_version=1,
                payload={"product_id": str(pid), "reason": reason[:64]},
                status=OutboxStatus.PENDING.value,
                retry_count=0,
                # Required by the publisher for non-order events. Epoch seconds
                # (fits the INTEGER column); consumers version documents by DB
                # snapshot time, so this is informational ordering only.
                aggregate_version=int(time.time()),
            )
        )
        added += 1
    return added


async def enqueue_product_events_for_listings(
    session: AsyncSession,
    listing_ids: Iterable[Any],
    *,
    reason: str,
) -> int:
    """Resolve listings to their products and enqueue ``product.updated``."""
    from app.modules.catalogue.models import ProductListing, ProductVariant

    ids = [lid for lid in (_as_uuid(x) for x in listing_ids) if lid is not None]
    if not ids:
        return 0
    stmt = (
        select(ProductVariant.product_id)
        .join(ProductListing, ProductListing.variant_id == ProductVariant.id)
        .where(ProductListing.id.in_(ids))
        .distinct()
    )
    product_ids = (await session.execute(stmt)).scalars().all()
    return await enqueue_product_events(session, product_ids, reason=reason)
