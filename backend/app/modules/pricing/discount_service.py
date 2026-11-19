import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalogue.models import Product, ProductListing, ProductVariant
from app.modules.pricing.models import Discount, DiscountType


class DiscountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_applicable_discounts_for_listing(
        self,
        listing_id: uuid.UUID,
        selling_price_paise: int,
    ) -> list[Discount]:
        """Fetch active, valid discounts applicable to this listing.

        Includes:
        1. Direct listing-specific discounts
        2. Product-specific platform deals (scope=PRODUCT)
        3. Category-specific platform deals (scope=CATEGORY)
        4. Platform-wide deals (scope=PLATFORM_WIDE)
        """
        # Fetch listing canonical product and category context
        listing_info_stmt = (
            select(Product.id, Product.category_id)
            .select_from(ProductListing)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .where(ProductListing.id == listing_id)
        )
        info_res = (await self.session.execute(listing_info_stmt)).first()
        product_id = info_res[0] if info_res else None
        category_id = info_res[1] if info_res else None

        now = datetime.now(UTC)

        clauses = [Discount.listing_id == listing_id]
        if product_id:
            clauses.append(
                (Discount.scope == "PRODUCT") & (Discount.product_id == product_id)
            )
        if category_id:
            clauses.append(
                (Discount.scope == "CATEGORY") & (Discount.category_id == category_id)
            )
        clauses.append(
            (Discount.scope == "PLATFORM_WIDE")
            & (Discount.listing_id.is_(None))
            & (Discount.product_id.is_(None))
            & (Discount.category_id.is_(None))
        )

        stmt = (
            select(Discount)
            .where(
                or_(*clauses),
                Discount.is_active.is_(True),
                Discount.valid_from <= now,
            )
            .order_by(Discount.created_at.desc())
        )
        res = await self.session.execute(stmt)
        all_discounts = res.scalars().all()

        valid_discounts = []
        for d in all_discounts:
            if d.valid_to and d.valid_to < now:
                continue
            if d.usage_limit is not None and d.times_used >= d.usage_limit:
                continue
            if selling_price_paise < d.min_order_paise:
                continue
            valid_discounts.append(d)

        return valid_discounts

    @staticmethod
    def calculate_unit_discount(
        selling_price_paise: int,
        discounts: Sequence[Discount],
    ) -> tuple[int, int]:
        """Calculate discount in integer paise and final discounted unit price.

        Applies discounts deterministically. Never mutates base price or produces negative prices.
        Returns:
          (discount_amount_paise, discounted_unit_price_paise)
        """
        if not discounts or selling_price_paise <= 0:
            return 0, selling_price_paise

        total_discount = 0
        current_price = selling_price_paise

        for d in discounts:
            if d.discount_type == DiscountType.PERCENTAGE.value:
                # basis points: 100 bp = 1%
                disc = round((selling_price_paise * d.discount_value) / 10000)
                if d.max_discount_paise is not None:
                    disc = min(disc, d.max_discount_paise)
            elif d.discount_type == DiscountType.FIXED_AMOUNT.value:
                disc = d.discount_value
            else:
                disc = 0

            # Prevent discount exceeding current price
            disc = max(0, min(disc, current_price))
            total_discount += disc
            current_price -= disc

            if current_price <= 0:
                break

        discounted_price = max(0, selling_price_paise - total_discount)
        return total_discount, discounted_price
