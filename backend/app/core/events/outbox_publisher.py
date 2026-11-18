from __future__ import annotations

import asyncio
import logging
import random
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.core.events.envelope import EventEnvelope
from app.core.events.kafka import (
    EventProducer,
    KafkaConnectionError,
    KafkaPublishError,
    MockKafkaProducer,
)
from app.modules.orders.models import OutboxEvent, OutboxStatus

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BATCH_SIZE: int = 20
DEFAULT_LEASE_SECONDS: float = 30.0
DEFAULT_BATCH_WINDOW_SECONDS: float = 15.0
DEFAULT_PER_EVENT_TIMEOUT_SECONDS: float = 2.0
DEFAULT_POLL_INTERVAL_SECONDS: float = 1.0
DEFAULT_MAX_RETRIES: int = 5
MAX_RETRIES: int = 5
BACKOFF_BASE_SECONDS: float = 1.0
BACKOFF_MAX_SECONDS: float = 300.0
BACKOFF_MAX_JITTER_SECONDS: float = 2.0

PERMANENT_ERROR_TYPES = (
    ValidationError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)


@dataclass(frozen=True)
class ClaimedOutboxItem:
    """Detached representation of an outbox event claimed for processing."""

    id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    retry_count: int
    correlation_id: str | None
    created_at: datetime
    aggregate_version: int | None = None


def get_topic_for_event(event_type: str) -> str:
    """
    Route event type to the appropriate canonical Kafka topic.
    - order.* -> basket.events.orders
    - payment.* -> basket.events.payments
    - product.*, catalogue.*, listing.*, variant.* -> basket.events.catalogue
    - inventory.*, store_inventory.* -> basket.events.inventory
    """
    etype = event_type.strip().lower()
    if etype.startswith("order."):
        return "basket.events.orders"
    if etype.startswith("payment."):
        return "basket.events.payments"
    if any(
        etype.startswith(prefix)
        for prefix in ("product.", "catalogue.", "listing.", "variant.")
    ):
        return "basket.events.catalogue"
    if any(etype.startswith(prefix) for prefix in ("inventory.", "store_inventory.")):
        return "basket.events.inventory"
    raise ValueError(f"No canonical Kafka topic mapping for event_type '{event_type}'")


def resolve_aggregate_version(
    aggregate_type: str,
    event_type: str,
    record_version: int | None,
    payload: dict[str, Any],
) -> int:
    """
    Resolve aggregate version preserving strict version semantics:
    1. If explicit aggregate_version was stored on OutboxEvent, use it.
    2. Else if explicit 'aggregate_version' is present in payload, use it.
    3. Else for legacy Order events (persisted before Phase 3 aggregate_version tracking):
       - 'order.created' -> version 1 (initial state creation)
       - 'order.confirmed' -> version 2 (transition from PENDING_PAYMENT to CONFIRMED)
       - 'order.cancelled' -> version 2 (transition from PENDING_PAYMENT to CANCELLED)
    4. For any other event without an aggregate version, raise ValueError.
       NEVER fabricate aggregate versions, silently default to 1, or substitute timestamps.
    """
    if record_version is not None:
        if isinstance(record_version, int) and record_version >= 1:
            return record_version
        raise ValueError(
            f"Invalid record aggregate_version '{record_version}' for event '{event_type}'"
        )

    if "aggregate_version" in payload:
        pv = payload["aggregate_version"]
        if isinstance(pv, int) and pv >= 1:
            return pv
        raise ValueError(
            f"Invalid payload 'aggregate_version' '{pv}' for event '{event_type}'"
        )

    agg_type = aggregate_type.strip().lower()
    etype = event_type.strip().lower()

    # Explicit domain compatibility mapping for legacy Order events only
    if agg_type == "order":
        if etype == "order.created":
            return 1
        if etype in ("order.confirmed", "order.cancelled"):
            return 2

    raise ValueError(
        f"Outbox event '{event_type}' on aggregate '{aggregate_type}' is missing required "
        f"'aggregate_version'. Refusing to fabricate version."
    )


