from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.modules.catalogue.models import ProductListing
from app.modules.missions.repository import MissionRepository

logger = logging.getLogger("basket_mission_recommendation")


@dataclass
class PlannedItem:
    listing: ProductListing
    group_name: str
    quantity: int
    unit_price_paise: int
    recommendation_reason: str
    sort_order: int


@dataclass
class PlannedMissionResult:
    items: list[PlannedItem]
    total_cost_paise: int
    remaining_budget_paise: int
    is_over_budget: bool
    budget_shortfall_paise: int
    summary_explanation: str


INTENT_KEYWORDS: dict[str, list[str]] = {
    "kitchen": [
        "kitchen",
        "cook",
        "cooking",
        "chef",
        "culinary",
        "pan",
        "pot",
        "utensil",
        "dining",
    ],
    "gym": [
        "gym",
        "workout",
        "fitness",
        "exercise",
        "dumbbell",
        "yoga",
        "training",
        "cardio",
        "weights",
    ],
    "apartment": [
        "apartment",
        "flat",
        "moving",
        "house",
        "homemaker",
        "home setup",
        "living room",
    ],
    "baby": ["baby", "newborn", "infant", "toddler", "diaper", "nursery", "childcare"],
    "wfh": [
        "wfh",
        "work from home",
        "office",
        "desk",
        "workstation",
        "study",
        "laptop",
    ],
    "grocery": [
        "grocery",
        "groceries",
        "pantry",
        "household",
        "food supply",
        "staples",
        "family ration",
    ],
    "travel": [
        "travel",
        "trip",
        "vacation",
        "journey",
        "tour",
        "backpacking",
        "luggage",
    ],
    "beauty": [
        "beauty",
        "grooming",
        "skincare",
        "personal care",
        "cosmetic",
        "hygiene",
    ],
    "auto": ["automotive", "car", "bike", "vehicle", "driving", "mechanic"],
}

CATEGORY_SLUG_MAP: dict[str, list[str]] = {
    "kitchen": ["home-kitchen", "grocery-food"],
    "gym": ["sports-fitness"],
    "apartment": ["furniture-decor", "home-kitchen", "electronics"],
    "baby": ["toys-baby-products", "beauty-personal-care"],
    "wfh": ["electronics", "furniture-decor", "books-stationery"],
    "grocery": ["grocery-food", "home-kitchen"],
    "travel": ["fashion-clothing", "beauty-personal-care", "electronics"],
    "beauty": ["beauty-personal-care"],
    "auto": ["automotive-accessories"],
}

GROUP_NAMES_BY_INTENT: dict[str, list[str]] = {
    "kitchen": [
        "Cookware & Appliances",
        "Food Storage & Containers",
        "Essential Groceries & Provisions",
    ],
    "gym": [
        "Strength & Resistance Gear",
        "Cardio, Recovery & Mats",
        "Fitness Accessories",
    ],
    "apartment": [
        "Living & Furnishing Basics",
        "Kitchen & Dining Setup",
        "Electronics & Ambient Utility",
    ],
    "baby": [
        "Infant Care & Essentials",
        "Feeding & Nursery Tools",
        "Gentle Hygiene & Comfort",
    ],
    "wfh": [
        "Ergonomic Desk & Seating",
        "Productivity Tech & Audio",
        "Stationery & Cables",
    ],
    "grocery": [
        "Daily Staples & Grain Provisions",
        "Fresh Pantry & Packaged Goods",
        "Household & Cleaning Essentials",
    ],
    "travel": [
        "Luggage & Apparel Essentials",
        "Toiletries & Hygiene Kit",
        "Portable Electronics & Converters",
    ],
    "beauty": [
        "Skincare & Cleansing",
        "Haircare & Treatment",
        "Daily Grooming Essentials",
    ],
    "auto": [
        "Vehicle Care & Accessories",
        "Cabin Comfort & Tech",
        "Safety & Maintenance",
    ],
}


