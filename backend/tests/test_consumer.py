from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import get_session_factory
from app.core.events.consumer import (
    BaseKafkaConsumer,
    DeadLetterPublishError,
    MockKafkaConsumer,
    TopicPartition,
    get_kafka_consumer,
)
from app.core.events.envelope import EventEnvelope
from app.core.events.inbox import (
    ConsumerInbox,
    InboxStatus,
    OrderSummaryProjection,
    get_inbox_record,
)
from app.core.events.kafka import EventProducer, MockKafkaProducer
from app.core.events.outbox_publisher import (
    compute_next_attempt_at,
    sanitize_error_message,
)
from app.modules.orders.consumer import (
    OrderProjectionConsumer,
)

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------


@pytest.fixture
async def clean_inbox_and_projections():
    """Ensure consumer_inbox and order_summary_projections are clean before and after tests."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(delete(ConsumerInbox))
        await session.execute(delete(OrderSummaryProjection))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(delete(ConsumerInbox))
        await session.execute(delete(OrderSummaryProjection))
        await session.commit()


# ------------------------------------------------------------------------------
# SECTION 1: Pure Logic & Production Safety Unit Tests
# ------------------------------------------------------------------------------


class TestConsumerPureLogicAndSafety:
    def test_backoff_formula_compliance(self):
        base_time = datetime(2026, 11, 18, 12, 0, 0, tzinfo=UTC)

        # Retry 0: 2^0 + 0 = 1s
        t0 = compute_next_attempt_at(0, base_time, custom_jitter=0.0)
        assert t0 == base_time + timedelta(seconds=1.0)

        # Retry 1: 2^1 + 0 = 2s
        t1 = compute_next_attempt_at(1, base_time, custom_jitter=0.0)
        assert t1 == base_time + timedelta(seconds=2.0)

        # Retry 4: 2^4 + 1.2 = 17.2s
        t4 = compute_next_attempt_at(4, base_time, custom_jitter=1.2)
        assert t4 == base_time + timedelta(seconds=17.2)

        # Max cap: 300s
        t10 = compute_next_attempt_at(10, base_time, custom_jitter=1.0)
        assert t10 == base_time + timedelta(seconds=300.0)

    def test_error_sanitization_removes_secrets(self):
        err = Exception(
            "Connection failed with auth token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def and password='super_secret_password_123'"
        )
        sanitized = sanitize_error_message(err)
        assert "Bearer ***" in sanitized
        assert "password=***" in sanitized
        assert "super_secret_password_123" not in sanitized

    def test_error_sanitization_razorpay_keys(self):
        err = Exception(
            "Payment failed for rzp_live_abcdef123456 and secret='testsecret'"
        )
        sanitized = sanitize_error_message(err)
        assert "rzp_live_***" in sanitized
        assert "secret=***" in sanitized
        assert "abcdef123456" not in sanitized

    def test_production_safety_check_rejects_mock_consumer(self):
        prod_settings = Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod.internal:5432/basket_db",
            SECRET_KEY=SecretStr(
                "prod-secret-key-min-32-chars-long-unpredictable-value-12345"
            ),
            INTERNAL_SERVICE_KEY=SecretStr(
                "prod-internal-key-min-32-chars-long-unpredictable-value-123"
            ),
            RAZORPAY_KEY_ID="rzp_live_production_key_12345",
            RAZORPAY_KEY_SECRET=SecretStr(
                "production_razorpay_key_secret_min_16_chars"
            ),
            RAZORPAY_WEBHOOK_SECRET=SecretStr("production_razorpay_webhook_secret_16"),
            KAFKA_BOOTSTRAP_SERVERS="kafka.prod.internal:9092",
            KAFKA_SECURITY_PROTOCOL="SSL",
            KAFKA_PRODUCER_ACKS="all",
        )
        assert prod_settings.is_production is True

        with pytest.raises(
            RuntimeError,
            match="MockKafkaConsumer is strictly forbidden in production",
        ):
            MockKafkaConsumer(prod_settings)

    def test_get_kafka_consumer_factory_rejects_mock_in_production(self):
        prod_settings = Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod.internal:5432/basket_db",
            SECRET_KEY=SecretStr(
                "prod-secret-key-min-32-chars-long-unpredictable-value-12345"
            ),
            INTERNAL_SERVICE_KEY=SecretStr(
                "prod-internal-key-min-32-chars-long-unpredictable-value-123"
            ),
            RAZORPAY_KEY_ID="rzp_live_production_key_12345",
            RAZORPAY_KEY_SECRET=SecretStr(
                "production_razorpay_key_secret_min_16_chars"
            ),
            RAZORPAY_WEBHOOK_SECRET=SecretStr("production_razorpay_webhook_secret_16"),
            KAFKA_BOOTSTRAP_SERVERS="kafka.prod.internal:9092",
            KAFKA_SECURITY_PROTOCOL="SSL",
            KAFKA_PRODUCER_ACKS="all",
        )
        with pytest.raises(
            RuntimeError,
            match="MockKafkaConsumer is strictly forbidden in production",
        ):
            get_kafka_consumer(
                "test-group",
                ["basket.events.orders"],
                prod_settings,
                force_mock=True,
            )

    def test_get_kafka_consumer_factory_passes_sasl_auth_kwargs(self):
        from unittest.mock import patch

        sasl_settings = Settings(
            ENVIRONMENT="development",
            KAFKA_BOOTSTRAP_SERVERS="kafka.example.com:9092",
            KAFKA_SECURITY_PROTOCOL="SASL_SSL",
            KAFKA_SASL_MECHANISM="SCRAM-SHA-256",
            KAFKA_SASL_USERNAME="avnadmin",
            KAFKA_SASL_PASSWORD="test_password_123",
            KAFKA_SSL_CA_LOCATION="infra/aiven/certs/ca.pem",
        )

        with patch("app.core.events.consumer.AIOKafkaConsumer") as mock_aiokafka:
            get_kafka_consumer(
                "test-group",
                ["basket.events.orders"],
                sasl_settings,
            )
            assert mock_aiokafka.called
            call_kwargs = mock_aiokafka.call_args[1]
            assert call_kwargs["security_protocol"] == "SASL_SSL"
            assert call_kwargs["sasl_mechanism"] == "SCRAM-SHA-256"
            assert call_kwargs["sasl_plain_username"] == "avnadmin"
            assert call_kwargs["sasl_plain_password"] == "test_password_123"
            assert "ssl_context" in call_kwargs
            assert call_kwargs["ssl_context"] is not None

    async def test_base_consumer_start_passes_sasl_auth_kwargs(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        sasl_settings = Settings(
            ENVIRONMENT="development",
            KAFKA_BOOTSTRAP_SERVERS="kafka.example.com:9092",
            KAFKA_SECURITY_PROTOCOL="SASL_SSL",
            KAFKA_SASL_MECHANISM="SCRAM-SHA-256",
            KAFKA_SASL_USERNAME="avnadmin",
            KAFKA_SASL_PASSWORD="test_password_123",
            KAFKA_SSL_CA_LOCATION="infra/aiven/certs/ca.pem",
        )

        mock_producer = AsyncMock(spec=EventProducer)
        mock_producer.is_connected = True

        consumer = OrderProjectionConsumer(
            session_factory=AsyncMock(),
            producer=mock_producer,
            config_settings=sasl_settings,
            consumer_impl=None,
        )

        mock_aiokafka_instance = AsyncMock()
        mock_aiokafka_instance.start = AsyncMock()
        mock_aiokafka_instance.subscribe = MagicMock()

        with patch(
            "app.core.events.consumer.AIOKafkaConsumer",
            return_value=mock_aiokafka_instance,
        ) as mock_aiokafka_cls:
            await consumer.start()
            assert mock_aiokafka_cls.called
            call_kwargs = mock_aiokafka_cls.call_args[1]
            assert call_kwargs["security_protocol"] == "SASL_SSL"
            assert call_kwargs["sasl_mechanism"] == "SCRAM-SHA-256"
            assert call_kwargs["sasl_plain_username"] == "avnadmin"
            assert call_kwargs["sasl_plain_password"] == "test_password_123"
            assert "ssl_context" in call_kwargs
            assert call_kwargs["ssl_context"] is not None
            await consumer.stop()


# ------------------------------------------------------------------------------
# SECTION 2: Strategy A ACID Atomicity & Deduplication Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStrategyAAtomicityAndDeduplication:
    async def test_fresh_event_atomic_processing_success(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-20261118-001",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 150000,
                "currency": "INR",
                "item_count": 2,
            },
        )

        record = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=10,
        )

        success = await consumer.process_record(record)
        assert success is True

        # Verify Kafka offset committed strictly after DB commit
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 11

        # Verify DB state: inbox has SUCCEEDED
        async with session_factory() as session:
            inbox_row = await get_inbox_record(
                session, consumer.consumer_group, envelope.event_id
            )
            assert inbox_row is not None
            assert inbox_row.status == InboxStatus.SUCCEEDED.value
            assert inbox_row.processed_at is not None

            # Verify domain projection created
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await session.execute(stmt)
            projection = res.scalar_one_or_none()
            assert projection is not None
            assert projection.order_number == "ORD-20261118-001"
            assert projection.status == "PENDING_PAYMENT"
            assert projection.total_payable_paise == 150000
            assert projection.last_aggregate_version == 1

    async def test_duplicate_event_skips_business_mutation_and_commits_offset(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-20261118-002",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 200000,
                "currency": "INR",
            },
        )

        rec1 = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=20,
        )

        # First delivery: normal processing
        assert await consumer.process_record(rec1) is True
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 21

        # Simulate redelivery with different offset or same offset
        rec2 = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=21,
        )

        # Manually alter projection in DB to verify second delivery does not touch it
        async with session_factory() as session:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await session.execute(stmt)
            proj = res.scalar_one()
            proj.status = "CUSTOM_TOUCHED_STATUS"
            await session.commit()

        # Second delivery: should be detected as duplicate, business logic skipped
        assert await consumer.process_record(rec2) is True
        assert await mock_consumer.committed(tp) == 22

        # Verify DB projection was NOT overwritten back to PENDING_PAYMENT
        async with session_factory() as session:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await session.execute(stmt)
            proj = res.scalar_one()
            assert proj.status == "CUSTOM_TOUCHED_STATUS"

    async def test_crash_recovery_after_db_commit_before_offset_commit(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()
        event_id = uuid.uuid4()

        # Simulate that earlier worker run succeeded in DB (committed both inbox and domain projection)
        # but crashed before calling commit_offset()
        async with session_factory() as session:
            session.add(
                ConsumerInbox(
                    consumer_group=consumer.consumer_group,
                    event_id=event_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    aggregate_version=1,
                    status=InboxStatus.SUCCEEDED.value,
                    processed_at=datetime.now(UTC),
                )
            )
            session.add(
                OrderSummaryProjection(
                    order_id=order_id,
                    order_number="ORD-CRASH-001",
                    status="PENDING_PAYMENT",
                    total_payable_paise=100000,
                    last_event_type="order.created",
                    last_aggregate_version=1,
                )
            )
            await session.commit()

        # Redelivered record upon restart
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-CRASH-001",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 100000,
            },
        )
        record = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=50,
        )

        # Worker processes re-delivered record
        assert await consumer.process_record(record) is True

        # Offset must be committed now
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 51

    async def test_business_error_rolls_back_domain_effects(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        class FaultyConsumer(BaseKafkaConsumer):
            async def handle_event(
                self, event: EventEnvelope, session: AsyncSession
            ) -> None:
                # Add domain record then crash
                session.add(
                    OrderSummaryProjection(
                        order_id=event.aggregate_id,
                        order_number="ORD-FAULTY-001",
                        status="FAULTY_TEMP",
                        total_payable_paise=10000,
                        last_event_type=event.event_type,
                        last_aggregate_version=1,
                    )
                )
                raise ConnectionResetError("Transient network drop during DB call")

        consumer = FaultyConsumer(
            consumer_group="test-faulty-group",
            topics=["basket.events.orders"],
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )

        record = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=60,
        )

        # Must return False for transient failure
        success = await consumer.process_record(record)
        assert success is False

        # Kafka offset NOT committed
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) is None

        # Verify domain mutation rolled back!
        async with session_factory() as session:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await session.execute(stmt)
            assert res.scalar_one_or_none() is None

            # Verify inbox recorded FAILED status
            inbox_row = await get_inbox_record(
                session, consumer.consumer_group, envelope.event_id
            )
            assert inbox_row is not None
            assert inbox_row.status == InboxStatus.FAILED.value


# ------------------------------------------------------------------------------
# SECTION 3: Ordering & Monotonic Aggregate Versioning Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrderingAndMonotonicAggregateVersions:
    async def test_monotonic_version_transitions(self, clean_inbox_and_projections):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Step 1: order.created (v1)
        e1 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-SEQ-001",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 50000,
            },
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e1)
            )
            is True
        )

        # Step 2: order.confirmed (v2)
        e2 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e2)
            )
            is True
        )

        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.status == "CONFIRMED"
            assert proj.payment_status == "SUCCEEDED"
            assert proj.last_aggregate_version == 2

    async def test_stale_older_version_rejected_without_regression(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Confirm order first at v2 (e.g. out of order arrival)
        e2 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id), "order_number": "ORD-STALE-01"},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e2)
            )
            is True
        )

        # Now late order.created arrives with v1
        e1 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_id": str(order_id), "status": "PENDING_PAYMENT"},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e1)
            )
            is True
        )

        # Must remain CONFIRMED, must NOT regress to PENDING_PAYMENT
        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.status == "CONFIRMED"
            assert proj.last_aggregate_version == 2

    async def test_terminal_state_protection_cancelled_cannot_be_confirmed(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Step 1: Order cancelled at v2
        e_cancel = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.cancelled",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e_cancel)
            )
            is True
        )

        # Step 2: Attempt to confirm cancelled order with v3
        e_confirm = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=3,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e_confirm)
            )
            is True
        )

        # Must still be CANCELLED
        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.status == "CANCELLED"

    async def test_cross_topic_ordering_payment_before_order(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Payment event arrives first on basket.events.payments
        e_pay = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="payment.succeeded",
            event_version=1,
            aggregate_type="Payment",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"amount_paise": 75000, "order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.payments", e_pay)
            )
            is True
        )

        # Verify provisional projection exists with SUCCEEDED payment status
        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.payment_status == "SUCCEEDED"

        # Now order.created arrives on basket.events.orders with v2
        e_ord = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-X-TOPIC-01",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 75000,
            },
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e_ord)
            )
            is True
        )

        # Projection merges seamlessly, retaining payment_status = SUCCEEDED
        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.payment_status == "SUCCEEDED"
            assert proj.last_aggregate_version == 2


# ------------------------------------------------------------------------------
# SECTION 4: Retries, DLQ Routing & Poison Messages
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRetriesAndDeadLetterQueue:
    async def test_poison_message_unparseable_json_routed_to_dlq(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        poison_bytes = b"NOT_A_VALID_JSON{:::broken"
        rec = mock_consumer.add_record(
            topic="basket.events.orders",
            value=poison_bytes,
            partition=0,
            offset=100,
        )

        # Poison messages return True because offset must be committed after DLQ
        assert await consumer.process_record(rec) is True

        # DLQ producer recorded the dead-letter event
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 1
        dlq_evt = dlq_events[0]
        assert dlq_evt.event_type == "dead_letter.failed"
        assert dlq_evt.payload["original_topic"] == "basket.events.orders"
        assert dlq_evt.payload["original_offset"] == 100

        # Offset was committed strictly after DLQ send
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 101

    async def test_retry_exhaustion_routes_to_dlq_after_5_attempts(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        class AlwaysFailingConsumer(BaseKafkaConsumer):
            async def handle_event(
                self, event: EventEnvelope, session: AsyncSession
            ) -> None:
                raise TimeoutError("Simulated remote dependency timeout")

        consumer = AlwaysFailingConsumer(
            consumer_group="test-dlq-exhaustion",
            topics=["basket.events.orders"],
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            max_retries=5,
            backoff_base_seconds=0.0,
            backoff_max_jitter_seconds=0.0,
        )

        order_id = uuid.uuid4()
        event_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )

        # Attempts 1 through 4: transient failures, offset NOT committed
        for _attempt in range(1, 5):
            rec = mock_consumer.add_record(
                topic="basket.events.orders",
                value=envelope,
                partition=0,
                offset=200,
            )
            success = await consumer.process_record(rec)
            assert success is False
            tp = TopicPartition("basket.events.orders", 0)
            assert await mock_consumer.committed(tp) is None

        # Attempt 5: Retries exhausted -> routes to DLQ and commits offset
        rec5 = mock_consumer.add_record(
            topic="basket.events.orders",
            value=envelope,
            partition=0,
            offset=200,
        )
        success5 = await consumer.process_record(rec5)
        assert success5 is True

        # DLQ producer recorded event
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 1
        assert dlq_events[0].payload["failed_event_id"] == str(event_id)

        # Offset is committed now
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 201

        # Inbox has DEAD_LETTER status
        async with session_factory() as session:
            inbox_row = await get_inbox_record(
                session, consumer.consumer_group, event_id
            )
            assert inbox_row is not None
            assert inbox_row.status == InboxStatus.DEAD_LETTER.value

    async def test_dlq_broker_failure_prevents_offset_commit(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()

        class FailingDLQProducer(MockKafkaProducer):
            async def send(
                self, topic: str, event: EventEnvelope, *, timeout: float | None = None
            ) -> None:
                raise ConnectionError("DLQ broker unreachable")

        failing_producer = FailingDLQProducer()
        await failing_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=failing_producer,
            consumer_impl=mock_consumer,
        )

        poison_bytes = b"BROKEN_BYTES_NO_JSON"
        rec = mock_consumer.add_record(
            topic="basket.events.orders",
            value=poison_bytes,
            partition=0,
            offset=300,
        )

        # When DLQ publishing fails, DeadLetterPublishError is raised and offset is NOT committed!
        with pytest.raises(DeadLetterPublishError):
            await consumer.process_record(rec)

        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) is None


# ------------------------------------------------------------------------------
# SECTION 5: Lifecycle & Batch Polling Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLifecycleAndBatchPolling:
    async def test_consumer_lifecycle_start_and_stop(self, clean_inbox_and_projections):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        mock_consumer = MockKafkaConsumer()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        assert consumer.is_running is False
        await consumer.start()
        assert consumer.is_running is True
        assert mock_producer.is_connected is True
        assert mock_consumer.is_running is True

        await consumer.stop()
        assert consumer.is_running is False

    async def test_batch_polling_processes_multiple_records(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )
        await consumer.start()

        # Add 3 records
        for i in range(3):
            order_id = uuid.uuid4()
            env = EventEnvelope(
                event_id=uuid.uuid4(),
                event_type="order.created",
                event_version=1,
                aggregate_type="Order",
                aggregate_id=order_id,
                aggregate_version=1,
                partition_key=str(order_id),
                payload={"order_id": str(order_id), "order_number": f"ORD-B-{i}"},
            )
            mock_consumer.add_record("basket.events.orders", env)

        processed = await consumer.poll_and_process_batch(max_records=10)
        assert processed == 3

        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 3


# ------------------------------------------------------------------------------
# SECTION 6: Multi-Worker Concurrent Processing & Race Condition Protection
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConcurrentProcessingAndRaces:
    async def test_concurrent_duplicate_delivery_race_executes_business_mutation_once(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer_1 = MockKafkaConsumer()
        await mock_consumer_1.start()

        mock_consumer_2 = MockKafkaConsumer()
        await mock_consumer_2.start()

        consumer_1 = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer_1,
        )
        consumer_2 = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer_2,
        )

        order_id = uuid.uuid4()
        event_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-RACE-001",
                "total_payable_paise": 120000,
            },
        )

        rec1 = mock_consumer_1.add_record("basket.events.orders", envelope, offset=1)
        rec2 = mock_consumer_2.add_record("basket.events.orders", envelope, offset=2)

        # Run both consumers concurrently on the exact same event
        results = await asyncio.gather(
            consumer_1.process_record(rec1),
            consumer_2.process_record(rec2),
        )

        # Both workers return True (one succeeded with mutation, one cleanly deduplicated)
        assert all(results)

        # Verify in DB: exactly ONE projection row exists and inbox is in SUCCEEDED state
        async with session_factory() as session:
            projections = (
                (
                    await session.execute(
                        select(OrderSummaryProjection).where(
                            OrderSummaryProjection.order_id == order_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(projections) == 1
            assert projections[0].order_number == "ORD-RACE-001"

            inbox_rows = (
                (
                    await session.execute(
                        select(ConsumerInbox).where(
                            ConsumerInbox.consumer_group == consumer_1.consumer_group,
                            ConsumerInbox.event_id == event_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(inbox_rows) == 1
            assert inbox_rows[0].status == InboxStatus.SUCCEEDED.value


# ------------------------------------------------------------------------------
# SECTION 7: Comprehensive Final Audit Regression Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConsumerAuditRegressions:
    async def test_durable_retry_scheduling_prevents_hot_redelivery_loop(
        self, clean_inbox_and_projections
    ):
        """Audit Item 1: next_attempt_at prevents hot redelivery loops across re-polls/restarts."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        call_count = 0

        class FlakyConsumer(BaseKafkaConsumer):
            async def handle_event(
                self, event: EventEnvelope, session: AsyncSession
            ) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionResetError("Transient network timeout")
                # On call 2, succeed
                session.add(
                    OrderSummaryProjection(
                        order_id=event.aggregate_id,
                        order_number="ORD-RETRY-001",
                        status="CONFIRMED",
                        total_payable_paise=1000,
                        last_event_type=event.event_type,
                        last_aggregate_version=event.aggregate_version,
                    )
                )

        consumer = FlakyConsumer(
            consumer_group="test-durable-retry-group",
            topics=["basket.events.orders"],
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            backoff_base_seconds=60.0,  # Schedule 60s in the future
        )

        order_id = uuid.uuid4()
        event_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )

        rec = mock_consumer.add_record("basket.events.orders", envelope, offset=10)

        # Attempt 1: fails transiently
        assert await consumer.process_record(rec) is False
        assert call_count == 1

        # Check PostgreSQL: next_attempt_at is set in the future
        async with session_factory() as session:
            inbox_row = await get_inbox_record(
                session, consumer.consumer_group, event_id
            )
            assert inbox_row is not None
            assert inbox_row.status == InboxStatus.FAILED.value
            assert inbox_row.retry_count == 1
            now = datetime.now(UTC)
            sched = inbox_row.next_attempt_at
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=UTC)
            assert sched > now

        # Immediate re-poll before schedule elapses: must NOT enter hot redelivery loop
        assert await consumer.process_record(rec) is False
        assert call_count == 1  # handle_event was NOT called again!

        # Now simulate that scheduled backoff time has passed
        async with session_factory() as session:
            row = await get_inbox_record(
                session, consumer.consumer_group, event_id, for_update=True
            )
            row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        # Re-poll now succeeds
        assert await consumer.process_record(rec) is True
        assert call_count == 2

        # Verify final state is SUCCEEDED
        async with session_factory() as session:
            row = await get_inbox_record(session, consumer.consumer_group, event_id)
            assert row.status == InboxStatus.SUCCEEDED.value

    async def test_duplicate_dlq_publication_is_idempotent_and_skips_broker_resend(
        self, clean_inbox_and_projections
    ):
        """Audit Item 2: Duplicate DLQ publication is idempotent and does not flood broker."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Pre-seed inbox with DEAD_LETTER status (simulating earlier crash between DB update and offset commit)
        async with session_factory() as session:
            session.add(
                ConsumerInbox(
                    consumer_group=consumer.consumer_group,
                    event_id=event_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    aggregate_version=1,
                    status=InboxStatus.DEAD_LETTER.value,
                    retry_count=5,
                    last_error="Permanent schema defect",
                    dlq_published_at=datetime.now(UTC),
                )
            )
            await session.commit()

        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        rec = mock_consumer.add_record("basket.events.orders", envelope, offset=55)

        # Redelivered record hits consumer
        assert await consumer.process_record(rec) is True

        # DLQ broker was NOT flooded with a duplicate publication
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 0

        # Offset was safely committed
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 56

    async def test_concurrent_duplicate_deliveries_independent_pg_sessions(
        self, clean_inbox_and_projections
    ):
        """Audit Item 3: 4 concurrent workers with independent PostgreSQL sessions."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumers = [MockKafkaConsumer() for _ in range(4)]
        for mc in mock_consumers:
            await mc.start()

        consumers = [
            OrderProjectionConsumer(
                session_factory=session_factory,
                producer=mock_producer,
                consumer_impl=mock_consumers[i],
            )
            for i in range(4)
        ]

        order_id = uuid.uuid4()
        event_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-4WAY-001",
                "total_payable_paise": 55000,
            },
        )

        records = [
            mock_consumers[i].add_record("basket.events.orders", envelope, offset=i)
            for i in range(4)
        ]

        # Dispatch 4 concurrent attempts on identical event
        results = await asyncio.gather(
            *[consumers[i].process_record(records[i]) for i in range(4)]
        )
        assert all(results)

        # Confirm exactly 1 projection in PostgreSQL
        async with session_factory() as session:
            projs = (
                (
                    await session.execute(
                        select(OrderSummaryProjection).where(
                            OrderSummaryProjection.order_id == order_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(projs) == 1
            assert projs[0].order_number == "ORD-4WAY-001"

    async def test_aggregate_version_gap_handling(self, clean_inbox_and_projections):
        """Audit Item 8: Aggregate version gap v1 -> v3 -> late v2."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Step 1: v1 (created)
        e1 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "order_number": "ORD-GAP-001",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 9000,
            },
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e1)
            )
            is True
        )

        # Step 2: v3 arrives with a gap (v2 missing / delayed)
        e3 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.cancelled",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=3,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e3)
            )
            is True
        )

        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.status == "CANCELLED"
            assert proj.last_aggregate_version == 3

        # Step 3: late v2 arrives (e.g. order.confirmed)
        e2 = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert (
            await consumer.process_record(
                mock_consumer.add_record("basket.events.orders", e2)
            )
            is True
        )

        # Projection state must NOT regress to CONFIRMED! Must remain CANCELLED at v3
        async with session_factory() as session:
            proj = (
                await session.execute(
                    select(OrderSummaryProjection).where(
                        OrderSummaryProjection.order_id == order_id
                    )
                )
            ).scalar_one()
            assert proj.status == "CANCELLED"
            assert proj.last_aggregate_version == 3

    async def test_malformed_non_json_persists_inbox_dead_letter_and_routes_dlq(
        self, clean_inbox_and_projections
    ):
        """Audit Item 9: Malformed message persists in inbox DEAD_LETTER and routes to DLQ."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        corrupt_bytes = b"\x00\x01\x02CORRUPT_PAYLOAD"
        rec = mock_consumer.add_record(
            "basket.events.orders", corrupt_bytes, partition=0, offset=88
        )

        assert await consumer.process_record(rec) is True

        # DLQ received message
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 1
        assert dlq_events[0].payload["original_offset"] == 88

        # Inbox has persistent DEAD_LETTER audit row
        synthetic_id = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{consumer.consumer_group}:basket.events.orders:0:88",
        )
        async with session_factory() as session:
            row = await get_inbox_record(session, consumer.consumer_group, synthetic_id)
            assert row is not None
            assert row.status == InboxStatus.DEAD_LETTER.value

    async def test_sensitive_data_redacted_from_dlq_payload_and_logs(
        self, clean_inbox_and_projections
    ):
        """Audit Item 10: Sensitive data excluded from DLQ payloads and sanitized."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        # Poison payload containing sensitive credentials
        poison_with_secrets = b'{"card_number": "4111222233334444", "password": "super_secret_password_999", "token": "Bearer eyJhbGciOiJIUzI1NiJ9"}'
        rec = mock_consumer.add_record(
            "basket.events.orders", poison_with_secrets, partition=0, offset=99
        )

        assert await consumer.process_record(rec) is True

        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 1
        payload = dlq_events[0].payload

        # Ensure no raw sensitive secrets in raw_payload_preview
        preview = payload["raw_payload_preview"]
        assert "super_secret_password_999" not in preview
        assert "password=***" in preview or "password" in preview

    async def test_lifespan_starts_and_stops_cleanly_when_kafka_unavailable(
        self,
    ):
        """Audit Item 4: Kafka unavailability never prevents API startup or health/checkout endpoints."""
        from httpx import ASGITransport, AsyncClient

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestDurableRetryScheduling:
    """Issue 1 Tests: Durable retry scheduling, partition pausing, and hot redelivery prevention."""

    async def test_transient_failure_pauses_partition_and_rewinds_offset(
        self, clean_inbox_and_projections
    ):
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            backoff_base_seconds=10.0,  # 10s backoff
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )
        rec = mock_consumer.add_record(
            "basket.events.orders", envelope, partition=0, offset=10
        )
        tp = TopicPartition("basket.events.orders", 0)

        # Inject transient failure into handle_event
        async def failing_handle(ev, sess):
            raise ConnectionError("Simulated database timeout")

        consumer.handle_event = failing_handle

        # Processing fails transiently
        success = await consumer.process_record(rec)
        assert success is False

        # Partition 0 must now be paused
        assert tp in consumer.paused_partitions()
        assert tp in mock_consumer.paused()

        # In-memory fetch offset was rewound to 10 (not advanced)
        assert mock_consumer._fetch_offsets[tp] == 10

        # Subsequent poll returns NO records for paused partition 0 (no hot loop!)
        polled = await mock_consumer.getmany(tp)
        assert len(polled.get(tp, [])) == 0

        # DB has FAILED status with scheduled next_attempt_at in future
        async with session_factory() as sess:
            inbox_rec = await get_inbox_record(sess, consumer.consumer_group, event_id)
            assert inbox_rec is not None
            assert inbox_rec.status == InboxStatus.FAILED.value
            assert inbox_rec.retry_count == 1
            assert inbox_rec.next_attempt_at > datetime.now(UTC)

    async def test_paused_partition_does_not_block_unrelated_partitions(
        self, clean_inbox_and_projections
    ):
        """Proves partition A pause does NOT block partition B processing."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            backoff_base_seconds=100.0,
        )

        tp0 = TopicPartition("basket.events.orders", 0)
        tp1 = TopicPartition("basket.events.orders", 1)

        await consumer.start()

        # Pause partition 0
        future_time = datetime.now(UTC) + timedelta(seconds=60)
        consumer.pause_partition(tp0, until=future_time, seek_offset=0)

        # Add record to partition 1 (unrelated partition)
        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_number": f"ORD-{order_id}",
                "status": "PENDING_PAYMENT",
                "total_payable_paise": 50000,
            },
        )
        mock_consumer.add_record(
            "basket.events.orders", envelope, partition=1, offset=0
        )

        # Poll and process batch
        processed = await consumer.poll_and_process_batch()
        assert processed == 1

        # Partition 1 was committed
        assert await mock_consumer.committed(tp1) == 1
        # Partition 0 remains paused
        assert tp0 in mock_consumer.paused()

    async def test_resume_ready_partitions_after_scheduled_delay(
        self, clean_inbox_and_projections
    ):
        """Proves partitions resume automatically when next_attempt_at is reached."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        tp = TopicPartition("basket.events.orders", 0)
        past_time = datetime.now(UTC) - timedelta(seconds=1)
        consumer.pause_partition(tp, until=past_time)

        assert tp in consumer.paused_partitions()
        assert tp in mock_consumer.paused()

        # Resume ready partitions
        resumed = consumer.resume_ready_partitions()
        assert tp in resumed
        assert tp not in consumer.paused_partitions()
        assert tp not in mock_consumer.paused()

    async def test_process_restart_preserves_retry_schedule_and_avoids_hot_loop(
        self, clean_inbox_and_projections
    ):
        """Simulate consumer crash and process restart while a retry is scheduled."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()

        mock_consumer_1 = MockKafkaConsumer()
        await mock_consumer_1.start()

        consumer_1 = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer_1,
            backoff_base_seconds=60.0,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )
        rec = mock_consumer_1.add_record(
            "basket.events.orders", envelope, partition=0, offset=22
        )

        # Trigger failure in worker 1
        async def fail_1(ev, sess):
            raise TimeoutError("DB lock timeout")

        consumer_1.handle_event = fail_1
        assert await consumer_1.process_record(rec) is False

        # Now simulate process restart: new consumer worker starts up
        mock_consumer_2 = MockKafkaConsumer()
        await mock_consumer_2.start()
        consumer_2 = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer_2,
        )

        # Redeliver uncommitted record to restarted worker
        rec_redelivered = mock_consumer_2.add_record(
            "basket.events.orders", envelope, partition=0, offset=22
        )
        tp = TopicPartition("basket.events.orders", 0)

        # Worker 2 processes record: reads DB, sees next_attempt_at in future, pauses partition!
        success = await consumer_2.process_record(rec_redelivered)
        assert success is False
        assert tp in consumer_2.paused_partitions()
        assert tp in mock_consumer_2.paused()


