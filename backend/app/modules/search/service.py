from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, settings
from app.core.search.circuit_breaker import (
    CircuitBreakerOpenError,
    SearchCircuitBreaker,
)
from app.core.search.client import (
    BaseSearchClient,
    OpenSearchError,
    get_opensearch_client,
)
from app.core.search.document import build_product_document
from app.core.search.index import DEFAULT_SEARCH_ALIAS
from app.core.search.index_health import SearchEngineStatus, current_search_engine
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.search.schemas import (
    ProductSearchItem,
    SearchFacetBucket,
    SearchFacets,
    SearchResponseSchema,
    SuggestionItem,
    SuggestionsResponse,
)

logger = logging.getLogger(__name__)


def escape_like(term: str) -> str:
    """Escape LIKE/ILIKE wildcards so user input is matched literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SearchService:
    """
    Universal Multi-Category, Multi-Retailer Search Service with Circuit Breaker
    and resilient PostgreSQL SQL fallback.
    """

    def __init__(
        self,
        search_client: BaseSearchClient | None = None,
        circuit_breaker: SearchCircuitBreaker | None = None,
        config_settings: Settings | None = None,
        search_alias: str = DEFAULT_SEARCH_ALIAS,
        index_health: Callable[[AsyncSession], Awaitable[SearchEngineStatus]]
        | None = None,
    ) -> None:
        self.settings = config_settings or settings
        # The configured cluster is trusted only while its index is kept in sync
        # (Version 2.0 A3). An explicitly injected client (tests) is not gated
        # unless a health check is injected too.
        if index_health is None and search_client is None:
            # Cached check against the global settings; uncached for a custom config.
            health_cfg = None if self.settings is settings else self.settings

            async def index_health(session: AsyncSession) -> SearchEngineStatus:
                return await current_search_engine(session, health_cfg)

        self._index_health = index_health
        # Only talk to a real cluster when one is configured. Previously an empty
        # in-memory mock index was used whenever OPENSEARCH_URL was unset, so every
        # search in development/sandbox returned 0 results instead of falling back
        # to PostgreSQL. Tests may still inject a mock client explicitly.
        self.client = search_client or (
            get_opensearch_client(self.settings)
            if self.settings.has_opensearch
            else None
        )
        self.circuit_breaker = circuit_breaker or SearchCircuitBreaker(
            failure_threshold=self.settings.OPENSEARCH_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_seconds=self.settings.OPENSEARCH_CIRCUIT_BREAKER_RECOVERY_SECONDS,
        )
        self.search_alias = search_alias

    async def search(
        self,
        db_session: AsyncSession,
        *,
        q: str | None = None,
        category_slug: str | None = None,
        brand: str | None = None,
        retailer_id: uuid.UUID | str | None = None,
        min_price_paise: int | None = None,
        max_price_paise: int | None = None,
        in_stock_only: bool = False,
        sort: Literal[
            "relevance", "price_asc", "price_desc", "rating_desc", "newest"
        ] = "relevance",
        page: int = 1,
        page_size: int = 20,
        force_fallback: bool = False,
    ) -> SearchResponseSchema:
        """
        Execute product search. Tries OpenSearch first; on circuit trip or engine failure,
        transparently falls back to PostgreSQL SQL query without failing the request.
        """
        from app.modules.i18n.service import normalize_query

        original_query = (q or "").strip()
        query_str, detected_lang, translated = normalize_query(original_query)
        result = await self._search_dispatch(
            db_session=db_session,
            query_str=query_str,
            original_query=original_query,
            category_slug=category_slug,
            brand=brand,
            retailer_id=retailer_id,
            min_price_paise=min_price_paise,
            max_price_paise=max_price_paise,
            in_stock_only=in_stock_only,
            sort=sort,
            page=page,
            page_size=page_size,
            force_fallback=force_fallback,
        )
        result.original_query = original_query or None
        result.interpreted_query = query_str or None
        result.detected_language = detected_lang
        result.query_translated = translated
        return result

    async def _search_dispatch(
        self,
        *,
        db_session: AsyncSession,
        query_str: str,
        original_query: str,
        category_slug,
        brand,
        retailer_id,
        min_price_paise,
        max_price_paise,
        in_stock_only,
        sort,
        page,
        page_size,
        force_fallback,
    ) -> SearchResponseSchema:
        start_time = time.monotonic()

        fallback_reason: str | None = None
        if not force_fallback and self.client is not None:
            fallback_reason = await self._untrusted_index_reason(db_session)

        # Circuit breaker / force fallback check
        if not force_fallback and self.client is not None and fallback_reason is None:
            try:
                return await self.circuit_breaker.call(
                    self._search_opensearch,
                    query_str=query_str,
                    category_slug=category_slug,
                    brand=brand,
                    retailer_id=str(retailer_id) if retailer_id else None,
                    min_price_paise=min_price_paise,
                    max_price_paise=max_price_paise,
                    in_stock_only=in_stock_only,
                    sort=sort,
                    page=page,
                    page_size=page_size,
                    start_time=start_time,
                )
            except (CircuitBreakerOpenError, OpenSearchError, Exception) as exc:
                logger.warning(
                    "OpenSearch query failed or circuit OPEN (%s: %s). Routing to PostgreSQL fallback.",
                    type(exc).__name__,
                    exc,
                )
                fallback_reason = "OPENSEARCH_UNAVAILABLE"

        # Fallback to PostgreSQL
        result = await self._search_postgres_fallback(
            session=db_session,
            query_str=query_str,
            category_slug=category_slug,
            brand=brand,
            retailer_id=str(retailer_id) if retailer_id else None,
            min_price_paise=min_price_paise,
            max_price_paise=max_price_paise,
            in_stock_only=in_stock_only,
            sort=sort,
            page=page,
            page_size=min(page_size, 20),  # Protect DB CPU by capping page size at 20
            start_time=start_time,
            original_query=original_query,
        )
        result.engine_reason = fallback_reason
        return result

    async def _untrusted_index_reason(self, db_session: AsyncSession) -> str | None:
        """Why the OpenSearch index must not be used now (None = it can be)."""
        if self._index_health is None:
            return None
        try:
            status = await self._index_health(db_session)
        except Exception as exc:  # the check must never break search
            logger.warning("Search index health check failed: %s", exc)
            return "INDEX_HEALTH_CHECK_FAILED"
        return None if status.use_opensearch else status.reason

    async def get_suggestions(
        self,
        db_session: AsyncSession,
        query: str,
        limit: int = 5,
    ) -> SuggestionsResponse:
        """Provide auto-completion suggestions for type-ahead UI."""
        clean_q = query.strip()
        if not clean_q:
            return SuggestionsResponse(query="", suggestions=[])

        # Try OpenSearch prefix / match query if circuit allows and the index is
        # trusted (a stale index would suggest products that no longer exist).
        try:
            if (
                self.client is not None
                and await self._untrusted_index_reason(db_session) is None
                and await self.circuit_breaker.allow_request()
            ):
                dsl = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": clean_q,
                                        "fields": ["name^3.0", "brand^2.0"],
                                        "type": "phrase_prefix",
                                    }
                                }
                            ],
                            "filter": [{"term": {"is_active": True}}],
                        }
                    },
                    "size": limit,
                    "_source": ["name", "brand", "slug", "category_name"],
                }
                res = await self.client.search(self.search_alias, dsl)
                hits = res.get("hits", {}).get("hits", [])
                suggestions: list[SuggestionItem] = []
                for h in hits:
                    src = h.get("_source", {})
                    suggestions.append(
                        SuggestionItem(
                            text=src.get("name", ""),
                            type="product",
                            slug=src.get("slug"),
                        )
                    )
                if suggestions:
                    return SuggestionsResponse(query=clean_q, suggestions=suggestions)
        except Exception:
            pass

        # Fallback: simple SQL query
        stmt = (
            select(Product.name, Product.slug, Product.brand)
            .where(
                and_(
                    Product.is_active == True,  # noqa: E712
                    or_(
                        Product.name.ilike(f"{escape_like(clean_q)}%", escape="\\"),
                        Product.brand.ilike(f"{escape_like(clean_q)}%", escape="\\"),
                    ),
                )
            )
            .limit(limit)
        )
        result = await db_session.execute(stmt)
        rows = result.all()
        suggestions = [
            SuggestionItem(text=row.name, type="product", slug=row.slug) for row in rows
        ]
        return SuggestionsResponse(query=clean_q, suggestions=suggestions)

    async def _search_opensearch(
        self,
        query_str: str,
        category_slug: str | None,
        brand: str | None,
        retailer_id: str | None,
        min_price_paise: int | None,
        max_price_paise: int | None,
        in_stock_only: bool,
        sort: str,
        page: int,
        page_size: int,
        start_time: float,
    ) -> SearchResponseSchema:
        """Construct DSL and execute search against OpenSearch."""
        must_clauses: list[dict[str, Any]] = []
        filter_clauses: list[dict[str, Any]] = [
            {"term": {"is_active": True}},
        ]

        if query_str:
            tokens = [t.strip() for t in query_str.split() if t.strip()]
            num_tokens = len(tokens)

            should_clauses: list[dict[str, Any]] = [
                {
                    "multi_match": {
                        "query": query_str,
                        "fields": [
                            "name^10.0",
                            "brand.text^6.0",
                            "searchable_text^3.0",
                        ],
                        "type": "phrase",
                        "boost": 10.0,
                    }
                },
                {
                    "multi_match": {
                        "query": query_str,
                        "fields": [
                            "name^6.0",
                            "brand.text^4.0",
                            "category_name.text^2.0",
                            "searchable_text^1.0",
                        ],
                        "type": "cross_fields",
                        "operator": "and",
                        "boost": 5.0,
                    }
                },
            ]

            if num_tokens <= 2:
                should_clauses.append(
                    {
                        "multi_match": {
                            "query": query_str,
                            "fields": [
                                "name^4.0",
                                "brand.text^3.0",
                                "category_name.text^2.0",
                                "description^1.0",
                                "searchable_text^1.0",
                            ],
                            "type": "best_fields",
                            "operator": "and",
                            "boost": 2.0,
                        }
                    }
                )
            else:
                should_clauses.append(
                    {
                        "multi_match": {
                            "query": query_str,
                            "fields": [
                                "name^4.0",
                                "brand.text^3.0",
                                "category_name.text^2.0",
                                "description^1.0",
                                "searchable_text^1.0",
                            ],
                            "type": "best_fields",
                            "operator": "or",
                            "minimum_should_match": "75%",
                            "boost": 1.0,
                        }
                    }
                )

            must_clauses.append(
                {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,
                    }
                }
            )
        else:
            must_clauses.append({"match_all": {}})

        if category_slug:
            filter_clauses.append({"term": {"category_slug": category_slug}})
        if brand:
            filter_clauses.append({"term": {"brand.raw": brand}})
        if retailer_id:
            filter_clauses.append({"term": {"retailers.retailer_id": retailer_id}})
        if in_stock_only:
            filter_clauses.append({"term": {"is_in_stock": True}})

        price_range: dict[str, Any] = {}
        if min_price_paise is not None:
            price_range["gte"] = min_price_paise
        if max_price_paise is not None:
            price_range["lte"] = max_price_paise
        if price_range:
            filter_clauses.append({"range": {"min_price_paise": price_range}})

        # Sorting
        sort_clauses: list[Any] = []
        if sort == "price_asc":
            sort_clauses.append({"min_price_paise": {"order": "asc"}})
        elif sort == "price_desc":
            sort_clauses.append({"min_price_paise": {"order": "desc"}})
        elif sort == "rating_desc":
            sort_clauses.append({"rating": {"order": "desc"}})
        elif sort == "newest":
            sort_clauses.append({"indexed_at": {"order": "desc"}})
        else:
            # relevance
            if query_str:
                sort_clauses.append("_score")
            sort_clauses.append({"rating": {"order": "desc"}})

        # Faceted aggregations
        aggregations: dict[str, Any] = {
            "categories": {"terms": {"field": "category_name.raw", "size": 20}},
            "brands": {"terms": {"field": "brand.raw", "size": 20}},
            "retailers": {
                "terms": {"field": "retailers.retailer_name.raw", "size": 20}
            },
            "price_stats": {"stats": {"field": "min_price_paise"}},
        }

        dsl: dict[str, Any] = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "sort": sort_clauses,
            "from": (page - 1) * page_size,
            "size": page_size,
            "aggs": aggregations,
        }

        raw_resp = await self.client.search(self.search_alias, dsl)
        took_ms = round((time.monotonic() - start_time) * 1000, 2)

        hits_data = raw_resp.get("hits", {})
        total_hits = (
            hits_data.get("total", {}).get("value", 0)
            if isinstance(hits_data.get("total"), dict)
            else hits_data.get("total", 0)
        )

        items: list[ProductSearchItem] = []
        for hit in hits_data.get("hits", []):
            src = hit.get("_source", {})
            items.append(
                ProductSearchItem(
                    product_id=src.get("product_id"),
                    name=src.get("name", ""),
                    slug=src.get("slug", ""),
                    brand=src.get("brand", ""),
                    description=src.get("description", ""),
                    category_id=src.get("category_id", ""),
                    category_name=src.get("category_name", ""),
                    category_slug=src.get("category_slug", ""),
                    primary_image_url=src.get("primary_image_url"),
                    min_price_paise=src.get("min_price_paise", 0),
                    max_price_paise=src.get("max_price_paise", 0),
                    currency=src.get("currency", "INR"),
                    is_in_stock=src.get("is_in_stock", True),
                    total_available_quantity=src.get("total_available_quantity", 0),
                    rating=src.get("rating", 5.0),
                    retailers=src.get("retailers", []),
                    variants=src.get("variants", []),
                    attributes=src.get("attributes", {}),
                )
            )

        # Parse facets
        aggs = raw_resp.get("aggregations", {})
        cat_buckets = [
            SearchFacetBucket(key=b["key"], doc_count=b["doc_count"])
            for b in aggs.get("categories", {}).get("buckets", [])
        ]
        brand_buckets = [
            SearchFacetBucket(key=b["key"], doc_count=b["doc_count"])
            for b in aggs.get("brands", {}).get("buckets", [])
        ]
        retailer_buckets = [
            SearchFacetBucket(key=b["key"], doc_count=b["doc_count"])
            for b in aggs.get("retailers", {}).get("buckets", [])
        ]
        price_stats = aggs.get("price_stats", {})

        facets = SearchFacets(
            categories=cat_buckets,
            brands=brand_buckets,
            retailers=retailer_buckets,
            price_stats=price_stats,
        )

        total_pages = max(1, (total_hits + page_size - 1) // page_size)

        return SearchResponseSchema(
            items=items,
            total=total_hits,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            engine="opensearch",
            facets=facets,
            took_ms=took_ms,
        )

    async def _search_postgres_fallback(
        self,
        session: AsyncSession,
        query_str: str,
        category_slug: str | None,
        brand: str | None,
        retailer_id: str | None,
        min_price_paise: int | None,
        max_price_paise: int | None,
        in_stock_only: bool,
        sort: str,
        page: int,
        page_size: int,
        start_time: float,
        original_query: str = "",
    ) -> SearchResponseSchema:
        """
        Resilient PostgreSQL fallback when OpenSearch is unavailable.
        Omits complex facet calculations to preserve DB CPU during degraded operation.
        """
        # Per-product aggregates over *publicly visible* listings (active listing,
        # active and verified retailer), mirroring build_product_document(). All
        # filtering, counting, sorting and pagination happen in SQL so that
        # `total` and page sizes are consistent with the filters applied.
        available_expr = func.greatest(
            func.coalesce(StoreInventory.on_hand_quantity, 0)
            - func.coalesce(StoreInventory.reserved_quantity, 0),
            0,
        )
        agg = (
            select(
                ProductVariant.product_id.label("product_id"),
                func.min(ProductListing.selling_price_paise).label("min_price"),
                func.coalesce(func.sum(available_expr), 0).label("available"),
            )
            .join(ProductListing, ProductListing.variant_id == ProductVariant.id)
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .outerjoin(StoreInventory, StoreInventory.listing_id == ProductListing.id)
            .where(
                ProductListing.is_active == True,  # noqa: E712
                Retailer.is_active == True,  # noqa: E712
                Retailer.verification_status == "VERIFIED",
            )
            .group_by(ProductVariant.product_id)
            .subquery()
        )
        available_col = func.coalesce(agg.c.available, 0)

        conditions = [Product.is_active == True]  # noqa: E712

        if query_str:
            tokens = [t.strip() for t in query_str.split() if t.strip()]
            if tokens:
                phrase_term = f"%{escape_like(query_str.strip())}%"
                token_conditions = []
                for t in tokens:
                    term = f"%{escape_like(t)}%"
                    token_conditions.append(
                        or_(
                            Product.name.ilike(term, escape="\\"),
                            Product.brand.ilike(term, escape="\\"),
                            Product.description.ilike(term, escape="\\"),
                        )
                    )
                from app.modules.i18n.models import ContentTranslation

                original = (original_query or "").strip()
                translated_match = Product.id.in_(
                    select(ContentTranslation.entity_id).where(
                        ContentTranslation.entity_type == "product",
                        ContentTranslation.field == "name",
                        ContentTranslation.value.ilike(
                            f"%{escape_like(original or query_str.strip())}%",
                            escape="\\",
                        ),
                    )
                )
                conditions.append(
                    or_(
                        Product.name.ilike(phrase_term, escape="\\"),
                        and_(*token_conditions),
                        translated_match,
                    )
                )

        if category_slug:
            conditions.append(
                Product.id.in_(
                    select(Product.id)
                    .join(Category, Product.category_id == Category.id)
                    .where(Category.slug == category_slug)
                )
            )

        if brand:
            conditions.append(Product.brand == brand)

        if retailer_id:
            try:
                ret_uuid = uuid.UUID(retailer_id)
            except ValueError:
                # Invalid retailer filter must yield no results, not all results.
                conditions.append(false())
            else:
                conditions.append(
                    Product.id.in_(
                        select(ProductVariant.product_id)
                        .join(
                            ProductListing,
                            ProductListing.variant_id == ProductVariant.id,
                        )
                        .where(
                            ProductListing.retailer_id == ret_uuid,
                            ProductListing.is_active == True,  # noqa: E712
                        )
                    )
                )

        # Same semantics as the OpenSearch query: range filter on min price.
        # Products without any purchasable listing have no price and never match
        # a price filter (NULL comparisons are false).
        if min_price_paise is not None:
            conditions.append(agg.c.min_price >= min_price_paise)
        if max_price_paise is not None:
            conditions.append(agg.c.min_price <= max_price_paise)
        if in_stock_only:
            conditions.append(available_col > 0)

        base_from = select(Product.id).outerjoin(agg, agg.c.product_id == Product.id)

        # Total count (with every filter applied)
        count_stmt = select(func.count()).select_from(
            base_from.where(and_(*conditions)).subquery()
        )
        total = (await session.execute(count_stmt)).scalar() or 0

        order_by: list[Any]
        if sort == "price_asc":
            order_by = [
                agg.c.min_price.asc().nulls_last(),
                Product.name.asc(),
                Product.id.asc(),
            ]
        elif sort == "price_desc":
            order_by = [
                agg.c.min_price.desc().nulls_last(),
                Product.name.asc(),
                Product.id.asc(),
            ]
        elif sort == "newest":
            order_by = [Product.created_at.desc(), Product.id.asc()]
        else:  # relevance / rating fallback: deterministic name order
            order_by = [Product.name.asc(), Product.id.asc()]

        page_ids_stmt = (
            base_from.where(and_(*conditions))
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        page_ids = list((await session.execute(page_ids_stmt)).scalars().all())

        products: list[Product] = []
        if page_ids:
            items_stmt = (
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
                .where(Product.id.in_(page_ids))
            )
            by_id = {
                p.id: p for p in (await session.execute(items_stmt)).scalars().all()
            }
            products = [by_id[pid] for pid in page_ids if pid in by_id]

        items: list[ProductSearchItem] = []
        for prod in products:
            doc = build_product_document(prod)

            items.append(
                ProductSearchItem(
                    product_id=doc["product_id"],
                    name=doc["name"],
                    slug=doc["slug"],
                    brand=doc["brand"],
                    description=doc["description"],
                    category_id=doc["category_id"],
                    category_name=doc["category_name"],
                    category_slug=doc["category_slug"],
                    primary_image_url=doc["primary_image_url"],
                    min_price_paise=doc["min_price_paise"],
                    max_price_paise=doc["max_price_paise"],
                    currency=doc["currency"],
                    is_in_stock=doc["is_in_stock"],
                    total_available_quantity=doc["total_available_quantity"],
                    rating=doc["rating"],
                    retailers=doc["retailers"],
                    variants=doc["variants"],
                    attributes=doc["attributes"],
                )
            )

        took_ms = round((time.monotonic() - start_time) * 1000, 2)
        total_pages = max(1, (total + page_size - 1) // page_size)

        return SearchResponseSchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            engine="postgres_fallback",
            facets=None,  # Omit facets to protect DB
            took_ms=took_ms,
        )
