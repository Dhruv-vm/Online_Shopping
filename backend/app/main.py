import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import check_db_readiness, get_engine
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import logger, setup_logging
from app.core.metrics import (
    REGISTRY,
    http_request_duration_seconds,
    http_requests_total,
    normalize_metric_path,
)
from app.core.search.client import get_opensearch_client
from app.core.search.index_health import (
    evaluate_search_engine,
    set_search_indexer_running,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager."""
    setup_logging()
    logger.info(
        "Starting %s in %s mode...", settings.PROJECT_NAME, settings.ENVIRONMENT
    )

    # Validate essential configuration at startup
    if (
        settings.is_production
        and settings.SECRET_KEY.get_secret_value()
        == "insecure-default-development-key-change-in-production"
    ):
        raise RuntimeError("FATAL: Insecure default SECRET_KEY detected in production!")

    # Attempt to initialize database engine if configured
    if settings.has_database:
        logger.info("DATABASE_URL provided; initializing database engine.")
        get_engine()
    else:
        logger.warning(
            "DATABASE_URL not configured. Running without database connection."
        )

    # Initialize and start Kafka consumers if configured, without blocking API startup
    order_consumer = None
    opensearch_consumer = None

    # With OUTBOX_DISPATCH=direct the same handlers run in-process (background
    # supervisor), so Kafka consumers are never started alongside (C2).
    if settings.has_kafka and settings.OUTBOX_DISPATCH == "kafka":
        try:
            from app.core.database import get_session_factory
            from app.core.search.consumer import OpenSearchConsumer
            from app.modules.orders.consumer import OrderProjectionConsumer

            session_factory = get_session_factory()
        except Exception as exc:
            logger.warning("Kafka consumers not started: %s", exc)
            session_factory = None
        # Started independently: one failing must not silently disable the other.
        if session_factory is not None:
            try:
                order_consumer = OrderProjectionConsumer(
                    session_factory=session_factory
                )
                await order_consumer.start()
                order_consumer.start_consuming()
                logger.info("OrderProjectionConsumer started successfully.")
            except Exception as exc:
                order_consumer = None
                logger.warning(
                    "OrderProjectionConsumer could not start: %s. Continuing in degraded mode.",
                    exc,
                )
            try:
                opensearch_consumer = OpenSearchConsumer(
                    session_factory=session_factory
                )
                await opensearch_consumer.start()
                logger.info("OpenSearchConsumer started successfully.")
                # Build this database's index from PostgreSQL before search trusts
                # it (same bootstrap as direct mode); until then search stays on
                # PostgreSQL.
                from app.core.search.index import IndexManager, resolve_index_prefix

                manager = IndexManager(
                    opensearch_consumer._search_client,
                    prefix=resolve_index_prefix(settings),
                )
                await manager.ensure_index_and_aliases()
                async with session_factory() as session:
                    indexed = await manager.reconcile_from_database(session)
                opensearch_consumer.start_consuming()
                set_search_indexer_running(True)
                logger.info(
                    "Search index '%s' rebuilt from PostgreSQL (%d products); "
                    "Kafka indexing active.",
                    manager.write_alias,
                    indexed,
                )
            except Exception as exc:
                opensearch_consumer = None
                logger.warning(
                    "OpenSearchConsumer could not start: %s. Search uses PostgreSQL.",
                    exc,
                )

    # Live change notices for browsers (Kafka mode; direct mode feeds the hub
    # from the dispatcher).
    realtime_listener = None
    if settings.has_kafka and settings.OUTBOX_DISPATCH == "kafka":
        try:
            from app.modules.realtime.hub import RealtimeKafkaListener

            realtime_listener = RealtimeKafkaListener()
            await realtime_listener.start()
            logger.info(
                "Realtime listener started (group %s).", realtime_listener.group_id
            )
        except Exception as exc:
            logger.warning("Realtime listener not started: %s", exc)
            realtime_listener = None

    # Background workers: outbox publisher, reservation expiry, reconciliation.
    supervisor = None
    if settings.has_database and settings.BACKGROUND_WORKERS_ENABLED:
        try:
            from app.core.background import BackgroundWorkerSupervisor
            from app.core.database import get_session_factory

            supervisor = BackgroundWorkerSupervisor(get_session_factory())
            await supervisor.start()
        except Exception as exc:
            logger.warning("Background workers failed to start: %s", exc)
            supervisor = None
    app.state.background_supervisor = supervisor

    yield

    # Shutdown logic
    if realtime_listener is not None:
        await realtime_listener.stop()
    if supervisor is not None:
        try:
            await supervisor.stop()
        except Exception as exc:
            logger.warning("Error stopping background workers: %s", exc)

    if opensearch_consumer is not None:
        set_search_indexer_running(False)
        try:
            logger.info("Stopping OpenSearchConsumer...")
            await opensearch_consumer.stop()
        except Exception as exc:
            logger.warning("Error stopping OpenSearchConsumer during shutdown: %s", exc)

    if order_consumer is not None:
        try:
            logger.info("Stopping OrderProjectionConsumer...")
            await order_consumer.stop()
        except Exception as exc:
            logger.warning(
                "Error stopping OrderProjectionConsumer during shutdown: %s", exc
            )

    engine = get_engine()
    if engine is not None:
        logger.info("Closing database engine connections...")
        await engine.dispose()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="2.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
        if not settings.is_production
        else None,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID and Request Logging Middleware
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Admin audit trail: every successful admin mutation is recorded.
    @app.middleware("http")
    async def admin_audit_middleware(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            from app.modules.governance.audit import record_admin_mutation

            await record_admin_mutation(request, response)
        return response

    # API responses are per-user and change constantly: never let a browser, the
    # Next.js proxy or a tunnel/CDN cache them unless an endpoint says otherwise.
    @app.middleware("http")
    async def api_no_store_middleware(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if (
            request.url.path.startswith("/api/")
            and "cache-control" not in response.headers
        ):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    # Prometheus Metrics Middleware (Bounded Labels)
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next) -> Response:
        start_time = time.monotonic()
        path = normalize_metric_path(request.url.path)
        method = request.method
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.monotonic() - start_time
            http_requests_total.inc(method=method, path=path, status=str(status_code))
            http_request_duration_seconds.observe(duration, method=method, path=path)

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Health, Readiness, and Observability Endpoints
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Process liveness endpoint."""
        return {
            "status": "ok",
            "service": "basket-backend",
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/ready", tags=["Health"])
    async def readiness_check(request: Request, response: Response) -> dict:
        """Readiness check across PostgreSQL, Kafka, and OpenSearch dependencies."""
        db_check = await check_db_readiness()

        # Kafka check: report the real publisher state and the outbox backlog,
        # not merely whether a bootstrap server is configured.
        kafka_check: dict[str, object] = {"status": "unconfigured"}
        supervisor = getattr(request.app.state, "background_supervisor", None)
        worker = getattr(supervisor, "_outbox_worker", None) if supervisor else None
        if settings.OUTBOX_DISPATCH == "direct":
            # Events are delivered in-process; Kafka is not used by this instance.
            kafka_check = {
                "status": "not_used",
                "dispatch": "direct",
                "dispatcher": "running"
                if worker is not None and worker.is_running
                else "stopped",
            }
        elif settings.has_kafka:
            kafka_check = {
                "status": "connected"
                if worker is not None and worker.producer.is_connected
                else "degraded"
            }
        if db_check["status"] == "connected":
            try:
                from sqlalchemy import func, select

                from app.core.database import get_session_factory
                from app.modules.orders.models import OutboxEvent

                sf = get_session_factory()
                if sf is not None:
                    async with sf() as s:
                        rows = (
                            await s.execute(
                                select(OutboxEvent.status, func.count())
                                .where(OutboxEvent.status.in_(["PENDING", "FAILED"]))
                                .group_by(OutboxEvent.status)
                            )
                        ).all()
                    counts = {status_: int(n) for status_, n in rows}
                    kafka_check["outbox_pending"] = counts.get("PENDING", 0)
                    kafka_check["outbox_failed"] = counts.get("FAILED", 0)
            except Exception as exc:  # readiness must never crash
                kafka_check["outbox_error"] = type(exc).__name__

        # OpenSearch check
        opensearch_check: dict[str, str] = {"status": "unconfigured"}
        if settings.has_opensearch:
            try:
                os_client = get_opensearch_client(settings)
                ping_ok = await os_client.ping()
                opensearch_check = {"status": "connected" if ping_ok else "degraded"}
            except Exception as exc:
                opensearch_check = {"status": "degraded", "error": str(exc)}

        # Which engine search uses now, and why (Version 2.0 A3).
        search_check: dict[str, object]
        try:
            from app.core.database import get_session_factory

            sf = get_session_factory() if db_check["status"] == "connected" else None
            if sf is not None:
                async with sf() as s:
                    search_check = (await evaluate_search_engine(s)).as_dict()
            else:
                search_check = (await evaluate_search_engine(None)).as_dict()
        except Exception as exc:  # readiness must never crash
            search_check = {"engine": "unknown", "error": type(exc).__name__}

        if db_check["status"] == "connected":
            overall_status = "ready"
            response.status_code = status.HTTP_200_OK
        elif db_check["status"] == "unconfigured":
            overall_status = "degraded"
            if settings.is_production:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            else:
                response.status_code = status.HTTP_200_OK
        else:
            overall_status = "not_ready"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": overall_status,
            "service": "basket-backend",
            "checks": {
                "database": db_check,
                "kafka": kafka_check,
                "opensearch": opensearch_check,
                "search": search_check,
            },
        }

    @app.get("/metrics", tags=["Observability"])
    async def get_metrics() -> Response:
        """Expose standard Prometheus metrics in text format 0.0.4."""
        content = REGISTRY.exposition()
        return Response(
            content=content,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # Mount v1 API
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Locally stored uploads (development). Private verification documents are
    # stored under media/private and are NOT served publicly.
    if (settings.MEDIA_STORAGE or "").lower() == "local":
        from pathlib import Path

        from fastapi.staticfiles import StaticFiles

        public_root = Path(settings.MEDIA_ROOT)
        public_root.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=str(public_root)), name="media")

    return app


app = create_app()
