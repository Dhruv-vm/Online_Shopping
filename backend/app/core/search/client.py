from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


class OpenSearchError(Exception):
    """Base exception for OpenSearch operations."""

    pass


class OpenSearchConnectionError(OpenSearchError):
    """Raised when connection to OpenSearch cluster fails or times out."""

    pass


class OpenSearchConflictError(OpenSearchError):
    """Raised on version conflict (HTTP 409)."""

    def __init__(
        self, message: str = "Version conflict", current_version: int | None = None
    ) -> None:
        super().__init__(message)
        self.current_version = current_version
        self.status_code = 409


class OpenSearchResponseError(OpenSearchError):
    """Raised when OpenSearch returns an unhandled HTTP error status."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"OpenSearch HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class BaseSearchClient(ABC):
    """Abstract interface for OpenSearch asynchronous clients."""

    @abstractmethod
    async def ping(self) -> bool:
        """Check cluster liveness."""
        pass

    @abstractmethod
    async def cluster_health(self) -> dict[str, Any]:
        """Check cluster health status."""
        pass

    @abstractmethod
    async def create_index(
        self, index: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create an index with optional mappings and settings."""
        pass

    @abstractmethod
    async def index_exists(self, index: str) -> bool:
        """Check if an index exists."""
        pass

    @abstractmethod
    async def delete_index(self, index: str) -> dict[str, Any]:
        """Delete an index."""
        pass

    @abstractmethod
    async def put_alias(self, index: str, alias: str) -> dict[str, Any]:
        """Add an alias to an index."""
        pass

    @abstractmethod
    async def update_aliases(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """Atomically perform alias actions."""
        pass

    @abstractmethod
    async def get_alias(self, alias: str) -> dict[str, Any]:
        """Get indices associated with an alias."""
        pass

    @abstractmethod
    async def index_document(
        self,
        index: str,
        doc_id: str,
        document: dict[str, Any],
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        """Index or update a document with optimistic concurrency control."""
        pass

    @abstractmethod
    async def get_document(self, index: str, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by ID."""
        pass

    @abstractmethod
    async def delete_document(
        self,
        index: str,
        doc_id: str,
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        """Delete a document by ID with version check."""
        pass

    @abstractmethod
    async def search(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        """Execute a search query against an index or alias."""
        pass

    @abstractmethod
    async def reindex(
        self, source_index: str, dest_index: str, wait_for_completion: bool = True
    ) -> dict[str, Any]:
        """Reindex documents from source index to destination index."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection pool and release resources."""
        pass


class OpenSearchClient(BaseSearchClient):
    """
    Production-grade asynchronous OpenSearch client using httpx.AsyncClient.
    Features:
    - Connection pooling & keepalive.
    - Strict TLS validation in production.
    - Zero credentials in logs.
    - Exponential backoff retries on network errors.
    """

    def __init__(self, config_settings: Settings | None = None) -> None:
        self._settings = config_settings or settings
        self._url = (self._settings.OPENSEARCH_URL or "").rstrip("/")
        if not self._url:
            raise ValueError("OPENSEARCH_URL is not configured.")

        # TLS verification
        verify_certs = self._settings.OPENSEARCH_VERIFY_CERTS
        if self._settings.is_production and not verify_certs:
            raise RuntimeError(
                "Insecure TLS (OPENSEARCH_VERIFY_CERTS=False) is forbidden in production."
            )

        # Auth setup (Zero-credential logging guaranteed)
        auth = None
        if self._settings.OPENSEARCH_USERNAME and self._settings.OPENSEARCH_PASSWORD:
            auth = (
                self._settings.OPENSEARCH_USERNAME,
                self._settings.OPENSEARCH_PASSWORD.get_secret_value(),
            )

        timeout = httpx.Timeout(
            timeout=self._settings.OPENSEARCH_TIMEOUT_SECONDS,
            connect=min(5.0, self._settings.OPENSEARCH_TIMEOUT_SECONDS),
        )
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)

        self._client = httpx.AsyncClient(
            base_url=self._url,
            auth=auth,
            verify=verify_certs,
            timeout=timeout,
            limits=limits,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._closed = False
        logger.info(
            "OpenSearchClient initialized for host %s (verify_certs=%s)",
            self._safe_host_preview(),
            verify_certs,
        )

    def _safe_host_preview(self) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self._url)
            return f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}"
        except Exception:
            return "<configured-opensearch-endpoint>"

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> httpx.Response:
        retries = (
            max_retries
            if max_retries is not None
            else self._settings.OPENSEARCH_MAX_RETRIES
        )
        last_exc: Exception | None = None

        for attempt in range(retries + 1):
            try:
                resp = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_data,
                )
                if resp.status_code == 409:
                    raise OpenSearchConflictError(
                        f"Document version conflict on {path}",
                    )
                if resp.status_code >= 500:
                    resp.raise_for_status()
                return resp
            except OpenSearchConflictError:
                raise
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as exc:
                last_exc = exc
                if attempt < retries:
                    backoff = 0.1 * (2**attempt)
                    logger.warning(
                        "OpenSearch %s %s transient error (%s). Retrying in %.2fs (attempt %d/%d)...",
                        method,
                        path,
                        type(exc).__name__,
                        backoff,
                        attempt + 1,
                        retries,
                    )
                    await asyncio.sleep(backoff)
                else:
                    break

        sanitized_exc_name = type(last_exc).__name__ if last_exc else "UnknownError"
        raise OpenSearchConnectionError(
            f"Failed to execute OpenSearch request {method} {path} after {retries + 1} attempts: {sanitized_exc_name}"
        ) from last_exc

    async def ping(self) -> bool:
        try:
            resp = await self._request_with_retry("GET", "/")
            return resp.status_code == 200
        except Exception:
            return False

    async def cluster_health(self) -> dict[str, Any]:
        resp = await self._request_with_retry("GET", "/_cluster/health", max_retries=1)
        if resp.status_code >= 400:
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def create_index(
        self, index: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = await self._request_with_retry("PUT", f"/{index}", json_data=body or {})
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def index_exists(self, index: str) -> bool:
        resp = await self._client.head(f"/{index}")
        return resp.status_code == 200

    async def delete_index(self, index: str) -> dict[str, Any]:
        resp = await self._request_with_retry("DELETE", f"/{index}")
        if resp.status_code not in (200, 404):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json() if resp.status_code == 200 else {"acknowledged": True}

    async def put_alias(self, index: str, alias: str) -> dict[str, Any]:
        resp = await self._request_with_retry("PUT", f"/{index}/_alias/{alias}")
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def update_aliases(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        resp = await self._request_with_retry(
            "POST", "/_aliases", json_data={"actions": actions}
        )
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def get_alias(self, alias: str) -> dict[str, Any]:
        resp = await self._client.get(f"/_alias/{alias}")
        if resp.status_code == 404:
            return {}
        if resp.status_code >= 400:
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def index_document(
        self,
        index: str,
        doc_id: str,
        document: dict[str, Any],
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version
            params["version_type"] = version_type

        resp = await self._request_with_retry(
            "PUT",
            f"/{index}/_doc/{doc_id}",
            params=params,
            json_data=document,
        )
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def get_document(self, index: str, doc_id: str) -> dict[str, Any] | None:
        resp = await self._client.get(f"/{index}/_doc/{doc_id}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def delete_document(
        self,
        index: str,
        doc_id: str,
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version
            params["version_type"] = version_type

        resp = await self._request_with_retry(
            "DELETE",
            f"/{index}/_doc/{doc_id}",
            params=params,
        )
        if resp.status_code == 404:
            return {"result": "not_found", "_id": doc_id}
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def search(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request_with_retry(
            "POST", f"/{index}/_search", json_data=query
        )
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def reindex(
        self, source_index: str, dest_index: str, wait_for_completion: bool = True
    ) -> dict[str, Any]:
        body = {
            "source": {"index": source_index},
            "dest": {"index": dest_index, "version_type": "external_gte"},
        }
        resp = await self._request_with_retry(
            "POST",
            "/_reindex",
            params={"wait_for_completion": "true" if wait_for_completion else "false"},
            json_data=body,
        )
        if resp.status_code not in (200, 201):
            raise OpenSearchResponseError(resp.status_code, resp.text)
        return resp.json()

    async def close(self) -> None:
        if not self._closed:
            await self._client.aclose()
            self._closed = True
            logger.info("OpenSearchClient closed.")


class MockOpenSearchClient(BaseSearchClient):
    """
    In-memory Mock OpenSearch client for local testing and CI.
    Supports:
    - Real external_gte versioning (rejects older versions with OpenSearchConflictError).
    - Multi-index and alias management.
    - Full search query evaluation (multi_match, match, term, range, bool queries, sorting, pagination).
    - Full facet / aggregation generation (categories, brands, retailers, price ranges).
    - Simulated downtime and transient errors.
    """

    def __init__(self, config_settings: Settings | None = None) -> None:
        self._settings = config_settings or settings
        self._indices: dict[str, dict[str, Any]] = {}
        self._aliases: dict[str, set[str]] = {}  # alias_name -> set of index_names
        self._documents: dict[
            str, dict[str, dict[str, Any]]
        ] = {}  # index -> {doc_id: doc_wrapper}
        self.simulate_downtime = False
        self.simulated_exception: Exception | None = None
        self._closed = False

    def _resolve_index_names(self, target: str) -> list[str]:
        if target in self._aliases:
            return list(self._aliases[target])
        if target in self._indices:
            return [target]
        # Check wildcard
        if "*" in target:
            prefix = target.replace("*", "")
            return [idx for idx in self._indices if idx.startswith(prefix)]
        return [target]

    async def ping(self) -> bool:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        return True

    async def cluster_health(self) -> dict[str, Any]:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        if self.simulated_exception:
            raise self.simulated_exception
        return {"status": "green", "number_of_nodes": 1, "timed_out": False}

    async def create_index(
        self, index: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        self._indices[index] = body or {}
        if index not in self._documents:
            self._documents[index] = {}
        return {"acknowledged": True, "shards_acknowledged": True, "index": index}

    async def index_exists(self, index: str) -> bool:
        return index in self._indices

    async def delete_index(self, index: str) -> dict[str, Any]:
        self._indices.pop(index, None)
        self._documents.pop(index, None)
        for alias_set in self._aliases.values():
            alias_set.discard(index)
        return {"acknowledged": True}

    async def put_alias(self, index: str, alias: str) -> dict[str, Any]:
        if alias not in self._aliases:
            self._aliases[alias] = set()
        self._aliases[alias].add(index)
        return {"acknowledged": True}

    async def update_aliases(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        for action in actions:
            if "add" in action:
                idx = action["add"]["index"]
                alias = action["add"]["alias"]
                await self.put_alias(idx, alias)
            elif "remove" in action:
                idx = action["remove"]["index"]
                alias = action["remove"]["alias"]
                if alias in self._aliases:
                    self._aliases[alias].discard(idx)
        return {"acknowledged": True}

    async def get_alias(self, alias: str) -> dict[str, Any]:
        if alias not in self._aliases:
            return {}
        result = {}
        for idx in self._aliases[alias]:
            result[idx] = {"aliases": {alias: {}}}
        return result

    async def index_document(
        self,
        index: str,
        doc_id: str,
        document: dict[str, Any],
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        if self.simulated_exception:
            raise self.simulated_exception

        target_indices = self._resolve_index_names(index)
        target_index = target_indices[0] if target_indices else index
        if target_index not in self._documents:
            self._documents[target_index] = {}

        existing_entry = self._documents[target_index].get(doc_id)
        if existing_entry is not None and version is not None:
            curr_version = existing_entry.get("_version", 1)
            if version_type == "external_gte" and version < curr_version:
                raise OpenSearchConflictError(
                    f"Version conflict on {doc_id}: incoming {version} < current {curr_version}",
                    current_version=curr_version,
                )

        doc_version = version if version is not None else 1
        self._documents[target_index][doc_id] = {
            "_id": doc_id,
            "_source": dict(document),
            "_version": doc_version,
        }
        return {
            "_index": target_index,
            "_id": doc_id,
            "_version": doc_version,
            "result": "created" if existing_entry is None else "updated",
        }

    async def get_document(self, index: str, doc_id: str) -> dict[str, Any] | None:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        target_indices = self._resolve_index_names(index)
        for idx in target_indices:
            if idx in self._documents and doc_id in self._documents[idx]:
                entry = self._documents[idx][doc_id]
                return {
                    "_index": idx,
                    "_id": doc_id,
                    "_version": entry["_version"],
                    "_source": dict(entry["_source"]),
                    "found": True,
                }
        return None

    async def delete_document(
        self,
        index: str,
        doc_id: str,
        *,
        version: int | None = None,
        version_type: str = "external_gte",
    ) -> dict[str, Any]:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        target_indices = self._resolve_index_names(index)
        for idx in target_indices:
            if idx in self._documents and doc_id in self._documents[idx]:
                existing_entry = self._documents[idx][doc_id]
                curr_version = existing_entry["_version"]
                if (
                    version is not None
                    and version_type == "external_gte"
                    and version < curr_version
                ):
                    raise OpenSearchConflictError(
                        f"Version conflict on delete {doc_id}: incoming {version} < current {curr_version}",
                        current_version=curr_version,
                    )
                del self._documents[idx][doc_id]
                return {
                    "_index": idx,
                    "_id": doc_id,
                    "result": "deleted",
                    "_version": version or (curr_version + 1),
                }
        return {"result": "not_found", "_id": doc_id}

    async def search(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        if self.simulate_downtime:
            raise OpenSearchConnectionError("Mock OpenSearch cluster is unreachable")
        if self.simulated_exception:
            raise self.simulated_exception

        target_indices = self._resolve_index_names(index)
        all_docs: list[dict[str, Any]] = []
        for idx in target_indices:
            if idx in self._documents:
                all_docs.extend(self._documents[idx].values())

        # Filtering and matching logic
        q_root = query.get("query", {})
        matched_docs: list[dict[str, Any]] = []

        for entry in all_docs:
            src = entry["_source"]
            if not self._evaluate_query(src, q_root):
                continue
            matched_docs.append(entry)

        # Sorting
        sort_criteria = query.get("sort", [])
        matched_docs = self._sort_documents(matched_docs, sort_criteria)

        total_count = len(matched_docs)
        from_idx = query.get("from", 0)
        size = query.get("size", 20)
        paged_docs = matched_docs[from_idx : from_idx + size]

        hits = [
            {
                "_index": d["_index"] if "_index" in d else target_indices[0],
                "_id": d["_id"],
                "_score": 1.0,
                "_version": d["_version"],
                "_source": dict(d["_source"]),
            }
            for d in paged_docs
        ]

        # Aggregations / Facets
        aggs_result = self._evaluate_aggregations(matched_docs, query.get("aggs", {}))

        return {
            "took": 5,
            "timed_out": False,
            "hits": {
                "total": {"value": total_count, "relation": "eq"},
                "max_score": 1.0 if hits else None,
                "hits": hits,
            },
            "aggregations": aggs_result,
        }

    def _evaluate_query(self, src: dict[str, Any], q: dict[str, Any]) -> bool:
        if not q or q == {"match_all": {}}:
            return True

        if "bool" in q:
            bool_q = q["bool"]
            # Must conditions
            for must in bool_q.get("must", []):
                if not self._evaluate_query(src, must):
                    return False
            # Filter conditions (exact matches, ranges)
            for flt in bool_q.get("filter", []):
                if not self._evaluate_query(src, flt):
                    return False
            # Must not
            for must_not in bool_q.get("must_not", []):
                if self._evaluate_query(src, must_not):
                    return False
            # Should conditions
            shoulds = bool_q.get("should", [])
            if shoulds:
                if not any(self._evaluate_query(src, should) for should in shoulds):
                    return False
            return True

        if "multi_match" in q:
            mm = q["multi_match"]
            query_str = str(mm.get("query", "")).lower()
            fields = mm.get("fields", ["name", "description", "brand"])
            found = False
            for f in fields:
                f_clean = f.split("^")[0]
                val = str(src.get(f_clean, "")).lower()
                if query_str in val:
                    found = True
                    break
            return found

        if "match" in q:
            for field, val in q["match"].items():
                expected = str(val).lower()
                actual = str(src.get(field, "")).lower()
                if expected not in actual:
                    return False
            return True

        if "term" in q:
            for field, val in q["term"].items():
                actual = src.get(field)
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                if actual != val:
                    # check string equivalence
                    if str(actual).lower() != str(val).lower():
                        return False
            return True

        if "terms" in q:
            for field, vals in q["terms"].items():
                actual = src.get(field)
                if actual not in vals:
                    return False
            return True

        if "range" in q:
            for field, range_spec in q["range"].items():
                val = src.get(field)
                if val is None:
                    return False
                if "gte" in range_spec and val < range_spec["gte"]:
                    return False
                if "lte" in range_spec and val > range_spec["lte"]:
                    return False
                if "gt" in range_spec and val <= range_spec["gt"]:
                    return False
                if "lt" in range_spec and val >= range_spec["lt"]:
                    return False
            return True

        return True

    def _sort_documents(
        self, docs: list[dict[str, Any]], sort_criteria: list[Any]
    ) -> list[dict[str, Any]]:
        if not sort_criteria:
            return docs

        sorted_docs = list(docs)
        for criterion in reversed(sort_criteria):
            if isinstance(criterion, str):
                field = criterion
                order = "asc"
            elif isinstance(criterion, dict):
                field, opts = next(iter(criterion.items()))
                order = opts.get("order", "asc") if isinstance(opts, dict) else opts
            else:
                continue

            reverse = order.lower() == "desc"
            sorted_docs.sort(key=lambda d: d["_source"].get(field, 0), reverse=reverse)
        return sorted_docs

    def _evaluate_aggregations(
        self, docs: list[dict[str, Any]], aggs_spec: dict[str, Any]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for agg_name, spec in aggs_spec.items():
            if "terms" in spec:
                field = spec["terms"]["field"]
                counts: dict[str, int] = {}
                for d in docs:
                    val = d["_source"].get(field)
                    if val is not None:
                        val_str = str(val)
                        counts[val_str] = counts.get(val_str, 0) + 1
                buckets = [
                    {"key": k, "doc_count": v}
                    for k, v in sorted(counts.items(), key=lambda x: -x[1])
                ]
                result[agg_name] = {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": buckets,
                }
            elif "stats" in spec:
                field = spec["stats"]["field"]
                vals = [
                    d["_source"].get(field)
                    for d in docs
                    if d["_source"].get(field) is not None
                ]
                if vals:
                    result[agg_name] = {
                        "count": len(vals),
                        "min": min(vals),
                        "max": max(vals),
                        "avg": sum(vals) / len(vals),
                        "sum": sum(vals),
                    }
                else:
                    result[agg_name] = {
                        "count": 0,
                        "min": None,
                        "max": None,
                        "avg": None,
                        "sum": 0,
                    }
        return result

    async def reindex(
        self, source_index: str, dest_index: str, wait_for_completion: bool = True
    ) -> dict[str, Any]:
        if source_index not in self._documents:
            return {"took": 1, "timed_out": False, "total": 0, "created": 0}
        if dest_index not in self._documents:
            self._documents[dest_index] = {}

        count = 0
        for doc_id, entry in self._documents[source_index].items():
            self._documents[dest_index][doc_id] = {
                "_id": doc_id,
                "_source": dict(entry["_source"]),
                "_version": entry["_version"],
            }
            count += 1
        return {"took": 5, "timed_out": False, "total": count, "created": count}

    async def close(self) -> None:
        self._closed = True


_search_client_instance: BaseSearchClient | None = None


def get_opensearch_client(
    config_settings: Settings | None = None,
    *,
    force_mock: bool = False,
) -> BaseSearchClient:
    """
    Factory returning OpenSearchClient (if configured) or MockOpenSearchClient.
    Safe for local development, CI, and test execution.
    """
    global _search_client_instance
    active_settings = config_settings or settings

    if force_mock or not active_settings.has_opensearch:
        if active_settings.is_production:
            raise RuntimeError(
                "MockOpenSearchClient is strictly forbidden in production."
            )
        return MockOpenSearchClient(active_settings)

    if _search_client_instance is None:
        _search_client_instance = OpenSearchClient(active_settings)
    return _search_client_instance
