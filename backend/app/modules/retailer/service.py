import datetime
import logging
import re
import uuid
from types import SimpleNamespace

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.orders.models import (
    CustomerNotification,
    Order,
    OrderItem,
    OrderStatusHistory,
)
from app.modules.pricing.models import Discount
from app.modules.retailer.schemas import (
    CatalogueProductLookupItem,
    CatalogueVariantItem,
    InventorySummaryStats,
    ListingInventorySummary,
    RetailerAnalyticsProductItem,
    RetailerAnalyticsResponse,
    RetailerBulkInventoryAdjustmentRequest,
    RetailerInventoryAdjustmentRequest,
    RetailerInventoryDashboardResponse,
    RetailerInventoryItemResponse,
    RetailerListingCreateRequest,
    RetailerListingListResponse,
    RetailerListingResponse,
    RetailerListingUpdateRequest,
    RetailerOfferCreateRequest,
    RetailerOfferItem,
    RetailerOfferUpdateRequest,
    RetailerOrderDetailResponse,
    RetailerOrderItemResponse,
    RetailerOrderListItem,
    RetailerOrderListResponse,
    RetailerOrderStatusUpdateRequest,
    RetailerOverviewResponse,
    RetailerProductCreateRequest,
    RetailerProfileResponse,
    RetailerProfileUpdateRequest,
)

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "product"


class RetailerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _derive_suborder_status(items: list[OrderItem]) -> str:
        if not items:
            return "CONFIRMED"
        active_items = [
            i
            for i in items
            if (getattr(i, "fulfillment_status", None) or "CONFIRMED") != "CANCELLED"
        ]
        if not active_items:
            return "CANCELLED"
        statuses = [
            getattr(i, "fulfillment_status", None) or "CONFIRMED" for i in active_items
        ]
        if all(s == "DELIVERED" for s in statuses):
            return "DELIVERED"
        if all(s in ("OUT_FOR_DELIVERY", "DELIVERED") for s in statuses):
            return "OUT_FOR_DELIVERY"
        if all(s in ("SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED") for s in statuses):
            return "SHIPPED"
        if all(
            s in ("PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED")
            for s in statuses
        ):
            return "PACKED"
        if any(
            s in ("PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED")
            for s in statuses
        ):
            return "PROCESSING"
        if all(s == "CONFIRMED" for s in statuses):
            return "CONFIRMED"
        return "PENDING_PAYMENT"

    # ================= Profile & Overview =================

    async def update_profile(
        self, retailer: Retailer, req: RetailerProfileUpdateRequest
    ) -> RetailerProfileResponse:
        if req.gstin is not None:
            import re as _re

            from app.modules.retailer.schemas import GSTIN_RE

            g = req.gstin.strip().upper()
            if g and not _re.fullmatch(GSTIN_RE, g):
                raise AppException(
                    code="INVALID_GSTIN",
                    message="GSTIN must be 15 characters, e.g. 29ABCDE1234F1Z5.",
                    status_code=422,
                )
            retailer.gstin = g or None
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

    def _assert_verified_and_active(
        self, retailer: Retailer, action: str = "manage store listings"
    ) -> None:
        if retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message=(
                    f"Retailer account verification status is '{retailer.verification_status}'. "
                    f"Only VERIFIED retailers can {action}."
                ),
                status_code=403,
            )
        if not retailer.is_active:
            raise AppException(
                code="RETAILER_SUSPENDED",
                message="Retailer account is deactivated or suspended.",
                status_code=403,
            )

    async def _sync_product_search(self, product_id: uuid.UUID | None) -> None:
        if not product_id:
            return
        # Durable path: transactional outbox event -> Kafka -> OpenSearch consumer.
        from app.core.events.catalogue_events import enqueue_product_events

        await enqueue_product_events(
            self.session, [product_id], reason="catalogue_change"
        )
        # Fast path: best-effort synchronous index update when OpenSearch is up.
        try:
            from app.core.config import settings
            from app.core.search.client import get_opensearch_client
            from app.core.search.index import IndexManager

            if settings.has_opensearch:
                os_client = get_opensearch_client(settings)
                if await os_client.ping():
                    idx_mgr = IndexManager(os_client)
                    await idx_mgr.sync_product(self.session, product_id)
        except Exception as exc:
            logger.warning("Search sync skipped for product %s: %s", product_id, exc)

    async def create_listing(
        self, retailer: Retailer, req: RetailerListingCreateRequest
    ) -> RetailerListingResponse:
        self._assert_verified_and_active(retailer, "create store listings")

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
        await self._after_price_change(full_listing, None)
        if variant.product_id:
            await self._sync_product_search(variant.product_id)
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
        self._assert_verified_and_active(retailer, "modify store listings")
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
        previous_selling = int(listing.selling_price_paise)
        previous_mrp = int(listing.original_price_paise)

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
        if (
            int(listing.selling_price_paise) != previous_selling
            or int(listing.original_price_paise) != previous_mrp
        ):
            await self._after_price_change(listing, previous_selling)
        if listing.variant and listing.variant.product_id:
            await self._sync_product_search(listing.variant.product_id)
        return self._build_listing_response(listing)

    async def _after_price_change(
        self, listing: ProductListing, previous_selling: int | None
    ) -> None:
        """Phase 3: record price history and publish price-change signals."""
        from app.core.events.marketplace_events import enqueue_marketplace_event
        from app.modules.price_intel.service import record_price_tick

        await record_price_tick(
            self.session,
            listing_id=listing.id,
            selling_price_paise=listing.selling_price_paise,
            mrp_paise=listing.original_price_paise,
        )
        # Listing events must carry product_id (envelope partitioning rule).
        product_id = (
            await self.session.execute(
                select(ProductVariant.product_id).where(
                    ProductVariant.id == listing.variant_id
                )
            )
        ).scalar_one()
        await enqueue_marketplace_event(
            self.session,
            event_type="price.changed",
            aggregate_type="listing",
            aggregate_id=listing.id,
            payload={
                "product_id": product_id,
                "listing_id": listing.id,
                "previous_price_paise": previous_selling,
                "price_paise": int(listing.selling_price_paise),
                "mrp_paise": int(listing.original_price_paise),
            },
        )
        from app.modules.price_intel.extras import trigger_price_alerts

        await trigger_price_alerts(self.session, listing.variant_id)
        if (
            previous_selling is not None
            and listing.selling_price_paise < previous_selling
        ):
            from app.modules.sale_stream.service import record_price_drop

            await record_price_drop(
                self.session, listing=listing, previous_price_paise=previous_selling
            )

    async def delete_listing(self, listing_id: uuid.UUID, retailer: Retailer) -> None:
        self._assert_verified_and_active(retailer, "delete store listings")
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

        prod_id = (
            listing.variant.product_id
            if (listing.variant and listing.variant.product_id)
            else None
        )
        # Deactivate listing to preserve historical order snapshots
        listing.is_active = False
        await self.session.flush()
        if prod_id:
            await self._sync_product_search(prod_id)

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
        self._assert_verified_and_active(retailer, "adjust inventory")
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
        if inv.listing and inv.listing.variant and inv.listing.variant.product_id:
            await self._sync_product_search(inv.listing.variant.product_id)
        return self._build_inventory_item_response(inv)

    async def bulk_adjust_inventory(
        self,
        retailer: Retailer,
        req: RetailerBulkInventoryAdjustmentRequest,
    ) -> list[RetailerInventoryItemResponse]:
        self._assert_verified_and_active(retailer, "adjust inventory")
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
            listing_image_url=getattr(listing, "image_url", None),
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

    # ================= Custom Product & Listing Creation =================

    async def create_custom_product_and_listing(
        self, retailer: Retailer, req: RetailerProductCreateRequest
    ) -> RetailerListingResponse:
        self._assert_verified_and_active(retailer, "create store products")

        # Verify category exists
        cat_stmt = select(Category).where(Category.id == req.category_id)
        category = (await self.session.execute(cat_stmt)).scalar_one_or_none()
        if not category:
            raise AppException(
                code="CATEGORY_NOT_FOUND",
                message="The specified category does not exist.",
                status_code=404,
            )

        # Check for duplicate variant SKU
        sku_stmt = select(ProductVariant).where(ProductVariant.sku == req.sku.strip())
        existing_sku = (await self.session.execute(sku_stmt)).scalar_one_or_none()
        if existing_sku:
            raise AppException(
                code="SKU_ALREADY_EXISTS",
                message=f"Product variant with SKU '{req.sku}' already exists in platform catalogue.",
                status_code=409,
            )

        # Generate unique product slug
        base_slug = _slugify(req.name)
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        product = Product(
            id=uuid.uuid4(),
            name=req.name.strip(),
            slug=slug,
            brand=req.brand.strip(),
            category_id=req.category_id,
            description=req.description.strip() if req.description else None,
            is_active=req.is_active,
        )
        self.session.add(product)
        await self.session.flush()

        if req.image_url and req.image_url.strip():
            img = ProductImage(
                id=uuid.uuid4(),
                product_id=product.id,
                url=req.image_url.strip(),
                is_primary=True,
                sort_order=0,
            )
            self.session.add(img)
            await self.session.flush()

        variant = ProductVariant(
            id=uuid.uuid4(),
            product_id=product.id,
            name=req.variant_name.strip() if req.variant_name else "Standard",
            sku=req.sku.strip(),
            attributes={"brand": req.brand.strip(), "retailer": retailer.name},
            is_active=req.is_active,
        )
        self.session.add(variant)
        await self.session.flush()

        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            variant_id=variant.id,
            seller_sku=(req.seller_sku or req.sku).strip(),
            original_price_paise=req.original_price_paise,
            selling_price_paise=req.selling_price_paise,
            currency="INR",
            hsn_code=req.hsn_code.strip() if req.hsn_code else "84713010",
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

        full_listing = await self._get_full_listing(listing.id, retailer.id)
        await self._after_price_change(full_listing, None)
        return self._build_listing_response(full_listing)

    # ================= Retailer Orders =================

    async def list_orders(
        self,
        retailer: Retailer,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RetailerOrderListResponse:
        # Enforce retailer tenant isolation on orders:
        # Only fetch orders containing OrderItems for this retailer
        subq = (
            select(OrderItem.order_id)
            .where(OrderItem.retailer_id == retailer.id)
            .distinct()
            .subquery()
        )

        query = (
            select(Order)
            .join(subq, Order.id == subq.c.order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
        )

        if status and status.strip():
            query = query.where(Order.status == status.strip().upper())

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query = query.where(func.lower(Order.order_number).like(term))

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        paged_stmt = query.order_by(Order.created_at.desc()).limit(limit).offset(offset)
        orders = (await self.session.execute(paged_stmt)).scalars().all()

        items: list[RetailerOrderListItem] = []
        for o in orders:
            # Filter order items strictly to this retailer
            my_items = [item for item in o.items if item.retailer_id == retailer.id]
            if not my_items:
                continue

            subtotal = sum(i.total_selling_price_paise for i in my_items)
            tax = sum(i.total_tax_paise for i in my_items)
            total_paise = subtotal + tax

            snap = o.delivery_address_snapshot or {}
            cust_name = (
                snap.get("recipient_name") or snap.get("full_name") or "Valued Customer"
            )
            city = snap.get("city")
            state = snap.get("state")

            item_responses = [
                RetailerOrderItemResponse(
                    id=i.id,
                    order_id=i.order_id,
                    listing_id=i.listing_id,
                    variant_id=i.variant_id,
                    product_title=i.product_title,
                    variant_title=i.variant_title,
                    sku=i.sku,
                    quantity=i.quantity,
                    unit_selling_price_paise=i.unit_selling_price_paise,
                    total_selling_price_paise=i.total_selling_price_paise,
                    total_tax_paise=i.total_tax_paise,
                    fulfillment_status=getattr(i, "fulfillment_status", None)
                    or "CONFIRMED",
                    created_at=i.created_at,
                )
                for i in my_items
            ]

            retailer_status = self._derive_suborder_status(my_items)

            items.append(
                RetailerOrderListItem(
                    id=o.id,
                    order_number=o.order_number,
                    status=retailer_status,
                    payment_status=o.payment_status,
                    customer_name=cust_name,
                    delivery_city=city,
                    delivery_state=state,
                    total_items=sum(i.quantity for i in my_items),
                    retailer_subtotal_paise=subtotal,
                    retailer_tax_paise=tax,
                    retailer_total_paise=total_paise,
                    created_at=o.created_at,
                    items=item_responses,
                )
            )

        return RetailerOrderListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_order_detail(
        self, order_id: uuid.UUID, retailer: Retailer
    ) -> RetailerOrderDetailResponse:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
            .where(Order.id == order_id)
        )
        order = (await self.session.execute(stmt)).scalar_one_or_none()
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order not found.",
                status_code=404,
            )

        # Enforce tenant isolation: check that this order has items for this retailer
        my_items = [i for i in order.items if i.retailer_id == retailer.id]
        if not my_items:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order not found or does not belong to this retailer.",
                status_code=404,
            )

        subtotal = sum(i.total_selling_price_paise for i in my_items)
        tax = sum(i.total_tax_paise for i in my_items)
        total_paise = subtotal + tax

        snap = order.delivery_address_snapshot or {}
        cust_name = (
            snap.get("recipient_name") or snap.get("full_name") or "Valued Customer"
        )

        item_responses = [
            RetailerOrderItemResponse(
                id=i.id,
                order_id=i.order_id,
                listing_id=i.listing_id,
                variant_id=i.variant_id,
                product_title=i.product_title,
                variant_title=i.variant_title,
                sku=i.sku,
                quantity=i.quantity,
                unit_selling_price_paise=i.unit_selling_price_paise,
                total_selling_price_paise=i.total_selling_price_paise,
                total_tax_paise=i.total_tax_paise,
                fulfillment_status=getattr(i, "fulfillment_status", None)
                or "CONFIRMED",
                created_at=i.created_at,
            )
            for i in my_items
        ]

        histories = [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "reason": h.reason,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in order.status_history
        ]

        retailer_status = self._derive_suborder_status(my_items)

        return RetailerOrderDetailResponse(
            id=order.id,
            order_number=order.order_number,
            status=retailer_status,
            payment_status=order.payment_status,
            customer_name=cust_name,
            delivery_address=snap,
            items=item_responses,
            retailer_subtotal_paise=subtotal,
            retailer_tax_paise=tax,
            retailer_total_paise=total_paise,
            created_at=order.created_at,
            status_history=histories,
        )

    async def update_order_status(
        self,
        order_id: uuid.UUID,
        retailer: Retailer,
        req: RetailerOrderStatusUpdateRequest,
    ) -> RetailerOrderDetailResponse:
        self._assert_verified_and_active(retailer, "update order status")

        stmt = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
            .where(Order.id == order_id)
            .with_for_update(of=Order)
        )
        order = (await self.session.execute(stmt)).scalar_one_or_none()
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order not found.",
                status_code=404,
            )

        my_items = [i for i in order.items if i.retailer_id == retailer.id]
        if not my_items:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order not found or does not belong to this retailer.",
                status_code=404,
            )

        # Retailers may only fulfil orders that have actually been paid for and
        # are still live. Unpaid orders are expired by the payment SLA job.
        if order.status in ("PENDING_PAYMENT", "CANCELLED", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_TRANSITION",
                message=f"Cannot update fulfilment for an order in status '{order.status}'.",
                status_code=409,
            )
        newly_cancelled: list = []

        target_status = req.status.strip().upper()
        # Defence in depth: fulfilment requires a captured payment, regardless of
        # how the order status was reached.
        if target_status != "CANCELLED" and order.payment_status not in (
            "SUCCEEDED",
            "PARTIALLY_REFUNDED",
        ):
            raise AppException(
                code="ORDER_NOT_PAID",
                message="This order has not been paid yet and cannot be fulfilled.",
                status_code=409,
            )
        allowed_statuses = {
            "CONFIRMED",
            "PROCESSING",
            "PACKED",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
            "CANCELLED",
        }
        if target_status not in allowed_statuses:
            raise AppException(
                code="INVALID_STATUS_TRANSITION",
                message=f"Invalid target status '{target_status}'. Allowed: {', '.join(sorted(allowed_statuses))}",
                status_code=422,
            )

        # Enforce valid transitions per item
        rank_map = {
            "PENDING_PAYMENT": 0,
            "CONFIRMED": 1,
            "PROCESSING": 2,
            "PACKED": 3,
            "SHIPPED": 4,
            "OUT_FOR_DELIVERY": 5,
            "DELIVERED": 6,
        }
        target_rank = rank_map.get(target_status)
        old_retailer_status = self._derive_suborder_status(my_items)

        for item in my_items:
            curr_item_status = getattr(item, "fulfillment_status", None) or "CONFIRMED"
            if curr_item_status == target_status:
                continue
            if curr_item_status == "DELIVERED":
                raise AppException(
                    code="INVALID_STATUS_TRANSITION",
                    message="Cannot change status of an already delivered item.",
                    status_code=422,
                )
            if curr_item_status == "CANCELLED":
                raise AppException(
                    code="INVALID_STATUS_TRANSITION",
                    message="Cannot change status of a cancelled item.",
                    status_code=422,
                )
            if target_status == "CANCELLED":
                if curr_item_status in ("SHIPPED", "OUT_FOR_DELIVERY"):
                    raise AppException(
                        code="INVALID_STATUS_TRANSITION",
                        message="Cannot cancel an item that has already been dispatched.",
                        status_code=422,
                    )
                item.fulfillment_status = target_status
                newly_cancelled.append(item)
                continue

            curr_rank = rank_map.get(curr_item_status, 0)
            if target_rank is not None and target_rank < curr_rank:
                raise AppException(
                    code="INVALID_STATUS_TRANSITION",
                    message=f"Cannot regress status from {curr_item_status} to {target_status}.",
                    status_code=422,
                )
            item.fulfillment_status = target_status

        # Synchronize and derive overall parent order status across ALL items
        parent_derived_status = self._derive_suborder_status(order.items)
        if order.status != parent_derived_status:
            order.status = parent_derived_status
            order.version = (order.version or 0) + 1
            if parent_derived_status == "DELIVERED" and not order.delivered_at:
                order.delivered_at = datetime.datetime.now(datetime.UTC)
            elif parent_derived_status == "CANCELLED" and not order.cancelled_at:
                order.cancelled_at = datetime.datetime.now(datetime.UTC)
                order.cancellation_reason = (
                    req.reason or f"Cancelled by {retailer.name}"
                )

        hist = OrderStatusHistory(
            id=uuid.uuid4(),
            order_id=order.id,
            from_status=old_retailer_status,
            to_status=target_status,
            reason=req.reason
            or f"Fulfillment updated to {target_status} by {retailer.name}",
        )
        self.session.add(hist)

        if order.customer_id:
            notif = CustomerNotification(
                id=uuid.uuid4(),
                customer_id=order.customer_id,
                order_id=order.id,
                title=f"Order {order.order_number} {target_status.replace('_', ' ').title()}",
                message=f"Items from {retailer.name} in order #{order.order_number} are now {target_status.lower().replace('_', ' ')}.",
                event_type=f"ORDER_{target_status}",
            )
            self.session.add(notif)

        await self.session.flush()
        if newly_cancelled:
            await self._compensate_cancelled_items(order, retailer, newly_cancelled)
        return await self.get_order_detail(order.id, retailer)

    async def _compensate_cancelled_items(
        self, order: Order, retailer: Retailer, items: list
    ) -> None:
        """Restock and refund items a retailer cancels after payment.

        Without this, a retailer cancellation left the customer charged for goods
        that will never ship and permanently removed the stock from inventory.
        """
        from app.modules.inventory.service import ReservationService

        await ReservationService(self.session).restock_inventory_items(
            [(i.listing_id, i.quantity) for i in items]
        )
        refund_paise = sum(
            int(i.unit_discounted_price_paise) * int(i.quantity) for i in items
        )
        if order.status == "CANCELLED":
            # Whole order cancelled: the customer is also owed the delivery fee.
            refund_paise += int(getattr(order, "delivery_fee_paise", 0) or 0)
        if refund_paise <= 0 or order.payment_status not in (
            "SUCCEEDED",
            "PARTIALLY_REFUNDED",
        ):
            await self.session.flush()
            return
        from app.modules.payments.schemas import CreateRefundRequest
        from app.modules.payments.service import PaymentService

        item_key = "-".join(sorted(str(i.id)[:8] for i in items))
        try:
            await PaymentService(self.session).create_refund(
                order_id=order.id,
                req=CreateRefundRequest(
                    amount_paise=refund_paise,
                    reason=f"Cancelled by retailer {retailer.name}"[:255],
                    capture_id=order.fulfilling_capture_id,
                ),
                idempotency_key=f"retailer_cancel_{order.id}_{item_key}"[:128],
                is_internal=True,
            )
        except Exception as exc:
            logger.error(
                "Refund for retailer-cancelled items on order %s failed: %s",
                order.id,
                exc,
            )
            self.session.add(
                OrderStatusHistory(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    from_status=order.status,
                    to_status=order.status,
                    reason=f"REFUND_PENDING: retailer cancellation refund of {refund_paise} paise needs retry",
                )
            )
            await self.session.flush()

    # ================= Retailer Offers & Discounts =================

    async def list_offers(self, retailer: Retailer) -> list[RetailerOfferItem]:
        # Scoped to RET_<retailer.id.hex[:24]> or retailer's listings
        scope_prefix = f"RET_{retailer.id.hex[:24]}"
        stmt = (
            select(Discount)
            .outerjoin(ProductListing, Discount.listing_id == ProductListing.id)
            .where(
                or_(
                    Discount.scope == scope_prefix,
                    ProductListing.retailer_id == retailer.id,
                )
            )
            .order_by(Discount.created_at.desc())
        )
        discounts = (await self.session.execute(stmt)).scalars().all()
        return [RetailerOfferItem.model_validate(d) for d in discounts]

    async def create_offer(
        self, retailer: Retailer, req: RetailerOfferCreateRequest
    ) -> RetailerOfferItem:
        self._assert_verified_and_active(retailer, "create offers")

        if req.listing_id:
            chk = (
                await self.session.execute(
                    select(ProductListing.id).where(
                        ProductListing.id == req.listing_id,
                        ProductListing.retailer_id == retailer.id,
                    )
                )
            ).scalar_one_or_none()
            if not chk:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Listing not found in your store catalogue.",
                    status_code=404,
                )

        if req.code and req.code.strip():
            existing_code = (
                await self.session.execute(
                    select(Discount.id).where(
                        func.upper(Discount.code) == req.code.strip().upper()
                    )
                )
            ).scalar_one_or_none()
            if existing_code:
                raise AppException(
                    code="OFFER_CODE_EXISTS",
                    message=f"Offer code '{req.code}' is already in use.",
                    status_code=409,
                )

        scope = f"RET_{retailer.id.hex[:24]}"
        discount = Discount(
            id=uuid.uuid4(),
            code=req.code.strip() if req.code else None,
            name=req.name.strip(),
            description=req.description.strip() if req.description else None,
            discount_type=req.discount_type,
            discount_value=req.discount_value,
            listing_id=req.listing_id,
            scope=scope,
            min_order_paise=req.min_order_paise,
            max_discount_paise=req.max_discount_paise,
            is_active=req.is_active,
            valid_from=datetime.datetime.now(datetime.UTC),
            valid_to=req.valid_to,
        )
        self.session.add(discount)
        await self.session.flush()
        from app.modules.sale_stream.service import record_flash_deal

        await record_flash_deal(self.session, discount=discount)
        return RetailerOfferItem.model_validate(discount)

    async def update_offer(
        self, offer_id: uuid.UUID, retailer: Retailer, req: RetailerOfferUpdateRequest
    ) -> RetailerOfferItem:
        self._assert_verified_and_active(retailer, "update offers")
        scope_prefix = f"RET_{retailer.id.hex[:24]}"

        stmt = select(Discount).where(
            Discount.id == offer_id,
            Discount.scope == scope_prefix,
        )
        discount = (await self.session.execute(stmt)).scalar_one_or_none()
        if not discount:
            raise AppException(
                code="OFFER_NOT_FOUND",
                message="Offer not found or not owned by your store.",
                status_code=404,
            )

        if req.name is not None:
            discount.name = req.name.strip()
        if req.description is not None:
            discount.description = req.description.strip() or None
        if req.discount_value is not None:
            if discount.discount_type == "PERCENTAGE" and req.discount_value > 9000:
                raise AppException(
                    code="VALIDATION_ERROR",
                    message="Percentage discounts may not exceed 9000 basis points (90%).",
                    status_code=422,
                )
            discount.discount_value = req.discount_value
        if req.min_order_paise is not None:
            discount.min_order_paise = req.min_order_paise
        if req.max_discount_paise is not None:
            discount.max_discount_paise = req.max_discount_paise
        if req.is_active is not None:
            discount.is_active = req.is_active
        if req.valid_to is not None:
            discount.valid_to = req.valid_to

        await self.session.flush()
        return RetailerOfferItem.model_validate(discount)

    async def delete_offer(self, offer_id: uuid.UUID, retailer: Retailer) -> None:
        self._assert_verified_and_active(retailer, "delete offers")
        scope_prefix = f"RET_{retailer.id.hex[:24]}"

        stmt = select(Discount).where(
            Discount.id == offer_id,
            Discount.scope == scope_prefix,
        )
        discount = (await self.session.execute(stmt)).scalar_one_or_none()
        if not discount:
            raise AppException(
                code="OFFER_NOT_FOUND",
                message="Offer not found or not owned by your store.",
                status_code=404,
            )

        discount.is_active = False
        await self.session.flush()

    # ================= Retailer Analytics =================

    async def get_analytics(self, retailer: Retailer) -> RetailerAnalyticsResponse:
        paid_states = ("SUCCEEDED", "PARTIALLY_REFUNDED")
        is_paid = Order.payment_status.in_(paid_states)
        live_item = OrderItem.fulfillment_status != "CANCELLED"
        # Top products and gross sales: non-cancelled items in paid orders.
        items_stmt = (
            select(
                OrderItem.listing_id,
                OrderItem.product_title,
                OrderItem.sku,
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.total_selling_price_paise).label("revenue_paise"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(OrderItem.retailer_id == retailer.id, is_paid, live_item)
            .group_by(OrderItem.listing_id, OrderItem.product_title, OrderItem.sku)
            .order_by(func.sum(OrderItem.total_selling_price_paise).desc())
        )
        top_items_rows = (await self.session.execute(items_stmt)).all()
        total_units = sum(int(row.units_sold or 0) for row in top_items_rows)
        gross_sales = sum(int(row.revenue_paise or 0) for row in top_items_rows)
        top_selling = [
            RetailerAnalyticsProductItem(
                listing_id=row.listing_id,
                product_name=row.product_title,
                variant_sku=row.sku or "",
                units_sold=int(row.units_sold or 0),
                revenue_paise=int(row.revenue_paise or 0),
            )
            for row in top_items_rows[:10]
        ]

        totals = (
            await self.session.execute(
                select(
                    func.count(func.distinct(OrderItem.order_id))
                    .filter(is_paid, live_item)
                    .label("paid_orders"),
                    func.count(func.distinct(OrderItem.order_id))
                    .filter(Order.status == "PENDING_PAYMENT")
                    .label("pending_payment_orders"),
                    func.coalesce(
                        func.sum(OrderItem.quantity).filter(
                            is_paid,
                            OrderItem.fulfillment_status.in_(
                                ("SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED")
                            ),
                        ),
                        0,
                    ).label("units_dispatched"),
                    func.coalesce(
                        func.sum(OrderItem.total_selling_price_paise).filter(
                            is_paid, OrderItem.fulfillment_status == "DELIVERED"
                        ),
                        0,
                    ).label("delivered_value"),
                )
                .select_from(OrderItem)
                .join(Order, OrderItem.order_id == Order.id)
                .where(OrderItem.retailer_id == retailer.id)
            )
        ).one()
        paid_orders = int(totals.paid_orders or 0)

        # Refunded returns attributed to this retailer's items reduce settled revenue.
        from app.modules.orders.models import OrderReturn, ReturnItem

        refunded_paise = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(ReturnItem.refund_subtotal_paise), 0))
                    .join(OrderReturn, ReturnItem.return_id == OrderReturn.id)
                    .join(OrderItem, ReturnItem.order_item_id == OrderItem.id)
                    .where(
                        OrderItem.retailer_id == retailer.id,
                        OrderReturn.status == "REFUNDED",
                    )
                )
            ).scalar()
            or 0
        )
        settled = max(0, int(totals.delivered_value or 0) - refunded_paise)

        aov = gross_sales // paid_orders if paid_orders > 0 else 0

        # Pipeline by sub-order status, aggregated in SQL (no ORM object loading).
        status_rows = (
            await self.session.execute(
                select(
                    OrderItem.order_id,
                    func.array_agg(OrderItem.fulfillment_status).label("statuses"),
                )
                .where(OrderItem.retailer_id == retailer.id)
                .group_by(OrderItem.order_id)
            )
        ).all()
        orders_by_status: dict[str, int] = {}
        fulfilled_orders = 0
        paid_order_ids: set = set()
        if status_rows:
            paid_order_ids = set(
                (
                    await self.session.execute(
                        select(Order.id).where(
                            Order.id.in_([r.order_id for r in status_rows]), is_paid
                        )
                    )
                ).scalars()
            )
        for row in status_rows:
            st = self._derive_suborder_status(
                [SimpleNamespace(fulfillment_status=x) for x in (row.statuses or [])]
            )
            orders_by_status[st] = orders_by_status.get(st, 0) + 1
            if st == "DELIVERED" and row.order_id in paid_order_ids:
                fulfilled_orders += 1

        # Stock health from StoreInventory
        inv_stmt = (
            select(
                func.count()
                .filter(
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    > StoreInventory.low_stock_threshold
                )
                .label("in_stock"),
                func.count()
                .filter(
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    <= StoreInventory.low_stock_threshold,
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    > 0,
                )
                .label("low_stock"),
                func.count()
                .filter(
                    (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                    <= 0
                )
                .label("out_of_stock"),
            )
            .join(ProductListing, StoreInventory.listing_id == ProductListing.id)
            .where(
                ProductListing.retailer_id == retailer.id,
                ProductListing.is_active.is_(True),
            )
        )
        inv_counts = (await self.session.execute(inv_stmt)).one()

        return RetailerAnalyticsResponse(
            gross_sales_paise=gross_sales,
            settled_revenue_paise=settled,
            paid_orders=paid_orders,
            fulfilled_orders=fulfilled_orders,
            units_dispatched=int(totals.units_dispatched or 0),
            pending_payment_orders=int(totals.pending_payment_orders or 0),
            total_revenue_paise=gross_sales,
            total_orders=paid_orders,
            total_units_sold=total_units,
            average_order_value_paise=aov,
            orders_by_status=orders_by_status,
            top_selling_products=top_selling,
            in_stock_count=int(inv_counts.in_stock or 0),
            low_stock_count=int(inv_counts.low_stock or 0),
            out_of_stock_count=int(inv_counts.out_of_stock or 0),
        )


# ---------------------------------------------------------------------------
# Onboarding: verification documents, resubmission, listing photos
# ---------------------------------------------------------------------------
async def submit_document(session, retailer: Retailer, req):
    from app.modules.catalogue.models import RetailerVerificationDocument
    from app.modules.media.storage import Base64Upload, save_upload

    if retailer.verification_status == "VERIFIED" and retailer.is_active is False:
        raise AppException(
            code="RETAILER_SUSPENDED",
            message="Suspended stores cannot submit documents.",
            status_code=403,
        )
    ref = ""
    if req.content_base64:
        ref = save_upload(
            Base64Upload(
                content_base64=req.content_base64, content_type=req.content_type
            ),
            folder=f"retailer-docs-{retailer.id.hex[:12]}",
            documents=True,
            private=True,
        )
    doc = RetailerVerificationDocument(
        id=uuid.uuid4(),
        retailer_id=retailer.id,
        document_type=req.document_type,
        document_url=ref,
        document_number=(req.document_number or "").strip().upper() or None,
        status="PENDING",
    )
    session.add(doc)
    await session.flush()
    return doc


async def list_documents(session, retailer: Retailer):
    from app.modules.catalogue.models import RetailerVerificationDocument

    return list(
        (
            await session.execute(
                select(RetailerVerificationDocument)
                .where(RetailerVerificationDocument.retailer_id == retailer.id)
                .order_by(RetailerVerificationDocument.created_at.desc())
            )
        ).scalars()
    )


async def resubmit_for_verification(session, retailer: Retailer) -> Retailer:
    """A REJECTED store may fix its details and ask for review again."""
    from app.modules.catalogue.models import RetailerVerificationHistory

    if retailer.verification_status != "REJECTED":
        raise AppException(
            code="INVALID_VERIFICATION_STATE",
            message="Only rejected applications can be resubmitted.",
            status_code=409,
        )
    session.add(
        RetailerVerificationHistory(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            admin_id=None,
            action="RESUBMIT",
            from_status="REJECTED",
            to_status="PENDING",
            reason="Resubmitted by retailer",
        )
    )
    retailer.verification_status = "PENDING"
    retailer.rejection_reason = None
    await session.flush()
    return retailer


async def set_listing_image(
    session, retailer: Retailer, listing_id: uuid.UUID, req
) -> str | None:
    from app.modules.media.storage import Base64Upload, save_upload

    svc = RetailerService(session)
    svc._assert_verified_and_active(retailer, "upload listing photos")
    listing = await session.get(ProductListing, listing_id)
    if listing is None or listing.retailer_id != retailer.id:
        raise AppException(
            code="LISTING_NOT_FOUND",
            message="Listing not found in your store catalogue.",
            status_code=404,
        )
    if req is None:
        listing.image_url = None
    else:
        listing.image_url = save_upload(
            Base64Upload(
                content_base64=req.content_base64, content_type=req.content_type
            ),
            folder="listings",
        )
    await session.flush()
    return listing.image_url
