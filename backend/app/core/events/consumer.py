from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer, TopicPartition
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.core.events.envelope import EventEnvelope
from app.core.events.inbox import ConsumerInbox, InboxStatus, get_inbox_record
from app.core.events.kafka import (
    EventProducer,
    KafkaConnectionError,
    build_kafka_auth_kwargs,
    get_kafka_producer,
)
from app.core.events.outbox_publisher import (
    classify_failure,
    compute_next_attempt_at,
    sanitize_error_message,
)

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_RETRIES: int = 5
DEFAULT_BACKOFF_BASE_SECONDS: float = 1.0
DEFAULT_BACKOFF_MAX_SECONDS: float = 300.0
DEFAULT_BACKOFF_MAX_JITTER_SECONDS: float = 2.0
DEFAULT_DLQ_TOPIC: str = "basket.events.dead-letter"


class ConsumerError(Exception):
    """Base exception for Kafka consumer operations."""

    pass


class ConsumerCommitError(ConsumerError):
    """Raised when committing Kafka offsets fails."""

    pass


class PoisonMessageError(ConsumerError):
    """Raised when an unparseable or schema-violating payload is encountered."""

    pass


class DeadLetterPublishError(ConsumerError):
    """Raised when publishing to the Dead-Letter Queue fails."""

    pass


class _TransientHandlerError(Exception):
    """Internal exception carrying failure context for transient retries."""

    def __init__(self, sanitized_error: str, retry_count: int) -> None:
        super().__init__(sanitized_error)
        self.sanitized_error = sanitized_error
        self.retry_count = retry_count


@dataclass(frozen=True)
class ConsumerRecord:
    """Decoupled representation of a polled Kafka message."""

    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes | None
    timestamp: int
    headers: tuple[tuple[str, bytes], ...] = ()


class EventConsumer(ABC):
    """Abstract interface for domain event consumers."""

    @property
    @abstractmethod
    def consumer_group(self) -> str:
        """Unique consumer group identifier."""
        pass

    @property
    @abstractmethod
    def topics(self) -> list[str]:
        """List of subscribed Kafka topics."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the consumer connection and polling loops."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the consumer and release resources."""
        pass

    @abstractmethod
    async def handle_event(self, event: EventEnvelope, session: AsyncSession) -> None:
        """
        Execute domain business logic inside the active ACID database transaction.
        Must raise an exception on failure to trigger rollback.
        """
        pass


