from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.identity.dependencies import require_role, verify_csrf_token
from app.modules.identity.models import User
from app.modules.vision.providers import UnconfiguredOCRProvider, get_ocr_provider
from app.modules.vision.schemas import (
    BuildCartRequest,
    BuildCartResponse,
    ParseListRequest,
    ParseListResponse,
    VisionStatusResponse,
)
from app.modules.vision.service import VisionListService

require_customer = require_role("customer")
router = APIRouter(
    prefix="/vision",
    tags=["Handwritten List to Basket"],
    dependencies=[Depends(verify_csrf_token)],
)


@router.get("/status", response_model=VisionStatusResponse)
async def vision_status() -> VisionStatusResponse:
    """Public: whether photo recognition is available. When it is not, the UI
    offers the clearly-labelled manual (typed list) fallback instead."""
    provider = get_ocr_provider()
    available = not isinstance(provider, UnconfiguredOCRProvider)
    return VisionStatusResponse(
        ocr_available=available,
        provider=provider.name,
        message=(
            "Photo recognition is available. Review every item before adding it."
            if available
            else "Photo recognition is not configured on this server. Type or paste your list instead."
        ),
    )


@router.post("/parse-list", response_model=ParseListResponse)
async def parse_shopping_list(
    payload: ParseListRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_customer)],
) -> ParseListResponse:
    """Extract items from a photo (requires a configured OCR provider; otherwise
    503 OCR_PROVIDER_UNAVAILABLE) or from typed/corrected text, and suggest
    in-stock listings for review. Nothing is added to the cart here."""
    return await VisionListService(db).parse(payload)


@router.post("/build-cart", response_model=BuildCartResponse)
async def build_cart_from_list(
    payload: BuildCartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> BuildCartResponse:
    """Add the reviewed selections to the customer's basket."""
    cart_id, added, skipped = await VisionListService(db).build_cart(
        user.id, payload.items
    )
    return BuildCartResponse(cart_id=cart_id, added=added, skipped=skipped)