class RecommendationEngine:
    def __init__(self, repo: MissionRepository):
        self.repo = repo

    def detect_intent(
        self,
        title: str,
        description: str | None = None,
        preferences: list[str] | None = None,
    ) -> str:
        text = f"{title} {description or ''} {' '.join(preferences or [])}".lower()
        best_intent = "general"
        highest_matches = 0

        for intent, keywords in INTENT_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > highest_matches:
                highest_matches = matches
                best_intent = intent

        return best_intent

    async def generate_plan(
        self,
        title: str,
        budget_paise: int,
        description: str | None = None,
        category_id: uuid.UUID | None = None,
        people_count: int = 1,
        preferences: list[str] | None = None,
        excluded_brands: list[str] | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> PlannedMissionResult:
        intent = self.detect_intent(title, description, preferences)
        categories = await self.repo.get_all_active_categories()
        category_by_id = {c.id: c for c in categories}
        category_by_slug = {c.slug: c for c in categories}

        # Load customer preference profile if personalization is enabled
        profile = None
        if customer_id:
            from sqlalchemy import select

            from app.modules.intent.models import CustomerPreferenceProfile

            stmt_p = select(CustomerPreferenceProfile).where(
                CustomerPreferenceProfile.customer_id == customer_id
            )
            res_p = await self.repo.session.execute(stmt_p)
            profile = res_p.scalar_one_or_none()

        pref_brands = (
            [b.strip().lower() for b in (profile.preferred_brands or []) if b.strip()]
            if profile and profile.personalization_enabled
            else []
        )

        # 1. Resolve target category IDs
        target_cat_ids: list[uuid.UUID] = []
        if category_id and category_id in category_by_id:
            target_cat_ids.append(category_id)
        else:
            target_slugs = CATEGORY_SLUG_MAP.get(intent, [])
            for slug in target_slugs:
                if slug in category_by_slug:
                    target_cat_ids.append(category_by_slug[slug].id)

        # 2. Query candidates from repository
        candidates = await self.repo.get_candidate_listings(
            category_ids=target_cat_ids if target_cat_ids else None,
            excluded_brands=excluded_brands,
            limit=100,
        )

        # Fallback if specific category was too narrow
        if len(candidates) < 3 and target_cat_ids:
            candidates = await self.repo.get_candidate_listings(
                category_ids=None,
                excluded_brands=excluded_brands,
                limit=100,
            )

        # 3. Score and group candidates
        group_names = GROUP_NAMES_BY_INTENT.get(
            intent, ["Primary Essentials", "Supportive Accessories", "Daily Supplies"]
        )

        # Score candidate listings
        pref_tokens = [p.lower().strip() for p in (preferences or []) if p.strip()]

        def score_listing(listing: ProductListing) -> tuple[int, int]:
            product = listing.variant.product
            score = 0
            # Preference matching
            p_text = f"{product.name} {product.description or ''} {product.brand or ''}".lower()
            for token in pref_tokens:
                if token in p_text:
                    score += 50
            # Intent Memory Personalization
            if (
                pref_brands
                and product.brand
                and product.brand.strip().lower() in pref_brands
            ):
                score += 60
            if profile and profile.personalization_enabled:
                priorities = profile.shopping_priorities or []
                if "LOWEST_PRICE" in priorities:
                    score += int(
                        (
                            1.0
                            - min(
                                1.0, listing.selling_price_paise / max(budget_paise, 1)
                            )
                        )
                        * 30
                    )
                if (
                    "QUALITY" in priorities
                    and listing.retailer
                    and (listing.retailer.rating or 0) >= 4.5
                ):
                    score += 25
            # Verified retailer boost
            if listing.retailer and listing.retailer.is_active:
                score += 20
            # Price within reasonable fraction of budget
            unit_price = listing.selling_price_paise
            if unit_price <= budget_paise:
                score += 10
            return (score, -unit_price)

        candidates.sort(key=score_listing, reverse=True)

        # Group candidates round-robin or category-thematic
        grouped_candidates: dict[str, list[ProductListing]] = {
            g: [] for g in group_names
        }
        for i, cand in enumerate(candidates):
            target_group = group_names[i % len(group_names)]
            grouped_candidates[target_group].append(cand)

        # 4. Greedy Selection with Budget Management
        selected_items: list[PlannedItem] = []
        running_cost_paise = 0
        sort_counter = 0

        # Pass 1: Select 1 top item from each group
        for group in group_names:
            group_items = grouped_candidates.get(group, [])
            for cand in group_items:
                unit_price = cand.selling_price_paise
                # Scale quantity if applicable (e.g. food/consumables for multiple people)
                qty = 1
                cat_slug = (
                    cand.variant.product.category.slug
                    if cand.variant.product.category
                    else ""
                )
                if people_count >= 3 and cat_slug in ("grocery-food", "home-kitchen"):
                    qty = min(2, people_count // 2 + 1)

                item_cost = unit_price * qty

                # Check if fits in remaining budget
                if running_cost_paise + item_cost <= budget_paise or not selected_items:
                    # Select this item
                    reason = self._build_recommendation_reason(
                        cand, group, qty, people_count, intent, pref_brands
                    )
                    selected_items.append(
                        PlannedItem(
                            listing=cand,
                            group_name=group,
                            quantity=qty,
                            unit_price_paise=unit_price,
                            recommendation_reason=reason,
                            sort_order=sort_counter,
                        )
                    )
                    running_cost_paise += item_cost
                    sort_counter += 1
                    break

        # Pass 2: Add complementary items while within budget
        for group in group_names:
            group_items = grouped_candidates.get(group, [])
            for cand in group_items:
                if any(si.listing.id == cand.id for si in selected_items):
                    continue

                unit_price = cand.selling_price_paise
                qty = 1
                item_cost = unit_price * qty

                if (
                    running_cost_paise + item_cost <= budget_paise
                    and len(selected_items) < 8
                ):
                    reason = self._build_recommendation_reason(
                        cand, group, qty, people_count, intent, pref_brands
                    )
                    selected_items.append(
                        PlannedItem(
                            listing=cand,
                            group_name=group,
                            quantity=qty,
                            unit_price_paise=unit_price,
                            recommendation_reason=reason,
                            sort_order=sort_counter,
                        )
                    )
                    running_cost_paise += item_cost
                    sort_counter += 1

        # Fallback: if no items fit under budget (very low budget), pick the single lowest priced valid candidate
        if not selected_items and candidates:
            lowest_cand = min(candidates, key=lambda c: c.selling_price_paise)
            unit_price = lowest_cand.selling_price_paise
            reason = f"Selected as the most affordable valid option ({lowest_cand.variant.product.name}) from {lowest_cand.retailer.name}."
            selected_items.append(
                PlannedItem(
                    listing=lowest_cand,
                    group_name=group_names[0],
                    quantity=1,
                    unit_price_paise=unit_price,
                    recommendation_reason=reason,
                    sort_order=0,
                )
            )
            running_cost_paise = unit_price

        # Budget Analytics
        is_over_budget = running_cost_paise > budget_paise
        budget_shortfall_paise = max(0, running_cost_paise - budget_paise)
        remaining_budget_paise = max(0, budget_paise - running_cost_paise)

        # Summary Explanation
        budget_inr = budget_paise / 100
        cost_inr = running_cost_paise / 100
        shortfall_inr = budget_shortfall_paise / 100
        remaining_inr = remaining_budget_paise / 100

        if not selected_items:
            summary = (
                f"No matching products found within your ₹{budget_inr:,.2f} budget criteria. "
                "Try adjusting your budget, removing brand exclusions, or selecting another category to discover suitable options."
            )
        elif is_over_budget:
            summary = (
                f"Planned {len(selected_items)} authentic marketplace products totaling ₹{cost_inr:,.2f}. "
                f"This exceeds your ₹{budget_inr:,.2f} budget by ₹{shortfall_inr:,.2f}. "
                "You can uncheck optional items or use 'Find Alternative' to select more affordable options."
            )
        else:
            summary = (
                f"Planned {len(selected_items)} authentic marketplace products totaling ₹{cost_inr:,.2f} "
                f"within your ₹{budget_inr:,.2f} budget (₹{remaining_inr:,.2f} remaining). "
                f"Optimized for {people_count} {'person' if people_count == 1 else 'people'} across verified retailers."
            )

        return PlannedMissionResult(
            items=selected_items,
            total_cost_paise=running_cost_paise,
            remaining_budget_paise=remaining_budget_paise,
            is_over_budget=is_over_budget,
            budget_shortfall_paise=budget_shortfall_paise,
            summary_explanation=summary,
        )

    def _build_recommendation_reason(
        self,
        listing: ProductListing,
        group: str,
        qty: int,
        people_count: int,
        intent: str,
        pref_brands: list[str] | None = None,
    ) -> str:
        product = listing.variant.product
        retailer = listing.retailer
        price_inr = listing.selling_price_paise / 100
        reason_parts = [
            f"Essential {group} item from {retailer.name if retailer else 'Partner Retailer'}.",
            f"Priced at ₹{price_inr:,.2f} with in-stock fulfillment.",
        ]
        if qty > 1:
            reason_parts.append(
                f"Quantity of {qty} recommended for a group of {people_count}."
            )
        if product.brand:
            if pref_brands and product.brand.strip().lower() in pref_brands:
                reason_parts.append(
                    f"Matches your saved preferred brand '{product.brand}'."
                )
            else:
                reason_parts.append(f"Trusted {product.brand} brand quality.")
        return " ".join(reason_parts)
