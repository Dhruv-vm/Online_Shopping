"""Version 2.0 Phase A3 — search must not trust an OpenSearch index that the
Kafka/outbox pipeline is not keeping in sync (v1.0 audit defect D5)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.search.client import MockOpenSearchClient
from app.core.search.index_health import (
    SearchEngineStatus,
    evaluate_search_engine,
    register_outbox_publisher,
    reset_search_engine_cache,
    set_search_indexer_running,
)
from app.modules.orders.models import OutboxEvent
from app.modules.search.service import SearchService
from tests.phase3_helpers import make_user


class _Producer:
    is_connected = True


class _Publisher:
    is_running = True
    producer = _Producer()


def _cfg(**over):
    base = {
        "OPENSEARCH_URL": "https://search.example.invalid:9200",
        "KAFKA_BOOTSTRAP_SERVERS": "kafka.example.invalid:9093",
        "SEARCH_INDEX_MAX_LAG_SECONDS": 300,
    }
    base.update(over)
    return settings.model_copy(update=base)


@pytest.fixture(autouse=True)
def _clean_sync_state():
    register_outbox_publisher(None)
    set_search_indexer_running(False)
    yield
    register_outbox_publisher(None)
    set_search_indexer_running(False)
    reset_search_engine_cache()


@pytest.mark.asyncio
async def test_engine_decision_for_each_pipeline_state():
    async with get_session_factory()() as s:
        st = await evaluate_search_engine(s, _cfg(OPENSEARCH_URL=""))
        assert (st.engine, st.reason) == ("postgres", "OPENSEARCH_NOT_CONFIGURED")

        st = await evaluate_search_engine(s, _cfg(KAFKA_BOOTSTRAP_SERVERS=""))
        assert (st.engine, st.reason) == ("postgres_fallback", "KAFKA_NOT_CONFIGURED")

        st = await evaluate_search_engine(s, _cfg())
        assert st.reason == "OUTBOX_PUBLISHER_NOT_CONNECTED"

        register_outbox_publisher(_Publisher())
        st = await evaluate_search_engine(s, _cfg())
        assert st.reason == "SEARCH_INDEXER_NOT_RUNNING"

        set_search_indexer_running(True)
        # The shared test database may hold old PENDING events from other tests;
        # a very large lag limit isolates the "healthy" case from them.
        st = await evaluate_search_engine(s, _cfg(SEARCH_INDEX_MAX_LAG_SECONDS=10**9))
        assert (st.engine, st.reason) == ("opensearch", None)


@pytest.mark.asyncio
async def test_outbox_backlog_means_stale_index():
    register_outbox_publisher(_Publisher())
    set_search_indexer_running(True)
    event_id = uuid.uuid4()
    async with get_session_factory()() as s:
        s.add(
            OutboxEvent(
                id=event_id,
                event_type="product.updated",
                aggregate_type="product",
                aggregate_id=uuid.uuid4(),
                payload={},
                status="PENDING",
                created_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        await s.commit()
    try:
        async with get_session_factory()() as s:
            st = await evaluate_search_engine(
                s, _cfg(SEARCH_INDEX_MAX_LAG_SECONDS=3600)
            )
        assert (st.engine, st.reason) == ("postgres_fallback", "OUTBOX_BACKLOG")
    finally:
        async with get_session_factory()() as s:
            await s.execute(delete(OutboxEvent).where(OutboxEvent.id == event_id))
            await s.commit()


class _CountingClient(MockOpenSearchClient):
    def __init__(self) -> None:
        super().__init__()
        self.search_calls = 0

    async def search(self, *args, **kwargs):
        self.search_calls += 1
        return await super().search(*args, **kwargs)


@pytest.mark.asyncio
async def test_untrusted_index_is_never_queried():
    client = _CountingClient()

    async def unhealthy(_session):
        return SearchEngineStatus("postgres_fallback", "KAFKA_NOT_CONFIGURED", "x")

    svc = SearchService(search_client=client, index_health=unhealthy)
    async with get_session_factory()() as s:
        res = await svc.search(s, q="laptop")
        sug = await svc.get_suggestions(s, "lap")
    assert client.search_calls == 0
    assert res.engine == "postgres_fallback"
    assert res.engine_reason == "KAFKA_NOT_CONFIGURED"
    assert sug.query == "lap"


@pytest.mark.asyncio
async def test_trusted_index_is_used():
    client = _CountingClient()

    async def healthy(_session):
        return SearchEngineStatus("opensearch", None, "Index in sync")

    svc = SearchService(
        search_client=client,
        index_health=healthy,
        search_alias="basket_products_search",
    )
    async with get_session_factory()() as s:
        res = await svc.search(s, q="anything")
    assert client.search_calls == 1
    assert res.engine == "opensearch" and res.engine_reason is None


@pytest.mark.asyncio
async def test_configured_cluster_without_kafka_falls_back_by_default():
    """Default wiring (no injected client): OpenSearch configured, Kafka not."""
    cfg = _cfg(KAFKA_BOOTSTRAP_SERVERS="")
    svc = SearchService(config_settings=cfg)
    assert svc.client is not None  # a real client object; must not be queried
    calls = 0

    async def no_network(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("OpenSearch must not be queried")

    svc.client.search = no_network  # type: ignore[method-assign]
    async with get_session_factory()() as s:
        res = await svc.search(s, q="laptop")
    assert calls == 0
    assert res.engine == "postgres_fallback"
    assert res.engine_reason == "KAFKA_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_health_endpoints_report_search_engine(
    async_client: AsyncClient, monkeypatch
):
    _, admin = await make_user("admin")
    # Test suite: OpenSearch and Kafka are blank → plain PostgreSQL.
    h = (await async_client.get("/api/v1/admin/system/health", headers=admin)).json()
    assert h["search_engine"]["engine"] == "postgres"
    assert {c["name"]: c["status"] for c in h["components"]}["OpenSearch"] == (
        "not_configured"
    )

    monkeypatch.setattr(settings, "OPENSEARCH_URL", "https://search.example.invalid")
    reset_search_engine_cache()
    h = (await async_client.get("/api/v1/admin/system/health", headers=admin)).json()
    assert h["search_engine"] == {
        "engine": "postgres_fallback",
        "reason": "KAFKA_NOT_CONFIGURED",
        "detail": h["search_engine"]["detail"],
    }
    os_row = next(c for c in h["components"] if c["name"] == "OpenSearch")
    assert os_row["status"] == "degraded" and "PostgreSQL" in os_row["detail"]

    ready = (await async_client.get("/ready")).json()
    assert ready["checks"]["search"]["engine"] == "postgres_fallback"
    assert ready["checks"]["search"]["reason"] == "KAFKA_NOT_CONFIGURED"