class MockKafkaConsumer:
    """
    In-memory mock Kafka consumer for deterministic local testing and CI.
    Supports manual offsets, redelivery, rebalancing simulation, and poison messages.
    """

    def __init__(self, config_settings: Settings | None = None) -> None:
        self._settings = config_settings or settings
        if self._settings.is_production:
            raise RuntimeError("MockKafkaConsumer is strictly forbidden in production")

        self._started = False
        self._subscribed_topics: set[str] = set()
        self._partitions: dict[TopicPartition, list[ConsumerRecord]] = {}
        self._fetch_offsets: dict[TopicPartition, int] = {}
        self._committed_offsets: dict[TopicPartition, int] = {}
        self._paused_partitions: set[TopicPartition] = set()

    async def start(self) -> None:
        if self._settings.is_production:
            raise RuntimeError("MockKafkaConsumer is strictly forbidden in production")
        self._started = True
        logger.debug("MockKafkaConsumer started")

    async def stop(self) -> None:
        self._started = False
        logger.debug("MockKafkaConsumer stopped")

    @property
    def is_running(self) -> bool:
        return self._started

    def subscribe(self, topics: list[str]) -> None:
        self._subscribed_topics = set(topics)
        for topic in topics:
            tp = TopicPartition(topic, 0)
            if tp not in self._partitions:
                self._partitions[tp] = []
                self._fetch_offsets[tp] = 0

    def add_record(
        self,
        topic: str,
        value: bytes | str | EventEnvelope,
        partition: int = 0,
        key: bytes | str | None = None,
        offset: int | None = None,
        timestamp: int | None = None,
    ) -> ConsumerRecord:
        """Helper to inject records for testing."""
        tp = TopicPartition(topic, partition)
        if tp not in self._partitions:
            self._partitions[tp] = []
            self._fetch_offsets[tp] = 0

        current_offset = offset if offset is not None else len(self._partitions[tp])

        val_bytes: bytes
        if isinstance(value, EventEnvelope):
            val_bytes = value.to_json_bytes()
        elif isinstance(value, str):
            val_bytes = value.encode("utf-8")
        else:
            val_bytes = value

        key_bytes: bytes | None = None
        if isinstance(key, str):
            key_bytes = key.encode("utf-8")
        elif isinstance(key, bytes):
            key_bytes = key

        rec = ConsumerRecord(
            topic=topic,
            partition=partition,
            offset=current_offset,
            key=key_bytes,
            value=val_bytes,
            timestamp=timestamp or int(datetime.now(UTC).timestamp() * 1000),
        )
        self._partitions[tp].append(rec)
        return rec

    def pause(self, *partitions: TopicPartition) -> None:
        """Pause fetching from the specified partitions."""
        for tp in partitions:
            self._paused_partitions.add(tp)

    def resume(self, *partitions: TopicPartition) -> None:
        """Resume fetching from the specified partitions."""
        for tp in partitions:
            self._paused_partitions.discard(tp)

    def paused(self) -> set[TopicPartition]:
        """Return the set of currently paused partitions."""
        return set(self._paused_partitions)

    async def getmany(
        self,
        *partitions: TopicPartition,
        timeout_ms: int = 1000,
        max_records: int = 50,
    ) -> dict[TopicPartition, list[ConsumerRecord]]:
        """Fetch records from subscribed partitions starting at fetch_offsets."""
        if not self._started:
            raise KafkaConnectionError("MockKafkaConsumer is not started")

        result: dict[TopicPartition, list[ConsumerRecord]] = {}
        target_tps = partitions or list(self._partitions.keys())

        for tp in target_tps:
            if tp.topic not in self._subscribed_topics:
                continue
            if tp in self._paused_partitions:
                continue
            records = self._partitions.get(tp, [])
            current_idx = self._fetch_offsets.get(tp, 0)
            eligible = records[current_idx : current_idx + max_records]
            if eligible:
                result[tp] = eligible
                self._fetch_offsets[tp] = current_idx + len(eligible)

        return result

    async def commit(self, offsets: dict[TopicPartition, int] | None = None) -> None:
        """Record committed offsets."""
        if not self._started:
            raise KafkaConnectionError("MockKafkaConsumer is not started")

        if offsets:
            for tp, off in offsets.items():
                self._committed_offsets[tp] = off
        else:
            for tp, off in self._fetch_offsets.items():
                self._committed_offsets[tp] = off

    async def committed(self, partition: TopicPartition) -> int | None:
        return self._committed_offsets.get(partition)

    def seek(self, partition: TopicPartition, offset: int) -> None:
        """Seek partition fetch position back for retry or replay testing."""
        self._fetch_offsets[partition] = offset


