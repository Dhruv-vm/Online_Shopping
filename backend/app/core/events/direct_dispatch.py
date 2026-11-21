"""Direct (in-process) outbox delivery for deployments without Kafka
(Version 2.0 Phase C2, ``OUTBOX_DISPATCH=direct``).

The existing :class:`OutboxPublisherWorker` keeps doing everything it does for
Kafka – claiming events with ``FOR UPDATE SKIP LOCKED`` + leases, per-event
timeouts, retry with backoff, recording errors and attempts, and marking events
PUBLISHED – but its producer is :class:`DirectDispatchProducer`, which hands each
event to the same consumer handlers the Kafka consumers use
(``OpenSearchConsumer``, ``OrderProjectionConsumer``) through their
``process_record`` path. That path runs the handler and the ``consumer_inbox``
claim in one transaction keyed by (consumer group, event id), so a redelivered
event – or one also delivered through Kafka by another instance using the same
consumer groups – never takes effect twice.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from app.core.events.consumer import BaseKafkaConsumer, ConsumerRecord
from app.core.events.envelope import EventEnvelope
from app.core.events.kafka import EventProducer

logger = logging.getLogger(__name__)


async def _notify_live_clients(event: EventEnvelope) -> None:
    """Tell connected browsers the entity changed (direct mode has no Kafka
    stream for the realtime listener). Never fails delivery."""
    try:
        from app.modules.realtime.hub import hub

        await hub.publish_envelope(event)
    except Exception as exc:  # pragma: no cover - push is best effort
        logger.debug("Realtime notice skipped for %s: %s", event.event_id, exc)


class DirectDispatchError(RuntimeError):
    """A consumer handler could not process the event yet (transient)."""


class _NoBrokerConsumer:
    """Stand-in for the Kafka client inside consumers used for direct delivery:
    there is no broker, so there are no offsets to commit."""


class InboxOnlyDeadLetterProducer(EventProducer):
    """Dead-letter "publisher" for direct mode. The poison or retry-exhausted
    event is already stored durably as DEAD_LETTER in ``consumer_inbox`` by the
    consumer; with no broker it is logged instead of sent to a DLQ topic."""

    def __init__(self) -> None:
        self._connected = False

    async def start(self) -> None:
        self._connected = True

    async def stop(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return True

    async def send(
        self, topic: str, event: EventEnvelope, *, timeout: float | None = None
    ) -> None:
        logger.error(
            "Dead-lettered event %s [%s] kept in consumer_inbox (no DLQ broker in direct mode)",
            event.event_id,
            event.event_type,
        )


def direct_consumer_kwargs() -> dict:
    """Constructor arguments that make a BaseKafkaConsumer usable for direct
    delivery (no Kafka client, inbox-only dead letters)."""
    return {
        "consumer_impl": _NoBrokerConsumer(),
        "producer": InboxOnlyDeadLetterProducer(),
    }


class DirectDispatchProducer(EventProducer):
    """EventProducer that delivers to in-process consumers instead of Kafka."""

    def __init__(self, consumers: Sequence[BaseKafkaConsumer]) -> None:
        self._by_topic: dict[str, list[BaseKafkaConsumer]] = {}
        for consumer in consumers:
            for topic in consumer.topics:
                self._by_topic.setdefault(topic, []).append(consumer)
        self._connected = False
        self.delivered = 0
        self.failed = 0

    @property
    def topics(self) -> list[str]:
        return sorted(self._by_topic)

    async def start(self) -> None:
        self._connected = True

    async def stop(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def send(
        self, topic: str, event: EventEnvelope, *, timeout: float | None = None
    ) -> None:
        consumers = self._by_topic.get(topic, [])
        if not consumers:
            # No in-process subscriber for this topic (e.g. search is not
            # configured): nothing to do, the event counts as delivered.
            self.delivered += 1
            await _notify_live_clients(event)
            return
        record = ConsumerRecord(
            topic=topic,
            partition=0,
            offset=0,
            key=str(event.aggregate_id).encode(),
            value=event.to_json_bytes(),
            timestamp=int(time.time() * 1000),
        )
        for consumer in consumers:
            ok = await consumer.process_record(record)
            if not ok:
                self.failed += 1
                # The publisher records the failure and retries with backoff;
                # consumers that already succeeded skip the event next time
                # (consumer_inbox), so a retry never duplicates their effects.
                raise DirectDispatchError(
                    f"{consumer.consumer_group} could not process {event.event_type} yet"
                )
        self.delivered += 1
        await _notify_live_clients(event)
