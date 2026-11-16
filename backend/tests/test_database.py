import pytest
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings
from app.core.database import get_engine, reset_engine


@pytest.mark.asyncio
async def test_sqlite_engine_creation():
    """Verify that SQLite engine creation does not fail with pool argument errors."""
    reset_engine()
    original_db_url = settings.DATABASE_URL
    try:
        settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        engine = get_engine()
        assert engine is not None
        # SQLite in-memory uses StaticPool
        assert isinstance(engine.pool, StaticPool)
    finally:
        settings.DATABASE_URL = original_db_url
        reset_engine()


@pytest.mark.asyncio
async def test_postgresql_engine_pool_settings():
    """Verify that PostgreSQL engine configuration retains pool_size, max_overflow, and pre_ping."""
    reset_engine()
    original_db_url = settings.DATABASE_URL
    try:
        settings.DATABASE_URL = (
            "postgresql+asyncpg://mockuser:mockpass@localhost:5432/mockdb"
        )
        engine = get_engine()
        assert engine is not None
        # PostgreSQL should configure QueuePool with pool_size and max_overflow
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == settings.DATABASE_POOL_SIZE
        assert engine.pool._max_overflow == settings.DATABASE_MAX_OVERFLOW
        assert engine.pool._pre_ping is True
    finally:
        settings.DATABASE_URL = original_db_url
        reset_engine()
