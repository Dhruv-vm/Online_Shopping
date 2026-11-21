"""BASKET Deal Assistant (Phase 3D, conversational part).

A transparent, deterministic shopping assistant over the live catalogue:

* understands budget ("under ₹15,000", "below 2k"), quantity, sort intent
  ("cheapest", "best"), and comparison/alternative/negotiation requests;
* searches the real catalogue (multilingual normalisation included);
* compares real store listings, explains price differences and suggests
  cheaper alternatives in the same category;
* points to retailer-approved negotiation where a store allows it, without
  revealing the store's floor price.

It never invents products, stock, prices, brands or discounts: every number
in a reply comes from the database. No external AI provider is configured,
so ``mode`` is always ``rule_based`` and the reply says so.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.schemas import (
    AssistantOption,
    AssistantReply,
    AssistantSeller,
)
from app.modules.negotiation.models import RetailerNegotiationRule
from app.modules.search.service import SearchService

_search = SearchService()

_STOPWORDS = {
    "i",
    "me",
    "my",
    "want",
    "need",
    "looking",
    "for",
    "a",
    "an",
    "the",
    "to",
    "buy",
    "get",
    "show",
    "find",
    "some",
    "please",
    "can",
    "you",
    "with",
    "and",
    "under",
    "below",
    "within",
    "less",
    "than",
    "upto",
    "up",
    "budget",
    "of",
    "rs",
    "inr",
    "cheapest",
    "cheap",
    "best",
    "good",
    "compare",
    "comparison",
    "alternatives",
    "alternative",
    "options",
    "option",
    "deal",
    "deals",
    "negotiate",
    "discount",
    "price",
    "prices",
    "around",
    "about",
    "in",
    "on",
    "is",
    "are",
    "what",
    "which",
    "me?",
    "?",
    "it",
    "that",
    "this",
}
_NUM = r"(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)\s*(k|thousand|lakh|lac)?"


@dataclass
class Intent:
    query: str
    budget_paise: int | None = None
    quantity: int = 1
    wants_cheapest: bool = False
    wants_compare: bool = False
    wants_alternatives: bool = False
    wants_negotiation: bool = False
    notes: list[str] = field(default_factory=list)


def _amount(num: str, unit: str | None) -> int:
    value = float(num.replace(",", ""))
    mult = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lac": 100_000}.get(
        (unit or "").lower(), 1
    )
    return int(round(value * mult * 100))


def parse_intent(message: str) -> Intent:
    text = message.strip()
    low = text.lower()
    budget = None
    m = re.search(
        r"(?:under|below|within|less than|upto|up to|budget(?: of)?|max(?:imum)?|<)\s*(?:₹|rs\.?|inr)?\s*"
        + _NUM,
        low,
    ) or re.search(r"(?:₹|rs\.?\s?|inr\s?)" + _NUM, low)
    if m:
        budget = _amount(m.group(1), m.group(2))
        low = low.replace(m.group(0), " ")
    qty = 1
    q = re.search(r"\b(\d{1,2})\s*(?:x|pcs|pieces|units|nos)\b", low) or re.search(
        r"\b(?:qty|quantity)\s*(\d{1,2})\b", low
    )
    if q:
        qty = max(1, min(10, int(q.group(1))))
        low = low.replace(q.group(0), " ")
    intent = Intent(
        query="",
        budget_paise=budget,
        quantity=qty,
        wants_cheapest=bool(re.search(r"\b(cheapest|lowest|cheap|budget)\b", low)),
        wants_compare=bool(
            re.search(r"\b(compare|comparison|vs|versus|difference)\b", low)
        ),
        wants_alternatives=bool(
            re.search(
                r"\b(alternative|alternatives|similar|instead|other options)\b", low
            )
        ),
        wants_negotiation=bool(
            re.search(r"\b(negotiate|bargain|deal|discount|offer)\b", low)
        ),
    )
    words = [
        w
        for w in re.findall(r"[\w'+\-.]+", low, flags=re.UNICODE)
        if w not in _STOPWORDS
    ]
    intent.query = " ".join(words).strip()
    return intent


def _option_from_hit(hit, qty: int) -> AssistantOption | None:
    sellers = []
    for r in hit.retailers or []:
        r = r if isinstance(r, dict) else r.model_dump()
        if not r.get("is_in_stock") or int(r.get("available_quantity", 0)) < qty:
            continue
        sellers.append(
            AssistantSeller(
                listing_id=uuid.UUID(str(r["listing_id"])),
                retailer_id=uuid.UUID(str(r["retailer_id"]))
                if r.get("retailer_id")
                else None,
                retailer_name=str(r.get("retailer_name") or ""),
                price_paise=int(r["selling_price_paise"]),
                mrp_paise=int(
                    r.get("original_price_paise") or r["selling_price_paise"]
                ),
                available_quantity=int(r.get("available_quantity", 0)),
                negotiable=False,
            )
        )
    if not sellers:
        return None
    sellers.sort(key=lambda s: s.price_paise)
    return AssistantOption(
        product_id=uuid.UUID(str(hit.product_id)),
        name=hit.name,
        brand=hit.brand,
        category_slug=hit.category_slug,
        image_url=hit.primary_image_url,
        best_price_paise=sellers[0].price_paise,
        sellers=sellers[:5],
        within_budget=True,
        explanation="",
    )


def _inr(paise: int) -> str:
    return f"₹{paise / 100:,.0f}" if paise % 100 == 0 else f"₹{paise / 100:,.2f}"


async def answer(session: AsyncSession, message: str) -> AssistantReply:
    intent = parse_intent(message)
    if not intent.query:
        return AssistantReply(
            mode="rule_based",
            ai_provider_configured=False,
            understood={
                "query": None,
                "budget_paise": intent.budget_paise,
                "quantity": intent.quantity,
            },
            message=(
                "Tell me what you are shopping for — for example “wireless headphones under ₹30,000” "
                "or “compare air fryers”."
            ),
            options=[],
            alternatives=[],
            disclaimer=DISCLAIMER,
        )

    res = await _search.search(
        session,
        q=intent.query,
        in_stock_only=True,
        sort="price_asc" if intent.wants_cheapest else "relevance",
        page_size=12,
    )
    options = [
        o for o in (_option_from_hit(h, intent.quantity) for h in res.items) if o
    ]

    # Negotiation availability (never reveals the floor).
    all_ids = [s.listing_id for o in options for s in o.sellers]
    rules = (
        (
            await session.execute(
                select(
                    RetailerNegotiationRule.listing_id,
                    RetailerNegotiationRule.retailer_id,
                ).where(RetailerNegotiationRule.is_active.is_(True))
            )
        ).all()
        if all_ids
        else []
    )
    store_wide = {rid for lid, rid in rules if lid is None}
    specific = {lid for lid, _ in rules if lid is not None}
    for o in options:
        for s in o.sellers:
            s.negotiable = s.listing_id in specific or (s.retailer_id in store_wide)

    budget = intent.budget_paise
    total = lambda p: p * intent.quantity  # noqa: E731
    within = [
        o for o in options if budget is None or total(o.best_price_paise) <= budget
    ]
    over = [
        o for o in options if budget is not None and total(o.best_price_paise) > budget
    ]
    for o in options:
        o.within_budget = budget is None or total(o.best_price_paise) <= budget
        if len(o.sellers) > 1:
            spread = o.sellers[-1].price_paise - o.sellers[0].price_paise
            o.explanation = (
                f"{len(o.sellers)} stores sell this. {o.sellers[0].retailer_name} is cheapest at "
                f"{_inr(o.sellers[0].price_paise)}; prices differ by up to {_inr(spread)} because each "
                "store sets its own price."
            )
        else:
            o.explanation = f"Sold by {o.sellers[0].retailer_name} at {_inr(o.sellers[0].price_paise)}."
        if o.sellers[0].mrp_paise > o.sellers[0].price_paise:
            pct = (
                (o.sellers[0].mrp_paise - o.sellers[0].price_paise)
                * 100
                / o.sellers[0].mrp_paise
            )
            o.explanation += (
                f" That is {pct:.0f}% below its MRP of {_inr(o.sellers[0].mrp_paise)}."
            )

    alternatives: list[AssistantOption] = []
    if (over and not within) or intent.wants_alternatives:
        cats = {o.category_slug for o in options if o.category_slug}
        for slug in list(cats)[:2]:
            alt = await _search.search(
                session,
                category_slug=slug,
                in_stock_only=True,
                max_price_paise=(budget // intent.quantity) if budget else None,
                sort="price_asc",
                page_size=6,
            )
            seen = {o.product_id for o in options}
            for h in alt.items:
                ao = _option_from_hit(h, intent.quantity)
                if ao and ao.product_id not in seen:
                    ao.within_budget = (
                        budget is None or total(ao.best_price_paise) <= budget
                    )
                    ao.explanation = f"A cheaper option in the same department from {ao.sellers[0].retailer_name}."
                    alternatives.append(ao)
                    seen.add(ao.product_id)
            if len(alternatives) >= 4:
                break

    shown = (within if budget is not None else options)[:4]
    lines: list[str] = []
    if not options:
        lines.append(
            f"I couldn't find anything in stock matching “{intent.query}”. "
            "You can request it, and stores near you will be told there is demand."
        )
    else:
        if budget is not None:
            lines.append(
                f"{len(within)} in-stock option(s) for “{intent.query}” fit your budget of {_inr(budget)}"
                + (f" for {intent.quantity} units" if intent.quantity > 1 else "")
                + "."
            )
            if over and not within:
                cheapest = min(over, key=lambda o: o.best_price_paise)
                lines.append(
                    f"The cheapest match is {cheapest.name} at {_inr(cheapest.best_price_paise)} — "
                    f"{_inr(total(cheapest.best_price_paise) - budget)} over budget."
                )
        else:
            lines.append(
                f"I found {len(options)} in-stock option(s) for “{intent.query}”."
            )
        if shown:
            best = min(shown, key=lambda o: o.best_price_paise)
            lines.append(
                f"Lowest price: {best.name} from {best.sellers[0].retailer_name} at {_inr(best.best_price_paise)}."
            )
        if intent.wants_negotiation:
            neg = [o for o in shown if any(s.negotiable for s in o.sellers)]
            lines.append(
                "Stores that accept offers are marked “Negotiable” — add the item to your basket and use "
                "“Negotiate” in the cart. Offers stay within each store's own rules."
                if neg
                else "None of these stores currently accept negotiated offers."
            )
        if alternatives:
            lines.append(
                f"I also found {len(alternatives)} alternative(s) in the same department."
            )

    return AssistantReply(
        mode="rule_based",
        ai_provider_configured=False,
        understood={
            "query": intent.query,
            "budget_paise": intent.budget_paise,
            "quantity": intent.quantity,
            "wants_cheapest": intent.wants_cheapest,
            "wants_compare": intent.wants_compare,
            "wants_alternatives": intent.wants_alternatives,
            "wants_negotiation": intent.wants_negotiation,
            "interpreted_query": res.interpreted_query,
        },
        message=" ".join(lines),
        options=shown if budget is not None else options[:4],
        alternatives=alternatives[:4],
        disclaimer=DISCLAIMER,
    )


DISCLAIMER = (
    "Rule-based assistant: answers come only from BASKET's live catalogue, prices and stock. "
    "No external AI model is configured."
)
