"""Handwritten List to Basket (Phase 3I, optional)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cart.integration import set_customer_cart_lines
from app.modules.catalogue.models import ProductListing, Retailer
from app.modules.search.service import SearchService
from app.modules.vision.parser import parse_list
from app.modules.vision.providers import get_ocr_provider
from app.modules.vision.schemas import MatchCandidate, ParsedListItem, ParseListResponse

_search = SearchService()


class VisionListService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def parse(self, req) -> ParseListResponse:
        provider_name = None
        if req.image_base64:
            provider = get_ocr_provider()
            provider_name = provider.name
            raw_text = await provider.extract_text(req.image_base64, req.content_type)
            source = "OCR"
        else:
            raw_text = req.text
            source = "TEXT"
        items: list[ParsedListItem] = []
        for p in parse_list(raw_text):
            query = f"{p.search_query} {p.size}" if p.size else p.search_query
            res = await _search.search(
                self.session, q=query, in_stock_only=True, page_size=5
            )
            if res.total == 0 and p.size:
                res = await _search.search(
                    self.session, q=p.search_query, in_stock_only=True, page_size=5
                )
            candidates: list[MatchCandidate] = []
            for hit in res.items[:5]:
                for r in sorted(
                    hit.retailers,
                    key=lambda x: (
                        x.get("selling_price_paise", 0) if isinstance(x, dict) else 0
                    ),
                ):
                    r = r if isinstance(r, dict) else r.model_dump()
                    if (
                        r.get("is_in_stock")
                        and r.get("available_quantity", 0) >= p.quantity
                    ):
                        candidates.append(
                            MatchCandidate(
                                listing_id=uuid.UUID(r["listing_id"]),
                                product_id=uuid.UUID(hit.product_id),
                                product_name=hit.name,
                                retailer_name=r["retailer_name"],
                                price_paise=int(r["selling_price_paise"]),
                                in_stock=True,
                            )
                        )
                        break
                if len(candidates) >= 3:
                    break
            items.append(
                ParsedListItem(
                    line=p.line,
                    name=p.name,
                    interpreted_as=query,
                    size=p.size,
                    quantity=p.quantity,
                    candidates=candidates,
                    suggested_listing_id=candidates[0].listing_id
                    if candidates
                    else None,
                )
            )
        return ParseListResponse(
            source=source,
            provider=provider_name,
            raw_text=raw_text,
            items=items,
            unmatched_count=sum(1 for i in items if not i.candidates),
        )

    async def build_cart(
        self, user_id: uuid.UUID, items
    ) -> tuple[uuid.UUID, int, list[dict]]:
        listings = {
            lst.id: lst
            for lst in (
                await self.session.execute(
                    select(ProductListing)
                    .options(
                        selectinload(ProductListing.inventory),
                        selectinload(ProductListing.retailer),
                    )
                    .where(ProductListing.id.in_([i.listing_id for i in items]))
                )
            ).scalars()
        }
        lines, skipped = [], []
        for i in items:
            lst = listings.get(i.listing_id)
            retailer: Retailer | None = lst.retailer if lst else None
            inv = lst.inventory if lst else None
            avail = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            if (
                lst is None
                or not lst.is_active
                or retailer is None
                or not retailer.is_active
                or retailer.verification_status != "VERIFIED"
            ):
                skipped.append(
                    {"listing_id": str(i.listing_id), "reason": "UNAVAILABLE"}
                )
            elif avail < i.quantity:
                skipped.append(
                    {
                        "listing_id": str(i.listing_id),
                        "reason": "INSUFFICIENT_STOCK",
                        "available": avail,
                    }
                )
            else:
                lines.append((lst.id, i.quantity))
        if not lines:
            from app.core.exceptions import AppException

            raise AppException(
                code="NOTHING_TO_ADD",
                message="None of the selected items can be added.",
                status_code=409,
                details={"skipped": skipped},
            )
        cart = await set_customer_cart_lines(self.session, user_id, lines)
        return cart.id, len(lines), skipped
