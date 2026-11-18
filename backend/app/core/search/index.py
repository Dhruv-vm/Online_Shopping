from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.search.client import BaseSearchClient, OpenSearchError
from app.core.search.document import build_product_document

logger = logging.getLogger(__name__)

DEFAULT_INDEX_VERSION = "v1"
DEFAULT_INDEX_NAME = "basket_products_v1"
DEFAULT_SEARCH_ALIAS = "basket_products_search"
DEFAULT_WRITE_ALIAS = "basket_products_write"
PRODUCT_INDEX_MAPPINGS: dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1 if settings.is_production else 0,
        "analysis": {
            "analyzer": {
                "basket_text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "trim"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "product_id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "basket_text_analyzer",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "slug": {"type": "keyword"},
            "brand": {
                "type": "keyword",
                "fields": {
                    "text": {"type": "text", "analyzer": "basket_text_analyzer"}
                },
            },
            "description": {"type": "text", "analyzer": "basket_text_analyzer"},
            "category_id": {"type": "keyword"},
            "category_name": {
                "type": "keyword",
                "fields": {
                    "text": {"type": "text", "analyzer": "basket_text_analyzer"}
                },
            },
            "category_slug": {"type": "keyword"},
            "parent_category_name": {"type": "keyword"},
            "primary_image_url": {"type": "keyword", "index": False},
            "min_price_paise": {"type": "long"},
            "max_price_paise": {"type": "long"},
            "currency": {"type": "keyword"},
            "is_in_stock": {"type": "boolean"},
            "total_available_quantity": {"type": "integer"},
            "rating": {"type": "float"},
            "is_active": {"type": "boolean"},
            "variant_ids": {"type": "keyword"},
            "retailer_ids": {"type": "keyword"},
            "listing_ids": {"type": "keyword"},
            "searchable_text": {
                "type": "text",
                "analyzer": "basket_text_analyzer",
            },
            "aggregate_version": {"type": "long"},
            "indexed_at": {"type": "date"},
            "retailers": {
                "type": "nested",
                "properties": {
                    "retailer_id": {"type": "keyword"},
                    "retailer_name": {"type": "keyword"},
                    "listing_id": {"type": "keyword"},
                    "selling_price_paise": {"type": "long"},
                    "original_price_paise": {"type": "long"},
                    "is_in_stock": {"type": "boolean"},
                    "available_quantity": {"type": "integer"},
                },
            },
            "variants": {
                "type": "nested",
                "properties": {
                    "variant_id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "sku": {"type": "keyword"},
                    "is_in_stock": {"type": "boolean"},
                },
            },
            "attributes": {"type": "object", "dynamic": True},
        }
    },
}


def get_versioned_index_name(
    prefix: str | None = None, version: str = DEFAULT_INDEX_VERSION
) -> str:
    p = prefix or settings.OPENSEARCH_INDEX_PREFIX
    return f"{p}_products_{version}"


def get_search_alias_name(prefix: str | None = None) -> str:
    p = prefix or settings.OPENSEARCH_INDEX_PREFIX
    return f"{p}_products_search"


def get_write_alias_name(prefix: str | None = None) -> str:
    p = prefix or settings.OPENSEARCH_INDEX_PREFIX
    return f"{p}_products_write"


