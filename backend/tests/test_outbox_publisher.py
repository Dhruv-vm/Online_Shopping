from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select, update

from app.core.config import Settings
from app.core.database import get_session_factory
from app.core.events.envelope import EventEnvelope
from app.core.events.kafka import (
    KafkaConnectionError,
    KafkaPublishError,
    MockKafkaProducer,
)
from app.core.events.outbox_publisher import (
    DEFAULT_BATCH_SIZE,
    OutboxPublisherWorker,
    claim_outbox_batch,
    classify_failure,
    compute_next_attempt_at,
    get_topic_for_event,
    resolve_aggregate_version,
    sanitize_error_message,
)
from app.modules.orders.models import OutboxEvent, OutboxStatus

# ------------------------------------------------------------------------------
# SECTION 1: Pure Logic & Helper Unit Tests
# ------------------------------------------------------------------------------


class TestOutboxPublisherHelperFunctions:
    def test_topic_routing_order_events(self):
        assert get_topic_for_event("order.created") == "basket.events.orders"
        assert get_topic_for_event("order.confirmed") == "basket.events.orders"
        assert get_topic_for_event("ORDER.CANCELLED") == "basket.events.orders"

    def test_topic_routing_payment_events(self):
        assert get_topic_for_event("payment.authorized") == "basket.events.payments"
        assert get_topic_for_event("payment.captured") == "basket.events.payments"
        assert get_topic_for_event("payment.refunded") == "basket.events.payments"

    def test_topic_routing_catalogue_events(self):
        assert get_topic_for_event("product.created") == "basket.events.catalogue"
        assert get_topic_for_event("catalogue.updated") == "basket.events.catalogue"
        assert get_topic_for_event("listing.price_changed") == "basket.events.catalogue"
        assert get_topic_for_event("variant.created") == "basket.events.catalogue"

    def test_topic_routing_inventory_events(self):
        assert get_topic_for_event("inventory.reserved") == "basket.events.inventory"
        assert (
            get_topic_for_event("store_inventory.stock_updated")
            == "basket.events.inventory"
        )

    def test_topic_routing_unmapped_event_type_raises(self):
        with pytest.raises(ValueError, match="No canonical Kafka topic mapping"):
            get_topic_for_event("user.registered")

    def test_exponential_backoff_and_jitter_formula(self):
        base_time = datetime(2026, 11, 18, 12, 0, 0, tzinfo=UTC)

        # Retry 0: 2^0 + 0 = 1s
        t0 = compute_next_attempt_at(0, base_time, custom_jitter=0.0)
        assert t0 == base_time + timedelta(seconds=1.0)

        # Retry 1: 2^1 + 0 = 2s
        t1 = compute_next_attempt_at(1, base_time, custom_jitter=0.0)
        assert t1 == base_time + timedelta(seconds=2.0)

        # Retry 3 with jitter 1.5s: 2^3 + 1.5 = 9.5s
        t3 = compute_next_attempt_at(3, base_time, custom_jitter=1.5)
        assert t3 == base_time + timedelta(seconds=9.5)

        # Retry 8: 2^8 = 256s + 1.0 = 257s
        t8 = compute_next_attempt_at(8, base_time, custom_jitter=1.0)
        assert t8 == base_time + timedelta(seconds=257.0)

        # Retry 10: capped at max 300s
        t10 = compute_next_attempt_at(10, base_time, custom_jitter=1.0)
        assert t10 == base_time + timedelta(seconds=300.0)

        # Random jitter is within [0, 2.0]
        for retry in range(5):
            t_rand = compute_next_attempt_at(retry, base_time)
            delay = (t_rand - base_time).total_seconds()
            expected_min = 2**retry
            expected_max = min(300.0, 2**retry + 2.0)
            assert expected_min <= delay <= expected_max

    def test_failure_classification_permanent(self):
        assert classify_failure(ValueError("Invalid format")) is True
        assert classify_failure(KeyError("missing_field")) is True
        assert classify_failure(TypeError("unhashable type")) is True
        assert classify_failure(AttributeError("no attribute")) is True

        try:
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=uuid.uuid4(),
                aggregate_version=1,
                payload={"customer_email": "leak@test.com"},
            )
        except ValidationError as val_err:
            assert classify_failure(val_err) is True

    def test_failure_classification_transient(self):
        assert classify_failure(KafkaPublishError("Broker unreachable")) is False
        assert classify_failure(KafkaConnectionError("Socket disconnected")) is False
        assert classify_failure(TimeoutError("Request timed out")) is False
        assert classify_failure(TimeoutError()) is False
        assert classify_failure(OSError("Network down")) is False

    def test_error_sanitization_redacts_credentials_and_truncates(self):
        sensitive_msg = (
            "Failed with password='SuperSecretPassword123' and token='my_secret_token'"
        )
        sanitized = sanitize_error_message(Exception(sensitive_msg))
        assert "SuperSecretPassword123" not in sanitized
        assert "my_secret_token" not in sanitized
        assert "password=***" in sanitized
        assert "token=***" in sanitized

        long_msg = "X" * 2000
        truncated = sanitize_error_message(Exception(long_msg), max_length=100)
        assert len(truncated) == 100
        assert truncated.endswith("...")

    def test_resolve_aggregate_version_explicit_record(self):
        v = resolve_aggregate_version(
            "order", "order.created", record_version=3, payload={}
        )
        assert v == 3

    def test_resolve_aggregate_version_payload(self):
        v = resolve_aggregate_version(
            "order",
            "order.created",
            record_version=None,
            payload={"aggregate_version": 4},
        )
        assert v == 4

    def test_resolve_aggregate_version_legacy_order_events(self):
        assert (
            resolve_aggregate_version(
                "order", "order.created", record_version=None, payload={}
            )
            == 1
        )
        assert (
            resolve_aggregate_version(
                "order", "order.confirmed", record_version=None, payload={}
            )
            == 2
        )
        assert (
            resolve_aggregate_version(
                "Order", "order.cancelled", record_version=None, payload={}
            )
            == 2
        )

    def test_resolve_aggregate_version_missing_on_non_order_raises(self):
        with pytest.raises(ValueError, match="missing required 'aggregate_version'"):
            resolve_aggregate_version(
                "catalogue", "product.created", record_version=None, payload={}
            )

    def test_resolve_aggregate_version_invalid_values_raise(self):
        with pytest.raises(ValueError, match="Invalid record aggregate_version"):
            resolve_aggregate_version(
                "order", "order.created", record_version=0, payload={}
            )
        with pytest.raises(ValueError, match="Invalid payload 'aggregate_version'"):
            resolve_aggregate_version(
                "order",
                "order.created",
                record_version=None,
                payload={"aggregate_version": -1},
            )
        with pytest.raises(ValueError, match="Invalid payload 'aggregate_version'"):
            resolve_aggregate_version(
                "order",
                "order.created",
                record_version=None,
                payload={"aggregate_version": "v1"},
            )


