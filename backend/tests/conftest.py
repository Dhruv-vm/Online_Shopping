from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db_session, get_engine, reset_engine
from app.main import create_app


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
