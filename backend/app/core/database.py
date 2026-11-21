import ssl
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""

    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def reset_engine() -> None:
    """Reset cached engine and session factory (primarily for testing)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def get_engine() -> AsyncEngine | None:
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    if not settings.has_database:
        return None

    db_url = settings.DATABASE_URL
    connect_args = {}

    if db_url.startswith("postgresql"):
        # Configure SSL for Aiven PostgreSQL if required
        if settings.DATABASE_SSL_MODE.lower() in (
            "require",
            "verify-ca",
            "verify-full",
        ):
            ssl_ctx = ssl.create_default_context()
            if settings.DATABASE_SSL_MODE.lower() == "require":
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx

    engine_kwargs: dict[str, Any] = {
        "echo": settings.SQL_ECHO,
        "connect_args": connect_args,
    }

    # Only pass connection pool parameters to dialects that support QueuePool
    if not db_url.startswith("sqlite"):
        engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        engine_kwargs["pool_pre_ping"] = True

    _engine = create_async_engine(
        db_url,
        **engine_kwargs,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    logger.info("Initialized SQLAlchemy 2.x async engine.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    global _session_factory
    if _session_factory is None:
        get_engine()
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session lifecycle."""
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured in this environment.")

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_readiness() -> dict:
    """Check database connectivity without leaking credentials."""
    if not settings.has_database:
        return {"status": "unconfigured", "message": "DATABASE_URL is not set."}

    engine = get_engine()
    if engine is None:
        return {
            "status": "error",
            "message": "Database engine could not be initialized.",
        }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "connected"}
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return {"status": "unreachable", "message": "Failed to connect to database."}
