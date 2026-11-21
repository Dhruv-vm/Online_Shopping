import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.catalogue.models import Product, ProductListing, ProductVariant
from app.modules.pricing.models import Discount, DiscountType

# Retailer offers are stored with scope "RET_<first 24 hex chars of retailer id>";
# every other scope (PLATFORM_WIDE, CATEGORY, PRODUCT, LISTING) is a platform deal.
RETAILER_SCOPE_PREFIX = "RET_"


def retailer_scope(retailer_id: uuid.UUID) -> str:
    return f"{RETAILER_SCOPE_PREFIX}{retailer_id.hex[:24]}"


def is_retailer_offer(discount: Discount) -> bool:
    return (discount.scope or "").startswith(RETAILER_SCOPE_PREFIX)


def normalize_discount_code(code: str | None) -> str | None:
    """Codes match exactly but case-insensitively (surrounding spaces ignored)."""
    if code is None:
        return None
    clean = code.strip().upper()
    return clean or None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def discount_is_live(d: Discount, now: datetime, *, check_usage: bool = True) -> bool:
    """Active, inside its validity window and (optionally) not used up."""
    if not d.is_active:
        return False
    start = _aware(d.valid_from)
    if start is not None and start > now:
        return False
    end = _aware(d.valid_to)
    if end is not None and end < now:
        return False
    return not (
        check_usage and d.usage_limit is not None and d.times_used >= d.usage_limit
    )


@dataclass(frozen=True)
class DiscountLine:
    """One basket line as the discount engine sees it (pre-discount price)."""

    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    product_id: uuid.UUID | None
    category_id: uuid.UUID | None
    unit_price_paise: int
    quantity: int


@dataclass
class LineDiscount:
    unit_discount_paise: int
    unit_price_paise: int
    applied: list[Discount] = field(default_factory=list)

    @property
    def applied_ids(self) -> list[str]:
        return [str(d.id) for d in self.applied]


@dataclass
class BasketDiscounts:
    lines: dict[uuid.UUID, LineDiscount]
    discount_code: str | None = None  # normalised code, set only if it applied
    code_discount_ids: frozenset[uuid.UUID] = frozenset()

    @property
    def code_applied(self) -> bool:
        return self.discount_code is not None


class DiscountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ v2.0
    async def _live_code_discounts(self, code: str, now: datetime) -> list[Discount]:
        rows = (
            (
                await self.session.execute(
                    select(Discount).where(func.upper(Discount.code) == code)
                )
            )
            .scalars()
            .all()
        )
        return [d for d in rows if discount_is_live(d, now)]

    async def _line_candidates(
        self, line: DiscountLine, now: datetime
    ) -> list[Discount]:
        """Live discounts whose scope covers this line (before code, minimum-order
        and stacking rules)."""
        clauses = [Discount.listing_id == line.listing_id]
        if line.product_id:
            clauses.append(
                (Discount.scope == "PRODUCT") & (Discount.product_id == line.product_id)
            )
        if line.category_id:
            clauses.append(
                (Discount.scope == "CATEGORY")
                & (Discount.category_id == line.category_id)
            )
        clauses.append(
            (Discount.scope == "PLATFORM_WIDE")
            & (Discount.listing_id.is_(None))
            & (Discount.product_id.is_(None))
            & (Discount.category_id.is_(None))
        )
        # The retailer's store-wide offer (no listing) covers all its listings.
        clauses.append(
            (Discount.scope == retailer_scope(line.retailer_id))
            & (Discount.listing_id.is_(None))
        )
        rows = (
            (
                await self.session.execute(
                    select(Discount).where(or_(*clauses), Discount.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        out = []
        for d in rows:
            if not discount_is_live(d, now):
                continue
            # A listing-bound retailer offer only ever belongs to its own store.
            if is_retailer_offer(d) and d.scope != retailer_scope(line.retailer_id):
                continue
            out.append(d)
        return out

    async def resolve_basket_discounts(
        self,
        lines: Sequence[DiscountLine],
        discount_code: str | None = None,
        *,
        now: datetime | None = None,
    ) -> BasketDiscounts:
        """Price every basket line under the Version 2.0 policy.

        * A discount with a code applies only when that code is supplied
          (exact, case-insensitive). A supplied code that is unknown, inactive,
          not yet valid, expired or used up → 422 INVALID_DISCOUNT_CODE.
        * ``min_order_paise`` is compared with the subtotal, before discounts,
          tax and delivery, of the basket lines the discount covers.
        * Per line: at most ONE platform deal and ONE retailer offer (the
          retailer's listing or store-wide offer), choosing the pair that gives
          the customer the lowest final unit price.
        """
        now = now or datetime.now(UTC)
        code = normalize_discount_code(discount_code)
        code_ids: frozenset[uuid.UUID] = frozenset()
        if code is not None:
            matched = await self._live_code_discounts(code, now)
            if not matched:
                raise AppException(
                    code="INVALID_DISCOUNT_CODE",
                    message="This discount code is not valid.",
                    status_code=422,
                )
            code_ids = frozenset(d.id for d in matched)

        candidates: dict[uuid.UUID, list[Discount]] = {}
        covered_subtotal: dict[uuid.UUID, int] = {}
        for line in lines:
            cands = [
                d
                for d in await self._line_candidates(line, now)
                if d.code is None or d.id in code_ids
            ]
            candidates[line.listing_id] = cands
            for d in cands:
                covered_subtotal[d.id] = covered_subtotal.get(d.id, 0) + (
                    line.unit_price_paise * line.quantity
                )

        result: dict[uuid.UUID, LineDiscount] = {}
        for line in lines:
            eligible = [
                d
                for d in candidates[line.listing_id]
                if covered_subtotal.get(d.id, 0) >= (d.min_order_paise or 0)
            ]
            retailer = [None, *[d for d in eligible if is_retailer_offer(d)]]
            platform = [None, *[d for d in eligible if not is_retailer_offer(d)]]
            best: tuple | None = None
            for r in retailer:
                for p in platform:
                    applied = [d for d in (r, p) if d is not None]
                    disc, price = self.calculate_unit_discount(
                        line.unit_price_paise, applied
                    )
                    key = (price, len(applied), sorted(str(d.id) for d in applied))
                    if best is None or key < best[0]:
                        best = (key, disc, price, applied)
            assert best is not None
            _, disc, price, applied = best
            if disc == 0:
                applied = []
            result[line.listing_id] = LineDiscount(disc, price, applied)

        used_code = code is not None and any(
            d.id in code_ids for ld in result.values() for d in ld.applied
        )
        return BasketDiscounts(
            lines=result,
            discount_code=code if used_code else None,
            code_discount_ids=code_ids,
        )

    async def line_context(self, listing: ProductListing) -> DiscountLine:
        """Build a single-unit DiscountLine for a listing (loads product/category)."""
        info = (
            await self.session.execute(
                select(Product.id, Product.category_id)
                .select_from(ProductVariant)
                .join(Product, ProductVariant.product_id == Product.id)
                .where(ProductVariant.id == listing.variant_id)
            )
        ).first()
        return DiscountLine(
            listing_id=listing.id,
            retailer_id=listing.retailer_id,
            product_id=info[0] if info else None,
            category_id=info[1] if info else None,
            unit_price_paise=int(listing.selling_price_paise),
            quantity=1,
        )

    # -------------------------------------------------------- v1.0 lookup
    async def get_applicable_discounts_for_listing(
        self,
        listing_id: uuid.UUID,
        selling_price_paise: int,
    ) -> list[Discount]:
        """Candidate lookup with v1.0 semantics (kept for compatibility).

        Pricing does NOT use this: it ignores discount codes, basket subtotals
        and the stacking policy. Use :meth:`resolve_basket_discounts`.

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
