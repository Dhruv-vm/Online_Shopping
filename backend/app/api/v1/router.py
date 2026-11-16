from fastapi import APIRouter

from app.core.config import settings

api_router = APIRouter()


@api_router.get("/info", tags=["System"])
async def get_api_info() -> dict:
    """Return version and environment metadata."""
    return {
        "project": settings.PROJECT_NAME,
        "version": "v1",
        "environment": settings.ENVIRONMENT,
    }
