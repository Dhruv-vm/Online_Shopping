from fastapi import APIRouter

from app.core.config import settings
from app.modules.admin.router import router as admin_router
from app.modules.cart.router import cart_router
from app.modules.catalogue.router import router as catalogue_router
from app.modules.identity.router import address_router, auth_router, user_router
from app.modules.intent.router import intent_router
from app.modules.inventory.router import router as inventory_router
from app.modules.missions.router import router as missions_router
from app.modules.orders.router import router as orders_router
from app.modules.payments.router import internal_router as internal_payments_router
from app.modules.payments.router import router as payments_router
from app.modules.pricing.router import router as pricing_router
from app.modules.retailer.router import router as retailer_router
from app.modules.search.router import router as search_router
from app.modules.substitutes.router import router as substitutes_router

api_router = APIRouter()

# Mount Identity & Auth endpoints
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(address_router)

# Mount Catalogue endpoints
api_router.include_router(catalogue_router)
api_router.include_router(catalogue_router, prefix="/catalogue")

# Mount Universal Search endpoints (Phase 3E)
api_router.include_router(search_router)

# Mount Cart endpoints
api_router.include_router(cart_router)

# Mount Basket Mission endpoints (Phase 2A)
api_router.include_router(missions_router)

# Mount Basket Substitute Intelligence endpoints (Phase 2B)
api_router.include_router(substitutes_router)

# Mount Basket Intent Memory endpoints (Phase 2C)
api_router.include_router(intent_router)

# Mount Pricing & Quotes endpoints
api_router.include_router(pricing_router)

# Mount Inventory Reservations endpoints (Phase 2D)
api_router.include_router(inventory_router)

# Mount Orders & Outbox endpoints (Phase 2E)
api_router.include_router(orders_router)

# Mount Payments & Gateway endpoints (Phase 2F)
api_router.include_router(payments_router)
api_router.include_router(internal_payments_router)

# Mount Retailer Portal endpoints (Phase 5A)
api_router.include_router(retailer_router)

# Mount Admin Portal endpoints (Phase 5A)
api_router.include_router(admin_router)


@api_router.get("/info", tags=["System"])
async def get_api_info() -> dict:
    """Return version and environment metadata."""
    return {
        "project": settings.PROJECT_NAME,
        "version": "v1",
        "environment": settings.ENVIRONMENT,
    }
