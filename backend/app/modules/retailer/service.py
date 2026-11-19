from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalogue.models import ProductListing, Retailer, StoreInventory
from app.modules.orders.models import OrderItem
from app.modules.retailer.schemas import (
    RetailerOverviewResponse,
    RetailerProfileResponse,
    RetailerProfileUpdateRequest,
)


class RetailerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_profile(
        self, retailer: Retailer, req: RetailerProfileUpdateRequest
    ) -> RetailerProfileResponse:
        if req.description is not None:
            retailer.description = req.description.strip() or None
        if req.logo_url is not None:
            retailer.logo_url = req.logo_url.strip() or None
        if req.business_address is not None:
            retailer.business_address = req.business_address.strip() or None
        if req.contact_phone is not None:
            retailer.contact_phone = req.contact_phone.strip() or None
        if req.contact_email is not None:
            retailer.contact_email = req.contact_email.strip() or None
        if req.business_hours is not None:
            retailer.business_hours = req.business_hours
        if req.policies is not None:
            retailer.policies = req.policies
        if req.is_open is not None:
            retailer.is_open = req.is_open

        await self.session.flush()
        await self.session.refresh(retailer)
        return RetailerProfileResponse.model_validate(retailer)

    async def get_overview(self, retailer: Retailer) -> RetailerOverviewResponse:
        # Count total listings
        listing_stmt = select(func.count(ProductListing.id)).where(
            ProductListing.retailer_id == retailer.id
        )
        total_listings = (await self.session.execute(listing_stmt)).scalar() or 0

        # Sum total inventory units
        inv_stmt = (
            select(func.coalesce(func.sum(StoreInventory.on_hand_quantity), 0))
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(ProductListing.retailer_id == retailer.id)
        )
        total_inventory = (await self.session.execute(inv_stmt)).scalar() or 0

        # Count recent distinct orders
        order_stmt = select(func.count(func.distinct(OrderItem.order_id))).where(
            OrderItem.retailer_id == retailer.id
        )
        recent_orders = (await self.session.execute(order_stmt)).scalar() or 0

        return RetailerOverviewResponse(
            retailer_id=retailer.id,
            store_name=retailer.name,
            slug=retailer.slug,
            state=retailer.state,
            is_open=retailer.is_open,
            verification_status=retailer.verification_status,
            rating=retailer.rating,
            total_listings=total_listings,
            total_inventory_units=total_inventory,
            recent_orders_count=recent_orders,
        )