class BaseKafkaConsumer(EventConsumer):
    """
    Asynchronous Kafka consumer engine implementing Strategy A reliability:
    1. Single ACID database transaction enclosing consumer_inbox claim and business mutation.
    2. Idempotent deduplication: duplicate events skip business logic and commit offset.
    3. Manual offset commit: committed strictly AFTER the database transaction commits.
    4. Bounded exponential backoff with full jitter for transient retries.
    5. Dead-Letter Queue (DLQ) routing for poison messages and retries exhausted (>= 5).
    6. Offset committed only AFTER DLQ broker confirms durable receipt.
    7. Zero-PII logging and sanitized error messages.
    """

    def __init__(
        self,
        consumer_group: str,
        topics: list[str],
        session_factory: async_sessionmaker[AsyncSession],
        producer: EventProducer | None = None,
        config_settings: Settings | None = None,
        *,
        dlq_topic: str = DEFAULT_DLQ_TOPIC,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS,
        backoff_max_jitter_seconds: float = DEFAULT_BACKOFF_MAX_JITTER_SECONDS,
        consumer_impl: Any | None = None,
    ) -> None:
        self._consumer_group = consumer_group
        self._topics = list(topics)
        self._session_factory = session_factory
        self._settings = config_settings or settings
        self._producer = producer or get_kafka_producer(self._settings)
        self._dlq_topic = dlq_topic
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_max_seconds = backoff_max_seconds
        self._backoff_max_jitter_seconds = backoff_max_jitter_seconds

        # Production safety check
        if consumer_impl is None:
            if not self._settings.has_kafka:
                if self._settings.is_production:
                    raise RuntimeError(
                        "MockKafkaConsumer is strictly forbidden in production"
                    )
                self._consumer = MockKafkaConsumer(self._settings)
            else:
                self._consumer = None  # Lazily created AIOKafkaConsumer
        else:
            if (
                isinstance(consumer_impl, MockKafkaConsumer)
                and self._settings.is_production
            ):
                raise RuntimeError(
                    "MockKafkaConsumer is strictly forbidden in production"
                )
            self._consumer = consumer_impl

        self._running = False
        self._consume_task: asyncio.Task[None] | None = None
        self._paused_partitions: dict[TopicPartition, datetime] = {}

    @property
    def consumer_group(self) -> str:
        return self._consumer_group

    @property
    def topics(self) -> list[str]:
        return list(self._topics)

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the consumer and underlying Kafka connection."""
        if self._running:
            return

        if (
            isinstance(self._consumer, MockKafkaConsumer)
            and self._settings.is_production
        ):
            raise RuntimeError("MockKafkaConsumer is strictly forbidden in production")

        if not self._producer.is_connected:
            await self._producer.start()

        if self._consumer is None:
            # Real AIOKafkaConsumer. aiokafka takes assignor *classes*; the Java/librdkafka
            # name "cooperative-sticky" made every group join fail on a real broker
            # (AttributeError: 'str' object has no attribute 'metadata'), so the default
            # range assignor is used. Per-key ordering comes from partitioning, not the assignor.
            consumer_kwargs: dict[str, Any] = {
                "bootstrap_servers": self._settings.KAFKA_BOOTSTRAP_SERVERS,
                "group_id": self._consumer_group,
                "enable_auto_commit": False,
                "auto_offset_reset": self._settings.KAFKA_CONSUMER_AUTO_OFFSET_RESET
                if hasattr(self._settings, "KAFKA_CONSUMER_AUTO_OFFSET_RESET")
                else "earliest",
                "max_poll_records": 50,
                **build_kafka_auth_kwargs(self._settings),
            }
            self._consumer = AIOKafkaConsumer(
                *self._topics,
                **consumer_kwargs,
            )

        await self._consumer.start()
        if hasattr(self._consumer, "subscribe"):
            self._consumer.subscribe(self._topics)

        self._running = True
        logger.info(
            "BaseKafkaConsumer started for group '%s' on topics %s",
            self._consumer_group,
            self._topics,
        )

    async def stop(self) -> None:
        """Stop the consumer and cancel background polling tasks."""
        self._running = False
        if self._consume_task and not self._consume_task.done():
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass

        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception as e:
                logger.warning(
                    "Error stopping consumer for group '%s': %s",
                    self._consumer_group,
                    e,
                )

        logger.info("BaseKafkaConsumer stopped for group '%s'", self._consumer_group)

    def pause_partition(
        self,
        tp: TopicPartition,
        until: datetime,
        seek_offset: int | None = None,
    ) -> None:
        """
        Durable retry scheduling: pause a specific partition until a scheduled timestamp
        and rewind its fetch offset to the uncommitted record.
        Unrelated partitions continue processing without obstruction.
        """
        sched_utc = until if until.tzinfo is not None else until.replace(tzinfo=UTC)
        self._paused_partitions[tp] = sched_utc

        if hasattr(self._consumer, "pause"):
            self._consumer.pause(tp)
        if seek_offset is not None and hasattr(self._consumer, "seek"):
            self._consumer.seek(tp, seek_offset)

        logger.info(
            "Partition %s:%d paused until %s (offset rewind to %s) to prevent hot redelivery",
            tp.topic,
            tp.partition,
            sched_utc.isoformat(),
            seek_offset,
        )

    def resume_partition(self, tp: TopicPartition) -> None:
        """Resume fetching from a paused partition."""
        self._paused_partitions.pop(tp, None)
        if hasattr(self._consumer, "resume"):
            self._consumer.resume(tp)
        logger.info("Partition %s:%d resumed", tp.topic, tp.partition)

    def resume_ready_partitions(
        self, now: datetime | None = None
    ) -> list[TopicPartition]:
        """Resume all partitions whose scheduled retry backoff time has elapsed."""
        current_time = now or datetime.now(UTC)
        resumed: list[TopicPartition] = []
        for tp, until in list(self._paused_partitions.items()):
            sched = until if until.tzinfo is not None else until.replace(tzinfo=UTC)
            if current_time >= sched:
                self.resume_partition(tp)
                resumed.append(tp)
        return resumed

    def paused_partitions(self) -> dict[TopicPartition, datetime]:
        """Return a mapping of currently paused partitions and their scheduled resume times."""
        return dict(self._paused_partitions)

    async def commit_offset(self, record: ConsumerRecord) -> None:
        """
        Manually commit the offset for a processed record strictly after DB transaction commits.
        In Kafka, committing offset N means the next record to fetch is N + 1.
        """
        tp = TopicPartition(record.topic, record.partition)
        target_offset = record.offset + 1

        try:
            if hasattr(self._consumer, "commit"):
                await self._consumer.commit({tp: target_offset})
                logger.debug(
                    "Committed offset %d on %s:%d for group %s",
                    target_offset,
                    record.topic,
                    record.partition,
                    self._consumer_group,
                )
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            raise ConsumerCommitError(
                f"Failed to commit offset {target_offset} on {record.topic}:{record.partition}: {sanitized}"
            ) from exc

    async def _route_to_dlq(
        self,
        *,
        original_topic: str,
        original_partition: int,
        original_offset: int,
        raw_value: bytes | None,
        error_message: str,
        correlation_id: str | None = None,
        event_id: uuid.UUID | None = None,
        aggregate_id: uuid.UUID | None = None,
    ) -> None:
        """
        Publish an unrecoverable poison message or retry-exhausted event to the Dead-Letter Queue.
        Awaits broker acknowledgement before returning.
        """
        raw_preview: str = ""
        if raw_value:
            try:
                raw_preview = raw_value.decode("utf-8")[:500]
            except Exception:
                raw_preview = "<binary data>"

        # Redact potential credentials, secrets, cards, or passwords before including in DLQ payload
        sanitized_preview = sanitize_error_message(Exception(raw_preview))
        if sanitized_preview.startswith("Exception: "):
            sanitized_preview = sanitized_preview[len("Exception: ") :]

        # Deterministic UUID generation ensures duplicate DLQ publications for the same record are idempotent
        dlq_event_id = event_id or uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{self._consumer_group}:{original_topic}:{original_partition}:{original_offset}",
        )
        dlq_agg_id = aggregate_id or dlq_event_id
        dlq_envelope_id = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"dlq:{self._consumer_group}:{original_topic}:{original_partition}:{original_offset}",
        )

        dlq_envelope = EventEnvelope(
            event_id=dlq_envelope_id,
            event_type="dead_letter.failed",
            event_version=1,
            aggregate_type="DeadLetter",
            aggregate_id=dlq_agg_id,
            aggregate_version=1,
            correlation_id=correlation_id,
            producer="basket-backend@0.1.0",
            partition_key=str(dlq_agg_id),
            payload={
                "failed_event_id": str(dlq_event_id),
                "original_topic": original_topic,
                "original_partition": original_partition,
                "original_offset": original_offset,
                "consumer_group": self._consumer_group,
                "error_message": sanitize_error_message(Exception(error_message)),
                "raw_payload_preview": sanitized_preview,
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )

        try:
            await self._producer.send(self._dlq_topic, dlq_envelope)
            logger.info(
                "Successfully routed unrecoverable record from %s:%d:%d to DLQ '%s'",
                original_topic,
                original_partition,
                original_offset,
                self._dlq_topic,
            )
        except Exception as exc:
            sanitized = sanitize_error_message(exc)
            raise DeadLetterPublishError(
                f"Failed to publish dead-letter record to topic '{self._dlq_topic}': {sanitized}"
            ) from exc

    async def process_record(
        self, record: ConsumerRecord, session: AsyncSession | None = None
    ) -> bool:
        """
        Process a single Kafka record using Strategy A ACID reliability:
        Returns True if processing succeeded or offset should be advanced (duplicate / DLQ).
        Returns False if transient error occurred and offset should NOT be advanced.
        """
        # Step 1: Parse & Validate Envelope
        raw_bytes = record.value
        envelope: EventEnvelope | None = None
        parse_error: Exception | None = None

        if raw_bytes is None:
            parse_error = ValueError("ConsumerRecord contains null value")
        else:
            try:
                envelope = EventEnvelope.from_json_bytes(raw_bytes)
            except Exception as exc:
                parse_error = exc

        # Poison message isolation
        if parse_error is not None:
            sanitized = sanitize_error_message(parse_error)
            logger.error(
                "Poison message on %s:%d:%d: %s. Routing to DLQ.",
                record.topic,
                record.partition,
                record.offset,
                sanitized,
            )
            # Deterministic synthetic UUID for poison message
            synthetic_id = uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{self._consumer_group}:{record.topic}:{record.partition}:{record.offset}",
            )

            # Check if poison message was already published in a previous run before crash
            async with self._session_factory() as check_session:
                existing = await get_inbox_record(
                    check_session,
                    self._consumer_group,
                    synthetic_id,
                )
                if (
                    existing
                    and existing.status == InboxStatus.DEAD_LETTER.value
                    and existing.dlq_published_at is not None
                ):
                    logger.info(
                        "Poison message %s was already published to DLQ at %s; skipping DLQ publish and committing offset.",
                        synthetic_id,
                        existing.dlq_published_at,
                    )
                    await self.commit_offset(record)
                    return True

            # Step A: Persist DEAD_LETTER intent in consumer_inbox (dlq_published_at=None)
            try:
                async with self._session_factory() as dlq_session:
                    async with dlq_session.begin():
                        row = await get_inbox_record(
                            dlq_session,
                            self._consumer_group,
                            synthetic_id,
                            for_update=True,
                        )
                        if row:
                            row.status = InboxStatus.DEAD_LETTER.value
                            row.retry_count = self._max_retries
                            row.last_error = sanitized
                            row.dlq_published_at = None
                        else:
                            dlq_session.add(
                                ConsumerInbox(
                                    consumer_group=self._consumer_group,
                                    event_id=synthetic_id,
                                    event_type="poison.message",
                                    schema_version=1,
                                    aggregate_type="PoisonMessage",
                                    aggregate_id=synthetic_id,
                                    aggregate_version=1,
                                    status=InboxStatus.DEAD_LETTER.value,
                                    retry_count=self._max_retries,
                                    last_error=sanitized,
                                    dlq_published_at=None,
                                )
                            )
            except Exception as e:
                logger.warning("Could not persist poison message to inbox: %s", e)

            # Step B: Route to DLQ broker first and await confirmation
            await self._route_to_dlq(
                original_topic=record.topic,
                original_partition=record.partition,
                original_offset=record.offset,
                raw_value=raw_bytes,
                error_message=sanitized,
                event_id=synthetic_id,
                aggregate_id=synthetic_id,
            )

            # Step C: Record dlq_published_at timestamp in database
            try:
                async with self._session_factory() as ack_session:
                    async with ack_session.begin():
                        row = await get_inbox_record(
                            ack_session,
                            self._consumer_group,
                            synthetic_id,
                            for_update=True,
                        )
                        if row:
                            row.dlq_published_at = datetime.now(UTC)
                            row.processed_at = datetime.now(UTC)
            except Exception as e:
                logger.warning(
                    "Could not record poison message dlq_published_at: %s", e
                )

            # Step D: Offset committed ONLY after DLQ broker confirms receipt and DB updated
            await self.commit_offset(record)
            return True

        assert envelope is not None

        # Step 2: Atomic Processing Invariant (Strategy A)
        if session is not None:
            return await self._execute_strategy_a(record, envelope, session)

        async with self._session_factory() as owned_session:
            return await self._execute_strategy_a(record, envelope, owned_session)

    async def _execute_strategy_a(
        self,
        record: ConsumerRecord,
        envelope: EventEnvelope,
        session: AsyncSession,
    ) -> bool:
        """
        Inner execution of Strategy A:
        ACID database transaction enclosing inbox claim and business mutation.
        """
        is_duplicate = False
        should_route_dlq = False
        dlq_error_msg: str = ""
        transient_failure = False
        failed_retry_count = 0

        try:
            async with session.begin():
                # Query inbox FOR UPDATE to serialize parallel consumer attempts for the same event
                inbox_row = await get_inbox_record(
                    session,
                    self._consumer_group,
                    envelope.event_id,
                    for_update=True,
                )

                if inbox_row is not None:
                    if inbox_row.status == InboxStatus.SUCCEEDED.value:
                        logger.info(
                            "Duplicate event %s already SUCCEEDED for group %s; skipping business logic.",
                            envelope.event_id,
                            self._consumer_group,
                        )
                        is_duplicate = True
                    elif inbox_row.status == InboxStatus.DEAD_LETTER.value:
                        if inbox_row.dlq_published_at is not None:
                            logger.info(
                                "Event %s was already routed to DEAD_LETTER and published at %s; skipping duplicate DLQ publish and committing offset.",
                                envelope.event_id,
                                inbox_row.dlq_published_at,
                            )
                            is_duplicate = True
                        else:
                            logger.warning(
                                "Event %s marked DEAD_LETTER but dlq_published_at is NULL (crash recovery); resuming DLQ publication flow.",
                                envelope.event_id,
                            )
                            should_route_dlq = True
                            dlq_error_msg = (
                                inbox_row.last_error or "Crash recovery DLQ publication"
                            )
                            failed_retry_count = inbox_row.retry_count
                    else:
                        # Row exists in PENDING, PROCESSING, or FAILED
                        # Check durable retry schedule to prevent hot redelivery loop
                        if (
                            inbox_row.status == InboxStatus.FAILED.value
                            and inbox_row.next_attempt_at is not None
                        ):
                            now = datetime.now(UTC)
                            sched = inbox_row.next_attempt_at
                            if sched.tzinfo is None:
                                sched = sched.replace(tzinfo=UTC)
                            if sched > now:
                                remaining = (sched - now).total_seconds()
                                logger.info(
                                    "Event %s for group %s retry scheduled at %s (%.1fs remaining); pausing partition to prevent hot redelivery loop",
                                    envelope.event_id,
                                    self._consumer_group,
                                    sched,
                                    remaining,
                                )
                                tp = TopicPartition(record.topic, record.partition)
                                self.pause_partition(
                                    tp, until=sched, seek_offset=record.offset
                                )
                                return False

                        inbox_row.status = InboxStatus.PROCESSING.value
                        failed_retry_count = inbox_row.retry_count
                else:
                    # Fresh event: insert inbox record in PROCESSING status
                    inbox_row = ConsumerInbox(
                        consumer_group=self._consumer_group,
                        event_id=envelope.event_id,
                        event_type=envelope.event_type,
                        schema_version=envelope.event_version,
                        aggregate_type=envelope.aggregate_type,
                        aggregate_id=envelope.aggregate_id,
                        aggregate_version=envelope.aggregate_version,
                        status=InboxStatus.PROCESSING.value,
                        retry_count=0,
                        correlation_id=envelope.correlation_id,
                    )
                    session.add(inbox_row)
                    failed_retry_count = 0

                if not is_duplicate:
                    try:
                        # Execute domain business operation inside active ACID boundary
                        await self.handle_event(envelope, session)
                        inbox_row.status = InboxStatus.SUCCEEDED.value
                        inbox_row.processed_at = datetime.now(UTC)
                        inbox_row.last_error = None
                        # Transaction will commit successfully upon block exit
                    except Exception as exc:
                        sanitized = sanitize_error_message(exc)
                        is_perm = classify_failure(exc)
                        new_retry_count = inbox_row.retry_count + 1
                        retries_exhausted = new_retry_count >= self._max_retries
                        failed_retry_count = new_retry_count

                        if is_perm or retries_exhausted:
                            # Permanent error or retry threshold reached: Mark DEAD_LETTER
                            logger.error(
                                "Event %s failed permanently or retries exhausted (%d/%d): %s. Flagged for DLQ.",
                                envelope.event_id,
                                new_retry_count,
                                self._max_retries,
                                sanitized,
                            )
                            should_route_dlq = True
                            dlq_error_msg = sanitized
                            raise _TransientHandlerError(
                                sanitized, new_retry_count
                            ) from exc
                        else:
                            # Transient retryable error
                            logger.warning(
                                "Event %s transient error on attempt %d/%d: %s. Rolling back.",
                                envelope.event_id,
                                new_retry_count,
                                self._max_retries,
                                sanitized,
                            )
                            transient_failure = True
                            dlq_error_msg = sanitized
                            raise _TransientHandlerError(
                                sanitized, new_retry_count
                            ) from exc

        except _TransientHandlerError:
            # Transaction cleanly rolled back
            pass
        except Exception as exc:
            err_str = str(exc)
            if (
                "uq_consumer_inbox_group_event" in err_str
                or "duplicate key value" in err_str
            ):
                logger.info(
                    "Concurrent insert race detected on consumer_inbox (%s, %s); treating as duplicate",
                    self._consumer_group,
                    envelope.event_id,
                )
                is_duplicate = True
            else:
                sanitized = sanitize_error_message(exc)
                logger.error(
                    "Unexpected database error processing event %s: %s",
                    envelope.event_id,
                    sanitized,
                )
                transient_failure = True
                dlq_error_msg = sanitized

        # Handlers outside the main transaction
        if is_duplicate:
            # Commit Kafka offset immediately and safely advance
            await self.commit_offset(record)
            return True

        if should_route_dlq:
            # Step A: In DB transaction, mark DEAD_LETTER with dlq_published_at=NULL (intent recorded)
            async with self._session_factory() as dlq_session:
                async with dlq_session.begin():
                    row = await get_inbox_record(
                        dlq_session,
                        self._consumer_group,
                        envelope.event_id,
                        for_update=True,
                    )
                    if row:
                        row.status = InboxStatus.DEAD_LETTER.value
                        row.retry_count = failed_retry_count
                        row.last_error = dlq_error_msg
                        row.dlq_published_at = None
                    else:
                        dlq_session.add(
                            ConsumerInbox(
                                consumer_group=self._consumer_group,
                                event_id=envelope.event_id,
                                event_type=envelope.event_type,
                                schema_version=envelope.event_version,
                                aggregate_type=envelope.aggregate_type,
                                aggregate_id=envelope.aggregate_id,
                                aggregate_version=envelope.aggregate_version,
                                status=InboxStatus.DEAD_LETTER.value,
                                retry_count=failed_retry_count,
                                last_error=dlq_error_msg,
                                processed_at=None,
                                correlation_id=envelope.correlation_id,
                                dlq_published_at=None,
                            )
                        )

            # Step B: Route to DLQ broker with deterministic envelope ID and await broker ACK
            await self._route_to_dlq(
                original_topic=record.topic,
                original_partition=record.partition,
                original_offset=record.offset,
                raw_value=record.value,
                error_message=dlq_error_msg,
                correlation_id=envelope.correlation_id,
                event_id=envelope.event_id,
                aggregate_id=envelope.aggregate_id,
            )

            # Step C: Record dlq_published_at timestamp in database
            async with self._session_factory() as ack_session:
                async with ack_session.begin():
                    row = await get_inbox_record(
                        ack_session,
                        self._consumer_group,
                        envelope.event_id,
                        for_update=True,
                    )
                    if row:
                        row.dlq_published_at = datetime.now(UTC)
                        row.processed_at = datetime.now(UTC)

            # Step D: Commit Kafka offset ONLY after DLQ confirmation and database update
            await self.commit_offset(record)
            return True

        if transient_failure:
            next_attempt = compute_next_attempt_at(
                failed_retry_count,
                base_seconds=self._backoff_base_seconds,
                max_seconds=self._backoff_max_seconds,
                max_jitter_seconds=self._backoff_max_jitter_seconds,
            )
            # Record FAILED attempt and scheduled next_attempt_at in inbox in clean transaction
            async with self._session_factory() as fail_session:
                async with fail_session.begin():
                    row = await get_inbox_record(
                        fail_session,
                        self._consumer_group,
                        envelope.event_id,
                        for_update=True,
                    )
                    if row:
                        row.status = InboxStatus.FAILED.value
                        row.retry_count = failed_retry_count
                        row.next_attempt_at = next_attempt
                        row.last_error = dlq_error_msg
                    else:
                        fail_session.add(
                            ConsumerInbox(
                                consumer_group=self._consumer_group,
                                event_id=envelope.event_id,
                                event_type=envelope.event_type,
                                schema_version=envelope.event_version,
                                aggregate_type=envelope.aggregate_type,
                                aggregate_id=envelope.aggregate_id,
                                aggregate_version=envelope.aggregate_version,
                                status=InboxStatus.FAILED.value,
                                retry_count=failed_retry_count,
                                next_attempt_at=next_attempt,
                                last_error=dlq_error_msg,
                                correlation_id=envelope.correlation_id,
                            )
                        )

            # Pause partition and rewind offset so we do not busy-poll
            tp = TopicPartition(record.topic, record.partition)
            self.pause_partition(tp, until=next_attempt, seek_offset=record.offset)
            return False

        # Fresh event succeeded: Commit Kafka offset strictly AFTER DB commit
        await self.commit_offset(record)
        return True

    async def poll_and_process_batch(self, max_records: int = 50) -> int:
        """Poll a batch of records from the consumer and process them sequentially."""
        if not self._running or self._consumer is None:
            return 0

        # Step 0: Resume any paused partitions whose backoff time has elapsed
        self.resume_ready_partitions()

        try:
            records_by_partition = await self._consumer.getmany(
                timeout_ms=1000, max_records=max_records
            )
        except Exception as exc:
            logger.warning(
                "Error polling records for group %s: %s",
                self._consumer_group,
                exc,
            )
            return 0

        total_processed = 0
        for tp, records in records_by_partition.items():
            for record in records:
                try:
                    success = await self.process_record(record)
                    if success:
                        total_processed += 1
                    else:
                        # Transient failure: apply backoff and break partition processing
                        # to preserve intra-partition order
                        logger.info(
                            "Transient failure on %s:%d, pausing partition batch",
                            tp.topic,
                            tp.partition,
                        )
                        break
                except Exception as exc:
                    logger.error(
                        "Unexpected error processing record %s:%d:%d: %s",
                        record.topic,
                        record.partition,
                        record.offset,
                        sanitize_error_message(exc),
                    )
                    break
        return total_processed


def get_kafka_consumer(
    consumer_group: str,
    topics: list[str],
    config_settings: Settings | None = None,
    *,
    force_mock: bool = False,
) -> Any:
    """Connection factory returning configured AIOKafkaConsumer or MockKafkaConsumer."""
    active_settings = config_settings or settings
    if force_mock or not active_settings.has_kafka:
        if active_settings.is_production:
            raise RuntimeError("MockKafkaConsumer is strictly forbidden in production")
        mock = MockKafkaConsumer(active_settings)
        mock.subscribe(topics)
        return mock
    consumer_kwargs: dict[str, Any] = {
        "bootstrap_servers": active_settings.KAFKA_BOOTSTRAP_SERVERS,
        "group_id": consumer_group,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        "max_poll_records": 50,
        **build_kafka_auth_kwargs(active_settings),
    }
    return AIOKafkaConsumer(
        *topics,
        **consumer_kwargs,
    )
