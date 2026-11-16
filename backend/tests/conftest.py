from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_engine, reset_engine
from app.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_database_engine():
    """Ensure engine and connections are scoped to each test's event loop."""
    reset_engine()
    yield
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
