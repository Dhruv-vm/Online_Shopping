from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiokafka.errors import KafkaError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.events.envelope import EventEnvelope
from app.core.events.kafka import (
    AioKafkaEventProducer,
    KafkaConnectionError,
    KafkaPublishError,
    MockKafkaProducer,
    get_kafka_producer,
)


class TestEventEnvelope:
    def test_valid_envelope_creation_defaults(self):
        agg_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            payload={"order_id": str(agg_id), "total_paise": 59900},
        )
        assert isinstance(event.event_id, uuid.UUID)
        assert event.event_version == 1
        assert event.producer == "basket-backend@0.1.0"
        assert event.partition_key == str(agg_id)
        assert event.occurred_at.tzinfo == UTC
        assert event.payload["total_paise"] == 59900

    # --------------------------------------------------------------------------
    # Event-Type-Aware Partition Key Tests (All 4 Cases + Invalid Keys)
    # --------------------------------------------------------------------------

    def test_case_1_order_partition_key_order_id(self):
        """Case 1: Orders must partition by order_id."""
        order_id = uuid.uuid4()
        # Default auto-resolves to order_id
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=order_id,
            aggregate_version=1,
            payload={"order_id": str(order_id)},
        )
        assert event.partition_key == str(order_id)

        # Explicit matching key succeeds
        event2 = EventEnvelope(
            event_type="order.confirmed",
            aggregate_type="order",
            aggregate_id=order_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id)},
        )
        assert event2.partition_key == str(order_id)

        # Mismatched partition key fails
        with pytest.raises(ValidationError, match="partition_key"):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=order_id,
                aggregate_version=1,
                partition_key=str(uuid.uuid4()),
                payload={"order_id": str(order_id)},
            )

    def test_case_2_payment_partition_key_order_id(self):
        """Case 2: Payments must partition by parent order_id, not payment_id."""
        payment_id = uuid.uuid4()
        order_id = uuid.uuid4()

        # Auto-resolves to order_id from payload
        event = EventEnvelope(
            event_type="payment.captured",
            aggregate_type="payment",
            aggregate_id=payment_id,
            aggregate_version=1,
            payload={"order_id": str(order_id), "amount_paise": 49900},
        )
        assert event.partition_key == str(order_id)

        # Explicit matching order_id succeeds
        event2 = EventEnvelope(
            event_type="payment.succeeded",
            aggregate_type="payment",
            aggregate_id=payment_id,
            aggregate_version=2,
            partition_key=str(order_id),
            payload={"order_id": str(order_id), "amount_paise": 49900},
        )
        assert event2.partition_key == str(order_id)

        # Partitioning by payment_id instead of order_id is rejected
        with pytest.raises(ValidationError, match="partition_key"):
            EventEnvelope(
                event_type="payment.captured",
                aggregate_type="payment",
                aggregate_id=payment_id,
                aggregate_version=1,
                partition_key=str(payment_id),  # Incorrect! Must be order_id
                payload={"order_id": str(order_id)},
            )

        # Missing order_id in payment payload fails
        with pytest.raises(ValidationError, match="must include 'order_id'"):
            EventEnvelope(
                event_type="payment.captured",
                aggregate_type="payment",
                aggregate_id=payment_id,
                aggregate_version=1,
                payload={"amount_paise": 49900},
            )

    def test_case_3_catalogue_partition_key_product_id(self):
        """Case 3: Catalogue (including listings and variants) must partition by product_id."""
        product_id = uuid.uuid4()
        listing_id = uuid.uuid4()

        # Product aggregate partitions by product_id
        event = EventEnvelope(
            event_type="product.created",
            aggregate_type="product",
            aggregate_id=product_id,
            aggregate_version=1,
            payload={"product_id": str(product_id), "title": "Apples 1kg"},
        )
        assert event.partition_key == str(product_id)

        # Listing aggregate (listing.updated) partitions by parent product_id from payload
        event_listing = EventEnvelope(
            event_type="listing.updated",
            aggregate_type="listing",
            aggregate_id=listing_id,
            aggregate_version=1,
            payload={"product_id": str(product_id), "selling_price_paise": 12000},
        )
        assert event_listing.partition_key == str(product_id)

        # Reject listing partitioned by listing_id instead of product_id
        with pytest.raises(ValidationError, match="partition_key"):
            EventEnvelope(
                event_type="listing.updated",
                aggregate_type="listing",
                aggregate_id=listing_id,
                aggregate_version=1,
                partition_key=str(listing_id),  # Incorrect! Must be product_id
                payload={"product_id": str(product_id)},
            )

        # Listing without product_id in payload fails
        with pytest.raises(ValidationError, match="must include 'product_id'"):
            EventEnvelope(
                event_type="listing.updated",
                aggregate_type="listing",
                aggregate_id=listing_id,
                aggregate_version=1,
                payload={"selling_price_paise": 12000},
            )

    def test_case_4_inventory_partition_key_product_id(self):
        """Case 4: Inventory updates must partition by product_id."""
        inventory_id = uuid.uuid4()
        product_id = uuid.uuid4()

        # Inventory aggregate partitions by parent product_id from payload
        event_inv = EventEnvelope(
            event_type="inventory.updated",
            aggregate_type="store_inventory",
            aggregate_id=inventory_id,
            aggregate_version=1,
            payload={"product_id": str(product_id), "on_hand_quantity": 42},
        )
        assert event_inv.partition_key == str(product_id)

        # Reject inventory partitioned by inventory_id instead of parent product_id
        with pytest.raises(ValidationError, match="partition_key"):
            EventEnvelope(
                event_type="inventory.updated",
                aggregate_type="store_inventory",
                aggregate_id=inventory_id,
                aggregate_version=1,
                partition_key=str(inventory_id),  # Incorrect! Must be product_id
                payload={"product_id": str(product_id)},
            )

        # Inventory without product_id in payload fails
        with pytest.raises(ValidationError, match="must include 'product_id'"):
            EventEnvelope(
                event_type="inventory.updated",
                aggregate_type="store_inventory",
                aggregate_id=inventory_id,
                aggregate_version=1,
                payload={"quantity": 10},
            )

    def test_invalid_event_type_format_fails(self):
        agg_id = uuid.uuid4()
        for invalid_type in ("ordercreated", "order.", ".created", "invalid"):
            with pytest.raises(ValidationError, match="event_type"):
                EventEnvelope(
                    event_type=invalid_type,
                    aggregate_type="order",
                    aggregate_id=agg_id,
                    aggregate_version=1,
                    payload={},
                )

    def test_aggregate_version_must_be_positive(self):
        agg_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=0,
                payload={},
            )
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=-1,
                payload={},
            )

    def test_occurred_at_naive_converted_to_utc(self):
        agg_id = uuid.uuid4()
        naive_dt = datetime(2026, 11, 18, 12, 0, 0)
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            occurred_at=naive_dt,
            payload={},
        )
        assert event.occurred_at.tzinfo == UTC

    def test_correlation_id_coercion(self):
        agg_id = uuid.uuid4()
        corr_uuid = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            correlation_id=str(corr_uuid),
            payload={},
        )
        assert event.correlation_id == str(corr_uuid)

        event_none = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            correlation_id=None,
            payload={},
        )
        assert event_none.correlation_id is None

    def test_extra_fields_forbidden(self):
        agg_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=1,
                unknown_extra_field="malicious",
                payload={},
            )

    @pytest.mark.parametrize(
        "pii_key",
        [
            "customer_id",
            "guest_token",
            "guest_token_hash",
            "user_id",
            "account_id",
            "email",
            "customer_email",
            "user_email",
            "phone",
            "phone_number",
            "mobile",
            "customer_phone",
            "full_name",
            "first_name",
            "last_name",
            "customer_name",
            "recipient_name",
            "address",
            "delivery_address",
            "shipping_address",
            "street",
            "street_address",
            "pincode",
            "pin_code",
            "postal_code",
            "password",
            "password_hash",
            "card_number",
            "credit_card",
            "debit_card",
            "card_cvv",
            "bank_account",
            "aadhaar",
            "pan",
        ],
    )
    def test_rejects_top_level_customer_pii(self, pii_key: str):
        agg_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="Customer PII field"):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=1,
                payload={pii_key: "confidential_value"},
            )

    def test_rejects_nested_customer_pii(self):
        agg_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="Customer PII field"):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=1,
                payload={"details": {"user": {"email": "customer@example.com"}}},
            )

        with pytest.raises(ValidationError, match="Customer PII field"):
            EventEnvelope(
                event_type="order.created",
                aggregate_type="order",
                aggregate_id=agg_id,
                aggregate_version=1,
                payload={"items": [{"sku": "SKU-1", "address": "123 Main St"}]},
            )

    def test_accepts_harmless_operational_identifiers(self):
        """Verifies harmless operational fields are never mistakenly rejected."""
        order_id = uuid.uuid4()
        product_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="payment.captured",
            aggregate_type="payment",
            aggregate_id=uuid.uuid4(),
            aggregate_version=1,
            payload={
                "order_id": str(order_id),
                "product_id": str(product_id),
                "provider_payment_id": "pay_test_12345",
                "provider_order_id": "order_test_67890",
                "provider_refund_id": "rfnd_test_abc",
                "amount_paise": 49900,
                "currency": "INR",
                "status": "CAPTURED",
                "quantity": 2,
                "title": "Fresh Apples 1kg",
                "brand": "Organic Farms",
            },
        )
        assert event.payload["provider_payment_id"] == "pay_test_12345"
        assert event.payload["status"] == "CAPTURED"
        assert event.payload["title"] == "Fresh Apples 1kg"

    def test_serialization_round_trip(self):
        agg_id = uuid.uuid4()
        original = EventEnvelope(
            event_type="product.created",
            aggregate_type="product",
            aggregate_id=agg_id,
            aggregate_version=3,
            payload={"product_id": str(agg_id), "title": "Organic Milk 1L"},
        )
        raw_bytes = original.to_json_bytes()
        assert isinstance(raw_bytes, bytes)

        restored = EventEnvelope.from_json_bytes(raw_bytes)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.aggregate_id == original.aggregate_id
        assert restored.aggregate_version == original.aggregate_version
        assert restored.partition_key == original.partition_key
        assert restored.payload == original.payload