def compute_next_attempt_at(
    retry_count: int,
    now: datetime | None = None,
    *,
    custom_jitter: float | None = None,
    base_seconds: float = BACKOFF_BASE_SECONDS,
    max_seconds: float = BACKOFF_MAX_SECONDS,
    max_jitter_seconds: float = BACKOFF_MAX_JITTER_SECONDS,
) -> datetime:
    """
    Compute durable next retry timestamp with bounded exponential backoff and full jitter:
    T_backoff = min(max_seconds, base_seconds * (2 ** retry_count) + jitter)
    """
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    # Cap exponential calculation to avoid float overflow
    bounded_power = min(max(0, retry_count), 16)
    exp_component = base_seconds * (2**bounded_power)
    jitter = (
        custom_jitter
        if custom_jitter is not None
        else random.uniform(0.0, max_jitter_seconds)
    )
    delay_seconds = min(max_seconds, exp_component + jitter)
    return now + timedelta(seconds=delay_seconds)


def classify_failure(exc: Exception) -> bool:
    """
    Classify failure mode:
    Returns True if failure is permanent (non-retryable payload/schema errors).
    Returns False if failure is transient (network timeout, broker unavailability).
    """
    if isinstance(exc, PERMANENT_ERROR_TYPES):
        return True
    if isinstance(
        exc,
        (
            KafkaPublishError,
            KafkaConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            OSError,
        ),
    ):
        return False
    if exc.__cause__ is not None:
        return classify_failure(exc.__cause__)
    return False


def sanitize_error_message(exc: Exception, max_length: int = 1000) -> str:
    """
    Sanitize exception message by redacting potential credentials, tokens, or payment details.
    """
    raw = f"{type(exc).__name__}: {str(exc)}"
    sanitized = re.sub(
        r"(key|secret|password|token|auth|cvv|card|card_number|account)=['\"][^'\"]+['\"]",
        r"\1=***",
        raw,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(rzp_live_|rzp_test_)[A-Za-z0-9]+",
        r"\1***",
        sanitized,
    )
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer ***", sanitized, flags=re.IGNORECASE
    )
    if len(sanitized) > max_length:
        return sanitized[: max_length - 3] + "..."
    return sanitized


