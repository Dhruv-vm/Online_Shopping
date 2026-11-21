from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.cart.service import CartService
from app.modules.missions.models import ShoppingMission, ShoppingMissionItem
from app.modules.missions.recommendation import RecommendationEngine
from app.modules.missions.repository import MissionRepository
from app.modules.missions.schemas import (
    MissionAddToCartResponse,
    MissionAlternativeItemResponse,
    MissionCreateRequest,
    MissionDetailResponse,
    MissionGroupResponse,
    MissionItemAddRequest,
    MissionItemReplaceRequest,
    MissionItemResponse,
    MissionItemUpdateRequest,
    MissionSummaryResponse,
    MissionUpdateRequest,
)

logger = logging.getLogger("basket_mission_service")


class MissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MissionRepository(session)
        self.engine = RecommendationEngine(self.repo)
        self.cart_service = CartService(session)

    async def create_mission(
        self, customer_id: uuid.UUID, payload: MissionCreateRequest
    ) -> MissionDetailResponse:
        """Create a new mission, run recommendations, persist items, and return detailed plan."""
        # Validate category if provided
        if payload.category_id:
            category = await self.repo.get_category_by_id(payload.category_id)
            if not category or not category.is_active:
                raise AppException(
                    code="CATEGORY_NOT_FOUND",
                    message="The selected category was not found or is inactive.",
                    status_code=400,
                )

        clean_preferences = [
            p.strip() for p in (payload.preferences or []) if p and p.strip()
        ]
        clean_excluded_brands = [
            b.strip() for b in (payload.excluded_brands or []) if b and b.strip()
        ]

        # 1. Create parent mission record
        mission = await self.repo.create_mission(
            customer_id=customer_id,
            title=payload.title.strip(),
            description=payload.description.strip() if payload.description else None,
            budget_paise=payload.budget_paise,
            category_id=payload.category_id,
            people_count=payload.people_count,
            preferences=clean_preferences,
            excluded_brands=clean_excluded_brands,
            status="ACTIVE",
        )

        # 2. Generate initial plan
        plan = await self.engine.generate_plan(
            title=payload.title.strip(),
            budget_paise=payload.budget_paise,
            description=payload.description.strip() if payload.description else None,
            category_id=payload.category_id,
            people_count=payload.people_count,
            preferences=clean_preferences,
            excluded_brands=clean_excluded_brands,
            customer_id=customer_id,
        )

        # 3. Persist items
        for p_item in plan.items:
            listing = p_item.listing
            await self.repo.add_mission_item(
                mission_id=mission.id,
                product_id=listing.variant.product_id,
                variant_id=listing.variant_id,
                listing_id=listing.id,
                retailer_id=listing.retailer_id,
                group_name=p_item.group_name,
                quantity=p_item.quantity,
                unit_price_paise=p_item.unit_price_paise,
                recommendation_reason=p_item.recommendation_reason,
                sort_order=p_item.sort_order,
                is_selected=True,
            )

        await self.session.commit()
        # 4. Fetch full mission with relationships
        full_mission = await self.repo.get_mission_by_id(mission.id)
        if not full_mission:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Mission could not be reloaded after creation.",
                status_code=500,
            )

        items = await self.repo.get_mission_items(mission.id)
        return self._format_mission_detail(
            full_mission, items, custom_explanation=plan.summary_explanation
        )

    async def preview_plan(
        self,
        payload: MissionCreateRequest,
        customer_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Generate in-memory preview without persisting."""
        if payload.category_id:
            category = await self.repo.get_category_by_id(payload.category_id)
            if not category or not category.is_active:
                raise AppException(
                    code="CATEGORY_NOT_FOUND",
                    message="The selected category was not found or is inactive.",
                    status_code=400,
                )

        clean_preferences = [
            p.strip() for p in (payload.preferences or []) if p and p.strip()
        ]
        clean_excluded_brands = [
            b.strip() for b in (payload.excluded_brands or []) if b and b.strip()
        ]

        plan = await self.engine.generate_plan(
            title=payload.title.strip(),
            budget_paise=payload.budget_paise,
            description=payload.description.strip() if payload.description else None,
            category_id=payload.category_id,
            people_count=payload.people_count,
            preferences=clean_preferences,
            excluded_brands=clean_excluded_brands,
            customer_id=customer_id,
        )

        groups_map: dict[str, list[dict[str, Any]]] = {}
        for p_item in plan.items:
            listing = p_item.listing
            variant = listing.variant
            product = variant.product
            retailer = listing.retailer
            inv = listing.inventory
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)

            primary_img = next(
                (img.url for img in product.images if img.is_primary),
                product.images[0].url if product.images else None,
            )

            item_dict = {
                "listing_id": str(listing.id),
                "product_id": str(product.id),
                "variant_id": str(variant.id),
                "product_name": product.name,
                "brand": product.brand or "",
                "variant_name": variant.name,
                "sku": variant.sku,
                "retailer_name": retailer.name if retailer else "Partner Retailer",
                "retailer_slug": retailer.slug if retailer else "",
                "image_url": primary_img,
                "group_name": p_item.group_name,
                "quantity": p_item.quantity,
                "unit_price_paise": p_item.unit_price_paise,
                "available_stock": available_stock,
                "is_in_stock": available_stock >= p_item.quantity,
                "subtotal_paise": p_item.unit_price_paise * p_item.quantity,
                "recommendation_reason": p_item.recommendation_reason,
            }
            groups_map.setdefault(p_item.group_name, []).append(item_dict)

        return {
            "title": payload.title,
            "budget_paise": payload.budget_paise,
            "total_cost_paise": plan.total_cost_paise,
            "remaining_budget_paise": plan.remaining_budget_paise,
            "is_over_budget": plan.is_over_budget,
            "budget_shortfall_paise": plan.budget_shortfall_paise,
            "items_count": len(plan.items),
            "summary_explanation": plan.summary_explanation,
            "groups": [
                {
                    "group_name": g_name,
                    "items": g_items,
                    "subtotal_paise": sum(i["subtotal_paise"] for i in g_items),
                    "items_count": len(g_items),
                }
                for g_name, g_items in groups_map.items()
            ],
        }

    async def get_mission(
        self, customer_id: uuid.UUID, mission_id: uuid.UUID
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )
        items = await self.repo.get_mission_items(mission_id)
        detail = self._format_mission_detail(mission, items)
        detail.purchased_items_count = await self._purchased_count(
            mission, [i for i in items if i.is_selected]
        )
        return detail

    async def list_missions(
        self, customer_id: uuid.UUID
    ) -> list[MissionSummaryResponse]:
        missions = await self.repo.get_missions_by_customer(customer_id)
        summaries: list[MissionSummaryResponse] = []
        for m in missions:
            # calculate total
            selected_items = [item for item in m.items if item.is_selected]
            total_paise = sum(
                item.unit_price_paise * item.quantity for item in selected_items
            )
            summaries.append(
                MissionSummaryResponse(
                    id=m.id,
                    title=m.title,
                    description=m.description,
                    budget_paise=m.budget_paise,
                    total_cost_paise=total_paise,
                    remaining_budget_paise=max(0, m.budget_paise - total_paise),
                    is_over_budget=total_paise > m.budget_paise,
                    items_count=len(selected_items),
                    status=m.status,
                    category_id=m.category_id,
                    category_name=m.category.name if m.category else None,
                    people_count=m.people_count,
                    carted_at=m.carted_at,
                    completed_at=m.completed_at,
                    completed_order_id=m.completed_order_id,
                    purchased_items_count=await self._purchased_count(
                        m, selected_items
                    ),
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
            )
        return summaries

    async def _purchased_count(self, mission, selected_items) -> int:
        from app.modules.missions.completion import purchased_listing_ids

        if mission.status == "COMPLETED":
            return len(selected_items)
        bought = await purchased_listing_ids(
            self.session, mission.customer_id, mission.carted_at
        )
        return len([i for i in selected_items if i.listing_id in bought])

    async def update_mission(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: MissionUpdateRequest,
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        if payload.title is not None:
            mission.title = payload.title
        if payload.description is not None:
            mission.description = payload.description
        if payload.budget_paise is not None:
            mission.budget_paise = payload.budget_paise
        if payload.status is not None:
            if mission.status == "COMPLETED" and payload.status != "ARCHIVED":
                raise AppException(
                    code="MISSION_ALREADY_COMPLETED",
                    message="A completed mission can only be archived.",
                    status_code=409,
                )
            mission.status = payload.status
        if payload.people_count is not None:
            mission.people_count = payload.people_count
        if payload.preferences is not None:
            mission.preferences = payload.preferences
        if payload.excluded_brands is not None:
            mission.excluded_brands = payload.excluded_brands

        await self.session.commit()
        refreshed = await self.repo.get_mission_by_id(mission_id)
        assert refreshed is not None
        items = await self.repo.get_mission_items(mission_id)
        return self._format_mission_detail(refreshed, items)

    async def delete_mission(
        self, customer_id: uuid.UUID, mission_id: uuid.UUID
    ) -> None:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )
        await self.repo.delete_mission(mission)
        await self.session.commit()

    async def add_item(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: MissionItemAddRequest,
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        # Look up listing with active & in-stock validation
        listing = await self.repo.get_valid_active_listing(payload.listing_id)
        if not listing:
            raise AppException(
                code="LISTING_NOT_AVAILABLE",
                message="Product listing is inactive, out of stock, or from an unverified retailer.",
                status_code=400,
            )

        sort_order = len(mission.items)
        reason = "Custom item added to your mission plan."
        await self.repo.add_mission_item(
            mission_id=mission.id,
            product_id=listing.variant.product_id,
            variant_id=listing.variant_id,
            listing_id=listing.id,
            retailer_id=listing.retailer_id,
            group_name=payload.group_name,
            quantity=payload.quantity,
            unit_price_paise=listing.selling_price_paise,
            recommendation_reason=reason,
            sort_order=sort_order,
            is_selected=True,
        )
        await self.session.commit()
        refreshed = await self.repo.get_mission_by_id(mission_id)
        assert refreshed is not None
        items = await self.repo.get_mission_items(mission_id)
        return self._format_mission_detail(refreshed, items)

    async def update_item(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: MissionItemUpdateRequest,
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        item = next((i for i in mission.items if i.id == item_id), None)
        if not item:
            raise AppException(
                code="MISSION_ITEM_NOT_FOUND",
                message="Mission item not found.",
                status_code=404,
            )

        if payload.quantity is not None:
            item.quantity = payload.quantity
        if payload.is_selected is not None:
            item.is_selected = payload.is_selected
        if payload.group_name is not None:
            item.group_name = payload.group_name

        await self.session.commit()
        refreshed = await self.repo.get_mission_by_id(mission_id)
        assert refreshed is not None
        items = await self.repo.get_mission_items(mission_id)
        return self._format_mission_detail(refreshed, items)

    async def delete_item(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        item = next((i for i in mission.items if i.id == item_id), None)
        if not item:
            raise AppException(
                code="MISSION_ITEM_NOT_FOUND",
                message="Mission item not found.",
                status_code=404,
            )

        await self.repo.delete_mission_item(item)
        await self.session.commit()
        refreshed = await self.repo.get_mission_by_id(mission_id)
        assert refreshed is not None
        items = await self.repo.get_mission_items(mission_id)
        return self._format_mission_detail(refreshed, items)

    async def get_item_alternatives(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> list[MissionAlternativeItemResponse]:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        item = next((i for i in mission.items if i.id == item_id), None)
        if not item:
            raise AppException(
                code="MISSION_ITEM_NOT_FOUND",
                message="Mission item not found.",
                status_code=404,
            )

        cat_id = item.product.category_id
        alt_listings = await self.repo.get_alternative_listings(
            category_id=cat_id,
            current_listing_id=item.listing_id,
            limit=10,
        )

        res: list[MissionAlternativeItemResponse] = []
        for alt in alt_listings:
            inv = alt.inventory
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)

            primary_img = next(
                (img.url for img in alt.variant.product.images if img.is_primary),
                alt.variant.product.images[0].url
                if alt.variant.product.images
                else None,
            )

            diff_paise = alt.selling_price_paise - item.unit_price_paise
            res.append(
                MissionAlternativeItemResponse(
                    listing_id=alt.id,
                    product_id=alt.variant.product_id,
                    variant_id=alt.variant_id,
                    product_name=alt.variant.product.name,
                    brand=alt.variant.product.brand or "",
                    retailer_id=alt.retailer_id,
                    retailer_name=alt.retailer.name if alt.retailer else "Retailer",
                    retailer_slug=alt.retailer.slug if alt.retailer else "",
                    selling_price_paise=alt.selling_price_paise,
                    price_diff_paise=diff_paise,
                    available_stock=available_stock,
                    is_in_stock=available_stock > 0,
                    image_url=primary_img,
                    match_type="SAME_CATEGORY",
                )
            )

        return res

    async def replace_item(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: MissionItemReplaceRequest,
    ) -> MissionDetailResponse:
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        item = next((i for i in mission.items if i.id == item_id), None)
        if not item:
            raise AppException(
                code="MISSION_ITEM_NOT_FOUND",
                message="Mission item not found.",
                status_code=404,
            )

        # Look up replacement listing verifying it is active, verified and in-stock
        new_listing = await self.repo.get_valid_active_listing(payload.new_listing_id)
        if not new_listing:
            raise AppException(
                code="ALTERNATIVE_NOT_AVAILABLE",
                message="Replacement product listing is inactive, out of stock, or from an unverified retailer.",
                status_code=400,
            )

        # Enforce category consistency
        if new_listing.variant.product.category_id != item.product.category_id:
            raise AppException(
                code="CATEGORY_MISMATCH",
                message="Alternative product must belong to the same department / category.",
                status_code=400,
            )

        item.listing_id = new_listing.id
        item.variant_id = new_listing.variant_id
        item.product_id = new_listing.variant.product_id
        item.retailer_id = new_listing.retailer_id
        item.unit_price_paise = new_listing.selling_price_paise
        item.recommendation_reason = "Customer-selected alternative option."
        if payload.quantity is not None:
            item.quantity = payload.quantity

        await self.session.commit()
        refreshed = await self.repo.get_mission_by_id(mission_id)
        assert refreshed is not None
        items = await self.repo.get_mission_items(mission_id)
        return self._format_mission_detail(refreshed, items)

    async def add_to_cart(
        self,
        customer_id: uuid.UUID,
        mission_id: uuid.UUID,
    ) -> MissionAddToCartResponse:
        """Add selected mission products to the customer's active shopping basket."""
        mission = await self.repo.get_mission_by_id(mission_id)
        if not mission or mission.customer_id != customer_id:
            raise AppException(
                code="MISSION_NOT_FOUND",
                message="Shopping mission not found.",
                status_code=404,
            )

        cart = await self.cart_service.repo.get_active_cart_by_customer_id(customer_id)
        if not cart:
            cart = await self.cart_service.repo.create_cart(customer_id=customer_id)
            await self.session.commit()
            cart = await self.cart_service.repo.get_cart_by_id(cart.id)

        added_count = 0
        skipped_count = 0
        warnings: list[str] = []

        items = await self.repo.get_mission_items(mission_id)
        selected_items = [i for i in items if i.is_selected]

        for item in selected_items:
            listing = item.listing
            product = item.product
            retailer = item.retailer

            # Check live inventory
            inv = listing.inventory if listing else None
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)

            # Check price changes
            if listing and listing.selling_price_paise != item.unit_price_paise:
                diff_inr = (listing.selling_price_paise - item.unit_price_paise) / 100
                warnings.append(
                    f"Price update for '{product.name}': price changed by ₹{diff_inr:+.2f} on marketplace."
                )

            if available_stock <= 0:
                skipped_count += 1
                warnings.append(
                    f"'{product.name}' is currently out of stock at {retailer.name if retailer else 'Retailer'} and was skipped."
                )
                continue

            qty_to_add = min(item.quantity, available_stock, 10)
            if item.quantity > 10:
                warnings.append(
                    f"Quantity for '{product.name}' was capped at basket limit of 10 units (requested {item.quantity})."
                )
            elif qty_to_add < item.quantity:
                warnings.append(
                    f"Only {qty_to_add} of {item.quantity} units of '{product.name}' were in stock and added to your basket."
                )

            try:
                await self.cart_service.add_item(
                    cart_id=cart.id,
                    listing_id=item.listing_id,
                    quantity=qty_to_add,
                )
                added_count += 1
            except Exception as exc:
                skipped_count += 1
                warnings.append(f"Failed to add '{product.name}': {exc}")

        if added_count:
            from datetime import UTC, datetime

            # Completion is later verified against paid orders created after this.
            mission.carted_at = datetime.now(UTC)
            await self.session.flush()

        # Refresh cart
        cart_items = await self.cart_service.repo.get_cart_items(cart.id)
        cart_resp = self.cart_service.format_cart_response(cart, cart_items)

        return MissionAddToCartResponse(
            mission_id=mission.id,
            added_items_count=added_count,
            skipped_items_count=skipped_count,
            warnings=warnings,
            cart=cart_resp.model_dump(),
        )

    def _format_mission_detail(
        self,
        mission: ShoppingMission,
        items: list[ShoppingMissionItem],
        custom_explanation: str | None = None,
    ) -> MissionDetailResponse:
        item_responses: list[MissionItemResponse] = []
        groups_map: dict[str, list[MissionItemResponse]] = {}

        total_cost_paise = 0
        unavailable_items_count = 0

        for item in items:
            product = item.product
            variant = item.variant
            listing = item.listing
            retailer = item.retailer
            inv = listing.inventory if listing else None
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)
            is_in_stock = available_stock >= item.quantity

            if not is_in_stock and item.is_selected:
                unavailable_items_count += 1

            current_selling_price_paise = (
                listing.selling_price_paise if listing else item.unit_price_paise
            )
            price_changed = current_selling_price_paise != item.unit_price_paise
            subtotal_paise = (
                current_selling_price_paise * item.quantity if item.is_selected else 0
            )

            if item.is_selected:
                total_cost_paise += subtotal_paise

            primary_img = None
            if product and product.images:
                primary_img = next(
                    (img.url for img in product.images if img.is_primary),
                    product.images[0].url,
                )

            resp_item = MissionItemResponse(
                id=item.id,
                mission_id=item.mission_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                listing_id=item.listing_id,
                retailer_id=item.retailer_id,
                product_name=product.name if product else "Product",
                brand=product.brand or "" if product else "",
                variant_name=variant.name if variant else "Standard",
                sku=variant.sku if variant else "",
                retailer_name=retailer.name if retailer else "Retailer",
                retailer_slug=retailer.slug if retailer else "",
                image_url=primary_img,
                group_name=item.group_name,
                quantity=item.quantity,
                unit_price_paise=item.unit_price_paise,
                current_selling_price_paise=current_selling_price_paise,
                price_changed=price_changed,
                available_stock=available_stock,
                is_in_stock=is_in_stock,
                subtotal_paise=subtotal_paise,
                is_selected=item.is_selected,
                recommendation_reason=item.recommendation_reason,
                sort_order=item.sort_order,
            )

            item_responses.append(resp_item)
            groups_map.setdefault(item.group_name, []).append(resp_item)

        groups: list[MissionGroupResponse] = [
            MissionGroupResponse(
                group_name=g_name,
                items=g_items,
                subtotal_paise=sum(i.subtotal_paise for i in g_items if i.is_selected),
                items_count=len([i for i in g_items if i.is_selected]),
            )
            for g_name, g_items in groups_map.items()
        ]

        is_over_budget = total_cost_paise > mission.budget_paise
        budget_shortfall_paise = max(0, total_cost_paise - mission.budget_paise)
        remaining_budget_paise = max(0, mission.budget_paise - total_cost_paise)

        if not custom_explanation:
            budget_inr = mission.budget_paise / 100
            cost_inr = total_cost_paise / 100
            shortfall_inr = budget_shortfall_paise / 100
            rem_inr = remaining_budget_paise / 100
            selected_count = len([i for i in item_responses if i.is_selected])
            if is_over_budget:
                custom_explanation = (
                    f"Shopping mission '{mission.title}' has {selected_count} selected items costing ₹{cost_inr:,.2f}, "
                    f"exceeding your ₹{budget_inr:,.2f} budget by ₹{shortfall_inr:,.2f}."
                )
            else:
                custom_explanation = (
                    f"Shopping mission '{mission.title}' is on track with {selected_count} selected items costing ₹{cost_inr:,.2f}, "
                    f"leaving ₹{rem_inr:,.2f} of your ₹{budget_inr:,.2f} budget."
                )

        return MissionDetailResponse(
            id=mission.id,
            customer_id=mission.customer_id,
            title=mission.title,
            description=mission.description,
            budget_paise=mission.budget_paise,
            category_id=mission.category_id,
            category_name=mission.category.name if mission.category else None,
            people_count=mission.people_count,
            preferences=mission.preferences,
            excluded_brands=mission.excluded_brands,
            status=mission.status,
            total_cost_paise=total_cost_paise,
            remaining_budget_paise=remaining_budget_paise,
            is_over_budget=is_over_budget,
            budget_shortfall_paise=budget_shortfall_paise,
            items_count=len([i for i in item_responses if i.is_selected]),
            unavailable_items_count=unavailable_items_count,
            summary_explanation=custom_explanation,
            groups=groups,
            items=item_responses,
            carted_at=mission.carted_at,
            completed_at=mission.completed_at,
            completed_order_id=mission.completed_order_id,
            purchased_items_count=(
                len([i for i in item_responses if i.is_selected])
                if mission.status == "COMPLETED"
                else 0
            ),
            created_at=mission.created_at,
            updated_at=mission.updated_at,
        )
