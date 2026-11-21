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
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.core.logging import redact_secrets
from app.core.search.index_health import (
    register_outbox_publisher,
    set_search_indexer_running,
)

logger = logging.getLogger(__name__)


def job_lock_key(name: str) -> int:
    """Stable signed 64-bit advisory-lock key for a job name."""
    digest = hashlib.sha256(f"basket-job:{name}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _log_job(record: dict) -> None:
    line = "job_run " + json.dumps(record, sort_keys=True, default=str)
    if record["status"] == "failed":
        logger.warning(line)
    else:
        logger.info(line)


async def run_job(
    session_factory,
    name: str,
    body: Callable[[], Awaitable[object]],
) -> dict:
    """Run one background job at most once at a time across all API instances.

    A dedicated "lock session" holds ``pg_try_advisory_xact_lock(<job key>)`` for
    the whole run, so the guarantee covers jobs that open and commit their own
    sessions. If another instance holds the lock, the run is skipped (the next
    cycle picks the work up). Exactly one structured ``job_run`` log line is
    written per run; a failure is logged and re-raised so callers keep their
    error handling.
    """
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(UTC)
    t0 = time.monotonic()
    record: dict = {
        "job": name,
        "run_id": run_id,
        "started_at": started.isoformat(),
        "status": "ok",
        "rows": None,
        "duration_ms": None,
        "error": None,
    }
    async with session_factory() as lock_session:
        got = (
            await lock_session.execute(
                select(func.pg_try_advisory_xact_lock(job_lock_key(name)))
            )
        ).scalar()
        if not got:
            record["status"] = "skipped"
            record["error"] = "lock held by another worker"
            record["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
            await lock_session.rollback()
            _log_job(record)
            return record
        try:
            result = await body()
            if isinstance(result, int) and not isinstance(result, bool):
                record["rows"] = result
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = redact_secrets(f"{type(exc).__name__}: {exc}")[:500]
            raise
        finally:
            record["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
            with contextlib.suppress(Exception):
                await lock_session.rollback()  # releases the advisory lock
            _log_job(record)
    return record


# Last-run status per periodic job, exposed on the admin operational-health page.
JOB_STATUS: dict[str, dict] = {}

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


async def escalate_payment_sla(session_factory) -> int:
    from app.modules.payments.reconciliation import ReconciliationService

    async with session_factory() as session:
        return await ReconciliationService(session).execute_75m_sla_escalation_job(
            limit=50
        )


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
            await run_job(
                session_factory,
                f"phase3.{job.__name__}",
                lambda job=job: run_in_txn(session_factory, job),
            )
        except Exception:
            pass  # already logged by run_job; the next job still runs


async def phase3_slow_jobs(session_factory) -> None:
    """Hourly: hot-seller detection, daily price snapshot (idempotent), demand expiry."""
    from app.modules.demand.service import expire_idle_pools
    from app.modules.price_intel.service import snapshot_all_active_listings
    from app.modules.recurring.service import prepare_due_recurring_baskets
    from app.modules.sale_stream.service import detect_hot_sellers

    for job in (
        detect_hot_sellers,
        snapshot_all_active_listings,
        expire_idle_pools,
        prepare_due_recurring_baskets,
    ):
        try:
            await run_job(
                session_factory,
                f"phase3.{job.__name__}",
                lambda job=job: run_in_txn(session_factory, job),
            )
        except Exception:
            pass  # already logged by run_job; the next job still runs


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
                started = datetime.now(UTC)
                try:
                    await job()
                    JOB_STATUS[name] = {
                        "last_run_at": started.isoformat(),
                        "last_ok": True,
                        "interval_seconds": interval,
                        "last_error": None,
                    }
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # run_job already wrote the structured failure line.
                    logger.debug("Background job %s failed: %s", name, exc)
                    JOB_STATUS[name] = {
                        "last_run_at": started.isoformat(),
                        "last_ok": False,
                        "interval_seconds": interval,
                        "last_error": type(exc).__name__,
                    }
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
                register_outbox_publisher(worker)
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

    async def _run_direct_dispatcher(self) -> None:
        """OUTBOX_DISPATCH=direct: deliver outbox events to the in-process consumer
        handlers through the normal publisher (claims, leases, retries)."""
        from app.core.events.direct_dispatch import (
            DirectDispatchProducer,
            direct_consumer_kwargs,
        )
        from app.core.events.outbox_publisher import OutboxPublisherWorker
        from app.modules.orders.consumer import OrderProjectionConsumer

        cfg, sf = self._settings, self._session_factory
        consumers = [
            OrderProjectionConsumer(
                session_factory=sf, config_settings=cfg, **direct_consumer_kwargs()
            )
        ]
        search_consumer = None
        if cfg.has_opensearch:
            from app.core.search.consumer import OpenSearchConsumer

            search_consumer = OpenSearchConsumer(
                session_factory=sf, config_settings=cfg, **direct_consumer_kwargs()
            )
            consumers.append(search_consumer)
        producer = DirectDispatchProducer(consumers)
        worker = OutboxPublisherWorker(
            session_factory=sf,
            producer=producer,
            config_settings=cfg,
            batch_size=cfg.OUTBOX_BATCH_SIZE,
            lease_seconds=cfg.OUTBOX_LEASE_SECONDS,
            poll_interval_seconds=cfg.OUTBOX_POLL_INTERVAL_SECONDS,
            max_retries=cfg.OUTBOX_MAX_RETRIES,
        )
        await worker.start()
        self._outbox_worker = worker
        register_outbox_publisher(worker)
        logger.info(
            "Outbox dispatcher running in DIRECT mode (topics: %s).",
            ", ".join(producer.topics) or "none",
        )
        if search_consumer is not None:
            await self._bootstrap_search_index(search_consumer)

    async def _bootstrap_search_index(self, search_consumer) -> None:
        """Build this database's index from PostgreSQL before search may trust it
        (until then the Phase A health check keeps search on PostgreSQL)."""
        from app.core.search.index import IndexManager, resolve_index_prefix

        delay = KAFKA_RECONNECT_INITIAL_SECONDS
        prefix = resolve_index_prefix(self._settings)
        while not self._stopping.is_set():
            try:
                manager = IndexManager(search_consumer._search_client, prefix=prefix)
                await manager.ensure_index_and_aliases()
                async with self._session_factory() as session:
                    count = await manager.reconcile_from_database(session)
                set_search_indexer_running(True)
                logger.info(
                    "Search index '%s' rebuilt from PostgreSQL (%d products); "
                    "direct indexing active.",
                    manager.write_alias,
                    count,
                )
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Search index bootstrap failed (%s); search stays on PostgreSQL. "
                    "Retrying in %.0fs.",
                    redact_secrets(str(exc))[:300],
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
            lambda: run_job(
                sf, "reservation-expiry", lambda: expire_stale_reservations(sf)
            ),
        )
        self._periodic(
            "payment-reconcile",
            cfg.PAYMENT_RECONCILE_INTERVAL_SECONDS,
            lambda: run_job(sf, "payment-reconcile", lambda: reconcile_payments(sf)),
        )
        self._periodic(
            "payment-sla-escalation",
            cfg.PAYMENT_SLA_ESCALATION_INTERVAL_SECONDS,
            lambda: run_job(
                sf, "payment-sla-escalation", lambda: escalate_payment_sla(sf)
            ),
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
        if cfg.OUTBOX_DISPATCH == "direct" and cfg.OUTBOX_PUBLISHER_ENABLED:
            if cfg.has_kafka:
                logger.warning(
                    "OUTBOX_DISPATCH=direct: KAFKA_BOOTSTRAP_SERVERS is ignored by "
                    "this instance (no Kafka publishing or consuming)."
                )
            self._tasks.append(
                asyncio.create_task(self._run_direct_dispatcher(), name="bg-outbox")
            )
        elif cfg.has_kafka and cfg.OUTBOX_PUBLISHER_ENABLED:
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
        if self._settings.OUTBOX_DISPATCH == "direct":
            set_search_indexer_running(False)
        if self._outbox_worker is not None:
            register_outbox_publisher(None)
            with contextlib.suppress(Exception):
                await self._outbox_worker.stop()
            self._outbox_worker = None
        logger.info("Background worker supervisor stopped.")