# ------------------------------------------------------------------------------
# SECTION 2: Database Outbox Claiming & Concurrency Tests
# ------------------------------------------------------------------------------


@pytest.fixture
async def clean_outbox():
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(delete(OutboxEvent))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(delete(OutboxEvent))
        await session.commit()


@pytest.mark.asyncio
class TestOutboxClaimingAndConcurrency:
    async def test_claim_batch_up_to_batch_size(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        async with session_factory() as session:
            for i in range(5):
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type="order",
                        aggregate_id=uuid.uuid4(),
                        event_type="order.created",
                        schema_version=1,
                        payload={"order_number": f"ORD-{i}"},
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=10),
                    )
                )
            await session.commit()

        async with session_factory() as session:
            async with session.begin():
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="worker-1",
                    batch_size=3,
                    lease_seconds=30.0,
                    now=now,
                )
                assert len(claimed) == 3

        async with session_factory() as session:
            # Check DB state
            stmt = select(OutboxEvent).where(OutboxEvent.claimed_by == "worker-1")
            res = await session.execute(stmt)
            claimed_db = list(res.scalars().all())
            assert len(claimed_db) == 3
            for evt in claimed_db:
                assert evt.status == OutboxStatus.PROCESSING.value
                assert evt.claim_expires_at is not None
                assert evt.claim_expires_at > now

    async def test_claim_batch_capped_at_20(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        async with session_factory() as session:
            for i in range(25):
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type="order",
                        aggregate_id=uuid.uuid4(),
                        event_type="order.created",
                        schema_version=1,
                        payload={"idx": i},
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=5),
                    )
                )
            await session.commit()

        async with session_factory() as session:
            async with session.begin():
                # Request 50, but bounded to max 20
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="worker-cap",
                    batch_size=50,
                    lease_seconds=30.0,
                    now=now,
                )
                assert len(claimed) == DEFAULT_BATCH_SIZE

    async def test_concurrent_workers_claim_distinct_batches_no_overlap(
        self, clean_outbox
    ):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        async with session_factory() as session:
            for i in range(10):
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type="order",
                        aggregate_id=uuid.uuid4(),
                        event_type="order.created",
                        schema_version=1,
                        payload={"idx": i},
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=10),
                    )
                )
            await session.commit()

        # Simulate two concurrent worker transactions
        async def run_worker(worker_id: str):
            async with session_factory() as s:
                async with s.begin():
                    return await claim_outbox_batch(
                        session=s,
                        worker_id=worker_id,
                        batch_size=5,
                        lease_seconds=30.0,
                        now=now,
                    )

        w1_items, w2_items = await asyncio.gather(
            run_worker("worker-alpha"),
            run_worker("worker-beta"),
        )

        w1_ids = {item.id for item in w1_items}
        w2_ids = {item.id for item in w2_items}

        assert len(w1_ids) == 5
        assert len(w2_ids) == 5
        # Strict zero intersection guaranteed by SKIP LOCKED
        assert w1_ids.isdisjoint(w2_ids)

    async def test_real_postgresql_skip_locked_concurrent_sessions(self, clean_outbox):
        """
        Explicit PostgreSQL integration test: verifies that SELECT ... FOR UPDATE SKIP LOCKED
        truly executes against real PostgreSQL across two concurrent, overlapping sessions.
        Worker 1 holds locks; Worker 2 queries concurrently, skips locked rows, and claims the rest.
        """
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        event_ids = []
        async with session_factory() as session:
            for i in range(10):
                eid = uuid.uuid4()
                event_ids.append(eid)
                session.add(
                    OutboxEvent(
                        id=eid,
                        aggregate_type="order",
                        aggregate_id=uuid.uuid4(),
                        event_type="order.created",
                        schema_version=1,
                        payload={"idx": i},
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=10),
                    )
                )
            await session.commit()

        lock_acquired_event = asyncio.Event()
        worker2_claimed_event = asyncio.Event()

        w1_claimed = []
        w2_claimed = []

        async def worker1_task():
            async with session_factory() as s1:
                async with s1.begin():
                    # Worker 1 claims 5 items with FOR UPDATE SKIP LOCKED and holds locks
                    claimed = await claim_outbox_batch(
                        session=s1,
                        worker_id="w1-locking",
                        batch_size=5,
                        lease_seconds=30.0,
                        now=now,
                    )
                    w1_claimed.extend(claimed)
                    assert len(w1_claimed) == 5
                    # Signal worker 2 while s1 transaction is still open holding row locks
                    lock_acquired_event.set()
                    # Wait for worker 2 to query concurrently while w1 locks are held
                    await worker2_claimed_event.wait()
                    # S1 transaction commits here

        async def worker2_task():
            # Wait until worker 1 has actively locked the rows in PostgreSQL
            await lock_acquired_event.wait()
            async with session_factory() as s2:
                async with s2.begin():
                    # Worker 2 queries PostgreSQL concurrently with FOR UPDATE SKIP LOCKED
                    claimed = await claim_outbox_batch(
                        session=s2,
                        worker_id="w2-concurrent",
                        batch_size=5,
                        lease_seconds=30.0,
                        now=now,
                    )
                    w2_claimed.extend(claimed)
                    assert len(w2_claimed) == 5
                    # Signal worker 1 that w2 successfully skipped locked rows and claimed 5
                    worker2_claimed_event.set()

        await asyncio.gather(worker1_task(), worker2_task())

        w1_ids = {it.id for it in w1_claimed}
        w2_ids = {it.id for it in w2_claimed}

        assert len(w1_ids) == 5
        assert len(w2_ids) == 5
        # The two sets must have 0 overlap, proving SKIP LOCKED bypassed active locks
        assert w1_ids.isdisjoint(w2_ids)
        assert w1_ids.union(w2_ids) == set(event_ids)

    async def test_active_leases_not_claimed(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        async with session_factory() as session:
            # Event actively leased for next 20 seconds
            session.add(
                OutboxEvent(
                    id=uuid.uuid4(),
                    aggregate_type="order",
                    aggregate_id=uuid.uuid4(),
                    event_type="order.created",
                    schema_version=1,
                    payload={},
                    status=OutboxStatus.PROCESSING.value,
                    claimed_by="other-worker",
                    claim_expires_at=now + timedelta(seconds=20),
                    next_attempt_at=now - timedelta(seconds=10),
                )
            )
            await session.commit()

        async with session_factory() as session:
            async with session.begin():
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="worker-new",
                    batch_size=10,
                    now=now,
                )
                assert len(claimed) == 0

    async def test_future_scheduled_events_not_claimed(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        async with session_factory() as session:
            # Event scheduled for retry in 5 minutes
            session.add(
                OutboxEvent(
                    id=uuid.uuid4(),
                    aggregate_type="order",
                    aggregate_id=uuid.uuid4(),
                    event_type="order.created",
                    schema_version=1,
                    payload={},
                    status=OutboxStatus.PENDING.value,
                    next_attempt_at=now + timedelta(minutes=5),
                )
            )
            await session.commit()

        async with session_factory() as session:
            async with session.begin():
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="worker-new",
                    batch_size=10,
                    now=now,
                )
                assert len(claimed) == 0

    async def test_expired_leases_reclaimed(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        event_id = uuid.uuid4()
        async with session_factory() as session:
            # Event crashed worker left in PROCESSING with expired lease
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=uuid.uuid4(),
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_number": "EXPIRED-1"},
                    status=OutboxStatus.PROCESSING.value,
                    claimed_by="dead-worker",
                    claim_expires_at=now - timedelta(seconds=5),
                    next_attempt_at=now - timedelta(seconds=60),
                )
            )
            await session.commit()

        async with session_factory() as session:
            async with session.begin():
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="revival-worker",
                    batch_size=10,
                    lease_seconds=30.0,
                    now=now,
                )
                assert len(claimed) == 1
                assert claimed[0].id == event_id

        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.claimed_by == "revival-worker"
            assert evt.status == OutboxStatus.PROCESSING.value
            assert evt.claim_expires_at > now

    async def test_empty_outbox_returns_empty_list(self, clean_outbox):
        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="w1",
                    batch_size=10,
                )
                assert claimed == []