class IndexManager:
    """Manages blue/green index lifecycle, aliases, reindexing, and database reconciliation."""

    def __init__(self, client: BaseSearchClient, prefix: str | None = None) -> None:
        self.client = client
        self.prefix = prefix or settings.OPENSEARCH_INDEX_PREFIX
        self.search_alias = get_search_alias_name(self.prefix)
        self.write_alias = get_write_alias_name(self.prefix)

    async def ensure_index_and_aliases(
        self, version: str = DEFAULT_INDEX_VERSION
    ) -> str:
        """Create versioned index and wire up read/write aliases if they do not exist."""
        index_name = get_versioned_index_name(self.prefix, version)

        # 1. Create index if missing
        exists = await self.client.index_exists(index_name)
        if not exists:
            logger.info("Creating OpenSearch index '%s'...", index_name)
            await self.client.create_index(index_name, body=PRODUCT_INDEX_MAPPINGS)

        # 2. Wire aliases
        search_alias_data = await self.client.get_alias(self.search_alias)
        if not search_alias_data:
            logger.info(
                "Pointing search alias '%s' to '%s'", self.search_alias, index_name
            )
            await self.client.put_alias(index_name, self.search_alias)

        write_alias_data = await self.client.get_alias(self.write_alias)
        if not write_alias_data:
            logger.info(
                "Pointing write alias '%s' to '%s'", self.write_alias, index_name
            )
            await self.client.put_alias(index_name, self.write_alias)

        return index_name

    async def create_new_version_index(self, new_version: str) -> str:
        """Create a new versioned index for blue/green migration."""
        new_index = get_versioned_index_name(self.prefix, new_version)
        exists = await self.client.index_exists(new_index)
        if exists:
            raise OpenSearchError(
                f"Cannot create index '{new_index}': index already exists."
            )

        logger.info("Creating new blue/green index '%s'", new_index)
        await self.client.create_index(new_index, body=PRODUCT_INDEX_MAPPINGS)
        return new_index

    async def swap_aliases_to_new_version(
        self, new_version: str, old_version: str | None = None
    ) -> None:
        """Atomically point search and write aliases to the new versioned index."""
        new_index = get_versioned_index_name(self.prefix, new_version)
        if not await self.client.index_exists(new_index):
            raise OpenSearchError(
                f"Target index '{new_index}' does not exist for alias swap."
            )

        actions: list[dict[str, Any]] = []

        # Find currently aliased indices
        current_search_indices = list(
            (await self.client.get_alias(self.search_alias)).keys()
        )
        current_write_indices = list(
            (await self.client.get_alias(self.write_alias)).keys()
        )

        for idx in current_search_indices:
            actions.append({"remove": {"index": idx, "alias": self.search_alias}})
        for idx in current_write_indices:
            actions.append({"remove": {"index": idx, "alias": self.write_alias}})

        actions.append({"add": {"index": new_index, "alias": self.search_alias}})
        actions.append({"add": {"index": new_index, "alias": self.write_alias}})

        logger.info(
            "Executing atomic alias swap to '%s': %d removals, 2 additions",
            new_index,
            len(actions) - 2,
        )
        await self.client.update_aliases(actions)

    async def rollback_alias(self, rollback_version: str) -> None:
        """Rollback aliases to an earlier versioned index."""
        logger.warning(
            "Rolling back search and write aliases to version '%s'", rollback_version
        )
        await self.swap_aliases_to_new_version(rollback_version)

    async def reconcile_from_database(
        self, session: AsyncSession, *, target_alias_or_index: str | None = None
    ) -> int:
        """
        Reconcile derived search documents from PostgreSQL (authoritative source of truth).
        Scans all products with full variants, listings, inventory, and category relationships.
        Indexes documents using external_gte versioning to prevent overwriting newer real-time events.
        """
        from app.modules.catalogue.models import (
            Category,
            Product,
            ProductListing,
            ProductVariant,
        )

        target = target_alias_or_index or self.write_alias
        logger.info(
            "Starting SQL-backed search reconciliation into target '%s'...", target
        )

        stmt = (
            select(Product)
            .options(
                selectinload(Product.category).selectinload(Category.parent),
                selectinload(Product.images),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.inventory),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.retailer),
            )
            .order_by(Product.created_at)
        )

        result = await session.execute(stmt)
        products = result.scalars().all()

        count = 0
        for prod in products:
            # Deterministic projection
            doc = build_product_document(
                product=prod,
                variants=prod.variants,
                category=prod.category,
                aggregate_version=getattr(prod, "version", 1),
            )
            await self.client.index_document(
                index=target,
                doc_id=str(prod.id),
                document=doc,
                version=doc["aggregate_version"],
                version_type="external_gte",
            )
            count += 1

        logger.info(
            "Reconciliation complete: successfully indexed %d canonical product documents into '%s'",
            count,
            target,
        )
        return count
