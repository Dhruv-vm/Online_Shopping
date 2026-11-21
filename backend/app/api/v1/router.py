from fastapi import APIRouter

from app.core.config import settings
from app.modules.admin.router import router as admin_router
from app.modules.assistant.router import router as assistant_router
from app.modules.auctions.router import admin_router as auctions_admin_router
from app.modules.auctions.router import retailer_router as auctions_retailer_router
from app.modules.auctions.router import router as auctions_router
from app.modules.cart.router import cart_router
from app.modules.catalogue.router import router as catalogue_router
from app.modules.community.router import admin_router as community_admin_router
from app.modules.community.router import retailer_router as community_retailer_router
from app.modules.community.router import router as community_router
from app.modules.demand.router import admin_router as demand_admin_router
from app.modules.demand.router import retailer_router as demand_retailer_router
from app.modules.demand.router import router as demand_router
from app.modules.exchange.router import admin_router as exchange_admin_router
from app.modules.exchange.router import retailer_router as exchange_retailer_router
from app.modules.exchange.router import router as exchange_router
from app.modules.governance.router import router as governance_router
from app.modules.i18n.router import admin_router as i18n_admin_router
from app.modules.i18n.router import router as i18n_router
from app.modules.identity.router import address_router, auth_router, user_router
from app.modules.intent.router import intent_router
from app.modules.inventory.router import internal_router as inventory_internal_router
from app.modules.inventory.router import router as inventory_router
from app.modules.missions.router import router as missions_router
from app.modules.negotiation.router import (
    retailer_router as negotiation_retailer_router,
)
from app.modules.negotiation.router import router as negotiation_router
from app.modules.orders.router import router as orders_router
from app.modules.passport.router import (
    admin_router as passport_admin_router,
)
from app.modules.passport.router import (
    public_router as passport_public_router,
)
from app.modules.passport.router import (
    retailer_router as passport_retailer_router,
)
from app.modules.payments.router import internal_router as internal_payments_router
from app.modules.payments.router import router as payments_router
from app.modules.price_intel.router import admin_router as price_intel_admin_router
from app.modules.price_intel.router import (
    retailer_router as price_intel_retailer_router,
)
from app.modules.price_intel.router import router as price_intel_router
from app.modules.pricing.router import router as pricing_router
from app.modules.retailer.router import router as retailer_router
from app.modules.sale_stream.router import router as sale_stream_router
from app.modules.search.router import router as search_router
from app.modules.substitutes.router import router as substitutes_router
from app.modules.vision.router import router as vision_router

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

# Mount Basket Product Passport endpoints (Phase 2D)
api_router.include_router(passport_public_router)
api_router.include_router(passport_retailer_router)
api_router.include_router(passport_admin_router)

# Mount Pricing & Quotes endpoints
api_router.include_router(pricing_router)

# Mount Inventory Reservations endpoints (Phase 2D)
api_router.include_router(inventory_router)
api_router.include_router(inventory_internal_router)

# Mount Orders & Outbox endpoints (Phase 2E)
api_router.include_router(orders_router)

# Mount Payments & Gateway endpoints (Phase 2F)
api_router.include_router(payments_router)
api_router.include_router(internal_payments_router)

# Mount Retailer Portal endpoints (Phase 5A)
api_router.include_router(retailer_router)

# Mount Admin Portal endpoints (Phase 5A)
api_router.include_router(admin_router)

# Phase 3 marketplace features
api_router.include_router(price_intel_router)
api_router.include_router(price_intel_retailer_router)
api_router.include_router(price_intel_admin_router)
api_router.include_router(governance_router)
api_router.include_router(assistant_router)
api_router.include_router(sale_stream_router)
api_router.include_router(i18n_router)
api_router.include_router(i18n_admin_router)
api_router.include_router(demand_router)
api_router.include_router(demand_retailer_router)
api_router.include_router(demand_admin_router)
api_router.include_router(community_router)
api_router.include_router(community_retailer_router)
api_router.include_router(community_admin_router)
api_router.include_router(exchange_router)
api_router.include_router(exchange_retailer_router)
api_router.include_router(exchange_admin_router)
api_router.include_router(negotiation_router)
api_router.include_router(negotiation_retailer_router)
api_router.include_router(auctions_router)
api_router.include_router(auctions_retailer_router)
api_router.include_router(auctions_admin_router)
api_router.include_router(vision_router)

from app.modules.realtime.router import router as realtime_router  # noqa: E402

api_router.include_router(realtime_router)

from app.modules.recurring.router import router as recurring_router  # noqa: E402

api_router.include_router(recurring_router)


@api_router.get("/info", tags=["System"])
async def get_api_info() -> dict:
    """Return version and environment metadata."""
    return {
        "project": settings.PROJECT_NAME,
        "version": "v1",
        "environment": settings.ENVIRONMENT,
    }
