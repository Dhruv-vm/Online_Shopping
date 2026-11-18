from __future__ import annotations

import asyncio
import logging
import ssl
from abc import ABC, abstractmethod
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import Settings, settings
from app.core.events.envelope import EventEnvelope

logger = logging.getLogger(__name__)


class KafkaEventError(Exception):
    """Base exception for Kafka event operations."""

    pass


class KafkaConnectionError(KafkaEventError):
    """Raised when connection to Kafka brokers fails or producer is not started."""

    pass


class KafkaPublishError(KafkaEventError):
    """Raised when an event fails to publish to Kafka."""

    pass


class EventProducer(ABC):
    """Abstract interface for domain event publication."""

    @abstractmethod
    async def start(self) -> None:
        """Start the producer connection."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the producer and release resources."""
        pass

    @abstractmethod
    async def send(
        self,
        topic: str,
        event: EventEnvelope,
        *,
        timeout: float | None = None,
    ) -> None:
        """Publish a single domain event to the given Kafka topic."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the producer is currently connected and active."""
        pass


class AioKafkaEventProducer(EventProducer):
    """Production Kafka producer client using aiokafka with TLS/SASL."""

    def __init__(self, config_settings: Settings) -> None:
        self._settings = config_settings
        self._producer: AIOKafkaProducer | None = None
        self._started = False

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        protocol = self._settings.KAFKA_SECURITY_PROTOCOL.upper()
        if protocol not in ("SSL", "SASL_SSL"):
            return None

        context = ssl.create_default_context(
            cafile=self._settings.KAFKA_SSL_CA_LOCATION
        )
        if (
            self._settings.KAFKA_SSL_CERTIFICATE_LOCATION
            and self._settings.KAFKA_SSL_KEY_LOCATION
        ):
            context.load_cert_chain(
                certfile=self._settings.KAFKA_SSL_CERTIFICATE_LOCATION,
                keyfile=self._settings.KAFKA_SSL_KEY_LOCATION,
            )
        return context

    async def start(self) -> None:
        if self._started and self._producer is not None:
            return

        if not self._settings.KAFKA_BOOTSTRAP_SERVERS:
            raise KafkaConnectionError("KAFKA_BOOTSTRAP_SERVERS is not configured")

        protocol = self._settings.KAFKA_SECURITY_PROTOCOL.upper()
        ssl_ctx = self._build_ssl_context()

        acks: Any = self._settings.KAFKA_PRODUCER_ACKS
        if isinstance(acks, str) and (acks.isdigit() or acks == "-1"):
            acks = int(acks)

        kwargs: dict[str, Any] = {
            "bootstrap_servers": self._settings.KAFKA_BOOTSTRAP_SERVERS,
            "client_id": self._settings.KAFKA_CLIENT_ID,
            "acks": acks,
            "request_timeout_ms": int(
                self._settings.KAFKA_PRODUCER_TIMEOUT_SECONDS * 1000
            ),
            "retry_backoff_ms": 100,
            "security_protocol": protocol,
        }

        if ssl_ctx is not None:
            kwargs["ssl_context"] = ssl_ctx

        if protocol in ("SASL_SSL", "SASL_PLAINTEXT"):
            kwargs["sasl_mechanism"] = self._settings.KAFKA_SASL_MECHANISM
            kwargs["sasl_plain_username"] = self._settings.KAFKA_SASL_USERNAME
            if self._settings.KAFKA_SASL_PASSWORD:
                kwargs["sasl_plain_password"] = (
                    self._settings.KAFKA_SASL_PASSWORD.get_secret_value()
                )

        try:
            self._producer = AIOKafkaProducer(**kwargs)
            await self._producer.start()
            self._started = True
            logger.info(
                "AioKafkaEventProducer started successfully for %s",
                self._settings.KAFKA_BOOTSTRAP_SERVERS,
            )
        except KafkaError as e:
            self._producer = None
            self._started = False
            raise KafkaConnectionError(
                f"Failed to connect to Kafka brokers: {e}"
            ) from e

    async def stop(self) -> None:
        if self._producer is not None:
            try:
                await self._producer.stop()
                logger.info("AioKafkaEventProducer stopped successfully")
            finally:
                self._producer = None
                self._started = False

    @property
    def is_connected(self) -> bool:
        return self._started and self._producer is not None

    async def send(
        self,
        topic: str,
        event: EventEnvelope,
        *,
        timeout: float | None = None,
    ) -> None:
        if not self.is_connected or self._producer is None:
            raise KafkaConnectionError("Producer is not started")

        key = event.partition_key.encode("utf-8") if event.partition_key else None
        value = event.to_json_bytes()
        effective_timeout = (
            timeout
            if timeout is not None
            else self._settings.KAFKA_PRODUCER_TIMEOUT_SECONDS
        )
        max_retries = max(1, self._settings.KAFKA_PRODUCER_RETRIES)
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                await asyncio.wait_for(
                    self._producer.send_and_wait(topic, value=value, key=key),
                    timeout=effective_timeout,
                )
                logger.debug(
                    "Published event %s (%s) to topic %s on attempt %d",
                    event.event_id,
                    event.event_type,
                    topic,
                    attempt,
                )
                return
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "Timeout publishing event %s to topic '%s' on attempt %d/%d after %ss",
                    event.event_id,
                    topic,
                    attempt,
                    max_retries,
                    effective_timeout,
                )
            except KafkaError as e:
                last_error = e
                logger.warning(
                    "Kafka error publishing event %s to topic '%s' on attempt %d/%d: %s",
                    event.event_id,
                    topic,
                    attempt,
                    max_retries,
                    e,
                )
            if attempt < max_retries:
                await asyncio.sleep(min(0.05 * (2 ** (attempt - 1)), 0.5))

        if isinstance(last_error, TimeoutError):
            raise KafkaPublishError(
                f"Timed out publishing event {event.event_id} to topic '{topic}' after {max_retries} attempts ({effective_timeout}s per attempt)"
            ) from last_error
        raise KafkaPublishError(
            f"Failed to publish event {event.event_id} to topic '{topic}' after {max_retries} attempts: {last_error}"
        ) from last_error


