import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.orders.models import OrderItem
from app.modules.retailer.schemas import (
    CatalogueProductLookupItem,
    CatalogueVariantItem,
    InventorySummaryStats,
    ListingInventorySummary,
    RetailerBulkInventoryAdjustmentRequest,
    RetailerInventoryAdjustmentRequest,
    RetailerInventoryDashboardResponse,
    RetailerInventoryItemResponse,
    RetailerListingCreateRequest,
    RetailerListingListResponse,
    RetailerListingResponse,
    RetailerListingUpdateRequest,
    RetailerOverviewResponse,
    RetailerProfileResponse,
    RetailerProfileUpdateRequest,
)


class RetailerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ================= Profile & Overview =================

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
        # Total listings
        listing_stmt = select(func.count(ProductListing.id)).where(
            ProductListing.retailer_id == retailer.id
        )
        total_listings = (await self.session.execute(listing_stmt)).scalar() or 0

        # Active listings
        active_stmt = select(func.count(ProductListing.id)).where(
            ProductListing.retailer_id == retailer.id,
            ProductListing.is_active.is_(True),
        )
        active_listings = (await self.session.execute(active_stmt)).scalar() or 0

        # Total on-hand inventory units
        inv_stmt = (
            select(func.coalesce(func.sum(StoreInventory.on_hand_quantity), 0))
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(ProductListing.retailer_id == retailer.id)
        )
        total_inventory = (await self.session.execute(inv_stmt)).scalar() or 0

        # Low stock alerts (available <= low_stock_threshold and available > 0)
        low_stock_stmt = (
            select(func.count(StoreInventory.id))
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(
                ProductListing.retailer_id == retailer.id,
                ProductListing.is_active.is_(True),
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                <= StoreInventory.low_stock_threshold,
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > 0,
            )
        )
        low_stock_alerts = (await self.session.execute(low_stock_stmt)).scalar() or 0

        # Out of stock alerts (available <= 0)
        out_of_stock_stmt = (
            select(func.count(StoreInventory.id))
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(
                ProductListing.retailer_id == retailer.id,
                ProductListing.is_active.is_(True),
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                <= 0,
            )
        )
        out_of_stock_alerts = (
            await self.session.execute(out_of_stock_stmt)
        ).scalar() or 0

        # Recent distinct orders
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
            active_listings=active_listings,
            total_inventory_units=total_inventory,
            low_stock_alerts=low_stock_alerts,
            out_of_stock_alerts=out_of_stock_alerts,
            recent_orders_count=recent_orders,
        )

    # ================= Platform Catalogue Lookup =================

    async def get_catalogue_products(
        self,
        retailer: Retailer,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogueProductLookupItem]:
        # Pre-query existing listings for this retailer to flag already listed variants
        existing_stmt = select(ProductListing.variant_id, ProductListing.id).where(
            ProductListing.retailer_id == retailer.id
        )
        existing_res = await self.session.execute(existing_stmt)
        existing_map = dict(existing_res.all())

        query = (
            select(Product)
            .join(Category, Product.category_id == Category.id)
            .options(
                selectinload(Product.category),
                selectinload(Product.variants),
                selectinload(Product.images),
            )
            .where(Product.is_active.is_(True))
        )

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(Product.name).like(term),
                    func.lower(Product.brand).like(term),
                )
            )

        if category_id:
            query = query.where(Product.category_id == category_id)

        query = query.order_by(Product.name.asc()).limit(limit).offset(offset)
        products = (await self.session.execute(query)).scalars().all()

        results: list[CatalogueProductLookupItem] = []
        for p in products:
            primary_img = next((img.url for img in p.images if img.is_primary), None)
            if not primary_img and p.images:
                primary_img = p.images[0].url

            variant_items: list[CatalogueVariantItem] = []
            for v in p.variants:
                if v.is_active:
                    listed_id = existing_map.get(v.id)
                    variant_items.append(
                        CatalogueVariantItem(
                            id=v.id,
                            name=v.name,
                            sku=v.sku,
                            attributes=v.attributes or {},
                            is_active=v.is_active,
                            is_already_listed=listed_id is not None,
                            existing_listing_id=listed_id,
                        )
                    )

            results.append(
                CatalogueProductLookupItem(
                    id=p.id,
                    name=p.name,
                    brand=p.brand,
                    category_id=p.category_id,
                    category_name=p.category.name if p.category else "",
                    description=p.description,
                    image_url=primary_img,
                    variants=variant_items,
                )
            )

        return results

    # ================= Retailer Listings =================

    async def list_listings(
        self,
        retailer: Retailer,
        search: str | None = None,
        is_active: bool | None = None,
        is_low_stock: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RetailerListingListResponse:
        base_query = (
            select(ProductListing)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .join(StoreInventory, StoreInventory.listing_id == ProductListing.id)
            .options(
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.category),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(ProductListing.inventory),
            )
            .where(ProductListing.retailer_id == retailer.id)
        )

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Product.name).like(term),
                    func.lower(ProductVariant.name).like(term),
                    func.lower(ProductVariant.sku).like(term),
                    func.lower(ProductListing.seller_sku).like(term),
                )
            )

        if is_active is not None:
            base_query = base_query.where(ProductListing.is_active.is_(is_active))

        if is_low_stock is True:
            base_query = base_query.where(
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                <= StoreInventory.low_stock_threshold
            )

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Fetch page
        paged_stmt = (
            base_query.order_by(ProductListing.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        listings = (await self.session.execute(paged_stmt)).scalars().all()

        items: list[RetailerListingResponse] = []
        for listing in listings:
            items.append(self._build_listing_response(listing))

        return RetailerListingListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_listing(
        self, retailer: Retailer, req: RetailerListingCreateRequest
    ) -> RetailerListingResponse:
        # Check variant existence
        variant_stmt = (
            select(ProductVariant)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.images),
            )
            .where(ProductVariant.id == req.variant_id)
        )
        variant = (await self.session.execute(variant_stmt)).scalar_one_or_none()
        if not variant:
            raise AppException(
                code="VARIANT_NOT_FOUND",
                message="The specified product variant was not found.",
                status_code=404,
            )

        # Check for duplicate listing for this retailer
        dup_stmt = select(ProductListing).where(
            ProductListing.retailer_id == retailer.id,
            ProductListing.variant_id == req.variant_id,
        )
        existing = (await self.session.execute(dup_stmt)).scalar_one_or_none()
        if existing:
            raise AppException(
                code="LISTING_ALREADY_EXISTS",
                message="Your store already has an active or existing listing for this product variant.",
                status_code=409,
            )

        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            variant_id=req.variant_id,
            seller_sku=req.seller_sku.strip() if req.seller_sku else None,
            original_price_paise=req.original_price_paise,
            selling_price_paise=req.selling_price_paise,
            currency="INR",
            hsn_code=req.hsn_code.strip() if req.hsn_code else None,
            gst_rate_basis_points=req.gst_rate_basis_points,
            is_active=req.is_active,
        )
        self.session.add(listing)
        await self.session.flush()

        inventory = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing.id,
            on_hand_quantity=req.initial_on_hand_quantity,
            reserved_quantity=0,
            low_stock_threshold=req.low_stock_threshold,
        )
        self.session.add(inventory)
        await self.session.flush()

        # Load fresh relationships
        full_listing = await self._get_full_listing(listing.id, retailer.id)
        return self._build_listing_response(full_listing)

    async def get_listing(
        self, listing_id: uuid.UUID, retailer: Retailer
    ) -> RetailerListingResponse:
        listing = await self._get_full_listing(listing_id, retailer.id)
        if not listing:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )
        return self._build_listing_response(listing)

    async def update_listing(
        self,
        listing_id: uuid.UUID,
        retailer: Retailer,
        req: RetailerListingUpdateRequest,
    ) -> RetailerListingResponse:
        listing = await self._get_full_listing(listing_id, retailer.id)
        if not listing:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )

        new_orig = (
            req.original_price_paise
            if req.original_price_paise is not None
            else listing.original_price_paise
        )
        new_selling = (
            req.selling_price_paise
            if req.selling_price_paise is not None
            else listing.selling_price_paise
        )

        if new_selling > new_orig:
            raise AppException(
                code="INVALID_PRICING",
                message=f"Selling price ({new_selling} paise) cannot exceed MRP ({new_orig} paise).",
                status_code=400,
            )

        if req.seller_sku is not None:
            listing.seller_sku = req.seller_sku.strip() or None
        if req.original_price_paise is not None:
            listing.original_price_paise = req.original_price_paise
        if req.selling_price_paise is not None:
            listing.selling_price_paise = req.selling_price_paise
        if req.hsn_code is not None:
            listing.hsn_code = req.hsn_code.strip() or None
        if req.gst_rate_basis_points is not None:
            listing.gst_rate_basis_points = req.gst_rate_basis_points
        if req.is_active is not None:
            listing.is_active = req.is_active

        if req.low_stock_threshold is not None and listing.inventory:
            listing.inventory.low_stock_threshold = req.low_stock_threshold

        await self.session.flush()
        await self.session.refresh(listing)
        return self._build_listing_response(listing)

    async def delete_listing(self, listing_id: uuid.UUID, retailer: Retailer) -> None:
        listing = await self._get_full_listing(listing_id, retailer.id)
        if not listing:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )

        # Check if active reservations exist
        if listing.inventory and listing.inventory.reserved_quantity > 0:
            raise AppException(
                code="CANNOT_DELETE_ACTIVE_RESERVATIONS",
                message="Cannot delete listing while customer holds or active reservations exist.",
                status_code=409,
            )

        # Deactivate listing to preserve historical order snapshots
        listing.is_active = False
        await self.session.flush()

    # ================= Retailer Inventory =================

    async def get_inventory_dashboard(
        self,
        retailer: Retailer,
        search: str | None = None,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RetailerInventoryDashboardResponse:
        base_query = (
            select(StoreInventory)
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .options(
                selectinload(StoreInventory.listing)
                .selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
            )
            .where(ProductListing.retailer_id == retailer.id)
        )

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Product.name).like(term),
                    func.lower(ProductVariant.name).like(term),
                    func.lower(ProductVariant.sku).like(term),
                    func.lower(ProductListing.seller_sku).like(term),
                )
            )

        if status_filter == "LOW_STOCK":
            base_query = base_query.where(
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                <= StoreInventory.low_stock_threshold,
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > 0,
            )
        elif status_filter == "OUT_OF_STOCK":
            base_query = base_query.where(
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                <= 0
            )
        elif status_filter == "IN_STOCK":
            base_query = base_query.where(
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > StoreInventory.low_stock_threshold
            )

        # Aggregate summary stats across retailer's entire inventory
        stats_stmt = (
            select(
                func.count(StoreInventory.id).label("total_items"),
                func.coalesce(func.sum(StoreInventory.on_hand_quantity), 0).label(
                    "total_on_hand"
                ),
                func.coalesce(func.sum(StoreInventory.reserved_quantity), 0).label(
                    "total_reserved"
                ),
                func.count(StoreInventory.id)
                .filter(
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    <= StoreInventory.low_stock_threshold,
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    > 0,
                )
                .label("low_stock_count"),
                func.count(StoreInventory.id)
                .filter(
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    <= 0
                )
                .label("out_of_stock_count"),
            )
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(ProductListing.retailer_id == retailer.id)
        )
        stats_res = (await self.session.execute(stats_stmt)).one()

        total_items = stats_res.total_items
        total_on_hand = stats_res.total_on_hand
        total_reserved = stats_res.total_reserved
        total_available = max(0, total_on_hand - total_reserved)
        low_stock_count = stats_res.low_stock_count
        out_of_stock_count = stats_res.out_of_stock_count

        # Total count for pagination
        count_stmt = select(func.count()).select_from(base_query.subquery())
        paged_total = (await self.session.execute(count_stmt)).scalar() or 0

        paged_stmt = (
            base_query.order_by(
                (
                    StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity
                ).asc(),
                StoreInventory.updated_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        inventories = (await self.session.execute(paged_stmt)).scalars().all()

        items: list[RetailerInventoryItemResponse] = []
        for inv in inventories:
            items.append(self._build_inventory_item_response(inv))

        return RetailerInventoryDashboardResponse(
            summary=InventorySummaryStats(
                total_items=total_items,
                total_on_hand_units=total_on_hand,
                total_reserved_units=total_reserved,
                total_available_units=total_available,
                low_stock_count=low_stock_count,
                out_of_stock_count=out_of_stock_count,
            ),
            items=items,
            total=paged_total,
            limit=limit,
            offset=offset,
        )

    async def adjust_inventory(
        self,
        listing_id: uuid.UUID,
        retailer: Retailer,
        req: RetailerInventoryAdjustmentRequest,
    ) -> RetailerInventoryItemResponse:
        # Fetch listing with inventory row lock for update
        stmt = (
            select(StoreInventory)
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .options(
                selectinload(StoreInventory.listing)
                .selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
            )
            .where(
                StoreInventory.listing_id == listing_id,
                ProductListing.retailer_id == retailer.id,
            )
            .with_for_update()
        )
        inv = (await self.session.execute(stmt)).scalar_one_or_none()
        if not inv:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )

        if req.adjustment_type == "SET":
            new_on_hand = req.quantity
        else:  # DELTA
            new_on_hand = inv.on_hand_quantity + req.quantity

        if new_on_hand < 0:
            raise AppException(
                code="NEGATIVE_STOCK_NOT_ALLOWED",
                message=f"Adjustment would result in negative stock ({new_on_hand}).",
                status_code=400,
            )

        if new_on_hand < inv.reserved_quantity:
            raise AppException(
                code="CANNOT_REDUCE_BELOW_RESERVED",
                message=(
                    f"Cannot reduce on-hand stock ({new_on_hand}) below "
                    f"currently reserved customer holds ({inv.reserved_quantity})."
                ),
                status_code=409,
            )

        inv.on_hand_quantity = new_on_hand
        if req.low_stock_threshold is not None:
            inv.low_stock_threshold = req.low_stock_threshold

        await self.session.flush()
        await self.session.refresh(inv)
        return self._build_inventory_item_response(inv)

    async def bulk_adjust_inventory(
        self,
        retailer: Retailer,
        req: RetailerBulkInventoryAdjustmentRequest,
    ) -> list[RetailerInventoryItemResponse]:
        results: list[RetailerInventoryItemResponse] = []
        for item in req.items:
            adj_req = RetailerInventoryAdjustmentRequest(
                adjustment_type="SET",
                quantity=item.on_hand_quantity,
                low_stock_threshold=item.low_stock_threshold,
                reason="Bulk inventory adjustment",
            )
            res = await self.adjust_inventory(item.listing_id, retailer, adj_req)
            results.append(res)
        return results

    # ================= Private Helpers =================

    async def _get_full_listing(
        self, listing_id: uuid.UUID, retailer_id: uuid.UUID
    ) -> ProductListing | None:
        stmt = (
            select(ProductListing)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .options(
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.category),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(ProductListing.inventory),
            )
            .where(
                ProductListing.id == listing_id,
                ProductListing.retailer_id == retailer_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _build_listing_response(
        self, listing: ProductListing
    ) -> RetailerListingResponse:
        v = listing.variant
        p = v.product
        cat = p.category
        inv = listing.inventory

        primary_img = next((img.url for img in p.images if img.is_primary), None)
        if not primary_img and p.images:
            primary_img = p.images[0].url

        on_hand = inv.on_hand_quantity if inv else 0
        reserved = inv.reserved_quantity if inv else 0
        thresh = inv.low_stock_threshold if inv else 10
        available = max(0, on_hand - reserved)

        return RetailerListingResponse(
            id=listing.id,
            retailer_id=listing.retailer_id,
            variant_id=listing.variant_id,
            product_id=p.id,
            product_name=p.name,
            brand=p.brand,
            category_name=cat.name if cat else "",
            variant_name=v.name,
            variant_sku=v.sku,
            variant_attributes=v.attributes or {},
            seller_sku=listing.seller_sku,
            original_price_paise=listing.original_price_paise,
            selling_price_paise=listing.selling_price_paise,
            currency=listing.currency,
            hsn_code=listing.hsn_code,
            gst_rate_basis_points=listing.gst_rate_basis_points,
            is_tax_verified=listing.is_tax_verified,
            is_active=listing.is_active,
            image_url=primary_img,
            inventory=ListingInventorySummary(
                on_hand_quantity=on_hand,
                reserved_quantity=reserved,
                available_quantity=available,
                low_stock_threshold=thresh,
                is_low_stock=available <= thresh and available > 0,
                is_out_of_stock=available <= 0,
            ),
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )

    def _build_inventory_item_response(
        self, inv: StoreInventory
    ) -> RetailerInventoryItemResponse:
        listing = inv.listing
        v = listing.variant
        p = v.product

        on_hand = inv.on_hand_quantity
        reserved = inv.reserved_quantity
        thresh = inv.low_stock_threshold
        available = max(0, on_hand - reserved)

        return RetailerInventoryItemResponse(
            listing_id=listing.id,
            product_name=p.name,
            variant_name=v.name,
            sku=v.sku,
            seller_sku=listing.seller_sku,
            selling_price_paise=listing.selling_price_paise,
            on_hand_quantity=on_hand,
            reserved_quantity=reserved,
            available_quantity=available,
            low_stock_threshold=thresh,
            is_low_stock=available <= thresh and available > 0,
            is_out_of_stock=available <= 0,
            is_active=listing.is_active,
            updated_at=inv.updated_at,
        )
