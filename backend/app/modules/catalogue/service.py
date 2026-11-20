import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.catalogue.models import Product, ProductImage
from app.modules.catalogue.repository import CatalogueRepository
from app.modules.catalogue.schemas import (
    CategorySchema,
    ProductDetailSchema,
    ProductImageSchema,
    ProductListingDetailSchema,
    ProductListResponseSchema,
    ProductSummarySchema,
    ProductVariantDetailSchema,
    RetailerSchema,
)


class CatalogueService:
    def __init__(self, session: AsyncSession):
        self.repo = CatalogueRepository(session)

    async def get_categories(self, top_level_only: bool = True) -> list[CategorySchema]:
        """Fetch all active categories with product counts."""
        categories_with_count = await self.repo.get_categories_with_count(
            active_only=True, top_level_only=top_level_only
        )
        return [
            CategorySchema(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                image_url=cat.image_url,
                icon=cat.icon,
                parent_id=cat.parent_id,
                product_count=count,
            )
            for cat, count in categories_with_count
        ]

    async def get_retailers(self) -> list[RetailerSchema]:
        """Fetch all active retailers."""
        retailers = await self.repo.get_retailers(active_only=True)
        return [
            RetailerSchema(
                id=ret.id,
                name=ret.name,
                slug=ret.slug,
                description=ret.description,
                logo_url=ret.logo_url,
                rating=ret.rating,
                is_active=ret.is_active,
            )
            for ret in retailers
        ]

    def _extract_primary_image(self, images: list[ProductImage]) -> str | None:
        """Find the primary image or the first sorted image URL."""
        if not images:
            return None
        primary = next((img for img in images if img.is_primary), None)
        return primary.url if primary else images[0].url

    def _build_product_summary(self, product: Product) -> ProductSummarySchema:
        """Compute aggregate pricing, stock, and image for a product summary."""
        selling_prices: list[int] = []
        original_prices: list[int] = []
        total_available_stock = 0
        retailer_ids: set[uuid.UUID] = set()

        for variant in product.variants:
            if not variant.is_active:
                continue
            for listing in variant.listings:
                if not listing.is_active:
                    continue
                retailer = getattr(listing, "retailer", None)
                if retailer is not None:
                    if (
                        not retailer.is_active
                        or getattr(retailer, "verification_status", "VERIFIED")
                        != "VERIFIED"
                    ):
                        continue
                retailer_ids.add(listing.retailer_id)
                selling_prices.append(listing.selling_price_paise)
                original_prices.append(listing.original_price_paise)
                if listing.inventory:
                    total_available_stock += listing.inventory.available_quantity

        min_price = min(selling_prices) if selling_prices else 0
        max_price = max(selling_prices) if selling_prices else 0
        original_price = max(original_prices) if original_prices else None

        return ProductSummarySchema(
            id=product.id,
            name=product.name,
            slug=product.slug,
            brand=product.brand,
            category_id=product.category.id,
            category_name=product.category.name,
            category_slug=product.category.slug,
            primary_image=self._extract_primary_image(product.images),
            min_price_paise=min_price,
            max_price_paise=max_price,
            original_price_paise=original_price,
            currency="INR",
            is_in_stock=total_available_stock > 0,
            variant_count=len([v for v in product.variants if v.is_active]),
            retailer_count=len(retailer_ids),
        )

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
    ) -> ProductListResponseSchema:
        """List products with filters, sorting, and pagination."""
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20

        products, total = await self.repo.list_products(
            category_slug=category_slug,
            category_id=category_id,
            retailer_id=retailer_id,
            brand=brand,
            search=search,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

        items = [self._build_product_summary(p) for p in products]
        pages = math.ceil(total / limit) if total > 0 else 1

        return ProductListResponseSchema(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    async def get_product_detail(self, identifier: str) -> ProductDetailSchema:
        """Fetch full product detail with variants, listings, and stock."""
        product = await self.repo.get_product_by_id_or_slug(identifier)
        if not product:
            raise AppException(
                code="NOT_FOUND",
                message=f"Product '{identifier}' was not found in the catalogue.",
                status_code=404,
            )

        all_selling_prices: list[int] = []
        all_original_prices: list[int] = []
        total_stock = 0

        variant_schemas: list[ProductVariantDetailSchema] = []
        for variant in product.variants:
            if not variant.is_active:
                continue

            variant_listings: list[ProductListingDetailSchema] = []
            variant_prices: list[int] = []
            variant_stock = 0

            for listing in variant.listings:
                retailer = getattr(listing, "retailer", None)
                if (
                    not listing.is_active
                    or not retailer
                    or not retailer.is_active
                    or getattr(retailer, "verification_status", "VERIFIED")
                    != "VERIFIED"
                ):
                    continue

                on_hand = listing.inventory.on_hand_quantity if listing.inventory else 0
                reserved = (
                    listing.inventory.reserved_quantity if listing.inventory else 0
                )
                avail = max(0, on_hand - reserved)
                in_stock = avail > 0

                variant_prices.append(listing.selling_price_paise)
                all_selling_prices.append(listing.selling_price_paise)
                all_original_prices.append(listing.original_price_paise)
                variant_stock += avail
                total_stock += avail

                variant_listings.append(
                    ProductListingDetailSchema(
                        id=listing.id,
                        retailer_id=listing.retailer_id,
                        retailer_name=retailer.name,
                        retailer_rating=retailer.rating,
                        retailer_state=retailer.state,
                        seller_sku=listing.seller_sku,
                        original_price_paise=listing.original_price_paise,
                        selling_price_paise=listing.selling_price_paise,
                        currency=listing.currency,
                        is_active=listing.is_active,
                        on_hand_quantity=on_hand,
                        reserved_quantity=reserved,
                        available_quantity=avail,
                        is_in_stock=in_stock,
                    )
                )

            # Sort listings by selling price ascending
            variant_listings.sort(
                key=lambda listing_item: listing_item.selling_price_paise
            )

            variant_schemas.append(
                ProductVariantDetailSchema(
                    id=variant.id,
                    product_id=variant.product_id,
                    name=variant.name,
                    sku=variant.sku,
                    attributes=variant.attributes,
                    is_active=variant.is_active,
                    listings=variant_listings,
                    min_price_paise=min(variant_prices) if variant_prices else None,
                    is_in_stock=variant_stock > 0,
                )
            )

        image_schemas = [
            ProductImageSchema(
                id=img.id,
                url=img.url,
                alt_text=img.alt_text,
                is_primary=img.is_primary,
                sort_order=img.sort_order,
                variant_id=img.variant_id,
            )
            for img in product.images
        ]

        min_price = min(all_selling_prices) if all_selling_prices else 0
        max_price = max(all_selling_prices) if all_selling_prices else 0
        original_price = max(all_original_prices) if all_original_prices else None

        return ProductDetailSchema(
            id=product.id,
            name=product.name,
            slug=product.slug,
            brand=product.brand,
            description=product.description,
            category_id=product.category.id,
            category_name=product.category.name,
            category_slug=product.category.slug,
            images=image_schemas,
            variants=variant_schemas,
            min_price_paise=min_price,
            max_price_paise=max_price,
            original_price_paise=original_price,
            currency="INR",
            is_in_stock=total_stock > 0,
            total_available_stock=total_stock,
        )