@pytest.mark.asyncio
class TestDLQCrashWindowIdempotency:
    """Issue 2 Tests: DLQ publication and offset commit crash-window idempotency at all boundaries."""

    async def test_dlq_crash_before_step_a_clean_retry(
        self, clean_inbox_and_projections
    ):
        """Boundary 1: Crash before DB mark DEAD_LETTER."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            max_retries=1,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )
        mock_consumer.add_record(
            "basket.events.orders", envelope, partition=0, offset=1
        )

        # Crash right inside business logic before DB mark DEAD_LETTER
        async def fail_step(ev, sess):
            raise ValueError("Permanent unparseable data")

        consumer.handle_event = fail_step
        # Strategy A execution catches and flags should_route_dlq
        # But if crash happens before Step A, nothing is in DB or DLQ.
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 0

    async def test_dlq_crash_between_step_a_and_step_b_recovery_publishes_dlq(
        self, clean_inbox_and_projections
    ):
        """Boundary 2: DB marked DEAD_LETTER with dlq_published_at=None, crash before DLQ publish."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Preseed DB state simulating crash after Step A (dlq_published_at is None)
        async with session_factory() as sess:
            sess.add(
                ConsumerInbox(
                    consumer_group=consumer.consumer_group,
                    event_id=event_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    aggregate_version=1,
                    status=InboxStatus.DEAD_LETTER.value,
                    retry_count=5,
                    last_error="Permanent defect",
                    dlq_published_at=None,
                )
            )
            await sess.commit()

        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )
        rec = mock_consumer.add_record(
            "basket.events.orders", envelope, partition=0, offset=40
        )

        # Restarted worker processes the uncommitted record
        assert await consumer.process_record(rec) is True

        # DLQ broker received exactly 1 message
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 1

        # DB dlq_published_at was updated
        async with session_factory() as sess:
            row = await get_inbox_record(sess, consumer.consumer_group, event_id)
            assert row is not None
            assert row.dlq_published_at is not None

        # Offset was committed
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 41

    async def test_dlq_crash_between_step_b_and_step_c_deterministic_identity_deduplicates(
        self, clean_inbox_and_projections
    ):
        """Boundary 3: DLQ broker ACKed, but crash occurred before DB update."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )

        # Direct call to _route_to_dlq simulating first attempt
        await consumer._route_to_dlq(
            original_topic="basket.events.orders",
            original_partition=0,
            original_offset=50,
            raw_value=envelope.to_json_bytes(),
            error_message="Permanent defect",
            event_id=event_id,
            aggregate_id=order_id,
        )

        first_dlq_event = mock_producer.get_events_for_topic(
            "basket.events.dead-letter"
        )[0]

        # Second attempt (after crash)
        await consumer._route_to_dlq(
            original_topic="basket.events.orders",
            original_partition=0,
            original_offset=50,
            raw_value=envelope.to_json_bytes(),
            error_message="Permanent defect",
            event_id=event_id,
            aggregate_id=order_id,
        )

        second_dlq_event = mock_producer.get_events_for_topic(
            "basket.events.dead-letter"
        )[1]

        # Deterministic UUIDv5 ensures both attempts produce IDENTICAL event_id and payload
        assert first_dlq_event.event_id == second_dlq_event.event_id
        assert (
            first_dlq_event.payload["failed_event_id"]
            == second_dlq_event.payload["failed_event_id"]
        )

    async def test_dlq_crash_between_step_c_and_step_d_skips_broker_resend_and_commits_offset(
        self, clean_inbox_and_projections
    ):
        """Boundary 4: DB has dlq_published_at set, crash before Kafka commit."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        event_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Preseed DB state where dlq_published_at IS NOT NULL
        async with session_factory() as sess:
            sess.add(
                ConsumerInbox(
                    consumer_group=consumer.consumer_group,
                    event_id=event_id,
                    event_type="order.created",
                    schema_version=1,
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    aggregate_version=1,
                    status=InboxStatus.DEAD_LETTER.value,
                    retry_count=5,
                    last_error="Permanent defect",
                    dlq_published_at=datetime.now(UTC),
                )
            )
            await sess.commit()

        envelope = EventEnvelope(
            event_id=event_id,
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}"},
        )
        rec = mock_consumer.add_record(
            "basket.events.orders", envelope, partition=0, offset=70
        )

        # Process redelivered record
        assert await consumer.process_record(rec) is True

        # DLQ broker was NOT called
        dlq_events = mock_producer.get_events_for_topic("basket.events.dead-letter")
        assert len(dlq_events) == 0

        # Offset was committed
        tp = TopicPartition("basket.events.orders", 0)
        assert await mock_consumer.committed(tp) == 71


