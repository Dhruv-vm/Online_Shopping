"""Customer intent workflow (final cycle, Part 6).

A customer says what they want (items, budget, frequency, service area,
timeframe). We save it, then show — from real data only — what the system
understood, which listings actually match, which stores can supply them, and
what happens next. Items no store can supply are recorded as Demand Gap
signals through the normal DemandService (deduplicated per customer), so
retailers see real, aggregated demand. Nothing here invents matches,
retailers or notifications.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.pincode import retailer_serves
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
)
from app.modules.demand.models import DemandPool, DemandPoolStatus, DemandSignalType
from app.modules.demand.service import DemandService, normalize_demand_text
from app.modules.intent.models import RecurringIntention
from app.modules.intent.schemas import (
    IntentBasketResponse,
    IntentDemandStatus,
    IntentItemIn,
    IntentItemResult,
    IntentListingMatch,
    IntentSubmitRequest,
    IntentSummary,
    IntentWorkflowResponse,
)
from app.modules.intent.service import IntentService

MAX_MATCHES = 3


def _dedupe_key(req: IntentSubmitRequest) -> str:
    names = sorted(normalize_demand_text(i.name) for i in req.items)
    raw = json.dumps([names, req.pincode or "", req.frequency])
    return hashlib.sha256(raw.encode()).hexdigest()


class IntentWorkflow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------ write
    async def submit(
        self, customer_id: uuid.UUID, req: IntentSubmitRequest
    ) -> IntentWorkflowResponse:
        key = _dedupe_key(req)
        existing = (
            await self.session.execute(
                select(RecurringIntention).where(
                    RecurringIntention.customer_id == customer_id,
                    RecurringIntention.dedupe_key == key,
                    RecurringIntention.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        intention = existing or RecurringIntention(
            id=uuid.uuid4(), customer_id=customer_id, is_active=True
        )
        self._apply(intention, req, key)
        if existing is None:
            self.session.add(intention)
        await self.session.flush()
        return await self.analyze(
            intention, record_demand=True, updated_existing=existing is not None
        )

    async def update(
        self, customer_id: uuid.UUID, intention_id: uuid.UUID, req: IntentSubmitRequest
    ) -> IntentWorkflowResponse:
        intention = await self._own(customer_id, intention_id)
        self._apply(intention, req, _dedupe_key(req))
        await self.session.flush()
        return await self.analyze(intention, record_demand=True, updated_existing=True)

    @staticmethod
    def _apply(
        intention: RecurringIntention, req: IntentSubmitRequest, key: str
    ) -> None:
        intention.title = req.title.strip()
        intention.items = [i.model_dump() for i in req.items]
        intention.budget_paise = req.budget_paise
        intention.frequency = req.frequency
        intention.pincode = req.pincode
        intention.purchase_by = req.purchase_by
        intention.notes = req.notes
        intention.dedupe_key = key
        intention.is_active = True

    async def _own(self, customer_id, intention_id) -> RecurringIntention:
        intention = await self.session.get(RecurringIntention, intention_id)
        if intention is None or intention.customer_id != customer_id:
            raise AppException(
                code="INTENT_NOT_FOUND", message="Intent not found.", status_code=404
            )
        return intention

    async def list_intents(self, customer_id) -> list[IntentSummary]:
        rows = (
            (
                await self.session.execute(
                    select(RecurringIntention)
                    .where(
                        RecurringIntention.customer_id == customer_id,
                        RecurringIntention.dedupe_key.is_not(None),
                    )
                    .order_by(RecurringIntention.updated_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        return [
            IntentSummary(
                id=r.id,
                title=r.title,
                frequency=r.frequency,
                budget_paise=r.budget_paise,
                pincode=r.pincode,
                item_count=len(r.items or []),
                is_active=r.is_active,
                last_status=(r.last_analysis or {}).get("status"),
                analyzed_at=r.analyzed_at,
            )
            for r in rows
        ]

    async def get(self, customer_id, intention_id) -> IntentWorkflowResponse:
        intention = await self._own(customer_id, intention_id)
        # Viewing never records new demand; it only refreshes matches and status.
        return await self.analyze(intention, record_demand=False)

    # ------------------------------------------------------------ analysis
    async def _matches(
        self, item: IntentItemIn, pincode: str | None, max_unit_paise: int | None
    ) -> tuple[list[IntentListingMatch], str | None, int]:
        from app.modules.search.service import SearchService

        query = item.name.strip()
        found = await SearchService().search(
            self.session, q=query, in_stock_only=True, sort="relevance", page_size=10
        )
        # Every word the customer typed must appear as a whole word in the product's
        # name, brand or category ("rice" must not match "Fisher-Price").
        words = [w for w in re.findall(r"\w+", query.casefold()) if len(w) > 1]

        def relevant(p) -> bool:
            hay = f"{p.name} {p.brand} {p.category_name}".casefold()
            return all(re.search(rf"\b{re.escape(w)}", hay) for w in words)

        product_ids = []
        for p in found.items:
            if not relevant(p):
                continue
            try:
                product_ids.append(uuid.UUID(str(p.product_id)))
            except ValueError:
                continue
        if not product_ids:
            return [], None, 0
        rows = (
            (
                await self.session.execute(
                    select(ProductListing)
                    .join(
                        ProductVariant, ProductVariant.id == ProductListing.variant_id
                    )
                    .join(Product, Product.id == ProductVariant.product_id)
                    .join(Retailer, Retailer.id == ProductListing.retailer_id)
                    .options(
                        selectinload(ProductListing.inventory),
                        selectinload(ProductListing.retailer),
                        selectinload(ProductListing.variant)
                        .selectinload(ProductVariant.product)
                        .selectinload(Product.category),
                    )
                    .where(
                        Product.id.in_(product_ids),
                        ProductListing.is_active.is_(True),
                        Retailer.is_active.is_(True),
                        Retailer.verification_status == "VERIFIED",
                    )
                    .order_by(ProductListing.selling_price_paise.asc())
                )
            )
            .scalars()
            .all()
        )
        out: list[IntentListingMatch] = []
        stores: set[uuid.UUID] = set()
        rank = {pid: i for i, pid in enumerate(product_ids)}
        rows = sorted(
            rows,
            key=lambda lst: (
                rank.get(lst.variant.product_id, 99),
                lst.selling_price_paise,
            ),
        )
        for lst in rows:
            inv = lst.inventory
            available = (
                max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            )
            if available < item.quantity:
                continue
            if pincode and not retailer_serves(lst.retailer.service_pincodes, pincode):
                continue
            if max_unit_paise is not None and lst.selling_price_paise > max_unit_paise:
                continue
            stores.add(lst.retailer_id)
            if len(out) < MAX_MATCHES:
                out.append(
                    IntentListingMatch(
                        listing_id=lst.id,
                        product_name=lst.variant.product.name,
                        product_slug=lst.variant.product.slug,
                        variant_name=lst.variant.name,
                        retailer_name=lst.retailer.name,
                        price_paise=int(lst.selling_price_paise),
                        original_price_paise=int(lst.original_price_paise),
                        available_quantity=available,
                        offers=await self._offer_names(lst),
                    )
                )
        out.sort(key=lambda m: m.price_paise)
        category = None
        for lst in rows:
            if lst.id == (out[0].listing_id if out else None):
                cat = lst.variant.product.category
                category = cat.name if cat else None
        return out, category, len(stores)

    async def _offer_names(self, lst: ProductListing) -> list[str]:
        """Live, code-free offers that would price this listing (real discounts only)."""
        from app.modules.pricing.discount_service import DiscountLine, DiscountService

        svc = DiscountService(self.session)
        line = DiscountLine(
            listing_id=lst.id,
            retailer_id=lst.retailer_id,
            product_id=lst.variant.product_id,
            category_id=lst.variant.product.category_id,
            unit_price_paise=int(lst.selling_price_paise),
            quantity=1,
        )
        cands = await svc._line_candidates(line, datetime.now(UTC))
        return [d.name for d in cands if d.code is None][:3]

    async def _demand(
        self, customer_id, item: IntentItemIn, pincode: str | None, record: bool
    ) -> IntentDemandStatus | None:
        signal_recorded = False
        if record:
            pool, duplicate = await DemandService(self.session).record_signal(
                signal_type=DemandSignalType.WISHLIST.value,
                query_text=item.name.strip(),
                pincode=pincode,
                user_id=customer_id,
            )
            signal_recorded = not duplicate
        else:
            norm = normalize_demand_text(item.name)
            pool = (
                await self.session.execute(
                    select(DemandPool)
                    .where(
                        DemandPool.normalized_product_name == norm,
                        (DemandPool.pincode == pincode)
                        if pincode
                        else DemandPool.pincode.is_(None),
                        DemandPool.status != DemandPoolStatus.EXPIRED.value,
                    )
                    .order_by(DemandPool.last_signal_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if pool is None:
                return None
        return IntentDemandStatus(
            pool_id=pool.id,
            display_name=pool.display_name,
            unique_customers=pool.unique_users_count,
            visibility_threshold=pool.visibility_threshold,
            visible_to_retailers=pool.unique_users_count >= pool.visibility_threshold,
            status=pool.status,
            signal_recorded_now=signal_recorded,
        )

    async def analyze(
        self,
        intention: RecurringIntention,
        *,
        record_demand: bool,
        updated_existing: bool = False,
    ) -> IntentWorkflowResponse:
        items = [IntentItemIn(**i) for i in (intention.items or [])]
        single = len(items) == 1
        results: list[IntentItemResult] = []
        cheapest = 0
        for item in items:
            # For a single-item intent the budget is a price ceiling per unit.
            cap = (
                intention.budget_paise // item.quantity
                if single and intention.budget_paise
                else None
            )
            matches, category, stores = await self._matches(
                item, intention.pincode, cap
            )
            understood = item.name.strip() + (
                f" ({item.specs.strip()})" if item.specs else ""
            )
            if matches:
                cheapest += matches[0].price_paise * item.quantity
                demand = None
                nxt = (
                    f"{stores} store(s) near you can supply this now. "
                    "Add it to your cart from here or open the product."
                )
                status = "AVAILABLE"
            else:
                demand = await self._demand(
                    intention.customer_id, item, intention.pincode, record_demand
                )
                status = "NOT_AVAILABLE"
                if demand is None:
                    nxt = "No store near you has this in stock yet."
                elif demand.visible_to_retailers:
                    nxt = (
                        "Recorded as demand. Enough shoppers asked for this that stores "
                        "now see it under Demand Gaps; when a store lists it you get an "
                        "in-app 'Now available near you' notification."
                    )
                else:
                    nxt = (
                        f"Recorded as demand ({demand.unique_customers} of "
                        f"{demand.visibility_threshold} shoppers needed before stores see "
                        "it). When a store lists it you get an in-app 'Now available "
                        "near you' notification."
                    )
            results.append(
                IntentItemResult(
                    name=item.name,
                    quantity=item.quantity,
                    specs=item.specs,
                    understood_as=understood,
                    category=category,
                    status=status,
                    matches=matches,
                    retailer_count=stores,
                    demand=demand,
                    next_step=nxt,
                )
            )

        available = [r for r in results if r.status == "AVAILABLE"]
        overall = (
            "MATCHED"
            if results and len(available) == len(results)
            else "PARTIALLY_MATCHED"
            if available
            else "WAITING_FOR_SUPPLY"
        )
        within = (
            None
            if intention.budget_paise is None or not available
            else cheapest <= intention.budget_paise
        )
        steps: list[str] = []
        if available:
            steps.append(
                "Create a basket: the cheapest matching listing for each available item "
                "is added to your cart, then you review prices and check out as usual."
            )
        if within is False:
            steps.append(
                "The cheapest matching basket is above your budget: remove items, lower "
                "quantities, or raise the budget and update this intent."
            )
        if len(available) < len(results):
            steps.append(
                "Items no store can supply yet are recorded in Demand Gaps (one signal per "
                "shopper per item). You are notified in-app when a store lists them."
            )
        if intention.frequency not in ("ONCE", None):
            steps.append(
                f"This intent repeats {intention.frequency.lower()}: open it any time to "
                "refresh prices and availability before you buy again."
            )
        now = datetime.now(UTC)
        intention.analyzed_at = now
        intention.last_analysis = {
            "status": overall,
            "cheapest_total_paise": cheapest,
            "available_items": len(available),
            "items": len(results),
        }
        await self.session.flush()
        await self.session.refresh(intention)  # server-set timestamps
        return IntentWorkflowResponse(
            intention=IntentService._map_intention(intention),
            items_requested=items,
            pincode=intention.pincode,
            purchase_by=intention.purchase_by,
            updated_existing=updated_existing,
            status=overall,
            items=results,
            cheapest_total_paise=cheapest,
            within_budget=within,
            can_create_basket=bool(available),
            next_steps=steps,
            analyzed_at=now,
        )

    # ------------------------------------------------------------ basket
    async def create_basket(self, customer_id, intention_id) -> IntentBasketResponse:
        from app.modules.cart.integration import set_customer_cart_lines

        result = await self.get(customer_id, intention_id)
        lines, added, skipped = [], [], []
        for r in result.items:
            if r.matches:
                m = r.matches[0]
                lines.append((m.listing_id, r.quantity))
                added.append(
                    {
                        "item": r.name,
                        "listing_id": str(m.listing_id),
                        "product_name": m.product_name,
                        "retailer_name": m.retailer_name,
                        "quantity": r.quantity,
                        "unit_price_paise": m.price_paise,
                    }
                )
            else:
                skipped.append(r.name)
        if not lines:
            raise AppException(
                code="NOTHING_TO_ADD",
                message="None of the items in this intent is available near you yet.",
                status_code=409,
            )
        await set_customer_cart_lines(self.session, customer_id, lines)
        intention = await self._own(customer_id, intention_id)
        intention.last_executed_at = datetime.now(UTC)
        await self.session.flush()
        msg = f"Added {len(added)} item(s) to your cart."
        if skipped:
            msg += f" Not available yet: {', '.join(skipped)}."
        return IntentBasketResponse(added=added, skipped=skipped, message=msg)
