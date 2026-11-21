from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.assistant.schemas import AssistantReply, AssistantRequest
from app.modules.assistant.service import answer

router = APIRouter(prefix="/assistant", tags=["Deal Assistant"])


@router.post("/chat", response_model=AssistantReply)
async def chat(
    payload: AssistantRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> AssistantReply:
    """Public, read-only: answer a shopping question from live catalogue data."""
    return await answer(db, payload.message)
