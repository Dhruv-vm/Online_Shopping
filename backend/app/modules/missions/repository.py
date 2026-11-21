import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.missions.models import ShoppingMission, ShoppingMissionItem


class MissionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_mission(
        self,
        customer_id: uuid.UUID,
        title: str,
        budget_paise: int,
        description: str | None = None,
        category_id: uuid.UUID | None = None,
        people_count: int = 1,
        preferences: list[str] | None = None,
        excluded_brands: list[str] | None = None,
        status: str = "ACTIVE",
    ) -> ShoppingMission:
        mission = ShoppingMission(
            customer_id=customer_id,
            title=title,
            description=description,
            budget_paise=budget_paise,
            category_id=category_id,
            people_count=people_count,
            preferences=preferences or [],
            excluded_brands=excluded_brands or [],
            status=status,
        )
        self.session.add(mission)
        await self.session.flush()
        return mission

    async def get_mission_by_id(self, mission_id: uuid.UUID) -> ShoppingMission | None:
        stmt = (
            select(ShoppingMission)
            .where(ShoppingMission.id == mission_id)
            .options(
                selectinload(ShoppingMission.category),
                selectinload(ShoppingMission.items)
                .selectinload(ShoppingMissionItem.product)
                .selectinload(Product.images),
                selectinload(ShoppingMission.items).selectinload(
                    ShoppingMissionItem.variant
                ),
                selectinload(ShoppingMission.items)
                .selectinload(ShoppingMissionItem.listing)
                .selectinload(ProductListing.inventory),
                selectinload(ShoppingMission.items).selectinload(
                    ShoppingMissionItem.retailer
                ),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_mission_items(
        self, mission_id: uuid.UUID
    ) -> list[ShoppingMissionItem]:
        stmt = (
            select(ShoppingMissionItem)
            .where(ShoppingMissionItem.mission_id == mission_id)
            .options(
                selectinload(ShoppingMissionItem.product).selectinload(Product.images),
                selectinload(ShoppingMissionItem.variant),
                selectinload(ShoppingMissionItem.listing).selectinload(
                    ProductListing.inventory
                ),
                selectinload(ShoppingMissionItem.retailer),
            )
            .order_by(
                ShoppingMissionItem.sort_order.asc(),
                ShoppingMissionItem.created_at.asc(),
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_missions_by_customer(
        self, customer_id: uuid.UUID
    ) -> list[ShoppingMission]:
        stmt = (
            select(ShoppingMission)
            .where(ShoppingMission.customer_id == customer_id)
            .options(
                selectinload(ShoppingMission.category),
                selectinload(ShoppingMission.items),
            )
            .order_by(ShoppingMission.updated_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def delete_mission(self, mission: ShoppingMission) -> None:
        await self.session.delete(mission)
        await self.session.flush()

    async def add_mission_item(
        self,
        mission_id: uuid.UUID,
        product_id: uuid.UUID,
        variant_id: uuid.UUID,
        listing_id: uuid.UUID,
        retailer_id: uuid.UUID,
        group_name: str,
        quantity: int,
        unit_price_paise: int,
        recommendation_reason: str,
        sort_order: int = 0,
        is_selected: bool = True,
    ) -> ShoppingMissionItem:
        item = ShoppingMissionItem(
            mission_id=mission_id,
            product_id=product_id,
            variant_id=variant_id,
            listing_id=listing_id,
            retailer_id=retailer_id,
            group_name=group_name,
            quantity=quantity,
            unit_price_paise=unit_price_paise,
            recommendation_reason=recommendation_reason,
            sort_order=sort_order,
            is_selected=is_selected,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_mission_item(self, item_id: uuid.UUID) -> ShoppingMissionItem | None:
        stmt = (
            select(ShoppingMissionItem)
            .where(ShoppingMissionItem.id == item_id)
            .options(
                selectinload(ShoppingMissionItem.product).selectinload(Product.images),
                selectinload(ShoppingMissionItem.variant),
                selectinload(ShoppingMissionItem.listing).selectinload(
                    ProductListing.inventory
                ),
                selectinload(ShoppingMissionItem.retailer),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_mission_item(self, item: ShoppingMissionItem) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def get_candidate_listings(
        self,
        category_ids: list[uuid.UUID] | None = None,
        excluded_brands: list[str] | None = None,
        search_terms: list[str] | None = None,
        max_price_paise: int | None = None,
        limit: int = 100,
    ) -> list[ProductListing]:
        """Fetch active listings from active, verified retailers with in-stock inventory."""
        stmt = (
            select(ProductListing)
            .join(Retailer, ProductListing.retailer_id == Retailer.id)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .join(StoreInventory, ProductListing.id == StoreInventory.listing_id)
            .where(
                ProductListing.is_active.is_(True),
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
                Category.is_active.is_(True),
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
                ProductListing.hsn_code.isnot(None),
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > 0,
            )
            .options(
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.category),
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.inventory),
            )
        )

        if category_ids:
            stmt = stmt.where(Product.category_id.in_(category_ids))

        if excluded_brands:
            clean_brands = [b.strip() for b in excluded_brands if b and b.strip()]
            for b in clean_brands:
                stmt = stmt.where(~Product.brand.ilike(f"%{b}%"))

        if max_price_paise is not None:
            stmt = stmt.where(ProductListing.selling_price_paise <= max_price_paise)

        stmt = stmt.order_by(ProductListing.selling_price_paise.asc()).limit(limit)
        res = await self.session.execute(stmt)
        candidates = list(res.scalars().all())

        # Exact brand exclusion check in Python
        if excluded_brands:
            excl_set = {b.strip().lower() for b in excluded_brands if b and b.strip()}
            if excl_set:
                candidates = [
                    c
                    for c in candidates
                    if not (
                        c.variant.product.brand
                        and any(
                            ex in c.variant.product.brand.lower() for ex in excl_set
                        )
                    )
                ]

        return candidates

    async def get_alternative_listings(
        self,
        category_id: uuid.UUID,
        current_listing_id: uuid.UUID,
        max_price_paise: int | None = None,
        limit: int = 10,
    ) -> list[ProductListing]:
        """Fetch alternatives from the same category with available stock."""
        stmt = (
            select(ProductListing)
            .join(Retailer, ProductListing.retailer_id == Retailer.id)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(StoreInventory, ProductListing.id == StoreInventory.listing_id)
            .where(
                ProductListing.id != current_listing_id,
                Product.category_id == category_id,
                ProductListing.is_active.is_(True),
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
                ProductListing.hsn_code.isnot(None),
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > 0,
            )
            .options(
                selectinload(ProductListing.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images),
                selectinload(ProductListing.variant),
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.inventory),
            )
        )

        if max_price_paise is not None:
            stmt = stmt.where(ProductListing.selling_price_paise <= max_price_paise)

        stmt = stmt.order_by(ProductListing.selling_price_paise.asc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_all_active_categories(self) -> list[Category]:
        stmt = select(Category).where(Category.is_active.is_(True))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_category_by_id(self, category_id: uuid.UUID) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_valid_active_listing(
        self, listing_id: uuid.UUID
    ) -> ProductListing | None:
        """Fetch listing verifying active status across listing, variant, product, retailer, and stock."""
        stmt = (
            select(ProductListing)
            .join(Retailer, ProductListing.retailer_id == Retailer.id)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(StoreInventory, ProductListing.id == StoreInventory.listing_id)
            .where(
                ProductListing.id == listing_id,
                ProductListing.is_active.is_(True),
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
                ProductListing.hsn_code.isnot(None),
                (StoreInventory.on_hand_quantity - StoreInventory.reserved_quantity)
                > 0,
            )
            .options(
                selectinload(ProductListing.variant).selectinload(
                    ProductVariant.product
                ),
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.inventory),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