# ------------------------------------------------------------------------------
# SECTION 3: Publishing Execution, Delivery, & Acknowledgment Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOutboxPublishingAndKafkaDelivery:
    async def test_successful_publish_batch_updates_database(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        corr_id = f"corr-{uuid.uuid4().hex[:8]}"

        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id), "total_paise": 15000},
                    status=OutboxStatus.PENDING.value,
                    correlation_id=corr_id,
                    next_attempt_at=now - timedelta(seconds=5),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="test-worker-publish",
        )

        published_count = await worker.publish_batch()
        assert published_count == 1

        # Verify Mock Kafka received the event
        assert len(mock_producer.published_events) == 1
        topic, envelope = mock_producer.published_events[0]
        assert topic == "basket.events.orders"
        assert envelope.event_id == event_id
        assert envelope.event_type == "order.created"
        assert envelope.aggregate_id == order_id
        assert envelope.partition_key == str(order_id)
        assert envelope.correlation_id == corr_id
        assert envelope.payload["total_paise"] == 15000

        # Verify PostgreSQL row state
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.PUBLISHED.value
            assert evt.published_at is not None
            assert evt.claim_expires_at is None
            assert evt.last_error is None

        await mock_producer.stop()

    async def test_topic_routing_across_domains(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        order_id = uuid.uuid4()
        prod_id = uuid.uuid4()

        events_data = [
            (
                "order",
                order_id,
                "order.confirmed",
                {"order_id": str(order_id)},
                2,
            ),
            (
                "payment",
                uuid.uuid4(),
                "payment.captured",
                {"order_id": str(order_id), "amount_paise": 5000},
                1,
            ),
            (
                "catalogue",
                prod_id,
                "product.updated",
                {"product_id": str(prod_id)},
                1,
            ),
            (
                "inventory",
                uuid.uuid4(),
                "inventory.reserved",
                {"product_id": str(prod_id), "qty": 2},
                1,
            ),
        ]

        async with session_factory() as session:
            for agg_type, agg_id, etype, payload, agg_v in events_data:
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type=agg_type,
                        aggregate_id=agg_id,
                        aggregate_version=agg_v,
                        event_type=etype,
                        schema_version=1,
                        payload=payload,
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=5),
                    )
                )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="test-router-worker",
        )

        published = await worker.publish_batch()
        assert published == 4

        topics_published = {t for t, _ in mock_producer.published_events}
        assert topics_published == {
            "basket.events.orders",
            "basket.events.payments",
            "basket.events.catalogue",
            "basket.events.inventory",
        }
        await mock_producer.stop()