class TestKafkaProducer:
    @pytest.mark.asyncio
    async def test_mock_producer_lifecycle_and_publish(self):
        producer = MockKafkaProducer()
        assert not producer.is_connected

        # Sending before start raises error
        agg_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            payload={"order_id": str(agg_id)},
        )
        with pytest.raises(KafkaConnectionError, match="not started"):
            await producer.send("basket.orders", event)

        await producer.start()
        assert producer.is_connected

        # Send events
        await producer.send("basket.orders", event)

        event2 = EventEnvelope(
            event_type="payment.captured",
            aggregate_type="payment",
            aggregate_id=uuid.uuid4(),
            aggregate_version=1,
            payload={"order_id": str(agg_id), "amount_paise": 1000},
        )
        await producer.send("basket.payments", event2)

        assert len(producer.published_events) == 2
        orders = producer.get_events_for_topic("basket.orders")
        assert len(orders) == 1
        assert orders[0].event_id == event.event_id

        payments = producer.get_events_for_topic("basket.payments")
        assert len(payments) == 1
        assert payments[0].event_id == event2.event_id

        producer.clear()
        assert len(producer.published_events) == 0

        await producer.stop()
        assert not producer.is_connected

    def test_get_kafka_producer_defaults_to_mock_when_servers_empty(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS=None,
        )
        producer = get_kafka_producer(settings)
        assert isinstance(producer, MockKafkaProducer)

    def test_get_kafka_producer_force_mock(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
            ENVIRONMENT="development",
        )
        producer = get_kafka_producer(settings, force_mock=True)
        assert isinstance(producer, MockKafkaProducer)

    def test_get_kafka_producer_returns_aiokafka_when_configured(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
            ENVIRONMENT="development",
        )
        producer = get_kafka_producer(settings)
        assert isinstance(producer, AioKafkaEventProducer)

    @pytest.mark.asyncio
    async def test_aiokafka_producer_send_not_started_raises(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
            ENVIRONMENT="development",
        )
        producer = AioKafkaEventProducer(settings)
        assert not producer.is_connected

        agg_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            payload={"order_id": str(agg_id)},
        )
        with pytest.raises(KafkaConnectionError, match="not started"):
            await producer.send("basket.orders", event)

    @pytest.mark.asyncio
    async def test_aiokafka_producer_send_timeout_raises_publish_error(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
            ENVIRONMENT="development",
            KAFKA_PRODUCER_TIMEOUT_SECONDS=0.01,
            KAFKA_PRODUCER_RETRIES=1,
        )
        producer = AioKafkaEventProducer(settings)
        producer._started = True
        mock_underlying = AsyncMock()

        async def slow_send(*args, **kwargs):
            await asyncio.sleep(0.5)

        mock_underlying.send_and_wait = slow_send
        producer._producer = mock_underlying

        agg_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            payload={"order_id": str(agg_id)},
        )

        with pytest.raises(KafkaPublishError, match="Timed out"):
            await producer.send("basket.orders", event, timeout=0.01)

    @pytest.mark.asyncio
    async def test_aiokafka_producer_send_kafka_error_raises_publish_error(self):
        settings = Settings(
            KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
            ENVIRONMENT="development",
            KAFKA_PRODUCER_RETRIES=1,
        )
        producer = AioKafkaEventProducer(settings)
        producer._started = True
        mock_underlying = AsyncMock()
        mock_underlying.send_and_wait.side_effect = KafkaError("Broker unavailable")
        producer._producer = mock_underlying

        agg_id = uuid.uuid4()
        event = EventEnvelope(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=agg_id,
            aggregate_version=1,
            payload={"order_id": str(agg_id)},
        )

        with pytest.raises(KafkaPublishError, match="Failed to publish"):
            await producer.send("basket.orders", event)


