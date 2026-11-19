import uuid

from sqlalchemy import (
    asc,
    case,
    desc,
    distinct,
    func,
    or_,
    select,
)
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


class CatalogueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_categories_with_count(
        self, active_only: bool = True
    ) -> list[tuple[Category, int]]:
        """Return categories with active product counts."""
        query = (
            select(
                Category,
                func.count(distinct(Product.id)).label("product_count"),
            )
            .outerjoin(
                Product,
                (Product.category_id == Category.id) & (Product.is_active.is_(True)),
            )
            .group_by(Category.id)
            .order_by(Category.name.asc())
        )
        if active_only:
            query = query.where(Category.is_active.is_(True))

        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def get_retailers(self, active_only: bool = True) -> list[Retailer]:
        """Return list of active, verified retailers."""
        query = select(Retailer).order_by(Retailer.name.asc())
        if active_only:
            query = query.where(
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_product_by_id_or_slug(
        self, identifier: str | uuid.UUID
    ) -> Product | None:
        """Fetch full product by UUID or slug with variants, images, listings, retailer, and inventory."""
        query = (
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.retailer),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.inventory),
            )
            .where(Product.is_active.is_(True))
        )

        try:
            val_uuid = uuid.UUID(str(identifier))
            query = query.where(Product.id == val_uuid)
        except ValueError:
            query = query.where(Product.slug == str(identifier))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_products(
        self,
        category_slug: str | None = None,
        category_id: uuid.UUID | None = None,
        retailer_id: uuid.UUID | None = None,
        brand: str | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        in_stock: bool | None = None,
        sort_by: str = "newest",
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        """Query and filter products with total count calculation."""
        # Base query joining necessary relations for filtering
        base_stmt = (
            select(Product.id)
            .join(Product.category)
            .outerjoin(
                ProductVariant,
                (ProductVariant.product_id == Product.id)
                & (ProductVariant.is_active.is_(True)),
            )
            .outerjoin(
                ProductListing,
                (ProductListing.variant_id == ProductVariant.id)
                & (ProductListing.is_active.is_(True)),
            )
            .outerjoin(
                Retailer,
                (Retailer.id == ProductListing.retailer_id)
                & (Retailer.is_active.is_(True))
                & (Retailer.verification_status == "VERIFIED"),
            )
            .outerjoin(StoreInventory, StoreInventory.listing_id == ProductListing.id)
            .where(Product.is_active.is_(True))
        )

        # Filters
        if category_id:
            base_stmt = base_stmt.where(Product.category_id == category_id)
        elif category_slug:
            base_stmt = base_stmt.where(Category.slug == category_slug)

        if retailer_id:
            base_stmt = base_stmt.where(ProductListing.retailer_id == retailer_id)

        if brand:
            base_stmt = base_stmt.where(
                func.lower(Product.brand) == brand.lower().strip()
            )

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            base_stmt = base_stmt.where(
                or_(
                    func.lower(Product.name).ilike(term),
                    func.lower(Product.brand).ilike(term),
                    func.lower(Product.description).ilike(term),
                    func.lower(Category.name).ilike(term),
                )
            )

        if min_price is not None:
            base_stmt = base_stmt.where(
                (ProductListing.selling_price_paise >= min_price)
                & (Retailer.id.is_not(None))
            )

        if max_price is not None:
            base_stmt = base_stmt.where(
                (ProductListing.selling_price_paise <= max_price)
                & (Retailer.id.is_not(None))
            )

        if in_stock is True:
            base_stmt = base_stmt.where(
                (
                    (
                        StoreInventory.on_hand_quantity
                        - StoreInventory.reserved_quantity
                    )
                    > 0
                )
                & (Retailer.id.is_not(None))
            )

        # Aggregation for sorting and distinct product IDs
        agg_stmt = base_stmt.group_by(Product.id).add_columns(
            func.coalesce(
                func.min(
                    case(
                        (Retailer.id.is_not(None), ProductListing.selling_price_paise),
                        else_=None,
                    )
                ),
                0,
            ).label("min_price"),
            func.max(Product.created_at).label("created_at"),
            func.min(Product.name).label("name"),
        )

        # Count total matching products
        count_stmt = select(func.count(distinct(base_stmt.subquery().c.id)))
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Sorting
        if sort_by == "price_asc":
            agg_stmt = agg_stmt.order_by(asc("min_price"))
        elif sort_by == "price_desc":
            agg_stmt = agg_stmt.order_by(desc("min_price"))
        elif sort_by == "name_asc":
            agg_stmt = agg_stmt.order_by(asc("name"))
        else:  # newest / default
            agg_stmt = agg_stmt.order_by(desc("created_at"))

        # Pagination on product IDs
        offset = (page - 1) * limit
        paged_ids_stmt = agg_stmt.offset(offset).limit(limit)
        ids_result = await self.session.execute(paged_ids_stmt)
        product_ids = [row[0] for row in ids_result.all()]

        if not product_ids:
            return [], total

        # Load complete product objects preserving page order
        products_stmt = (
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.retailer),
                selectinload(Product.variants)
                .selectinload(ProductVariant.listings)
                .selectinload(ProductListing.inventory),
            )
            .where(Product.id.in_(product_ids))
        )
        products_result = await self.session.execute(products_stmt)
        product_map = {p.id: p for p in products_result.scalars().all()}

        # Order as fetched in paged_ids
        ordered_products = [
            product_map[pid] for pid in product_ids if pid in product_map
        ]
        return ordered_products, total
