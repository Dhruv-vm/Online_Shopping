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

    # Initialize and start Kafka consumer if configured, without blocking API startup
    consumer = None
    if settings.has_kafka:
        try:
            from app.core.database import get_session_factory
            from app.modules.orders.consumer import OrderProjectionConsumer

            session_factory = get_session_factory()
            consumer = OrderProjectionConsumer(session_factory=session_factory)
            await consumer.start()
            logger.info(
                "OrderProjectionConsumer initialized and started during lifespan."
            )
        except Exception as exc:
            logger.warning(
                "OrderProjectionConsumer could not start at lifespan startup: %s. Continuing in degraded mode.",
                exc,
            )
            consumer = None

    yield

    # Shutdown logic
    if consumer is not None:
        try:
            logger.info("Stopping OrderProjectionConsumer...")
            await consumer.stop()
        except Exception as exc:
            logger.warning("Error stopping consumer during shutdown: %s", exc)

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

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Health and Readiness Endpoints
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
        """Readiness check including database status."""
        db_check = await check_db_readiness()

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
            },
        }

    # Mount v1 API
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_app()