async def claim_outbox_batch(
    session: AsyncSession,
    worker_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> list[ClaimedOutboxItem]:
    """
    Atomically claim an outbox batch using SELECT ... FOR UPDATE SKIP LOCKED.
    Eligible rows:
    - status = 'PENDING' AND next_attempt_at <= now
    - status = 'PROCESSING' AND claim_expires_at <= now (expired lease crash recovery)

    Updates claimed rows to PROCESSING with worker lease.
    Caller commits this transaction before initiating network publishing.
    """
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    effective_batch_size = max(1, min(batch_size, DEFAULT_BATCH_SIZE))
    claim_expires_at = now + timedelta(seconds=lease_seconds)

    stmt = (
        select(OutboxEvent)
        .where(
            (
                (OutboxEvent.status == OutboxStatus.PENDING.value)
                & (OutboxEvent.next_attempt_at <= now)
            )
            | (
                (OutboxEvent.status == OutboxStatus.PROCESSING.value)
                & (OutboxEvent.claim_expires_at <= now)
            )
        )
        .order_by(OutboxEvent.next_attempt_at.asc(), OutboxEvent.created_at.asc())
        .limit(effective_batch_size)
        .with_for_update(skip_locked=True)
    )

    res = await session.execute(stmt)
    events = list(res.scalars().all())
    if not events:
        return []

    claimed_items: list[ClaimedOutboxItem] = []
    for event in events:
        event.status = OutboxStatus.PROCESSING.value
        event.claimed_by = worker_id
        event.claim_expires_at = claim_expires_at
        claimed_items.append(
            ClaimedOutboxItem(
                id=event.id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                schema_version=event.schema_version,
                payload=dict(event.payload or {}),
                retry_count=event.retry_count,
                correlation_id=event.correlation_id,
                created_at=event.created_at,
                aggregate_version=event.aggregate_version,
            )
        )

    return claimed_items


class OutboxPublisherWorker:
    """
    Continuous transactional outbox publisher with multi-worker concurrency,
    lease expiration recovery, durable backoff retry, and lifecycle management.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
        producer: EventProducer,
        worker_id: str | None = None,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_batch_window_seconds: float = DEFAULT_BATCH_WINDOW_SECONDS,
        per_event_timeout_seconds: float = DEFAULT_PER_EVENT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        custom_jitter: float | None = None,
        config_settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.producer = producer
        self.worker_id = worker_id or f"outbox-worker-{uuid.uuid4().hex[:8]}"
        self.batch_size = max(1, min(batch_size, DEFAULT_BATCH_SIZE))
        self.lease_seconds = lease_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_batch_window_seconds = max_batch_window_seconds
        self.per_event_timeout_seconds = per_event_timeout_seconds
        self.max_retries = max_retries
        self._custom_jitter = custom_jitter
        self._settings = config_settings or settings
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def publish_batch(self, now: datetime | None = None) -> int:
        """
        Execute a single batch iteration:
        1. Claim batch within dedicated short-lived DB transaction (FOR UPDATE SKIP LOCKED).
        2. Release DB transaction locks before remote network operations.
        3. Publish each event individually with per-event timeout and batch window check.
        4. Acknowledge published events or record failure state with lease ownership checks.
        Returns the number of events successfully published to Kafka and acknowledged in DB.
        """
        if now is None:
            now = datetime.now(UTC)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        async with self.session_factory() as claim_session:
            async with claim_session.begin():
                claimed_items = await claim_outbox_batch(
                    session=claim_session,
                    worker_id=self.worker_id,
                    batch_size=self.batch_size,
                    lease_seconds=self.lease_seconds,
                    now=now,
                )

        if not claimed_items:
            return 0

        logger.info(
            "Worker %s claimed %d outbox event(s)",
            self.worker_id,
            len(claimed_items),
        )

        batch_start_mono = time.monotonic()
        successful_count = 0

        for idx, item in enumerate(claimed_items):
            # Enforce batch window deadline (15s default)
            elapsed = time.monotonic() - batch_start_mono
            if elapsed > self.max_batch_window_seconds:
                unprocessed = claimed_items[idx:]
                logger.warning(
                    "Worker %s reached max batch window deadline (%.2fs > %.2fs); "
                    "relinquishing remaining %d event(s) to avoid lease expiry",
                    self.worker_id,
                    elapsed,
                    self.max_batch_window_seconds,
                    len(unprocessed),
                )
                await self._relinquish_claimed_events(unprocessed)
                break

            succeeded = await self._process_single_event(item, now)
            if succeeded:
                successful_count += 1

        return successful_count

    async def _relinquish_claimed_events(self, items: list[ClaimedOutboxItem]) -> None:
        """Safely reset un-sent batch items back to PENDING immediately upon batch window expiry."""
        if not items:
            return
        try:
            item_ids = [it.id for it in items]
            async with self.session_factory() as session:
                async with session.begin():
                    stmt = (
                        update(OutboxEvent)
                        .where(
                            OutboxEvent.id.in_(item_ids),
                            OutboxEvent.claimed_by == self.worker_id,
                            OutboxEvent.status == OutboxStatus.PROCESSING.value,
                        )
                        .values(
                            status=OutboxStatus.PENDING.value,
                            claim_expires_at=None,
                        )
                    )
                    await session.execute(stmt)
            logger.info(
                "Worker %s explicitly relinquished %d un-sent items back to PENDING",
                self.worker_id,
                len(items),
            )
        except Exception as exc:
            logger.error(
                "Worker %s failed to explicitly relinquish items: %s",
                self.worker_id,
                exc,
            )

    async def _process_single_event(
        self, item: ClaimedOutboxItem, batch_now: datetime
    ) -> bool:
        start_mono = time.monotonic()
        topic: str | None = None
        try:
            topic = get_topic_for_event(item.event_type)
            payload = dict(item.payload or {})

            agg_version = resolve_aggregate_version(
                aggregate_type=item.aggregate_type,
                event_type=item.event_type,
                record_version=item.aggregate_version,
                payload=payload,
            )

            envelope = EventEnvelope(
                event_id=item.id,
                event_type=item.event_type,
                event_version=max(1, item.schema_version),
                aggregate_type=item.aggregate_type,
                aggregate_id=item.aggregate_id,
                aggregate_version=agg_version,
                occurred_at=item.created_at,
                correlation_id=item.correlation_id,
                payload=payload,
            )

            # Publish to Kafka with bounded timeout
            await self.producer.send(
                topic=topic,
                event=envelope,
                timeout=self.per_event_timeout_seconds,
            )

            # Acknowledge in PostgreSQL under strict lease ownership check
            now_utc = datetime.now(UTC)
            async with self.session_factory() as update_session:
                async with update_session.begin():
                    stmt = (
                        update(OutboxEvent)
                        .where(
                            OutboxEvent.id == item.id,
                            OutboxEvent.claimed_by == self.worker_id,
                        )
                        .values(
                            status=OutboxStatus.PUBLISHED.value,
                            published_at=now_utc,
                            claim_expires_at=None,
                            last_error=None,
                        )
                    )
                    res = await update_session.execute(stmt)
                    if res.rowcount == 0:
                        logger.warning(
                            "Lease lost for outbox event %s by worker %s; acknowledgement update skipped (rowcount=0)",
                            item.id,
                            self.worker_id,
                        )
                        return False

            elapsed_ms = (time.monotonic() - start_mono) * 1000
            logger.info(
                "Worker %s successfully published event %s [%s] to topic '%s' in %.2fms",
                self.worker_id,
                item.id,
                item.event_type,
                topic,
                elapsed_ms,
            )
            return True

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start_mono) * 1000
            is_permanent = classify_failure(exc)
            sanitized_err = sanitize_error_message(exc)

            logger.error(
                "Worker %s failed publishing event %s [%s] (permanent=%s) after %.2fms: %s",
                self.worker_id,
                item.id,
                item.event_type,
                is_permanent,
                elapsed_ms,
                sanitized_err,
            )

            await self._handle_event_failure(item, exc, is_permanent, sanitized_err)
            return False

    async def _handle_event_failure(
        self,
        item: ClaimedOutboxItem,
        exc: Exception,
        is_permanent: bool,
        sanitized_err: str,
    ) -> None:
        now_utc = datetime.now(UTC)
        new_retry = item.retry_count + 1

        if is_permanent or new_retry >= self.max_retries:
            new_status = OutboxStatus.FAILED.value
            next_attempt = None
            action_desc = "permanently failed"
        else:
            new_status = OutboxStatus.PENDING.value
            next_attempt = compute_next_attempt_at(
                retry_count=new_retry,
                now=now_utc,
                custom_jitter=self._custom_jitter,
            )
            action_desc = (
                f"scheduled for retry #{new_retry} at {next_attempt.isoformat()}"
            )

        try:
            async with self.session_factory() as update_session:
                async with update_session.begin():
                    values_to_update: dict[str, Any] = {
                        "status": new_status,
                        "retry_count": new_retry,
                        "claim_expires_at": None,
                        "last_error": sanitized_err,
                    }
                    if next_attempt is not None:
                        values_to_update["next_attempt_at"] = next_attempt

                    stmt = (
                        update(OutboxEvent)
                        .where(
                            OutboxEvent.id == item.id,
                            OutboxEvent.claimed_by == self.worker_id,
                        )
                        .values(**values_to_update)
                    )
                    res = await update_session.execute(stmt)
                    if res.rowcount == 0:
                        logger.warning(
                            "Lease lost for outbox event %s by worker %s while persisting failure state (rowcount=0)",
                            item.id,
                            self.worker_id,
                        )
                    else:
                        logger.info(
                            "Worker %s transitioned event %s to %s (%s)",
                            self.worker_id,
                            item.id,
                            new_status,
                            action_desc,
                        )
        except Exception as db_exc:
            logger.critical(
                "Worker %s failed to persist failure state for event %s: %s",
                self.worker_id,
                item.id,
                db_exc,
            )

    async def run(self) -> None:
        """Continuous polling loop."""
        logger.info("OutboxPublisherWorker %s starting poll loop", self.worker_id)
        while self._running:
            try:
                published_count = await self.publish_batch()
                if published_count == 0 and self._running:
                    await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                logger.info(
                    "OutboxPublisherWorker %s received cancellation request",
                    self.worker_id,
                )
                break
            except Exception as exc:
                logger.error(
                    "Unexpected error in worker %s poll loop: %s",
                    self.worker_id,
                    sanitize_error_message(exc),
                    exc_info=True,
                )
                if self._running:
                    await asyncio.sleep(self.poll_interval_seconds)

    async def start(self) -> None:
        """Start worker and background task with production safety check."""
        if self._running:
            return

        # Production safety guard: reject MockKafkaProducer
        if self._settings.ENVIRONMENT.lower() == "production" and isinstance(
            self.producer, MockKafkaProducer
        ):
            raise RuntimeError(
                "CRITICAL: MockKafkaProducer is strictly forbidden in production environment. "
                "A real AioKafkaEventProducer must be configured."
            )

        if not self.producer.is_connected:
            await self.producer.start()

        self._running = True
        self._task = asyncio.create_task(
            self.run(), name=f"outbox-publisher-{self.worker_id}"
        )
        logger.info("OutboxPublisherWorker %s started", self.worker_id)

    async def stop(self) -> None:
        """Cleanly cancel task and stop producer."""
        if not self._running and self._task is None:
            return

        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self.producer.is_connected:
            await self.producer.stop()

        logger.info("OutboxPublisherWorker %s stopped cleanly", self.worker_id)
