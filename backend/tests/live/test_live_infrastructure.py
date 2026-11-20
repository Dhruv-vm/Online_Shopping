"""Opt-in LIVE infrastructure tests (Kafka + OpenSearch).

Run only with BASKET_LIVE_INFRA_TESTS=1 and real KAFKA_*/OPENSEARCH_* settings.
They are designed to leave no trace:
* OpenSearch: a uniquely named probe index + aliases, deleted at the end.
* Kafka: a unique consumer group starting at the latest offset; probe events
  reference products that exist only in the test database.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid

import pytest
from sqlalchemy import update

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    os.environ.get("BASKET_LIVE_INFRA_TESTS") != "1"
    or not (settings.has_kafka and settings.has_opensearch),
    reason="live infrastructure tests are opt-in",
)


def _kafka_resolves() -> bool:
    import socket

    try:
        host, port = settings.KAFKA_BOOTSTRAP_SERVERS.split(",")[0].rsplit(":", 1)
        socket.getaddrinfo(host, int(port))
        return True
    except Exception:
        return False


needs_kafka = pytest.mark.skipif(
    settings.has_kafka and not _kafka_resolves(),
    reason="Kafka bootstrap host does not resolve (service powered off or deleted)",
)

REQUIRED_TOPICS = [
    "basket.events.orders",
    "basket.events.payments",
    "basket.events.catalogue",
    "basket.events.inventory",
    "basket.events.marketplace",
    settings.KAFKA_DLQ_TOPIC,
]


async def _consumer(topic: str):
    from aiokafka import AIOKafkaConsumer

    from app.core.events.kafka import build_kafka_auth_kwargs

    c = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"basket-audit-probe-{uuid.uuid4().hex[:8]}",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        **build_kafka_auth_kwargs(settings),
    )
    await c.start()
    deadline = time.monotonic() + 30
    while not c.assignment() and time.monotonic() < deadline:
        await c.getmany(timeout_ms=500)
    assert c.assignment(), "consumer never received a partition assignment"
    for tp in c.assignment():
        await c.seek_to_end(tp)
    return c


@needs_kafka
@pytest.mark.asyncio
async def test_live_kafka_topics_and_round_trip():
    from app.core.events.envelope import EventEnvelope
    from app.core.events.kafka import AioKafkaEventProducer

    producer = AioKafkaEventProducer(settings)
    await producer.start()
    try:
        meta = await producer._producer.client.fetch_all_metadata()
        topics = set(meta.topics())
        missing = [t for t in REQUIRED_TOPICS if t not in topics]
        print(
            f"\nKAFKA topics present: {sorted(t for t in topics if t.startswith('basket'))}"
        )
        print(f"KAFKA required topics missing: {missing}")

        consumer = await _consumer("basket.events.catalogue")
        try:
            env = EventEnvelope(
                event_id=uuid.uuid4(),
                event_type="product.updated",
                event_version=1,
                aggregate_type="product",
                aggregate_id=uuid.uuid4(),
                aggregate_version=int(time.time()),
                payload={"reason": "audit_live_probe"},
            )
            await producer.send("basket.events.catalogue", env, timeout=15)
            found = None
            deadline = time.monotonic() + 30
            while found is None and time.monotonic() < deadline:
                batch = await consumer.getmany(timeout_ms=1000)
                for records in batch.values():
                    for r in records:
                        if (
                            EventEnvelope.from_json_bytes(r.value).event_id
                            == env.event_id
                        ):
                            found = r
            assert found is not None, "probe event was not consumed back from Kafka"
        finally:
            await consumer.stop()
        assert not missing, f"Kafka topics must be created before go-live: {missing}"
    finally:
        await producer.stop()


@needs_kafka
@pytest.mark.asyncio
async def test_live_outbox_to_kafka_to_opensearch():
    """outbox row -> OutboxPublisherWorker -> live Kafka -> OpenSearchConsumer -> live OpenSearch."""
    from app.core.database import get_session_factory
    from app.core.events.catalogue_events import enqueue_product_events
    from app.core.events.kafka import AioKafkaEventProducer
    from app.core.events.outbox_publisher import OutboxPublisherWorker
    from app.core.search.client import OpenSearchClient
    from app.core.search.consumer import OpenSearchConsumer
    from app.core.search.index import IndexManager
    from app.modules.orders.models import OutboxEvent
    from app.modules.search.service import SearchService
    from tests.factories import create_test_listing

    client = OpenSearchClient(settings)
    assert await client.ping(), "OpenSearch cluster is not reachable"
    prefix = f"auditprobe{uuid.uuid4().hex[:8]}"
    mgr = IndexManager(client, prefix=prefix)
    index_name = await mgr.ensure_index_and_aliases()
    sf = get_session_factory()
    try:
        name = f"Audit Live Probe {uuid.uuid4().hex[:6]}"
        listing = await create_test_listing(
            product_name=name, category_slug="phase3-test", category_name="Phase 3 Test"
        )
        product_id = uuid.UUID(listing["product_id"])
        async with sf() as s:
            # Publish ONLY the probe event from the scratch test database.
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .values(status="FAILED", last_error="parked by live probe")
            )
            await enqueue_product_events(s, [product_id], reason="audit_live_probe")
            await s.commit()

        consumer = await _consumer("basket.events.catalogue")
        producer = AioKafkaEventProducer(settings)
        await producer.start()
        try:
            worker = OutboxPublisherWorker(session_factory=sf, producer=producer)
            published = await worker.publish_batch()
            assert published == 1, (
                f"expected exactly the probe event, published {published}"
            )
            os_consumer = OpenSearchConsumer(
                session_factory=sf,
                search_client=client,
                index_alias=mgr.write_alias,
                consumer_impl=consumer,
                consumer_group=f"audit-probe-{prefix}",
            )
            handled = False
            deadline = time.monotonic() + 30
            while not handled and time.monotonic() < deadline:
                batch = await consumer.getmany(timeout_ms=1000)
                for records in batch.values():
                    for r in records:
                        from app.core.events.envelope import EventEnvelope

                        if (
                            EventEnvelope.from_json_bytes(r.value).aggregate_id
                            == product_id
                        ):
                            assert await os_consumer.process_record(r) is True
                            handled = True
            assert handled, "probe event did not arrive from Kafka"
        finally:
            await consumer.stop()
            await producer.stop()

        await asyncio.sleep(1.5)  # index refresh
        doc = await client.get_document(mgr.write_alias, str(product_id))
        assert doc is not None and doc["_source"]["name"] == name
        res = await SearchService(
            search_client=client, search_alias=mgr.search_alias
        ).search(None, q=name)
        assert res.engine == "opensearch" and any(
            i.product_id == str(product_id) for i in res.items
        )
    finally:
        await client.delete_index(index_name)
        assert not await client.index_exists(index_name)


@pytest.mark.asyncio
async def test_live_opensearch_projection_versioning_search_and_delete():
    """Live cluster: real consumer projection, snapshot versioning, search, delete."""
    from datetime import UTC, datetime

    from app.core.database import get_session_factory
    from app.core.events.envelope import EventEnvelope
    from app.core.search.client import OpenSearchClient, OpenSearchConflictError
    from app.core.search.consumer import OpenSearchConsumer
    from app.core.search.index import IndexManager
    from app.core.search.versioning import snapshot_version
    from app.modules.search.service import SearchService
    from tests.factories import create_test_listing

    client = OpenSearchClient(settings)
    assert await client.ping(), "OpenSearch cluster is not reachable"
    prefix = f"auditprobe{uuid.uuid4().hex[:8]}"
    mgr = IndexManager(client, prefix=prefix)
    index_name = await mgr.ensure_index_and_aliases()
    sf = get_session_factory()
    try:
        name = f"Audit Live Probe {uuid.uuid4().hex[:6]}"
        listing = await create_test_listing(
            product_name=name, category_slug="phase3-test", category_name="Phase 3 Test"
        )
        pid = listing["product_id"]
        consumer = OpenSearchConsumer(
            session_factory=sf, search_client=client, index_alias=mgr.write_alias
        )

        def env(event_type: str, version: int) -> EventEnvelope:
            return EventEnvelope(
                event_id=uuid.uuid4(),
                event_type=event_type,
                event_version=1,
                occurred_at=datetime.now(UTC),
                aggregate_type="product",
                aggregate_id=pid,
                aggregate_version=version,
                payload={"product_id": pid},
            )

        async with sf() as s:
            await consumer.handle_event(env("product.updated", 1), s)
        await asyncio.sleep(1.5)
        doc = await client.get_document(mgr.write_alias, pid)
        assert (
            doc
            and doc["_source"]["name"] == name
            and doc["_source"]["is_in_stock"] is True
        )
        v1 = doc["_version"]

        # A stale write (older snapshot) is rejected by the live cluster.
        with pytest.raises(OpenSearchConflictError):
            await client.index_document(
                index=mgr.write_alias,
                doc_id=pid,
                document={"name": "stale"},
                version=v1 - 1,
                version_type="external_gte",
            )
        # A newer event with a LOWER aggregate counter still refreshes (regression fixed in audit).
        async with sf() as s:
            await consumer.handle_event(env("product.updated", 1), s)
        assert (await client.get_document(mgr.write_alias, pid))["_version"] > v1

        await asyncio.sleep(1.5)
        res = await SearchService(
            search_client=client, search_alias=mgr.search_alias
        ).search(None, q=name)
        assert res.engine == "opensearch" and any(
            i.product_id == pid for i in res.items
        )

        async with sf() as s:
            await consumer.handle_event(env("product.deleted", 2), s)
        assert await client.get_document(mgr.write_alias, pid) is None
        assert snapshot_version() > v1
    finally:
        await client.delete_index(index_name)
        assert not await client.index_exists(index_name)
