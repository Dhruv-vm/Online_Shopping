from __future__ import annotations

from app.core.search.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitState,
    SearchCircuitBreaker,
)
from app.core.search.client import (
    BaseSearchClient,
    MockOpenSearchClient,
    OpenSearchClient,
    OpenSearchConflictError,
    OpenSearchConnectionError,
    OpenSearchError,
    OpenSearchResponseError,
    get_opensearch_client,
)
from app.core.search.consumer import (
    DEFAULT_OPENSEARCH_CONSUMER_GROUP,
    DEFAULT_OPENSEARCH_WRITE_ALIAS,
    OpenSearchConsumer,
)
from app.core.search.document import build_product_document
from app.core.search.index import (
    DEFAULT_INDEX_NAME,
    DEFAULT_SEARCH_ALIAS,
    DEFAULT_WRITE_ALIAS,
    PRODUCT_INDEX_MAPPINGS,
    IndexManager,
)

__all__ = [
    "BaseSearchClient",
    "CircuitBreakerOpenError",
    "CircuitState",
    "DEFAULT_INDEX_NAME",
    "DEFAULT_OPENSEARCH_CONSUMER_GROUP",
    "DEFAULT_OPENSEARCH_WRITE_ALIAS",
    "DEFAULT_SEARCH_ALIAS",
    "DEFAULT_WRITE_ALIAS",
    "IndexManager",
    "MockOpenSearchClient",
    "OpenSearchClient",
    "OpenSearchConflictError",
    "OpenSearchConnectionError",
    "OpenSearchConsumer",
    "OpenSearchError",
    "OpenSearchResponseError",
    "PRODUCT_INDEX_MAPPINGS",
    "SearchCircuitBreaker",
    "build_product_document",
    "get_opensearch_client",
]