class TestKafkaConfigValidation:
    def test_production_rejects_mock_or_localhost_bootstrap_servers(self):
        for invalid_server in (
            "localhost:9092",
            "127.0.0.1:9092",
            "mock-kafka.aivencloud.com:1234",
        ):
            with pytest.raises(ValidationError, match="mock or localhost"):
                Settings(
                    ENVIRONMENT="production",
                    SECRET_KEY="a" * 32,
                    JWT_SECRET_KEY="b" * 32,
                    INTERNAL_SERVICE_KEY="c" * 32,
                    RAZORPAY_KEY_ID="rzp_live_testvalid123",
                    RAZORPAY_KEY_SECRET="productionsecret16chars",
                    RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
                    KAFKA_BOOTSTRAP_SERVERS=invalid_server,
                )

    def test_production_accepts_valid_kafka_servers(self):
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_testvalid123",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
        )
        assert s.has_kafka is True
        assert s.KAFKA_BOOTSTRAP_SERVERS == "basket-kafka-prod.aivencloud.com:21345"

    def test_production_requires_acks_all_and_rejects_acks_0_and_1(self):
        """Production must enforce acks=all (or -1) and reject acks=0 and acks=1."""
        # acks=all accepted
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_testvalid123",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
            KAFKA_PRODUCER_ACKS="all",
        )
        assert s.KAFKA_PRODUCER_ACKS == "all"

        # acks=-1 accepted
        s_neg1 = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_testvalid123",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
            KAFKA_PRODUCER_ACKS="-1",
        )
        assert s_neg1.KAFKA_PRODUCER_ACKS == "-1"

        # acks=0 rejected in production
        with pytest.raises(ValidationError, match="acks=0 and acks=1 are prohibited"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                JWT_SECRET_KEY="b" * 32,
                INTERNAL_SERVICE_KEY="c" * 32,
                RAZORPAY_KEY_ID="rzp_live_testvalid123",
                RAZORPAY_KEY_SECRET="productionsecret16chars",
                RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
                KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
                KAFKA_PRODUCER_ACKS="0",
            )

        # acks=1 rejected in production
        with pytest.raises(ValidationError, match="acks=0 and acks=1 are prohibited"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                JWT_SECRET_KEY="b" * 32,
                INTERNAL_SERVICE_KEY="c" * 32,
                RAZORPAY_KEY_ID="rzp_live_testvalid123",
                RAZORPAY_KEY_SECRET="productionsecret16chars",
                RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
                KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
                KAFKA_PRODUCER_ACKS="1",
            )

    def test_production_rejects_plaintext_security_protocol(self):
        with pytest.raises(
            ValidationError, match="cannot be 'PLAINTEXT' in production"
        ):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                JWT_SECRET_KEY="b" * 32,
                INTERNAL_SERVICE_KEY="c" * 32,
                RAZORPAY_KEY_ID="rzp_live_testvalid123",
                RAZORPAY_KEY_SECRET="productionsecret16chars",
                RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
                KAFKA_BOOTSTRAP_SERVERS="basket-kafka-prod.aivencloud.com:21345",
                KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
            )

    def test_invalid_security_protocol_rejected(self):
        with pytest.raises(ValidationError, match="KAFKA_SECURITY_PROTOCOL"):
            Settings(
                KAFKA_SECURITY_PROTOCOL="INVALID_PROTOCOL",
            )

    def test_invalid_producer_acks_rejected(self):
        with pytest.raises(ValidationError, match="KAFKA_PRODUCER_ACKS"):
            Settings(
                KAFKA_PRODUCER_ACKS="invalid_acks",
            )
