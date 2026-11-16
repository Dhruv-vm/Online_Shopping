from fastapi import APIRouter

from app.core.config import settings
from app.modules.catalogue.router import router as catalogue_router

api_router = APIRouter()

# Mount Catalogue endpoints
api_router.include_router(catalogue_router)


@api_router.get("/info", tags=["System"])
async def get_api_info() -> dict:
    """Return version and environment metadata."""
    return {
        "project": settings.PROJECT_NAME,
        "version": "v1",
        "environment": settings.ENVIRONMENT,
    }
