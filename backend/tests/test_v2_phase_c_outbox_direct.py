"""Version 2.0 Phase C2: outbox delivery without Kafka (OUTBOX_DISPATCH=direct)
and database-specific OpenSearch index names.

The shared test database can hold PENDING outbox rows left by other tests; the
``_park_other_events`` fixture postpones them for the duration of each test (and
restores them) so only this test's events are claimed."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, update

from app.core.background import BackgroundWorkerSupervisor
from app.core.config import Settings, settings
from app.core.database import get_session_factory
from app.core.events.consumer import BaseKafkaConsumer
from app.core.events.direct_dispatch import (
    DirectDispatchProducer,
    direct_consumer_kwargs,
)
from app.core.events.envelope import EventEnvelope
from app.core.events.inbox import ConsumerInbox
from app.core.events.outbox_publisher import OutboxPublisherWorker
from app.core.search.client import MockOpenSearchClient
from app.core.search.consumer import OpenSearchConsumer
from app.core.search.index import (
    get_search_alias_name,
    get_write_alias_name,
    resolve_index_prefix,
)
from app.core.search.index_health import (
    SearchEngineStatus,
    evaluate_search_engine,
    outbox_dispatch_status,
    register_outbox_publisher,
    reset_search_engine_cache,
    set_search_indexer_running,
)
from app.modules.orders.models import OutboxEvent
from app.modules.search.service import SearchService
from tests.phase3_helpers import make_retailer

TOPIC = "basket.events.catalogue"


@pytest.fixture(autouse=True)
async def _park_other_events():
    started = datetime.now(UTC)
    async with get_session_factory()() as s:
        rows = (
            await s.execute(
                select(OutboxEvent.id, OutboxEvent.next_attempt_at).where(
                    OutboxEvent.status.in_(("PENDING", "PROCESSING")),
                    OutboxEvent.created_at < started,
                )
            )
        ).all()
        if rows:
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id.in_([r[0] for r in rows]))
                .values(
                    next_attempt_at=started + timedelta(days=1),
                    claim_expires_at=started + timedelta(days=1),
                )
            )
            await s.commit()
    yield
    async with get_session_factory()() as s:
        for rid, nxt in rows:
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == rid)
                .values(next_attempt_at=nxt, claim_expires_at=None)
            )
        await s.commit()
    register_outbox_publisher(None)
    set_search_indexer_running(False)
    reset_search_engine_cache()


def _worker(producer, **kw):
    return OutboxPublisherWorker(
        session_factory=get_session_factory(),
        producer=producer,
        poll_interval_seconds=0.05,
        **kw,
    )


async def _status(event_id):
    async with get_session_factory()() as s:
        e = await s.get(OutboxEvent, event_id)
        return e.status, e.retry_count, e.last_error


class _CountingConsumer(BaseKafkaConsumer):
    """A consumer whose handler fails the first ``fail_times`` deliveries."""

    def __init__(self, fail_times=0):
        super().__init__(
            consumer_group=f"v2c-test-{uuid.uuid4().hex[:8]}",
            topics=[TOPIC],
            session_factory=get_session_factory(),
            backoff_base_seconds=0,
            backoff_max_seconds=0,
            backoff_max_jitter_seconds=0,
            **direct_consumer_kwargs(),
        )
        self.fail_times = fail_times
        self.calls = 0
        self.effects: list[uuid.UUID] = []

    async def handle_event(self, event, session):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("downstream briefly unavailable")
        self.effects.append(event.event_id)


async def _own_event():
    eid = uuid.uuid4()
    async with get_session_factory()() as s:
        s.add(
            OutboxEvent(
                id=eid,
                aggregate_type="product",
                aggregate_id=uuid.uuid4(),
                event_type="product.updated",
                schema_version=1,
                payload={"reason": "v2c-test"},
                status="PENDING",
                retry_count=0,
                aggregate_version=1,
            )
        )
        await s.commit()
    return eid


# ------------------------------------------------------------------- C2 core
@pytest.mark.asyncio
async def test_price_update_reaches_search_without_kafka(async_client: AsyncClient):
    listing, rh = await make_retailer(
        selling_price_paise=70000, original_price_paise=90000
    )
    mock = MockOpenSearchClient()
    consumer = OpenSearchConsumer(
        session_factory=get_session_factory(),
        search_client=mock,
        **direct_consumer_kwargs(),
    )
    producer = DirectDispatchProducer([consumer])
    await producer.start()
    worker = _worker(producer)

    async def search_price():
        async def healthy(_s):
            return SearchEngineStatus("opensearch", None, "test")

        svc = SearchService(search_client=mock, index_health=healthy)
        async with get_session_factory()() as s:
            res = await svc.search(s, q=listing["product_name"])
        assert res.engine == "opensearch"
        hit = next(i for i in res.items if str(i.product_id) == listing["product_id"])
        return hit.min_price_paise

    for price in (65000, 61000):
        r = await async_client.patch(
            f"/api/v1/retailer/listings/{listing['id']}",
            headers=rh,
            json={"selling_price_paise": price},
        )
        assert r.status_code == 200, r.text
        assert await worker.publish_batch() >= 1  # one publisher cycle
        assert await search_price() == price

    async with get_session_factory()() as s:
        mine = (
            (
                await s.execute(
                    select(OutboxEvent.status).where(
                        OutboxEvent.aggregate_id == uuid.UUID(listing["product_id"])
                    )
                )
            )
            .scalars()
            .all()
        )
    assert mine and set(mine) == {"PUBLISHED"}


@pytest.mark.asyncio
async def test_failed_handler_retries_with_backoff_then_publishes_once():
    consumer = _CountingConsumer(fail_times=1)
    producer = DirectDispatchProducer([consumer])
    await producer.start()
    worker = _worker(producer)
    eid = await _own_event()

    assert await worker.publish_batch() == 0
    status, retries, err = await _status(eid)
    assert status == "PENDING" and retries == 1 and err  # attempt + error recorded
    async with get_session_factory()() as s:
        nxt = (await s.get(OutboxEvent, eid)).next_attempt_at
    assert nxt > datetime.now(UTC)  # backoff scheduled, not hot-looped
    assert await worker.publish_batch() == 0  # not due yet → not retried

    async with get_session_factory()() as s:  # time passes
        await s.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == eid)
            .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
    assert await worker.publish_batch() == 1
    assert (await _status(eid))[0] == "PUBLISHED"
    assert consumer.effects == [eid]


@pytest.mark.asyncio
async def test_duplicate_delivery_has_no_duplicate_effect():
    consumer = _CountingConsumer()
    producer = DirectDispatchProducer([consumer])
    await producer.start()
    env = EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="product.updated",
        event_version=1,
        aggregate_type="product",
        aggregate_id=uuid.uuid4(),
        aggregate_version=1,
        occurred_at=datetime.now(UTC),
        payload={},
    )
    for _ in range(3):
        await producer.send(TOPIC, env)
    assert consumer.effects == [env.event_id] and consumer.calls == 1
    async with get_session_factory()() as s:
        rows = (
            (
                await s.execute(
                    select(ConsumerInbox.status).where(
                        ConsumerInbox.consumer_group == consumer.consumer_group,
                        ConsumerInbox.event_id == env.event_id,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert rows == ["SUCCEEDED"]


@pytest.mark.asyncio
async def test_two_direct_workers_never_deliver_an_event_twice():
    consumer = _CountingConsumer()
    producer = DirectDispatchProducer([consumer])
    await producer.start()
    ids = [await _own_event() for _ in range(8)]
    w1, w2 = _worker(producer), _worker(producer)
    for _ in range(3):
        await asyncio.gather(w1.publish_batch(), w2.publish_batch())
    assert sorted(consumer.effects, key=str) == sorted(ids, key=str)
    assert consumer.calls == len(ids)
    for eid in ids:
        assert (await _status(eid))[0] == "PUBLISHED"


# ---------------------------------------------------------- mode selection
def test_dispatch_mode_is_explicit():
    assert Settings(_env_file=None).OUTBOX_DISPATCH == "kafka"
    assert (
        Settings(OUTBOX_DISPATCH=" DIRECT ", _env_file=None).OUTBOX_DISPATCH == "direct"
    )
    with pytest.raises(ValidationError):
        Settings(OUTBOX_DISPATCH="both", _env_file=None)


@pytest.mark.asyncio
async def test_supervisor_runs_exactly_one_dispatcher():
    sf = get_session_factory()
    direct = settings.model_copy(
        update={
            "OUTBOX_DISPATCH": "direct",
            "OPENSEARCH_URL": "",
            "KAFKA_BOOTSTRAP_SERVERS": "kafka.example.invalid:9093",
        }
    )
    sup = BackgroundWorkerSupervisor(sf, config=direct)
    await sup.start()
    try:
        await asyncio.sleep(0.3)
        assert isinstance(sup._outbox_worker.producer, DirectDispatchProducer)
        assert outbox_dispatch_status(direct)["dispatcher_running"] is True
    finally:
        await sup.stop()
    assert outbox_dispatch_status(direct)["dispatcher_running"] is False

    # Kafka mode without a broker never falls back to direct on its own.
    kafka_less = settings.model_copy(
        update={"OUTBOX_DISPATCH": "kafka", "KAFKA_BOOTSTRAP_SERVERS": ""}
    )
    sup = BackgroundWorkerSupervisor(sf, config=kafka_less)
    await sup.start()
    try:
        await asyncio.sleep(0.2)
        assert sup._outbox_worker is None
    finally:
        await sup.stop()


@pytest.mark.asyncio
async def test_direct_bootstrap_builds_this_databases_index_then_search_trusts_it():
    mock = MockOpenSearchClient()
    consumer = OpenSearchConsumer(
        session_factory=get_session_factory(),
        search_client=mock,
        **direct_consumer_kwargs(),
    )
    cfg = settings.model_copy(
        update={
            "OUTBOX_DISPATCH": "direct",
            "OPENSEARCH_URL": "https://os.example.invalid",
            "KAFKA_BOOTSTRAP_SERVERS": "",
            "SEARCH_INDEX_MAX_LAG_SECONDS": 10**9,
        }
    )
    producer = DirectDispatchProducer([consumer])
    await producer.start()
    worker = _worker(producer)
    worker._running = True  # registered as a live dispatcher without its loop
    register_outbox_publisher(worker)
    async with get_session_factory()() as s:
        before = await evaluate_search_engine(s, cfg)
    assert (before.engine, before.reason) == (
        "postgres_fallback",
        "SEARCH_INDEXER_NOT_RUNNING",
    )

    sup = BackgroundWorkerSupervisor(get_session_factory(), config=cfg)
    await sup._bootstrap_search_index(consumer)
    alias = get_write_alias_name(resolve_index_prefix(cfg))
    assert mock._resolve_index_names(alias)  # this database's alias exists
    assert any(mock._documents[i] for i in mock._resolve_index_names(alias))
    async with get_session_factory()() as s:
        after = await evaluate_search_engine(s, cfg)
    assert after.engine == "opensearch"

    register_outbox_publisher(None)  # dispatcher gone → back to PostgreSQL
    async with get_session_factory()() as s:
        gone = await evaluate_search_engine(s, cfg)
    assert gone.reason == "OUTBOX_DISPATCHER_NOT_RUNNING"


# ------------------------------------------------------ per-database indexes
def test_index_names_are_database_specific_and_secret_free():
    def cfg(url, **kw):
        return Settings(DATABASE_URL=url, _env_file=None, **kw)

    a = resolve_index_prefix(cfg("postgresql+asyncpg://u:Pw1@db:5432/basket_db"))
    b = resolve_index_prefix(cfg("postgresql+asyncpg://u:Pw1@db:5432/basket_v2b_demo"))
    a2 = resolve_index_prefix(cfg("postgresql+asyncpg://other:Pw2@db:5432/basket_db"))
    c = resolve_index_prefix(cfg("postgresql+asyncpg://u:Pw1@elsewhere:5432/basket_db"))
    assert a != b and a != c and a == a2  # identity = host:port/name, not the user
    assert "pw1" not in a.lower() and "u:" not in a
    assert a.startswith("basket_basket_db_") and a == a.lower()
    off = resolve_index_prefix(
        cfg(
            "postgresql+asyncpg://u:p@db/basket_db", OPENSEARCH_INDEX_PER_DATABASE=False
        )
    )
    assert off == "basket"
    # Runtime defaults use this database's names.
    mine = resolve_index_prefix(settings)
    assert SearchService().search_alias == get_search_alias_name(mine)
    consumer = OpenSearchConsumer(
        session_factory=get_session_factory(),
        search_client=MockOpenSearchClient(),
        **direct_consumer_kwargs(),
    )
    assert consumer._index_alias == get_write_alias_name(mine)


@pytest.mark.asyncio
async def test_phase3_marketplace_events_are_publishable(async_client: AsyncClient):
    """Found by the live direct-mode run and the payload audit: order.created
    carried customer_id; exchange.request_created, demand.pool_created and
    auction.started carried the customer's pincode (all rejected by the
    envelope's PII guard); price.changed lacked product_id. None of them could
    ever be published, in any dispatch mode."""
    from tests.phase3_helpers import make_user

    started = datetime.now(UTC)
    _, cust = await make_user()
    rfq = await async_client.post(
        "/api/v1/exchange/requests",
        headers=cust,
        json={
            "title": "Outbox check",
            "delivery_pincode": "560034",
            "budget_limit_paise": 100000,
            "items": [{"name": "Rice 5kg", "quantity": 1}],
        },
    )
    assert rfq.status_code == 201, rfq.text
    sig = await async_client.post(
        "/api/v1/demand/signal",
        headers=cust,
        json={"query_text": f"zz-v2c-{uuid.uuid4().hex[:8]}", "pincode": "560034"},
    )
    assert sig.status_code in (200, 201), sig.text
    listing, rh = await make_retailer(
        selling_price_paise=50000, original_price_paise=60000
    )
    r = await async_client.patch(
        f"/api/v1/retailer/listings/{listing['id']}",
        headers=rh,
        json={"selling_price_paise": 49000},
    )
    assert r.status_code == 200, r.text

    # order.created (carried customer_id) and auction.started (carried pincode)
    from tests.phase3_helpers import place_order

    seller, _ = await make_retailer(
        service_pincodes=["400001"],
        selling_price_paise=30000,
        original_price_paise=30000,
    )
    _, buyer = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=buyer,
        json={"listing_id": seller["id"], "quantity": 1},
    )
    auc = await async_client.post(
        "/api/v1/auctions/start", headers=buyer, json={"pincode": "400001"}
    )
    assert auc.status_code == 201, auc.text
    await place_order(async_client, buyer)

    producer = DirectDispatchProducer([])  # delivery itself is not under test
    await producer.start()
    worker = _worker(producer)
    for _ in range(4):
        await worker.publish_batch()
    async with get_session_factory()() as s:
        rows = (
            await s.execute(
                select(
                    OutboxEvent.event_type, OutboxEvent.status, OutboxEvent.last_error
                ).where(
                    OutboxEvent.created_at >= started,
                    OutboxEvent.event_type.in_(
                        (
                            "exchange.request_created",
                            "demand.pool_created",
                            "price.changed",
                        )
                    ),
                )
            )
        ).all()
    assert {r[0] for r in rows} == {
        "exchange.request_created",
        "demand.pool_created",
        "price.changed",
    }
    assert all(r[1] == "PUBLISHED" for r in rows), rows
