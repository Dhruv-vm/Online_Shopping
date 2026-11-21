"""AI Negotiator: rule-bound conversational deal assistant (Phase 3D).

Safety controls
* Prices never go below the retailer floor (min_floor_price or max discount).
* The floor is never revealed; offers step through a fixed concession ladder.
* Max 3 rounds; sessions expire after 15 minutes; a changed cart voids the session.
* At most DAILY_SESSION_LIMIT sessions per customer per day.
* Agreed prices are applied only through single-use price awards on the
  customer's own server-side quote.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events.marketplace_events import enqueue_marketplace_event
from app.core.exceptions import AppException
from app.modules.cart.repository import CartRepository
from app.modules.catalogue.models import ProductListing, ProductVariant, Retailer
from app.modules.negotiation.messages import render
from app.modules.negotiation.models import (
    NegotiationSession,
    NegotiationStatus,
    RetailerNegotiationRule,
)
from app.modules.negotiation.schemas import (
    NegotiationLine,
    NegotiationSessionResponse,
    RuleItem,
)
from app.modules.pricing.awards import issue_award
from app.modules.pricing.discount_service import DiscountLine, DiscountService

SESSION_TTL = timedelta(minutes=15)
DAILY_SESSION_LIMIT = 10
CONCESSION_LADDER = {1: 0.4, 2: 0.7, 3: 1.0}


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _fingerprint(items) -> str:
    raw = "|".join(sorted(f"{i.listing_id}:{i.quantity}" for i in items))
    return hashlib.sha256(raw.encode()).hexdigest()


def _offer_lines(lines: list[dict], fraction: float) -> int:
    total = 0
    for ln in lines:
        gap = ln["list_unit"] - ln["floor_unit"]
        ln["offer_unit"] = ln["list_unit"] - math.floor(gap * fraction)
        total += ln["offer_unit"] * ln["quantity"]
    return total


def _fraction_for_total(lines: list[dict], target_total: int) -> float:
    list_total = sum(ln["list_unit"] * ln["quantity"] for ln in lines)
    floor_total = sum(ln["floor_unit"] * ln["quantity"] for ln in lines)
    if list_total == floor_total:
        return 0.0
    return max(0.0, min(1.0, (list_total - target_total) / (list_total - floor_total)))


class NegotiationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------- rules
    async def upsert_rule(self, retailer: Retailer, req) -> RetailerNegotiationRule:
        if req.listing_id is not None:
            listing = await self.session.get(ProductListing, req.listing_id)
            if listing is None or listing.retailer_id != retailer.id:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Listing not found in your store catalogue.",
                    status_code=404,
                )
            if (
                req.min_floor_price_paise
                and req.min_floor_price_paise > listing.selling_price_paise
            ):
                raise AppException(
                    code="FLOOR_ABOVE_PRICE",
                    message="Floor price cannot exceed the selling price.",
                    status_code=422,
                )
        elif req.min_floor_price_paise is not None:
            raise AppException(
                code="FLOOR_NEEDS_LISTING",
                message="A floor price applies to a specific listing.",
                status_code=422,
            )
        rule = (
            await self.session.execute(
                select(RetailerNegotiationRule).where(
                    RetailerNegotiationRule.retailer_id == retailer.id,
                    RetailerNegotiationRule.listing_id == req.listing_id
                    if req.listing_id
                    else RetailerNegotiationRule.listing_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if rule is None:
            rule = RetailerNegotiationRule(
                id=uuid.uuid4(), retailer_id=retailer.id, listing_id=req.listing_id
            )
            self.session.add(rule)
        rule.min_floor_price_paise = req.min_floor_price_paise
        rule.max_auto_discount_bps = int(round(req.max_auto_discount_percent * 100))
        rule.bundle_quantity_threshold = req.bundle_quantity_threshold
        rule.bundle_extra_discount_bps = int(
            round(req.bundle_extra_discount_percent * 100)
        )
        rule.is_active = req.is_active
        await self.session.flush()
        return rule

    async def list_rules(self, retailer: Retailer) -> list[RetailerNegotiationRule]:
        return list(
            (
                await self.session.execute(
                    select(RetailerNegotiationRule)
                    .where(RetailerNegotiationRule.retailer_id == retailer.id)
                    .order_by(RetailerNegotiationRule.created_at)
                )
            ).scalars()
        )

    async def delete_rule(self, retailer: Retailer, rule_id: uuid.UUID) -> None:
        rule = await self.session.get(RetailerNegotiationRule, rule_id)
        if rule is None or rule.retailer_id != retailer.id:
            raise AppException(
                code="RULE_NOT_FOUND", message="Rule not found.", status_code=404
            )
        await self.session.delete(rule)
        await self.session.flush()

    @staticmethod
    def rule_item(r: RetailerNegotiationRule) -> RuleItem:
        return RuleItem(
            id=r.id,
            listing_id=r.listing_id,
            min_floor_price_paise=r.min_floor_price_paise,
            max_auto_discount_percent=r.max_auto_discount_bps / 100,
            bundle_quantity_threshold=r.bundle_quantity_threshold,
            bundle_extra_discount_percent=r.bundle_extra_discount_bps / 100,
            is_active=r.is_active,
            created_at=r.created_at,
        )

    # -------------------------------------------------------------- engine
    async def _build_lines(self, cart_items) -> list[dict]:
        listings = {
            lst.id: lst
            for lst in (
                await self.session.execute(
                    select(ProductListing)
                    .options(
                        selectinload(ProductListing.variant).selectinload(
                            ProductVariant.product
                        )
                    )
                    .where(ProductListing.id.in_([i.listing_id for i in cart_items]))
                )
            ).scalars()
        }
        rules = list(
            (
                await self.session.execute(
                    select(RetailerNegotiationRule).where(
                        RetailerNegotiationRule.retailer_id.in_(
                            {lst.retailer_id for lst in listings.values()}
                        ),
                        RetailerNegotiationRule.is_active.is_(True),
                    )
                )
            ).scalars()
        )
        # Same public price the quote would give (Version 2.0 discount policy,
        # no discount code).
        priced = await DiscountService(self.session).resolve_basket_discounts(
            [
                DiscountLine(
                    listing_id=lst.id,
                    retailer_id=lst.retailer_id,
                    product_id=lst.variant.product_id if lst.variant else None,
                    category_id=(
                        lst.variant.product.category_id
                        if lst.variant and lst.variant.product
                        else None
                    ),
                    unit_price_paise=lst.selling_price_paise,
                    quantity=item.quantity,
                )
                for item in cart_items
                for lst in [listings[item.listing_id]]
            ]
        )
        lines = []
        for item in cart_items:
            lst = listings[item.listing_id]
            list_unit = priced.lines[lst.id].unit_price_paise
            rule = next((r for r in rules if r.listing_id == lst.id), None) or next(
                (
                    r
                    for r in rules
                    if r.retailer_id == lst.retailer_id and r.listing_id is None
                ),
                None,
            )
            floor_unit = list_unit
            if rule is not None:
                bps = rule.max_auto_discount_bps
                if (
                    rule.bundle_quantity_threshold
                    and item.quantity >= rule.bundle_quantity_threshold
                ):
                    bps += rule.bundle_extra_discount_bps
                floor_unit = math.ceil(list_unit * (10000 - bps) / 10000)
                if rule.min_floor_price_paise:
                    floor_unit = max(floor_unit, rule.min_floor_price_paise)
                floor_unit = max(1, min(floor_unit, list_unit))
            lines.append(
                {
                    "listing_id": str(lst.id),
                    "product_name": lst.variant.product.name,
                    "quantity": item.quantity,
                    "list_unit": int(list_unit),
                    "floor_unit": int(floor_unit),
                    "offer_unit": int(list_unit),
                }
            )
        return lines

    async def _cart(self, user_id: uuid.UUID):
        repo = CartRepository(self.session)
        cart = await repo.get_active_cart_by_customer_id(user_id)
        items = await repo.get_cart_items(cart.id) if cart else []
        if not cart or not items:
            raise AppException(
                code="EMPTY_CART",
                message="Add items to your basket before negotiating.",
                status_code=400,
            )
        return cart, items

    def _say(self, s: NegotiationSession, key: str, **amounts) -> bool:
        text, fallback = render(s.language, key, **amounts)
        s.messages = [
            *s.messages,
            {"role": "assistant", "text": text, "at": datetime.now(UTC).isoformat()},
        ]
        return fallback

    async def start(self, user_id: uuid.UUID, req) -> NegotiationSession:
        from app.modules.i18n.service import validate_language

        language = validate_language(req.language)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(NegotiationSession)
                .where(
                    NegotiationSession.user_id == user_id,
                    NegotiationSession.created_at >= today,
                )
            )
        ).scalar() or 0
        if count >= DAILY_SESSION_LIMIT:
            raise AppException(
                code="NEGOTIATION_LIMIT",
                message="Daily negotiation limit reached.",
                status_code=429,
            )
        cart, items = await self._cart(user_id)
        await self.session.execute(
            update(NegotiationSession)
            .where(
                NegotiationSession.cart_id == cart.id,
                NegotiationSession.status == NegotiationStatus.IN_PROGRESS.value,
            )
            .values(status=NegotiationStatus.EXPIRED.value)
        )
        lines = await self._build_lines(items)
        list_total = sum(ln["list_unit"] * ln["quantity"] for ln in lines)
        floor_total = sum(ln["floor_unit"] * ln["quantity"] for ln in lines)
        offer = _offer_lines(lines, CONCESSION_LADDER[1])
        s = NegotiationSession(
            id=uuid.uuid4(),
            user_id=user_id,
            cart_id=cart.id,
            cart_fingerprint=_fingerprint(items),
            language=language,
            target_price_paise=req.target_price_paise,
            max_budget_paise=req.max_budget_paise,
            list_total_paise=list_total,
            floor_total_paise=floor_total,
            current_round=1,
            max_rounds=3,
            proposed_price_paise=offer,
            lines=lines,
            messages=[],
            status=NegotiationStatus.IN_PROGRESS.value,
            expires_at=datetime.now(UTC) + SESSION_TTL,
        )
        if floor_total >= list_total:
            s.status = NegotiationStatus.REJECTED.value
            self._say(s, "nothing", list=list_total)
        else:
            self._say(s, "opening", list=list_total, offer=offer)
            if req.max_budget_paise and floor_total > req.max_budget_paise:
                self._say(
                    s, "over_budget", offer=floor_total, budget=req.max_budget_paise
                )
            if req.target_price_paise:
                await self._apply_counter(
                    s, req.target_price_paise, from_customer=False
                )
        self.session.add(s)
        await self.session.flush()
        await enqueue_marketplace_event(
            self.session,
            event_type="negotiation.started",
            aggregate_type="negotiation",
            aggregate_id=s.id,
            payload={"session_id": s.id, "list_total_paise": list_total},
        )
        return s

    async def _own(
        self, session_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = True
    ) -> NegotiationSession:
        s = await self.session.get(NegotiationSession, session_id, with_for_update=lock)
        if s is None or s.user_id != user_id:
            raise AppException(
                code="NEGOTIATION_NOT_FOUND",
                message="Negotiation not found.",
                status_code=404,
            )
        if s.status == NegotiationStatus.IN_PROGRESS.value and _aware(
            s.expires_at
        ) <= datetime.now(UTC):
            s.status = NegotiationStatus.EXPIRED.value
        return s

    async def _assert_live(self, s: NegotiationSession) -> None:
        if s.status != NegotiationStatus.IN_PROGRESS.value:
            raise AppException(
                code="NEGOTIATION_CLOSED",
                message=f"Negotiation is {s.status}.",
                status_code=409,
            )
        _, items = await self._cart(s.user_id)
        if _fingerprint(items) != s.cart_fingerprint:
            s.status = NegotiationStatus.REJECTED.value
            await self.session.flush()
            raise AppException(
                code="CART_CHANGED",
                message="Your basket changed; start a new negotiation.",
                status_code=409,
            )

    async def _apply_counter(
        self, s: NegotiationSession, proposed: int, *, from_customer: bool = True
    ) -> None:
        if from_customer:
            s.messages = [
                *s.messages,
                {
                    "role": "customer",
                    "text": f"₹{proposed / 100:,.2f}",
                    "at": datetime.now(UTC).isoformat(),
                },
            ]
        lines = [dict(ln) for ln in s.lines]
        if proposed >= s.proposed_price_paise:
            self._say(
                s, "already_better", offer=s.proposed_price_paise, proposed=proposed
            )
        elif proposed >= s.floor_total_paise:
            agreed = _offer_lines(lines, _fraction_for_total(lines, proposed))
            s.lines = lines
            s.proposed_price_paise = agreed
            self._say(s, "agree", agreed=agreed)
        elif s.current_round < s.max_rounds:
            s.current_round += 1
            s.proposed_price_paise = _offer_lines(
                lines, CONCESSION_LADDER[s.current_round]
            )
            s.lines = lines
            key = "final" if s.current_round == s.max_rounds else "counter"
            self._say(s, key, offer=s.proposed_price_paise, proposed=proposed)
        else:
            self._say(s, "final", offer=s.proposed_price_paise)

    async def counter(self, user_id: uuid.UUID, req) -> NegotiationSession:
        s = await self._own(req.session_id, user_id)
        await self._assert_live(s)
        if sum(1 for m in s.messages if m["role"] == "customer") >= s.max_rounds + 2:
            raise AppException(
                code="MAX_ROUNDS_REACHED",
                message="No more counter-offers in this session.",
                status_code=409,
            )
        await self._apply_counter(s, req.proposed_price_paise)
        await self.session.flush()
        return s

    async def accept(self, user_id: uuid.UUID, req):
        from app.modules.cart.models import Cart
        from app.modules.pricing.quote_service import QuoteService

        s = await self._own(req.session_id, user_id)
        await self._assert_live(s)
        for ln in s.lines:
            if ln["offer_unit"] < ln["list_unit"]:
                await issue_award(
                    self.session,
                    customer_id=user_id,
                    listing_id=uuid.UUID(ln["listing_id"]),
                    unit_price_paise=ln["offer_unit"],
                    max_quantity=ln["quantity"],
                    source="NEGOTIATION",
                    source_id=s.id,
                    ttl=SESSION_TTL,
                )
        await self.session.flush()
        cart = await self.session.get(Cart, s.cart_id)
        quote = await QuoteService(self.session).generate_quote_from_cart(cart)
        s.status = NegotiationStatus.ACCEPTED.value
        s.final_accepted_price_paise = s.proposed_price_paise
        s.quote_id = quote.id
        self._say(s, "accepted", agreed=s.proposed_price_paise)
        await enqueue_marketplace_event(
            self.session,
            event_type="negotiation.accepted",
            aggregate_type="negotiation",
            aggregate_id=s.id,
            payload={
                "session_id": s.id,
                "agreed_paise": s.proposed_price_paise,
                "list_total_paise": s.list_total_paise,
                "quote_id": quote.id,
            },
        )
        await self.session.flush()
        return s, quote

    async def get(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> NegotiationSession:
        return await self._own(session_id, user_id, lock=False)

    @staticmethod
    def to_response(s: NegotiationSession, quote=None) -> NegotiationSessionResponse:
        return NegotiationSessionResponse(
            id=s.id,
            status=s.status,
            language=s.language,
            language_fallback=s.language not in ("en", "hi"),
            current_round=s.current_round,
            max_rounds=s.max_rounds,
            list_total_paise=s.list_total_paise,
            current_offer_paise=s.proposed_price_paise,
            savings_paise=s.list_total_paise - s.proposed_price_paise,
            final_accepted_price_paise=s.final_accepted_price_paise,
            within_budget=(s.proposed_price_paise <= s.max_budget_paise)
            if s.max_budget_paise
            else None,
            lines=[
                NegotiationLine(
                    listing_id=uuid.UUID(ln["listing_id"]),
                    product_name=ln["product_name"],
                    quantity=ln["quantity"],
                    list_unit_price_paise=ln["list_unit"],
                    offer_unit_price_paise=ln["offer_unit"],
                    negotiable=ln["floor_unit"] < ln["list_unit"],
                )
                for ln in s.lines
            ],
            messages=s.messages,
            expires_at=s.expires_at,
            quote_id=s.quote_id,
            quote_total_payable_paise=quote.total_payable_paise if quote else None,
            quote_expires_at=quote.expires_at if quote else None,
        )
