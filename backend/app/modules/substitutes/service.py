from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import AppException
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
)
from app.modules.substitutes.schemas import (
    AvailabilityStatus,
    SpecComparison,
    SubstituteItemResponse,
    SubstituteListResponse,
    SubstituteType,
)

logger = logging.getLogger("basket_substitutes")


def _tokenize(text: str) -> set[str]:
    """Tokenize and normalize text into lowercase word tokens."""
    return {word for word in re.findall(r"\w+", text.lower()) if len(word) > 1}


def _calculate_jaccard(tokens1: set[str], tokens2: set[str]) -> float:
    """Calculate Jaccard similarity between two token sets."""
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def _get_primary_image_url(
    variant: ProductVariant | None, product: Product | None
) -> str | None:
    """Extract primary image URL from variant or product."""
    if variant and variant.images:
        for img in variant.images:
            if img.is_primary:
                return img.url
        if len(variant.images) > 0:
            return variant.images[0].url

    if product and product.images:
        for img in product.images:
            if img.is_primary:
                return img.url
        if len(product.images) > 0:
            return product.images[0].url

    return None


class SubstituteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_substitutes_for_listing(
        self,
        listing_id: uuid.UUID,
        filter_type: SubstituteType | None = None,
        limit: int = 10,
        in_stock_only: bool = True,
    ) -> SubstituteListResponse:
        """
        Discovers, scores, and categorizes genuine substitutes for a given product listing.
        All substitutes share the same category, belong to verified retailers, and are actively listed.
        """
        # 1. Fetch original listing with all relational details
        orig_stmt = (
            select(ProductListing)
            .options(
                joinedload(ProductListing.variant)
                .joinedload(ProductVariant.product)
                .joinedload(Product.category),
                joinedload(ProductListing.variant)
                .joinedload(ProductVariant.product)
                .joinedload(Product.images),
                joinedload(ProductListing.variant).joinedload(ProductVariant.images),
                joinedload(ProductListing.retailer),
                joinedload(ProductListing.inventory),
            )
            .where(ProductListing.id == listing_id)
        )
        orig_res = await self.session.execute(orig_stmt)
        orig_listing = orig_res.unique().scalar_one_or_none()

        if not orig_listing:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message=f"Product listing {listing_id} was not found.",
                status_code=404,
            )

        orig_variant = orig_listing.variant
        orig_product = orig_variant.product if orig_variant else None
        orig_retailer = orig_listing.retailer
        orig_category = orig_product.category if orig_product else None

        if not orig_product or not orig_category:
            raise AppException(
                code="PRODUCT_DATA_INCOMPLETE",
                message="Listing product or category data is incomplete.",
                status_code=500,
            )

        # Check original inventory and availability
        orig_inv = orig_listing.inventory
        orig_on_hand = orig_inv.on_hand_quantity if orig_inv else 0
        orig_reserved = orig_inv.reserved_quantity if orig_inv else 0
        orig_stock = max(0, orig_on_hand - orig_reserved)
        orig_is_in_stock = (
            orig_listing.is_active
            and (orig_variant.is_active if orig_variant else False)
            and (orig_product.is_active if orig_product else False)
            and (orig_retailer.is_active if orig_retailer else False)
            and orig_stock > 0
        )

        trigger_reason = (
            "OUT_OF_STOCK"
            if not orig_is_in_stock
            else ("LOW_STOCK" if orig_stock < 5 else "EXPLORE")
        )

        orig_price = orig_listing.selling_price_paise
        orig_attrs = (orig_variant.attributes or {}) if orig_variant else {}
        orig_brand = orig_product.brand or ""
        orig_name_tokens = _tokenize(
            f"{orig_product.name} {orig_variant.name if orig_variant else ''}"
        )

        # 2. Query candidates in the exact same category
        # Candidates must be active and from VERIFIED retailers
        cand_stmt = (
            select(ProductListing)
            .join(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Retailer, ProductListing.retailer_id == Retailer.id)
            .options(
                joinedload(ProductListing.variant)
                .joinedload(ProductVariant.product)
                .joinedload(Product.category),
                joinedload(ProductListing.variant)
                .joinedload(ProductVariant.product)
                .joinedload(Product.images),
                joinedload(ProductListing.variant).joinedload(ProductVariant.images),
                joinedload(ProductListing.retailer),
                joinedload(ProductListing.inventory),
            )
            .where(
                Product.category_id == orig_product.category_id,
                ProductListing.id != orig_listing.id,
                ProductListing.is_active.is_(True),
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
                Retailer.is_active.is_(True),
                Retailer.verification_status == "VERIFIED",
                ProductListing.hsn_code.isnot(None),
            )
        )
        cand_res = await self.session.execute(cand_stmt)
        candidate_listings = cand_res.unique().scalars().all()

        evaluated_substitutes: list[SubstituteItemResponse] = []

        for cand in candidate_listings:
            cand_variant = cand.variant
            cand_product = cand_variant.product if cand_variant else None
            cand_retailer = cand.retailer

            if not cand_variant or not cand_product or not cand_retailer:
                continue

            # Stock check
            cand_inv = cand.inventory
            cand_on_hand = cand_inv.on_hand_quantity if cand_inv else 0
            cand_reserved = cand_inv.reserved_quantity if cand_inv else 0
            cand_stock = max(0, cand_on_hand - cand_reserved)
            cand_in_stock = cand_stock > 0

            if in_stock_only and not cand_in_stock:
                continue

            if cand_stock >= 5:
                avail_status = AvailabilityStatus.IN_STOCK
            elif cand_stock > 0:
                avail_status = AvailabilityStatus.LOW_STOCK
            else:
                avail_status = AvailabilityStatus.OUT_OF_STOCK

            cand_price = cand.selling_price_paise
            price_diff_paise = cand_price - orig_price
            price_diff_percentage = round(
                ((cand_price - orig_price) / max(orig_price, 1)) * 100, 1
            )
            savings_pct = (
                round(((orig_price - cand_price) / max(orig_price, 1)) * 100, 1)
                if cand_price < orig_price
                else 0.0
            )

            # Specification Comparison
            cand_attrs = cand_variant.attributes or {}
            all_attr_keys = sorted(set(orig_attrs.keys()) | set(cand_attrs.keys()))

            matching_specs: list[str] = []
            differing_specs: list[str] = []
            detailed_comparisons: list[SpecComparison] = []

            # Compare Brand
            cand_brand = cand_product.brand or ""
            brand_is_match = (
                bool(orig_brand)
                and bool(cand_brand)
                and orig_brand.strip().lower() == cand_brand.strip().lower()
            )
            if brand_is_match:
                matching_specs.append(f"Brand: {orig_brand}")
            else:
                differing_specs.append(
                    f"Brand: {cand_brand or 'N/A'} (was {orig_brand or 'N/A'})"
                )

            detailed_comparisons.append(
                SpecComparison(
                    attribute_key="brand",
                    label="Brand",
                    original_value=orig_brand or "N/A",
                    substitute_value=cand_brand or "N/A",
                    is_match=brand_is_match,
                )
            )

            matched_attr_count = 1 if brand_is_match else 0
            total_specs_compared = 1 + len(all_attr_keys)

            for key in all_attr_keys:
                label = key.replace("_", " ").title()
                orig_val = orig_attrs.get(key)
                cand_val = cand_attrs.get(key)

                val_match = (
                    orig_val is not None
                    and cand_val is not None
                    and str(orig_val).strip().lower() == str(cand_val).strip().lower()
                )

                if val_match:
                    matched_attr_count += 1
                    matching_specs.append(f"{label}: {cand_val}")
                    detailed_comparisons.append(
                        SpecComparison(
                            attribute_key=key,
                            label=label,
                            original_value=orig_val,
                            substitute_value=cand_val,
                            is_match=True,
                        )
                    )
                else:
                    differing_specs.append(
                        f"{label}: {cand_val if cand_val is not None else 'N/A'} "
                        f"(was {orig_val if orig_val is not None else 'N/A'})"
                    )
                    detailed_comparisons.append(
                        SpecComparison(
                            attribute_key=key,
                            label=label,
                            original_value=orig_val if orig_val is not None else "N/A",
                            substitute_value=cand_val
                            if cand_val is not None
                            else "N/A",
                            is_match=False,
                        )
                    )

            # Similarity Scoring Heuristic
            spec_overlap_score = (
                matched_attr_count / total_specs_compared
                if total_specs_compared > 0
                else 0.5
            )
            brand_score = 1.0 if brand_is_match else 0.0

            cand_name_tokens = _tokenize(f"{cand_product.name} {cand_variant.name}")
            name_score = _calculate_jaccard(orig_name_tokens, cand_name_tokens)

            price_ratio = abs(cand_price - orig_price) / max(orig_price, 1)
            price_score = max(0.0, 1.0 - min(1.0, price_ratio))

            similarity_score = round(
                (0.40 * spec_overlap_score)
                + (0.25 * brand_score)
                + (0.20 * name_score)
                + (0.15 * price_score),
                2,
            )

            # Categorize applicable Substitute Types
            applicable_types: list[SubstituteType] = []

            # 1. AVAILABLE_NOW: in stock when original is out of stock / low stock
            if cand_in_stock and (not orig_is_in_stock or orig_stock < 3):
                applicable_types.append(SubstituteType.AVAILABLE_NOW)

            # 2. BUDGET_FRIENDLY: cheaper by at least 5% or > ₹100
            if cand_price < orig_price and (
                savings_pct >= 5.0 or (orig_price - cand_price) >= 10000
            ):
                applicable_types.append(SubstituteType.BUDGET_FRIENDLY)

            # 3. BETTER_VALUE: high rating (>= 4.5) with price <= orig_price * 1.05 and good spec overlap
            if (
                cand_retailer.rating >= 4.5
                and cand_price <= int(orig_price * 1.05)
                and spec_overlap_score >= 0.4
            ):
                applicable_types.append(SubstituteType.BETTER_VALUE)

            # 4. PREMIUM_UPGRADE: higher price (> 5% more) with premium brand or enhanced specs
            if cand_price > int(orig_price * 1.05):
                applicable_types.append(SubstituteType.PREMIUM_UPGRADE)

            # 5. CLOSEST_MATCH: high overall similarity
            if similarity_score >= 0.5 or brand_is_match:
                applicable_types.append(SubstituteType.CLOSEST_MATCH)

            # Determine Primary Type
            primary_type: SubstituteType
            if (
                not orig_is_in_stock
                and SubstituteType.AVAILABLE_NOW in applicable_types
            ):
                primary_type = SubstituteType.AVAILABLE_NOW
            elif (
                SubstituteType.CLOSEST_MATCH in applicable_types
                and similarity_score >= 0.7
            ):
                primary_type = SubstituteType.CLOSEST_MATCH
            elif (
                SubstituteType.BUDGET_FRIENDLY in applicable_types
                and savings_pct >= 10.0
            ):
                primary_type = SubstituteType.BUDGET_FRIENDLY
            elif SubstituteType.BETTER_VALUE in applicable_types:
                primary_type = SubstituteType.BETTER_VALUE
            elif SubstituteType.PREMIUM_UPGRADE in applicable_types:
                primary_type = SubstituteType.PREMIUM_UPGRADE
            elif applicable_types:
                primary_type = applicable_types[0]
            else:
                primary_type = SubstituteType.CLOSEST_MATCH
                applicable_types.append(SubstituteType.CLOSEST_MATCH)

            # Explanations and Compatibility Notes
            if primary_type == SubstituteType.AVAILABLE_NOW:
                reason = (
                    f"In stock now ({cand_stock} available) from verified retailer "
                    f"'{cand_retailer.name}' with {cand_retailer.rating}★ rating."
                )
            elif primary_type == SubstituteType.BUDGET_FRIENDLY:
                savings_rupees = (orig_price - cand_price) / 100.0
                reason = (
                    f"Save ₹{savings_rupees:.2f} ({savings_pct}% off) with matching category "
                    f"and comparable core specifications."
                )
            elif primary_type == SubstituteType.BETTER_VALUE:
                reason = (
                    f"Excellent value from top-rated retailer '{cand_retailer.name}' "
                    f"({cand_retailer.rating}★) with robust feature parity."
                )
            elif primary_type == SubstituteType.PREMIUM_UPGRADE:
                upgrade_cost = (cand_price - orig_price) / 100.0
                reason = (
                    f"Premium upgrade (+₹{upgrade_cost:.2f}) offering elevated brand tier "
                    f"and enhanced specifications."
                )
            else:
                reason = (
                    f"Closest match with {int(similarity_score * 100)}% compatibility "
                    f"and matching category attributes."
                )

            compat_notes = (
                "Direct drop-in replacement in the same category."
                if len(differing_specs) <= 1
                else f"Compatible within {orig_category.name}. Note {len(differing_specs)} differing attributes."
            )

            primary_img = _get_primary_image_url(cand_variant, cand_product)

            evaluated_substitutes.append(
                SubstituteItemResponse(
                    listing_id=cand.id,
                    product_id=cand_product.id,
                    product_name=cand_product.name,
                    product_slug=cand_product.slug,
                    brand=cand_brand,
                    variant_id=cand_variant.id,
                    variant_name=cand_variant.name,
                    variant_sku=cand_variant.sku,
                    variant_attributes=cand_attrs,
                    primary_image_url=primary_img,
                    retailer_id=cand_retailer.id,
                    retailer_name=cand_retailer.name,
                    retailer_slug=cand_retailer.slug,
                    retailer_rating=cand_retailer.rating,
                    retailer_verification_status=cand_retailer.verification_status,
                    original_price_paise=cand.original_price_paise,
                    selling_price_paise=cand.selling_price_paise,
                    price_diff_paise=price_diff_paise,
                    price_diff_percentage=price_diff_percentage,
                    savings_percentage=savings_pct,
                    available_stock=cand_stock,
                    is_in_stock=cand_in_stock,
                    availability_status=avail_status,
                    similarity_score=similarity_score,
                    substitute_type=primary_type,
                    applicable_types=applicable_types,
                    reason=reason,
                    matching_specs=matching_specs,
                    differing_specs=differing_specs,
                    detailed_comparisons=detailed_comparisons,
                    compatibility_notes=compat_notes,
                )
            )

        # Filter by requested filter_type if specified
        if filter_type:
            evaluated_substitutes = [
                sub
                for sub in evaluated_substitutes
                if filter_type in sub.applicable_types
                or sub.substitute_type == filter_type
            ]

        # Ranking:
        # Prioritize in-stock, then highest similarity score, then closest price
        evaluated_substitutes.sort(
            key=lambda x: (
                not x.is_in_stock,
                -x.similarity_score,
                abs(x.price_diff_paise),
            )
        )

        final_substitutes = evaluated_substitutes[:limit]

        return SubstituteListResponse(
            original_listing_id=orig_listing.id,
            original_product_name=orig_product.name,
            original_product_slug=orig_product.slug,
            original_brand=orig_brand,
            original_category_id=orig_category.id,
            original_category_name=orig_category.name,
            original_selling_price_paise=orig_price,
            original_is_in_stock=orig_is_in_stock,
            original_available_stock=orig_stock,
            original_attributes=orig_attrs,
            substitutes=final_substitutes,
            total_count=len(final_substitutes),
            trigger_reason=trigger_reason,
        )