@pytest.mark.asyncio
class TestAggregateVersionGapsAndReconciliation:
    """Issue 3 Tests: Version gaps, durable deferral, and reconciliation."""

    async def test_version_gap_detection_and_deferral(
        self, clean_inbox_and_projections
    ):
        """Proves order.confirmed (v2) arriving with missing order.created (v1) is deferred."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            enable_gap_deferral=True,
            max_gap_deferrals=2,
        )

        order_id = uuid.uuid4()
        confirmed_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}", "status": "CONFIRMED"},
        )
        rec = mock_consumer.add_record(
            "basket.events.orders", confirmed_env, partition=0, offset=1
        )

        # First attempt: gap detected, deferred
        success = await consumer.process_record(rec)
        assert success is False

        # Partition is paused
        tp = TopicPartition("basket.events.orders", 0)
        assert tp in consumer.paused_partitions()

    async def test_delayed_order_created_reconciles_missing_items_into_confirmed_projection(
        self, clean_inbox_and_projections
    ):
        """
        Critical test: order.confirmed (v2) arrived first (deferral disabled or exhausted).
        Then delayed order.created (v1) arrives.
        Reconciliation MUST backfill item_count and total_payable_paise WITHOUT regressing status.
        """
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            enable_gap_deferral=False,  # Proceed directly to state creation
        )

        order_id = uuid.uuid4()

        # Step 1: order.confirmed (v2) arrives first
        confirmed_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={
                "order_number": f"ORD-{order_id}",
                "status": "CONFIRMED",
                "total_payable_paise": 250000,
            },
        )
        rec_conf = mock_consumer.add_record(
            "basket.events.orders", confirmed_env, partition=0, offset=1
        )
        assert await consumer.process_record(rec_conf) is True

        # Projection is CONFIRMED but item_count is 0
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            assert p.status == "CONFIRMED"
            assert p.item_count == 0
            assert p.last_aggregate_version == 2

        # Step 2: delayed order.created (v1) arrives later
        created_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_number": f"ORD-{order_id}",
                "status": "PENDING_PAYMENT",
                "items": [
                    {"listing_id": str(uuid.uuid4()), "quantity": 1},
                    {"listing_id": str(uuid.uuid4()), "quantity": 2},
                ],
                "total_payable_paise": 250000,
            },
        )
        rec_create = mock_consumer.add_record(
            "basket.events.orders", created_env, partition=0, offset=2
        )
        assert await consumer.process_record(rec_create) is True

        # Step 3: Verify RECONCILIATION
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            # Items were reconciled!
            assert p.item_count == 2
            # Terminal status CONFIRMED was NOT regressed to PENDING_PAYMENT!
            assert p.status == "CONFIRMED"
            assert p.last_aggregate_version == 2

    async def test_delayed_order_created_reconciles_missing_items_into_cancelled_projection(
        self, clean_inbox_and_projections
    ):
        """
        Terminal cancellation precedence:
        order.cancelled (v3) arrives before order.created (v1).
        Reconciliation populates baseline items without reverting CANCELLED.
        """
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            enable_gap_deferral=False,
        )

        order_id = uuid.uuid4()

        # Step 1: order.cancelled (v3) arrives first
        cancel_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.cancelled",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=3,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}", "status": "CANCELLED"},
        )
        rec_cancel = mock_consumer.add_record(
            "basket.events.orders", cancel_env, partition=0, offset=1
        )
        assert await consumer.process_record(rec_cancel) is True

        # Step 2: order.created (v1) arrives later
        create_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_number": f"ORD-{order_id}",
                "status": "PENDING_PAYMENT",
                "items": [{"listing_id": str(uuid.uuid4()), "quantity": 3}],
                "total_payable_paise": 75000,
            },
        )
        rec_create = mock_consumer.add_record(
            "basket.events.orders", create_env, partition=0, offset=2
        )
        assert await consumer.process_record(rec_create) is True

        # Verify CANCELLED is preserved and items are populated
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            assert p.status == "CANCELLED"
            assert p.item_count == 1
            assert p.total_payable_paise == 75000

    async def test_terminal_state_protection_cancelled_order_refuses_confirmation(
        self, clean_inbox_and_projections
    ):
        """Cancelled order cannot be moved to CONFIRMED."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
            enable_gap_deferral=False,
        )

        order_id = uuid.uuid4()

        # Cancel order (v2)
        cancel_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.cancelled",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}", "status": "CANCELLED"},
        )
        rec_cancel = mock_consumer.add_record(
            "basket.events.orders", cancel_env, partition=0, offset=1
        )
        assert await consumer.process_record(rec_cancel) is True

        # Stale confirmation arrives (v1 or out-of-order)
        confirm_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.confirmed",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_number": f"ORD-{order_id}", "status": "CONFIRMED"},
        )
        rec_confirm = mock_consumer.add_record(
            "basket.events.orders", confirm_env, partition=0, offset=2
        )
        assert await consumer.process_record(rec_confirm) is True

        # Status must remain CANCELLED
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            assert p.status == "CANCELLED"

    async def test_cross_topic_ordering_payment_succeeded_before_order_created_reconciles(
        self, clean_inbox_and_projections
    ):
        """Cross-topic resilience: payment.succeeded from payments topic arrives before order.created."""
        session_factory = get_session_factory()
        mock_producer = MockKafkaProducer()
        await mock_producer.start()
        mock_consumer = MockKafkaConsumer()
        await mock_consumer.start()

        consumer = OrderProjectionConsumer(
            session_factory=session_factory,
            producer=mock_producer,
            consumer_impl=mock_consumer,
        )

        order_id = uuid.uuid4()

        # Step 1: payment.succeeded arrives on basket.events.payments
        payment_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="payment.succeeded",
            event_version=1,
            aggregate_type="Payment",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_id": str(order_id),
                "amount_paise": 120000,
                "currency": "INR",
            },
        )
        rec_pay = mock_consumer.add_record(
            "basket.events.payments", payment_env, partition=0, offset=1
        )
        assert await consumer.process_record(rec_pay) is True

        # Projection has payment_status SUCCEEDED, item_count 0
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            assert p.payment_status == "SUCCEEDED"
            assert p.item_count == 0

        # Step 2: order.created arrives on basket.events.orders
        order_env = EventEnvelope(
            event_id=uuid.uuid4(),
            event_type="order.created",
            event_version=1,
            aggregate_type="Order",
            aggregate_id=order_id,
            aggregate_version=1,
            partition_key=str(order_id),
            payload={
                "order_number": f"ORD-{order_id}",
                "status": "PENDING_PAYMENT",
                "items": [
                    {"listing_id": str(uuid.uuid4()), "quantity": 1},
                    {"listing_id": str(uuid.uuid4()), "quantity": 4},
                ],
                "total_payable_paise": 120000,
            },
        )
        rec_ord = mock_consumer.add_record(
            "basket.events.orders", order_env, partition=0, offset=1
        )
        assert await consumer.process_record(rec_ord) is True

        # Step 3: Verified projection reconciled order number and item count while keeping SUCCEEDED
        async with session_factory() as sess:
            stmt = select(OrderSummaryProjection).where(
                OrderSummaryProjection.order_id == order_id
            )
            res = await sess.execute(stmt)
            p = res.scalar_one()
            assert p.item_count == 2
            assert p.total_payable_paise == 120000
            assert p.payment_status == "SUCCEEDED"
            assert p.status == "PENDING_PAYMENT"
