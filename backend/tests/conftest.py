from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db_session, get_engine, reset_engine
from app.main import create_app

_catalogue_seeded = False


@pytest.fixture(autouse=True)
async def ensure_baseline_catalogue():
    """Ensure standard test catalogue is seeded if running on a fresh/clean database."""
    global _catalogue_seeded
    if _catalogue_seeded:
        return
    if settings.has_database and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            async for session in get_db_session():
                res = await session.execute(text("SELECT count(*) FROM categories"))
                if (res.scalar() or 0) < 7:
                    from app.seeds.seed_catalogue import seed_database

                    await seed_database()
                _catalogue_seeded = True
                break
        except Exception:
            pass


@pytest.fixture(autouse=True)
async def cleanup_database_engine():
    """Ensure engine and connections are scoped to each test's event loop."""
    reset_engine()
    yield
    if settings.has_database and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            async for session in get_db_session():
                await session.execute(
                    text("""
                        UPDATE store_inventory
                        SET on_hand_quantity = 50, reserved_quantity = 0
                        WHERE reserved_quantity > 0 OR on_hand_quantity < 10
                    """)
                )
                await session.commit()
                break
        except Exception:
            pass
    engine = get_engine()
    if engine is not None:
        await engine.dispose()
    reset_engine()


@pytest.fixture
def app_instance():
    return create_app()


@pytest.fixture
async def async_client(app_instance) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
