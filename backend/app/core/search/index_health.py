"""Decide whether the OpenSearch index can be trusted (Version 2.0 Phase A3).

The index is only updated by the Kafka pipeline (outbox publisher -> Kafka ->
OpenSearchConsumer). When any part of that pipeline is down, or outbox events
are piling up, the index is stale (or, on a shared cluster, may describe another
database), so search must use PostgreSQL instead.

State is per process: the publisher and the indexer run inside this API process.
"""

from __future__ import annotations

import datetime
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings

Engine = Literal["opensearch", "postgres", "postgres_fallback"]

# Set by the background supervisor / application lifespan.
_SYNC_STATE: dict[str, Any] = {"publisher": None, "indexer_running": False}

_CACHE_TTL_SECONDS = 10.0
_cache: tuple[float, SearchEngineStatus] | None = None


@dataclass(frozen=True)
class SearchEngineStatus:
    engine: Engine
    reason: str | None = None
    detail: str = ""

    @property
    def use_opensearch(self) -> bool:
        return self.engine == "opensearch"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def register_outbox_publisher(worker: Any | None) -> None:
    """Record the running outbox publisher (or None when it stops)."""
    _SYNC_STATE["publisher"] = worker
    reset_search_engine_cache()


def set_search_indexer_running(running: bool) -> None:
    """Record whether the OpenSearch indexing consumer runs in this process."""
    _SYNC_STATE["indexer_running"] = bool(running)
    reset_search_engine_cache()


def reset_search_engine_cache() -> None:
    global _cache
    _cache = None


def _publisher_connected() -> bool:
    worker = _SYNC_STATE.get("publisher")
    if worker is None:
        return False
    running = getattr(worker, "is_running", False)
    producer = getattr(worker, "producer", None)
    return bool(running) and bool(getattr(producer, "is_connected", False))


async def _oldest_pending_seconds(session: AsyncSession) -> int | None:
    from app.modules.orders.models import OutboxEvent

    oldest = (
        await session.execute(
            select(func.min(OutboxEvent.created_at)).where(
                OutboxEvent.status == "PENDING"
            )
        )
    ).scalar_one_or_none()
    if oldest is None:
        return None
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=datetime.UTC)
    return int((datetime.datetime.now(datetime.UTC) - oldest).total_seconds())


async def evaluate_search_engine(
    session: AsyncSession | None, config: Settings | None = None
) -> SearchEngineStatus:
    """Return which engine search must use right now, and why."""
    cfg = config or settings
    if not cfg.has_opensearch:
        return SearchEngineStatus(
            "postgres", "OPENSEARCH_NOT_CONFIGURED", "Search uses PostgreSQL"
        )
    if not cfg.has_kafka:
        return SearchEngineStatus(
            "postgres_fallback",
            "KAFKA_NOT_CONFIGURED",
            "Index cannot be kept in sync without Kafka; search uses PostgreSQL",
        )
    if not _publisher_connected():
        return SearchEngineStatus(
            "postgres_fallback",
            "OUTBOX_PUBLISHER_NOT_CONNECTED",
            "Outbox publisher is not connected to Kafka; search uses PostgreSQL",
        )
    if not _SYNC_STATE.get("indexer_running"):
        return SearchEngineStatus(
            "postgres_fallback",
            "SEARCH_INDEXER_NOT_RUNNING",
            "OpenSearch indexing consumer is not running; search uses PostgreSQL",
        )
    if session is not None:
        try:
            lag = await _oldest_pending_seconds(session)
        except Exception as exc:  # never fail a search because of the check
            return SearchEngineStatus(
                "postgres_fallback",
                "OUTBOX_CHECK_FAILED",
                f"Could not read the outbox ({type(exc).__name__}); search uses PostgreSQL",
            )
        if lag is not None and lag > cfg.SEARCH_INDEX_MAX_LAG_SECONDS:
            return SearchEngineStatus(
                "postgres_fallback",
                "OUTBOX_BACKLOG",
                f"Oldest unpublished event is {lag}s old; search uses PostgreSQL",
            )
    return SearchEngineStatus("opensearch", None, "Index in sync")


async def current_search_engine(
    session: AsyncSession | None, config: Settings | None = None
) -> SearchEngineStatus:
    """Cached (10 s) version of :func:`evaluate_search_engine` for the search path."""
    global _cache
    now = time.monotonic()
    if config is None and _cache is not None and now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]
    status = await evaluate_search_engine(session, config)
    if config is None:
        _cache = (now, status)
    return status
