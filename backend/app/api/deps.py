from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a managed database session."""
    async for session in get_db_session():
        yield session