# ------------------------------------------------------------------------------
# SECTION 4: Crash Recovery & Stale Worker Rejection Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrashRecoveryAndStaleWorker:
    async def test_worker_crash_before_publish_recovered_after_lease_expiry(
        self, clean_outbox
    ):
        """Worker 1 claims event, crashes. After lease expires, Worker 2 recovers it."""
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Simulate Worker 1 claimed the event but crashed; lease expires in the past
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PROCESSING.value,
                    claimed_by="crashed-worker-1",
                    claim_expires_at=now - timedelta(seconds=1),
                    next_attempt_at=now - timedelta(seconds=30),
                )
            )
            await session.commit()

        worker_2 = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="survivor-worker-2",
        )

        published = await worker_2.publish_batch(now=now)
        assert published == 1

        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.PUBLISHED.value
            assert evt.claimed_by == "survivor-worker-2"
            assert evt.published_at is not None

        await mock_producer.stop()

    async def test_worker_crash_after_kafka_ack_republishes_at_least_once(
        self, clean_outbox
    ):
        """
        Worker 1 sends event to Kafka, then crashes before updating DB.
        Lease expires. Worker 2 recovers and re-sends to Kafka (at-least-once).
        """
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Step 1: Worker 1 published to Kafka
        initial_envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=order_id,
            aggregate_version=1,
            payload={"order_id": str(order_id)},
        )
        await mock_producer.send("basket.events.orders", initial_envelope)
        assert len(mock_producer.published_events) == 1

        # But in DB, Worker 1 crashed before marking PUBLISHED, lease expired:
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PROCESSING.value,
                    claimed_by="crashed-worker-1",
                    claim_expires_at=now - timedelta(seconds=5),
                    next_attempt_at=now - timedelta(seconds=30),
                )
            )
            await session.commit()

        # Step 2: Worker 2 recovers and runs publish_batch
        worker_2 = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="worker-2",
        )
        published = await worker_2.publish_batch(now=now)
        assert published == 1

        # Kafka received event twice (at-least-once delivery demonstration)
        assert len(mock_producer.published_events) == 2
        assert mock_producer.published_events[0][1].event_id == event_id
        assert mock_producer.published_events[1][1].event_id == event_id

        # DB now shows PUBLISHED
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.PUBLISHED.value

        await mock_producer.stop()

    async def test_stale_worker_acknowledgement_rejected_via_lease_check(
        self, clean_outbox
    ):
        """
        Worker 1 claims event. Lease expires.
        Worker 2 claims event.
        Worker 1 wakes up and attempts acknowledgement update: rowcount == 0,
        update rejected, worker 2's lease and ownership remain intact.
        """
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Insert event claimed by worker 1 with expired lease
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PROCESSING.value,
                    claimed_by="stale-worker-1",
                    claim_expires_at=now - timedelta(seconds=10),
                    next_attempt_at=now - timedelta(seconds=60),
                )
            )
            await session.commit()

        # Worker 2 claims the event
        async with session_factory() as session:
            async with session.begin():
                w2_claimed = await claim_outbox_batch(
                    session=session,
                    worker_id="active-worker-2",
                    batch_size=10,
                    lease_seconds=30.0,
                    now=now,
                )
                assert len(w2_claimed) == 1
                assert w2_claimed[0].id == event_id

        # Worker 1 now attempts stale update:
        async with session_factory() as session:
            async with session.begin():
                stale_stmt = (
                    update(OutboxEvent)
                    .where(
                        OutboxEvent.id == event_id,
                        OutboxEvent.claimed_by == "stale-worker-1",
                    )
                    .values(
                        status=OutboxStatus.PUBLISHED.value,
                        published_at=datetime.now(UTC),
                    )
                )
                res = await session.execute(stale_stmt)
                # rowcount must be 0 because claimed_by is now 'active-worker-2'
                assert res.rowcount == 0

        # Verify DB still reflects active-worker-2's lease
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.claimed_by == "active-worker-2"
            assert evt.status == OutboxStatus.PROCESSING.value

        await mock_producer.stop()


