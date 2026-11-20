"""In-process background workers.

Before this module existed the transactional outbox publisher, expired
reservation cleanup and payment reconciliation were implemented but never
started by anything: outbox events piled up, Kafka consumers received nothing,
and abandoned checkouts held stock indefinitely.

``BackgroundWorkerSupervisor`` is started from the FastAPI lifespan. Every job
is safe to run in several API replicas at once:

* the outbox publisher claims rows with ``FOR UPDATE SKIP LOCKED`` + leases;
* reservations are released one per transaction under row locks, and an
  already-released reservation is simply skipped;
* payment reconciliation claims webhook events with leases.

Set ``BACKGROUND_WORKERS_ENABLED=false`` to run these jobs in dedicated worker
processes instead.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

KAFKA_RECONNECT_INITIAL_SECONDS = 5.0
KAFKA_RECONNECT_MAX_SECONDS = 300.0


async def expire_stale_reservations(session_factory, limit: int = 100) -> int:
    """Release reservations past their TTL, one transaction per reservation."""
    from app.modules.inventory.repository import ReservationRepository
    from app.modules.inventory.service import ReservationService

    async with session_factory() as session:
        expired = await ReservationRepository(session).get_expired_active_reservations(
            limit=limit
        )
        ids = [r.id for r in expired]

    released = 0
    for reservation_id in ids:
        async with session_factory() as session:
            try:
                await ReservationService(session).release_reservation(
                    reservation_id=reservation_id, reason="TTL_EXPIRED", internal=True
                )
                await session.commit()
                released += 1
            except Exception as exc:  # concurrent release, already confirmed, etc.
                await session.rollback()
                logger.debug("Skipping reservation %s: %s", reservation_id, exc)
    if released:
        logger.info("Released %d expired inventory reservation(s)", released)
    return released


async def reconcile_payments(session_factory) -> None:
    from app.modules.payments.reconciliation import ReconciliationService

    async with session_factory() as session:
        await ReconciliationService(session).reconcile_pending(
            batch_size=50, max_age_minutes=1440, pending_cutoff_minutes=5
        )


async def escalate_payment_sla(session_factory) -> None:
    from app.modules.payments.reconciliation import ReconciliationService

    async with session_factory() as session:
        await ReconciliationService(session).execute_75m_sla_escalation_job(limit=50)


async def run_in_txn(session_factory, fn) -> object:
    async with session_factory() as session:
        try:
            result = await fn(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def phase3_fast_jobs(session_factory) -> None:
    """Every 15s: close auctions, settle group buys, expire awards/RFQs/stream."""
    from app.modules.auctions.service import close_ended_auctions
    from app.modules.community.service import settle_expired_campaigns
    from app.modules.exchange.service import expire_open_requests
    from app.modules.pricing.awards import expire_stale_awards
    from app.modules.sale_stream.service import expire_sale_stream

    for job in (
        close_ended_auctions,
        settle_expired_campaigns,
        expire_open_requests,
        expire_stale_awards,
        expire_sale_stream,
    ):
        try:
            await run_in_txn(session_factory, job)
        except Exception as exc:
            logger.warning("Phase 3 job %s failed: %s", job.__name__, exc)


async def phase3_slow_jobs(session_factory) -> None:
    """Hourly: hot-seller detection, daily price snapshot (idempotent), demand expiry."""
    from app.modules.demand.service import expire_idle_pools
    from app.modules.price_intel.service import snapshot_all_active_listings
    from app.modules.sale_stream.service import detect_hot_sellers

    for job in (detect_hot_sellers, snapshot_all_active_listings, expire_idle_pools):
        try:
            await run_in_txn(session_factory, job)
        except Exception as exc:
            logger.warning("Phase 3 job %s failed: %s", job.__name__, exc)


class BackgroundWorkerSupervisor:
    """Owns all periodic jobs and the outbox publisher for one process."""

    def __init__(self, session_factory, config: Settings | None = None) -> None:
        self._session_factory = session_factory
        self._settings = config or settings
        self._tasks: list[asyncio.Task[None]] = []
        self._outbox_worker = None
        self._stopping = asyncio.Event()

    # ------------------------------------------------------------------ jobs
    def _periodic(
        self, name: str, interval: float, job: Callable[[], Awaitable[object]]
    ) -> None:
        async def loop() -> None:
            while not self._stopping.is_set():
                try:
                    await job()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("Background job %s failed: %s", name, exc)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), timeout=interval)

        self._tasks.append(asyncio.create_task(loop(), name=f"bg-{name}"))

    async def _run_outbox_publisher(self) -> None:
        """Start the publisher, retrying the Kafka connection with backoff.

        While Kafka is unreachable, events stay PENDING in ``outbox_events`` and
        are published once the broker returns: nothing is lost and the API keeps
        serving requests (graceful degradation).
        """
        from app.core.events.kafka import AioKafkaEventProducer
        from app.core.events.outbox_publisher import OutboxPublisherWorker

        delay = KAFKA_RECONNECT_INITIAL_SECONDS
        while not self._stopping.is_set():
            worker = OutboxPublisherWorker(
                session_factory=self._session_factory,
                producer=AioKafkaEventProducer(self._settings),
                config_settings=self._settings,
            )
            try:
                await worker.start()
                self._outbox_worker = worker
                logger.info("Outbox publisher running (Kafka connected).")
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Outbox publisher could not connect to Kafka (%s); "
                    "events remain queued in outbox_events. Retrying in %.0fs.",
                    exc,
                    delay,
                )
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), timeout=delay)
                delay = min(delay * 2, KAFKA_RECONNECT_MAX_SECONDS)

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        cfg = self._settings
        sf = self._session_factory
        if sf is None:
            logger.warning("Background workers not started: no database configured.")
            return

        self._periodic(
            "reservation-expiry",
            cfg.RESERVATION_CLEANUP_INTERVAL_SECONDS,
            lambda: expire_stale_reservations(sf),
        )
        self._periodic(
            "payment-reconcile",
            cfg.PAYMENT_RECONCILE_INTERVAL_SECONDS,
            lambda: reconcile_payments(sf),
        )
        self._periodic(
            "payment-sla-escalation",
            cfg.PAYMENT_SLA_ESCALATION_INTERVAL_SECONDS,
            lambda: escalate_payment_sla(sf),
        )
        self._periodic(
            "phase3-fast",
            cfg.PHASE3_FAST_JOB_INTERVAL_SECONDS,
            lambda: phase3_fast_jobs(sf),
        )
        self._periodic(
            "phase3-slow",
            cfg.PHASE3_SLOW_JOB_INTERVAL_SECONDS,
            lambda: phase3_slow_jobs(sf),
        )
        if cfg.has_kafka and cfg.OUTBOX_PUBLISHER_ENABLED:
            self._tasks.append(
                asyncio.create_task(self._run_outbox_publisher(), name="bg-outbox")
            )
        else:
            logger.warning(
                "Kafka not configured: outbox events will accumulate as PENDING "
                "until a publisher runs."
            )
        logger.info(
            "Background worker supervisor started (%d task(s)).", len(self._tasks)
        )

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        if self._outbox_worker is not None:
            with contextlib.suppress(Exception):
                await self._outbox_worker.stop()
            self._outbox_worker = None
        logger.info("Background worker supervisor stopped.")