class MockKafkaProducer(EventProducer):
    """In-memory mock producer for local testing and offline development."""

    def __init__(self) -> None:
        self._started = False
        self._published_events: list[tuple[str, EventEnvelope]] = []

    async def start(self) -> None:
        self._started = True
        logger.debug("MockKafkaProducer started")

    async def stop(self) -> None:
        self._started = False
        logger.debug("MockKafkaProducer stopped")

    @property
    def is_connected(self) -> bool:
        return self._started

    async def send(
        self,
        topic: str,
        event: EventEnvelope,
        *,
        timeout: float | None = None,
    ) -> None:
        if not self.is_connected:
            raise KafkaConnectionError("MockKafkaProducer is not started")
        self._published_events.append((topic, event))
        logger.debug(
            "MockKafkaProducer recorded event %s (%s) on topic %s",
            event.event_id,
            event.event_type,
            topic,
        )

    @property
    def published_events(self) -> list[tuple[str, EventEnvelope]]:
        return list(self._published_events)

    def get_events_for_topic(self, topic: str) -> list[EventEnvelope]:
        return [evt for t, evt in self._published_events if t == topic]

    def clear(self) -> None:
        self._published_events.clear()


def get_kafka_producer(
    config_settings: Settings | None = None,
    *,
    force_mock: bool = False,
) -> EventProducer:
    """Connection factory returning AioKafkaEventProducer or MockKafkaProducer."""
    active_settings = config_settings or settings
    if force_mock or not active_settings.has_kafka:
        return MockKafkaProducer()
    return AioKafkaEventProducer(active_settings)
