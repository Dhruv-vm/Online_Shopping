from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.orders.service import OrderService


def get_order_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OrderService:
    return OrderService(session)