# ------------------------------------------------------------------------------
# SECTION 5: Retry & Failure Classification Tests
# ------------------------------------------------------------------------------


class TransientFailingProducer(MockKafkaProducer):
    async def send(
        self, topic: str, event: EventEnvelope, *, timeout: float | None = None
    ) -> None:
        raise KafkaPublishError("Broker network partition")


@pytest.mark.asyncio
class TestRetryAndFailureHandling:
    async def test_transient_error_schedules_retry_with_backoff(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        failing_producer = TransientFailingProducer()
        await failing_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PENDING.value,
                    retry_count=0,
                    next_attempt_at=now - timedelta(seconds=5),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=failing_producer,
            worker_id="test-retry-worker",
            custom_jitter=0.0,
        )

        published = await worker.publish_batch(now=now)
        assert published == 0

        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            # Must remain PENDING for next retry
            assert evt.status == OutboxStatus.PENDING.value
            assert evt.retry_count == 1
            assert evt.claim_expires_at is None
            # Next attempt scheduled 2^1 = 2 seconds after failure
            assert evt.next_attempt_at > now
            assert "KafkaPublishError" in evt.last_error

        await failing_producer.stop()

    async def test_permanent_error_marks_failed_immediately(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Payload contains forbidden PII field "customer_email"
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={
                        "order_id": str(order_id),
                        "customer_email": "violation@test.com",
                    },
                    status=OutboxStatus.PENDING.value,
                    retry_count=0,
                    next_attempt_at=now - timedelta(seconds=5),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="test-pii-worker",
        )

        published = await worker.publish_batch(now=now)
        assert published == 0

        # Never sent to Kafka
        assert len(mock_producer.published_events) == 0

        # DB row transitions directly to FAILED, not scheduled for retry
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.FAILED.value
            assert evt.claim_expires_at is None
            assert (
                "customer_email" in evt.last_error
                or "strictly prohibited" in evt.last_error
            )

        await mock_producer.stop()

    async def test_retry_exhaustion_marks_failed(self, clean_outbox):
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        failing_producer = TransientFailingProducer()
        await failing_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Event already at retry_count = 4 (MAX_RETRIES - 1 with 5 attempts)
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PENDING.value,
                    retry_count=4,
                    next_attempt_at=now - timedelta(seconds=5),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=failing_producer,
            worker_id="test-exhaustion-worker",
            max_retries=5,
        )

        published = await worker.publish_batch(now=now)
        assert published == 0

        # After 5th failure, transitions to FAILED
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.FAILED.value
            assert evt.retry_count == 5
            assert evt.claim_expires_at is None

        await failing_producer.stop()

    async def test_exact_terminal_transition_at_5_attempts(self, clean_outbox):
        """
        Verify the exact authoritative retry threshold (5 attempts):
        Attempts 1..4: remain PENDING with next_attempt_at scheduled in the future.
        Attempt 5: transitions permanently to FAILED.
        """
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        failing_producer = TransientFailingProducer()
        await failing_producer.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PENDING.value,
                    retry_count=0,
                    next_attempt_at=now - timedelta(seconds=1),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=failing_producer,
            worker_id="test-5-attempt-worker",
            custom_jitter=0.0,
            max_retries=5,
        )

        simulated_now = now
        # Run attempts 1 to 4: must stay PENDING
        for expected_retry in range(1, 5):
            published = await worker.publish_batch(now=simulated_now)
            assert published == 0

            async with session_factory() as session:
                res = await session.execute(
                    select(OutboxEvent).where(OutboxEvent.id == event_id)
                )
                evt = res.scalar_one()
                assert evt.status == OutboxStatus.PENDING.value, (
                    f"Failed at attempt {expected_retry}"
                )
                assert evt.retry_count == expected_retry
                assert evt.claim_expires_at is None
                assert evt.next_attempt_at > simulated_now
                # Fast forward simulated_now past next_attempt_at for next iteration
                simulated_now = evt.next_attempt_at + timedelta(seconds=1)

        # 5th attempt: must reach threshold and transition to FAILED
        published = await worker.publish_batch(now=simulated_now)
        assert published == 0

        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(OutboxEvent.id == event_id)
            )
            evt = res.scalar_one()
            assert evt.status == OutboxStatus.FAILED.value
            assert evt.retry_count == 5
            assert evt.claim_expires_at is None
            assert "KafkaPublishError" in evt.last_error

        await failing_producer.stop()

    async def test_retries_preserve_event_id_and_aggregate_version(self, clean_outbox):
        """
        Verify that retries preserve the exact same event_id, event_version,
        aggregate_version, and partition_key across retry attempts.
        """
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        published_envelopes: list[EventEnvelope] = []

        class FlakyProducer(MockKafkaProducer):
            def __init__(self):
                super().__init__()
                self.calls = 0

            async def send(
                self, topic: str, event: EventEnvelope, *, timeout: float | None = None
            ) -> None:
                self.calls += 1
                published_envelopes.append(event)
                if self.calls == 1:
                    raise KafkaPublishError("Temporary broker blip")
                await super().send(topic, event, timeout=timeout)

        flaky = FlakyProducer()
        await flaky.start()

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=event_id,
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.confirmed",
                    schema_version=1,
                    aggregate_version=2,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PENDING.value,
                    retry_count=0,
                    next_attempt_at=now - timedelta(seconds=5),
                )
            )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=flaky,
            worker_id="test-version-preservation",
            custom_jitter=0.0,
        )

        # Attempt 1 fails
        await worker.publish_batch(now=now)
        assert len(published_envelopes) == 1
        env1 = published_envelopes[0]
        assert env1.event_id == event_id
        assert env1.aggregate_version == 2

        # Fast forward time past retry delay
        future_now = now + timedelta(seconds=10)
        # Attempt 2 succeeds
        pub2 = await worker.publish_batch(now=future_now)
        assert pub2 == 1
        assert len(published_envelopes) == 2
        env2 = published_envelopes[1]

        # Invariant: event_id, event_version, aggregate_version, partition_key remain identical!
        assert env2.event_id == env1.event_id == event_id
        assert env2.event_version == env1.event_version == 1
        assert env2.aggregate_version == env1.aggregate_version == 2
        assert env2.partition_key == env1.partition_key == str(order_id)
        assert env2.occurred_at == env1.occurred_at

        await flaky.stop()


