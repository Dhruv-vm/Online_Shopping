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

    if settings.has_kafka:
        try:
            from app.core.database import get_session_factory
            from app.core.search.consumer import OpenSearchConsumer
            from app.modules.orders.consumer import OrderProjectionConsumer

            session_factory = get_session_factory()
            order_consumer = OrderProjectionConsumer(session_factory=session_factory)
            await order_consumer.start()
            logger.info("OrderProjectionConsumer started successfully.")

            opensearch_consumer = OpenSearchConsumer(session_factory=session_factory)
            await opensearch_consumer.start()
            logger.info("OpenSearchConsumer started successfully.")
        except Exception as exc:
            logger.warning(
                "Background consumer could not start at lifespan startup: %s. Continuing in degraded mode.",
                exc,
            )

    yield

    # Shutdown logic
    if opensearch_consumer is not None:
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
        version="0.1.0",
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
    async def readiness_check(response: Response) -> dict:
        """Readiness check across PostgreSQL, Kafka, and OpenSearch dependencies."""
        db_check = await check_db_readiness()

        # Kafka check
        kafka_check: dict[str, str] = {"status": "unconfigured"}
        if settings.has_kafka:
            kafka_check = {"status": "connected"}

        # OpenSearch check
        opensearch_check: dict[str, str] = {"status": "unconfigured"}
        if settings.has_opensearch:
            try:
                os_client = get_opensearch_client(settings)
                ping_ok = await os_client.ping()
                opensearch_check = {"status": "connected" if ping_ok else "degraded"}
            except Exception as exc:
                opensearch_check = {"status": "degraded", "error": str(exc)}

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

    return app


app = create_app()
