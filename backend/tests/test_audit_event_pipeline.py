"""End-to-end event pipeline test (audit 2026-11).

domain change -> outbox row (same txn) -> OutboxPublisherWorker -> Kafka
-> OpenSearchConsumer (inbox idempotency) -> search document refreshed.

Kafka and OpenSearch are replaced by the project's in-memory test doubles
(MockKafkaProducer / MockKafkaConsumer / MockOpenSearchClient); PostgreSQL,
the outbox claim/lease SQL and the consumer inbox are real. A live-broker run
is still required before production (see BACKEND_AUDIT.md).
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.events.consumer import MockKafkaConsumer
from app.core.events.kafka import KafkaConnectionError, MockKafkaProducer
from app.core.events.outbox_publisher import OutboxPublisherWorker
from app.core.search.client import MockOpenSearchClient
from app.core.search.consumer import OpenSearchConsumer
from app.modules.catalogue.models import ProductListing, ProductVariant
from app.modules.orders.models import OutboxEvent
from tests.factories import get_test_listing

WRITE_ALIAS = "basket_products_write"


async def _reserve(async_client: AsyncClient) -> uuid.UUID:
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    assert (
        await async_client.post(
            "/api/v1/cart/items", json={"listing_id": str(listing_id), "quantity": 1}
        )
    ).status_code == 200
    quote = await async_client.post("/api/v1/quotes", json={})
    res = await async_client.post(
        "/api/v1/reservations", json={"quote_id": quote.json()["id"]}
    )
    assert res.status_code == 201
    async with get_session_factory()() as session:
        return (
            await session.execute(
                select(ProductVariant.product_id)
                .join(ProductListing, ProductListing.variant_id == ProductVariant.id)
                .where(ProductListing.id == listing_id)
            )
        ).scalar_one()


async def _latest_event_for(product_id: uuid.UUID) -> OutboxEvent:
    async with get_session_factory()() as session:
        return (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.aggregate_type == "product",
                    OutboxEvent.aggregate_id == product_id,
                )
                .order_by(OutboxEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one()


async def _drain_until_published(worker, event_id: uuid.UUID, max_batches: int = 200):
    for _ in range(max_batches):
        async with get_session_factory()() as session:
            row = await session.get(OutboxEvent, event_id)
            if row.status == "PUBLISHED":
                return row
        if await worker.publish_batch(now=datetime.now(UTC)) == 0:
            break
    async with get_session_factory()() as session:
        return await session.get(OutboxEvent, event_id)


@pytest.mark.asyncio
async def test_stock_change_flows_through_outbox_kafka_and_consumer(
    async_client: AsyncClient,
):
    sf = get_session_factory()
    product_id = await _reserve(async_client)
    event = await _latest_event_for(product_id)
    assert event.status == "PENDING"

    # 1. Publisher relays the outbox row to Kafka and marks it PUBLISHED
    producer = MockKafkaProducer()
    await producer.start()
    worker = OutboxPublisherWorker(session_factory=sf, producer=producer)
    row = await _drain_until_published(worker, event.id)
    assert row.status == "PUBLISHED"
    published = [
        env
        for topic, env in producer.published_events
        if topic == "basket.events.catalogue" and env.event_id == event.id
    ]
    assert len(published) == 1
    envelope = published[0]

    # 2. Consumer indexes the product from authoritative PostgreSQL state
    search = MockOpenSearchClient()
    await search.create_index("basket_products_v1")
    await search.update_aliases(
        actions=[{"add": {"index": "basket_products_v1", "alias": WRITE_ALIAS}}]
    )
    kafka_consumer = MockKafkaConsumer()
    await kafka_consumer.start()
    consumer = OpenSearchConsumer(
        session_factory=sf,
        search_client=search,
        index_alias=WRITE_ALIAS,
        producer=producer,
        consumer_impl=kafka_consumer,
        consumer_group=f"audit-test-{uuid.uuid4().hex[:8]}",
    )
    record = kafka_consumer.add_record(
        topic="basket.events.catalogue", value=envelope, partition=0, offset=1
    )
    assert await consumer.process_record(record) is True
    doc = await search.get_document(WRITE_ALIAS, str(product_id))
    assert doc is not None
    first_version = doc["_version"]

    # 3. Duplicate delivery (at-least-once) is absorbed by the consumer inbox
    dup = kafka_consumer.add_record(
        topic="basket.events.catalogue", value=envelope, partition=0, offset=2
    )
    assert await consumer.process_record(dup) is True
    doc_after = await search.get_document(WRITE_ALIAS, str(product_id))
    assert doc_after["_version"] == first_version  # not re-processed


class _BrokerDownProducer(MockKafkaProducer):
    async def send(self, topic, event, *, timeout=None):  # noqa: D401
        raise KafkaConnectionError("broker unavailable")


@pytest.mark.asyncio
async def test_kafka_outage_keeps_events_queued_for_retry(async_client: AsyncClient):
    """Kafka unavailable: the event is not lost; it is rescheduled with backoff."""
    sf = get_session_factory()
    product_id = await _reserve(async_client)
    event = await _latest_event_for(product_id)

    producer = _BrokerDownProducer()
    await producer.start()
    worker = OutboxPublisherWorker(session_factory=sf, producer=producer)
    for _ in range(200):
        async with sf() as session:
            row = await session.get(OutboxEvent, event.id)
        if row.retry_count >= 1:
            break
        if await worker.publish_batch(now=datetime.now(UTC)) == 0:
            # publish_batch returns successes (0 here); stop once our row moved
            async with sf() as session:
                row = await session.get(OutboxEvent, event.id)
            if row.retry_count >= 1:
                break
    async with sf() as session:
        row = await session.get(OutboxEvent, event.id)
    assert row.status == "PENDING"
    assert row.retry_count >= 1
    assert row.next_attempt_at > datetime.now(UTC)
    assert row.last_error and "broker unavailable" in row.last_error
