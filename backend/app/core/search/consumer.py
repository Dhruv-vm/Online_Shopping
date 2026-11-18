from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import Settings, settings
from app.core.events.consumer import BaseKafkaConsumer
from app.core.events.envelope import EventEnvelope
from app.core.events.kafka import EventProducer
from app.core.search.client import (
    BaseSearchClient,
    OpenSearchConflictError,
    get_opensearch_client,
)
from app.core.search.document import build_product_document
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    StoreInventory,
)

logger = logging.getLogger(__name__)

DEFAULT_OPENSEARCH_CONSUMER_GROUP = "basket-opensearch-sync"
DEFAULT_OPENSEARCH_WRITE_ALIAS = "basket_products_write"
DEFAULT_OPENSEARCH_TOPICS = [
    "basket.events.catalogue",
    "basket.events.inventory",
]


class OpenSearchConsumer(BaseKafkaConsumer):
    """
    Kafka consumer implementing Strategy B (OpenSearch Derived Read-Model Consumer):
    1. Listens to catalogue and inventory Kafka topics.
    2. Queries authoritative PostgreSQL state.
    3. Builds canonical, deterministic product projection document.
    4. Indexes into OpenSearch with external_gte aggregate_version.
    5. Discards HTTP 409 version conflicts safely (stale events).
    6. Commits consumer_inbox status and Kafka offset only after successful OpenSearch ACK.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        search_client: BaseSearchClient | None = None,
        producer: EventProducer | None = None,
        config_settings: Settings | None = None,
        consumer_group: str = DEFAULT_OPENSEARCH_CONSUMER_GROUP,
        topics: list[str] | None = None,
        index_alias: str = DEFAULT_OPENSEARCH_WRITE_ALIAS,
        consumer_impl: Any | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = config_settings or settings
        sub_topics = topics or DEFAULT_OPENSEARCH_TOPICS

        super().__init__(
            consumer_group=consumer_group,
            topics=sub_topics,
            session_factory=session_factory,
            producer=producer,
            config_settings=cfg,
            consumer_impl=consumer_impl,
            **kwargs,
        )

        self._search_client = search_client or get_opensearch_client(cfg)
        self._index_alias = index_alias

    async def handle_event(
        self, envelope: EventEnvelope, session: AsyncSession
    ) -> None:
        """
        Execute Strategy B event processing:
        - Resolve product entity ID
        - If deleted: issue OpenSearch DELETE
        - If updated/created: construct canonical doc and issue OpenSearch PUT
        """
        product_id = await self._resolve_product_id(envelope, session)
        if product_id is None:
            logger.debug(
                "Could not resolve product_id for event %s (type=%s, aggregate=%s:%s)",
                envelope.event_id,
                envelope.event_type,
                envelope.aggregate_type,
                envelope.aggregate_id,
            )
            return

        # Check for deletion event
        if envelope.event_type in ("product.deleted", "product.deactivated"):
            await self._delete_from_index(product_id, envelope.aggregate_version)
            return

        # Query authoritative PostgreSQL state with all child associations
        stmt = (
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.retailer),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.inventory),
            )
            .where(Product.id == product_id)
        )
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()

        if product is None or not product.is_active:
            # Entity deactivated or missing from DB -> remove from search index
            await self._delete_from_index(product_id, envelope.aggregate_version)
            return

        doc = build_product_document(
            product, aggregate_version=envelope.aggregate_version
        )

        try:
            await self._search_client.index_document(
                index=self._index_alias,
                doc_id=str(product_id),
                document=doc,
                version=envelope.aggregate_version,
                version_type="external_gte",
            )
            logger.info(
                "OpenSearch synced product %s v%d for event %s",
                product_id,
                envelope.aggregate_version,
                envelope.event_id,
            )
        except OpenSearchConflictError as exc:
            # 409 Conflict: OpenSearch already has this or newer aggregate_version.
            # Stale event discarded cleanly without error.
            logger.info(
                "OpenSearch version conflict for product %s v%d (stale event discarded): %s",
                product_id,
                envelope.aggregate_version,
                exc,
            )

    async def _resolve_product_id(
        self,
        envelope: EventEnvelope,
        session: AsyncSession,
    ) -> uuid.UUID | None:
        """Resolve the target Product UUID across all supported aggregate events."""
        # 1. Direct product aggregate
        if envelope.aggregate_type.lower() == "product":
            try:
                if isinstance(envelope.aggregate_id, uuid.UUID):
                    return envelope.aggregate_id
                return uuid.UUID(str(envelope.aggregate_id))
            except ValueError:
                return None

        # 2. Check payload for product_id
        if "product_id" in envelope.payload and envelope.payload["product_id"]:
            try:
                raw_pid = envelope.payload["product_id"]
                if isinstance(raw_pid, uuid.UUID):
                    return raw_pid
                return uuid.UUID(str(raw_pid))
            except ValueError:
                pass

        # 3. ProductListing aggregate
        if envelope.aggregate_type.lower() == "productlisting":
            try:
                raw_lid = envelope.aggregate_id
                listing_uuid = (
                    raw_lid
                    if isinstance(raw_lid, uuid.UUID)
                    else uuid.UUID(str(raw_lid))
                )
                listing = await session.get(ProductListing, listing_uuid)
                if listing:
                    variant = await session.get(ProductVariant, listing.variant_id)
                    if variant:
                        return variant.product_id
            except (ValueError, Exception):
                return None

        # 4. ProductVariant aggregate
        if envelope.aggregate_type.lower() == "productvariant":
            try:
                raw_vid = envelope.aggregate_id
                variant_uuid = (
                    raw_vid
                    if isinstance(raw_vid, uuid.UUID)
                    else uuid.UUID(str(raw_vid))
                )
                variant = await session.get(ProductVariant, variant_uuid)
                if variant:
                    return variant.product_id
            except (ValueError, Exception):
                return None

        # 5. StoreInventory aggregate
        if envelope.aggregate_type.lower() == "storeinventory":
            try:
                raw_iid = envelope.aggregate_id
                inv_uuid = (
                    raw_iid
                    if isinstance(raw_iid, uuid.UUID)
                    else uuid.UUID(str(raw_iid))
                )
                inv = await session.get(StoreInventory, inv_uuid)
                if inv:
                    listing = await session.get(ProductListing, inv.listing_id)
                    if listing:
                        variant = await session.get(ProductVariant, listing.variant_id)
                        if variant:
                            return variant.product_id
            except (ValueError, Exception):
                return None

        return None

    async def _delete_from_index(self, product_id: uuid.UUID, version: int) -> None:
        """Issue external_gte versioned deletion to OpenSearch."""
        try:
            await self._search_client.delete_document(
                index=self._index_alias,
                doc_id=str(product_id),
                version=version,
                version_type="external_gte",
            )
            logger.info(
                "OpenSearch deleted document %s v%d",
                product_id,
                version,
            )
        except OpenSearchConflictError as exc:
            logger.info(
                "OpenSearch delete conflict for product %s v%d (ignored): %s",
                product_id,
                version,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "OpenSearch delete failed for product %s v%d: %s",
                product_id,
                version,
                exc,
            )