# ------------------------------------------------------------------------------
# SECTION 6: Worker Lifecycle & Production Safety Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkerLifecycleAndProductionSafety:
    async def test_worker_start_and_stop_lifecycle(self, clean_outbox):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="test-lifecycle",
            poll_interval_seconds=0.05,
        )

        assert not worker.is_running
        await worker.start()
        assert worker.is_running
        assert mock_producer.is_connected

        # Insert an event while running
        order_id = uuid.uuid4()
        async with session_factory() as session:
            session.add(
                OutboxEvent(
                    id=uuid.uuid4(),
                    aggregate_type="order",
                    aggregate_id=order_id,
                    event_type="order.created",
                    schema_version=1,
                    payload={"order_id": str(order_id)},
                    status=OutboxStatus.PENDING.value,
                    next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
            await session.commit()

        # Wait briefly for worker polling loop to pick it up
        await asyncio.sleep(0.2)

        assert len(mock_producer.published_events) == 1

        await worker.stop()
        assert not worker.is_running
        assert not mock_producer.is_connected

    async def test_production_safety_check_rejects_mock_producer(self):
        session_factory = get_session_factory()
        prod_settings = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_testvalid123",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
            KAFKA_SECURITY_PROTOCOL="SSL",
            KAFKA_PRODUCER_ACKS="all",
        )
        mock_producer = MockKafkaProducer()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            config_settings=prod_settings,
        )

        with pytest.raises(
            RuntimeError,
            match="MockKafkaProducer is strictly forbidden in production",
        ):
            await worker.start()

    async def test_batch_window_deadline_relinquishes_remaining_events(
        self, clean_outbox
    ):
        session_factory = get_session_factory()
        now = datetime.now(UTC)

        # Producer that sleeps 0.05s on each send
        class SlowProducer(MockKafkaProducer):
            async def send(
                self, topic: str, event: EventEnvelope, *, timeout: float | None = None
            ) -> None:
                await asyncio.sleep(0.05)
                await super().send(topic, event, timeout=timeout)

        slow_producer = SlowProducer()
        await slow_producer.start()

        order_id = uuid.uuid4()
        async with session_factory() as session:
            for i in range(5):
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type="order",
                        aggregate_id=order_id,
                        event_type="order.created",
                        schema_version=1,
                        payload={"order_id": str(order_id), "idx": i},
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=5),
                    )
                )
            await session.commit()

        # Configure tiny batch window of 0.08s (enough for ~1-2 events, then breaks)
        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=slow_producer,
            worker_id="test-window-worker",
            batch_size=5,
            max_batch_window_seconds=0.08,
        )

        published = await worker.publish_batch(now=now)
        # Should publish fewer than 5 because window expires
        assert 1 <= published < 5
        assert len(slow_producer.published_events) == published

        # Verify remaining events were safely relinquished back to PENDING
        async with session_factory() as session:
            res = await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.status == OutboxStatus.PENDING.value
                )
            )
            relinquished = res.scalars().all()
            assert len(relinquished) == (5 - published)
            for evt in relinquished:
                assert evt.claim_expires_at is None
                assert evt.claimed_by == "test-window-worker"

        await slow_producer.stop()

    async def test_duplicate_publication_and_out_of_order_delivery_simulation(
        self, clean_outbox
    ):
        """Proves out-of-order arrival and duplicate publishing safety under OpenSearch external_gte versioning."""
        session_factory = get_session_factory()
        now = datetime.now(UTC)
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        order_id = uuid.uuid4()

        # Insert 3 events with strictly monotonic aggregate versions: 1, 2, 3
        events_spec = [
            ("order.created", 1, {"status": "PENDING_PAYMENT"}),
            ("order.confirmed", 2, {"status": "CONFIRMED"}),
            ("order.cancelled", 3, {"status": "CANCELLED"}),
        ]

        async with session_factory() as session:
            for etype, v, payload_extra in events_spec:
                payload = {
                    "order_id": str(order_id),
                    "aggregate_version": v,
                    **payload_extra,
                }
                session.add(
                    OutboxEvent(
                        id=uuid.uuid4(),
                        aggregate_type="order",
                        aggregate_id=order_id,
                        aggregate_version=v,
                        event_type=etype,
                        schema_version=1,
                        payload=payload,
                        status=OutboxStatus.PENDING.value,
                        next_attempt_at=now - timedelta(seconds=10),
                    )
                )
            await session.commit()

        worker = OutboxPublisherWorker(
            session_factory=session_factory,
            producer=mock_producer,
            worker_id="test-ordering-worker",
            batch_size=10,
        )

        published = await worker.publish_batch(now=now)
        assert published == 3
        assert len(mock_producer.published_events) == 3

        # Simulated downstream consumer maintaining an OpenSearch external_gte index
        opensearch_index: dict[str, dict[str, Any]] = {}

        def apply_to_opensearch(envelope: EventEnvelope) -> str:
            doc_id = str(envelope.aggregate_id)
            existing = opensearch_index.get(doc_id)
            if existing is None:
                opensearch_index[doc_id] = {
                    "version": envelope.aggregate_version,
                    "status": envelope.payload.get("status"),
                }
                return "CREATED"

            current_ver = existing["version"]
            # Under OpenSearch external_gte:
            # - Strictly greater version (> current_ver): updates document and version
            # - Equal version (== current_ver): accepts idempotent update without increment
            # - Strictly lesser version (< current_ver): rejects with version_conflict_engine_exception
            if envelope.aggregate_version > current_ver:
                opensearch_index[doc_id] = {
                    "version": envelope.aggregate_version,
                    "status": envelope.payload.get("status"),
                }
                return "UPDATED"
            elif envelope.aggregate_version == current_ver:
                return "IDEMPOTENT_EQUAL_VERSION"
            else:
                return "VERSION_CONFLICT_REJECTED"

        envelopes_by_version = {
            env.aggregate_version: env for _, env in mock_producer.published_events
        }

        # 1. Out-of-order delivery: Version 2 arrives first
        res_v2 = apply_to_opensearch(envelopes_by_version[2])
        assert res_v2 == "CREATED"
        assert opensearch_index[str(order_id)]["version"] == 2
        assert opensearch_index[str(order_id)]["status"] == "CONFIRMED"

        # 2. Late delivery: Version 1 arrives second (older than version 2)
        res_v1 = apply_to_opensearch(envelopes_by_version[1])
        assert res_v1 == "VERSION_CONFLICT_REJECTED"
        # State is safely protected from regression: stays CONFIRMED at version 2
        assert opensearch_index[str(order_id)]["version"] == 2
        assert opensearch_index[str(order_id)]["status"] == "CONFIRMED"

        # 3. Version 3 arrives
        res_v3 = apply_to_opensearch(envelopes_by_version[3])
        assert res_v3 == "UPDATED"
        assert opensearch_index[str(order_id)]["version"] == 3
        assert opensearch_index[str(order_id)]["status"] == "CANCELLED"

        # 4. Duplicate delivery of Version 2 (republished / retry replay)
        res_dup_v2 = apply_to_opensearch(envelopes_by_version[2])
        assert res_dup_v2 == "VERSION_CONFLICT_REJECTED"
        assert opensearch_index[str(order_id)]["version"] == 3

        # 5. Duplicate delivery of Version 3 (republished / retry replay)
        res_dup_v3 = apply_to_opensearch(envelopes_by_version[3])
        assert res_dup_v3 == "IDEMPOTENT_EQUAL_VERSION"
        assert opensearch_index[str(order_id)]["version"] == 3
        assert opensearch_index[str(order_id)]["status"] == "CANCELLED"

        await mock_producer.stop()
