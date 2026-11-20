"""Basket Community Exchange: customer RFQs and retailer bids (Phase 3C)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events.marketplace_events import enqueue_marketplace_event
from app.core.exceptions import AppException
from app.core.notify import notify_customer
from app.core.pincode import retailer_serves
from app.modules.cart.integration import set_customer_cart_lines
from app.modules.catalogue.models import ProductListing, ProductVariant, Retailer
from app.modules.exchange.models import (
    ExchangeBid,
    ExchangeBidStatus,
    ExchangeRequest,
    ExchangeRequestStatus,
)
from app.modules.exchange.schemas import (
    BidItem,
    BidLine,
    ExchangeRequestItem,
    ManifestItem,
)
from app.modules.pricing.awards import issue_award

AWARD_TTL = timedelta(hours=48)


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class ExchangeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----------------------------------------------------------- customer
    async def create_request(self, user_id: uuid.UUID, req) -> ExchangeRequest:
        r = ExchangeRequest(
            id=uuid.uuid4(),
            user_id=user_id,
            title=req.title.strip(),
            delivery_pincode=req.delivery_pincode,
            budget_limit_paise=req.budget_limit_paise,
            items_manifest=[i.model_dump() for i in req.items],
            status=ExchangeRequestStatus.BIDDING_OPEN.value,
            expires_at=datetime.now(UTC) + timedelta(hours=req.bidding_hours),
        )
        self.session.add(r)
        await self.session.flush()
        await enqueue_marketplace_event(
            self.session,
            event_type="exchange.request_created",
            aggregate_type="exchange_request",
            aggregate_id=r.id,
            payload={
                "request_id": r.id,
                "pincode": r.delivery_pincode,
                "items": len(r.items_manifest),
            },
        )
        return r

    async def _locked_request(self, request_id: uuid.UUID) -> ExchangeRequest:
        r = await self.session.get(ExchangeRequest, request_id, with_for_update=True)
        if r is None:
            raise AppException(
                code="RFQ_NOT_FOUND", message="Request not found.", status_code=404
            )
        if r.status == ExchangeRequestStatus.BIDDING_OPEN.value and _aware(
            r.expires_at
        ) <= datetime.now(UTC):
            r.status = ExchangeRequestStatus.EXPIRED.value
            await self.session.flush()
        return r

    async def get_own(
        self, request_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExchangeRequest:
        r = await self.session.get(ExchangeRequest, request_id)
        if r is None or r.user_id != user_id:
            raise AppException(
                code="RFQ_NOT_FOUND", message="Request not found.", status_code=404
            )
        return r

    async def cancel(
        self, request_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExchangeRequest:
        r = await self._locked_request(request_id)
        if r.user_id != user_id:
            raise AppException(
                code="RFQ_NOT_FOUND", message="Request not found.", status_code=404
            )
        if r.status != ExchangeRequestStatus.BIDDING_OPEN.value:
            raise AppException(
                code="RFQ_CLOSED",
                message="Only open requests can be cancelled.",
                status_code=409,
            )
        r.status = ExchangeRequestStatus.CANCELLED.value
        await self.session.flush()
        return r

    async def moderate_cancel(
        self, request_id: uuid.UUID, reason: str
    ) -> ExchangeRequest:
        """Admin moderation: close an abusive/invalid open RFQ and tell the customer."""
        from app.core.notify import notify_customer

        r = await self._locked_request(request_id)
        if r.status != ExchangeRequestStatus.BIDDING_OPEN.value:
            raise AppException(
                code="RFQ_CLOSED",
                message="Only open requests can be moderated.",
                status_code=409,
            )
        r.status = ExchangeRequestStatus.CANCELLED.value
        notify_customer(
            self.session,
            customer_id=r.user_id,
            title="Your request was closed by BASKET",
            message=f"Your request was closed by our moderation team: {reason}",
            event_type="RFQ_MODERATED",
        )
        await self.session.flush()
        return r

    async def accept_bid(
        self, request_id: uuid.UUID, user_id: uuid.UUID, bid_id: uuid.UUID
    ):
        r = await self._locked_request(request_id)
        if r.user_id != user_id:
            raise AppException(
                code="RFQ_NOT_FOUND", message="Request not found.", status_code=404
            )
        if r.status != ExchangeRequestStatus.BIDDING_OPEN.value:
            raise AppException(
                code="RFQ_CLOSED", message=f"Request is {r.status}.", status_code=409
            )
        bid = await self.session.get(ExchangeBid, bid_id, with_for_update=True)
        if (
            bid is None
            or bid.request_id != r.id
            or bid.status != ExchangeBidStatus.SUBMITTED.value
        ):
            raise AppException(
                code="BID_NOT_FOUND", message="Bid not found.", status_code=404
            )
        # Re-validate stock and listing state at acceptance time.
        lines: list[tuple[uuid.UUID, int]] = []
        for line in bid.line_items:
            listing = await self._listing(uuid.UUID(line["listing_id"]))
            inv = listing.inventory
            avail = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            if not listing.is_active or avail < line["quantity"]:
                raise AppException(
                    code="BID_NO_LONGER_AVAILABLE",
                    message="The retailer no longer has stock for this bid.",
                    status_code=409,
                )
            await issue_award(
                self.session,
                customer_id=user_id,
                listing_id=listing.id,
                unit_price_paise=line["unit_price_paise"],
                max_quantity=line["quantity"],
                source="EXCHANGE",
                source_id=r.id,
                ttl=AWARD_TTL,
            )
            lines.append((listing.id, line["quantity"]))
        bid.status = ExchangeBidStatus.ACCEPTED.value
        await self.session.execute(
            update(ExchangeBid)
            .where(
                ExchangeBid.request_id == r.id,
                ExchangeBid.id != bid.id,
                ExchangeBid.status == ExchangeBidStatus.SUBMITTED.value,
            )
            .values(status=ExchangeBidStatus.REJECTED.value)
        )
        r.status = ExchangeRequestStatus.AWARDED.value
        r.accepted_bid_id = bid.id
        cart = await set_customer_cart_lines(self.session, user_id, lines)
        await enqueue_marketplace_event(
            self.session,
            event_type="exchange.bid_accepted",
            aggregate_type="exchange_request",
            aggregate_id=r.id,
            payload={
                "request_id": r.id,
                "bid_id": bid.id,
                "retailer_id": bid.retailer_id,
                "amount_paise": bid.bid_amount_paise,
            },
        )
        await self.session.flush()
        return r, cart, len(lines)

    # ----------------------------------------------------------- retailer
    async def _listing(self, listing_id: uuid.UUID) -> ProductListing:
        lst = (
            await self.session.execute(
                select(ProductListing)
                .options(
                    selectinload(ProductListing.inventory),
                    selectinload(ProductListing.variant).selectinload(
                        ProductVariant.product
                    ),
                )
                .where(ProductListing.id == listing_id)
            )
        ).scalar_one_or_none()
        if lst is None:
            raise AppException(
                code="LISTING_NOT_FOUND", message="Listing not found.", status_code=404
            )
        return lst

    async def submit_bid(
        self, request_id: uuid.UUID, retailer: Retailer, req
    ) -> ExchangeBid:
        if not retailer.is_active or retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message="Only verified retailers can bid.",
                status_code=403,
            )
        r = await self._locked_request(request_id)
        if r.status != ExchangeRequestStatus.BIDDING_OPEN.value:
            raise AppException(
                code="RFQ_CLOSED", message=f"Request is {r.status}.", status_code=409
            )
        if not retailer_serves(retailer.service_pincodes, r.delivery_pincode):
            raise AppException(
                code="PINCODE_NOT_SERVICED",
                message="Outside your service area.",
                status_code=403,
            )
        manifest = r.items_manifest
        seen: set[int] = set()
        lines: list[dict] = []
        total = 0
        for ln in req.lines:
            if ln.manifest_index >= len(manifest) or ln.manifest_index in seen:
                raise AppException(
                    code="INVALID_BID_LINE",
                    message="Each requested item may be quoted once.",
                    status_code=422,
                )
            seen.add(ln.manifest_index)
            listing = await self._listing(ln.listing_id)
            if listing.retailer_id != retailer.id or not listing.is_active:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Listing not found in your store catalogue.",
                    status_code=404,
                )
            qty = int(manifest[ln.manifest_index]["quantity"])
            inv = listing.inventory
            avail = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            if avail < qty:
                raise AppException(
                    code="INSUFFICIENT_STOCK",
                    message=f"Not enough stock for '{manifest[ln.manifest_index]['name']}'.",
                    status_code=409,
                )
            if ln.unit_price_paise > listing.selling_price_paise:
                raise AppException(
                    code="BID_ABOVE_LIST_PRICE",
                    message="Bid price cannot exceed your current listing price.",
                    status_code=422,
                )
            total += ln.unit_price_paise * qty
            lines.append(
                {
                    "manifest_index": ln.manifest_index,
                    "listing_id": str(listing.id),
                    "quantity": qty,
                    "unit_price_paise": ln.unit_price_paise,
                    "list_price_paise": int(listing.selling_price_paise),
                    "product_name": listing.variant.product.name,
                }
            )
        if r.budget_limit_paise is not None and total > r.budget_limit_paise:
            raise AppException(
                code="BID_OVER_BUDGET",
                message="Bid exceeds the customer's budget.",
                status_code=422,
            )
        bid = (
            await self.session.execute(
                select(ExchangeBid)
                .where(
                    ExchangeBid.request_id == r.id,
                    ExchangeBid.retailer_id == retailer.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if bid and bid.status not in (
            ExchangeBidStatus.SUBMITTED.value,
            ExchangeBidStatus.WITHDRAWN.value,
        ):
            raise AppException(
                code="BID_LOCKED",
                message="This bid can no longer be changed.",
                status_code=409,
            )
        if bid is None:
            bid = ExchangeBid(id=uuid.uuid4(), request_id=r.id, retailer_id=retailer.id)
            self.session.add(bid)
        bid.bid_amount_paise = total
        bid.estimated_delivery_hours = req.estimated_delivery_hours
        bid.notes = req.notes
        bid.line_items = lines
        bid.items_covered = len(lines)
        bid.status = ExchangeBidStatus.SUBMITTED.value
        notify_customer(
            self.session,
            customer_id=r.user_id,
            title="New offer on your request",
            message=f"{retailer.name} offered ₹{total / 100:.2f} for '{r.title}' ({len(lines)}/{len(manifest)} items).",
            event_type="EXCHANGE_BID_RECEIVED",
        )
        await enqueue_marketplace_event(
            self.session,
            event_type="exchange.bid_submitted",
            aggregate_type="exchange_request",
            aggregate_id=r.id,
            payload={
                "request_id": r.id,
                "bid_id": bid.id,
                "retailer_id": retailer.id,
                "amount_paise": total,
            },
        )
        await self.session.flush()
        return bid

    async def withdraw_bid(self, request_id: uuid.UUID, retailer: Retailer) -> None:
        r = await self._locked_request(request_id)
        bid = (
            await self.session.execute(
                select(ExchangeBid)
                .where(
                    ExchangeBid.request_id == r.id,
                    ExchangeBid.retailer_id == retailer.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if (
            bid is None
            or bid.status != ExchangeBidStatus.SUBMITTED.value
            or r.status != ExchangeRequestStatus.BIDDING_OPEN.value
        ):
            raise AppException(
                code="BID_NOT_FOUND",
                message="No open bid to withdraw.",
                status_code=404,
            )
        bid.status = ExchangeBidStatus.WITHDRAWN.value
        await self.session.flush()

    async def open_for_retailer(self, retailer: Retailer, *, limit: int, offset: int):
        conds = [
            ExchangeRequest.status == ExchangeRequestStatus.BIDDING_OPEN.value,
            ExchangeRequest.expires_at > datetime.now(UTC),
        ]
        served = list(retailer.service_pincodes or [])
        if served:
            conds.append(ExchangeRequest.delivery_pincode.in_(served))
        return await self._page(conds, limit, offset)

    async def _page(self, conds, limit, offset):
        total = (
            await self.session.execute(
                select(func.count()).select_from(ExchangeRequest).where(*conds)
            )
        ).scalar() or 0
        rows = (
            (
                await self.session.execute(
                    select(ExchangeRequest)
                    .where(*conds)
                    .order_by(ExchangeRequest.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def list_for_customer(self, user_id, limit, offset):
        return await self._page([ExchangeRequest.user_id == user_id], limit, offset)

    async def list_admin(self, status, limit, offset):
        conds = [ExchangeRequest.status == status] if status else []
        return await self._page(conds, limit, offset)

    # ----------------------------------------------------------- serialisation
    async def serialize(
        self, requests, *, include_bids: bool = False, retailer_id=None
    ) -> list[ExchangeRequestItem]:
        if not requests:
            return []
        ids = [r.id for r in requests]
        bids = (
            await self.session.execute(
                select(ExchangeBid, Retailer)
                .join(Retailer, Retailer.id == ExchangeBid.retailer_id)
                .where(
                    ExchangeBid.request_id.in_(ids),
                    ExchangeBid.status != ExchangeBidStatus.WITHDRAWN.value,
                )
                .order_by(ExchangeBid.bid_amount_paise.asc())
            )
        ).all()
        by_req: dict[uuid.UUID, list[BidItem]] = {}
        for b, ret in bids:
            req = next(r for r in requests if r.id == b.request_id)
            by_req.setdefault(b.request_id, []).append(
                BidItem(
                    id=b.id,
                    retailer_id=b.retailer_id,
                    retailer_name=ret.name,
                    retailer_rating=float(ret.rating),
                    bid_amount_paise=b.bid_amount_paise,
                    estimated_delivery_hours=b.estimated_delivery_hours,
                    items_covered=b.items_covered,
                    items_requested=len(req.items_manifest),
                    notes=b.notes,
                    status=b.status,
                    lines=[
                        BidLine(
                            manifest_index=ln["manifest_index"],
                            item_name=req.items_manifest[ln["manifest_index"]]["name"],
                            listing_id=uuid.UUID(ln["listing_id"]),
                            product_name=ln["product_name"],
                            quantity=ln["quantity"],
                            unit_price_paise=ln["unit_price_paise"],
                            list_price_paise=ln["list_price_paise"],
                            line_total_paise=ln["unit_price_paise"] * ln["quantity"],
                        )
                        for ln in b.line_items
                    ],
                    created_at=b.created_at,
                    updated_at=b.updated_at,
                )
            )
        out = []
        for r in requests:
            rb = by_req.get(r.id, [])
            out.append(
                ExchangeRequestItem(
                    id=r.id,
                    title=r.title,
                    delivery_pincode=r.delivery_pincode,
                    budget_limit_paise=r.budget_limit_paise,
                    items=[ManifestItem(**i) for i in r.items_manifest],
                    status=r.status,
                    accepted_bid_id=r.accepted_bid_id,
                    expires_at=r.expires_at,
                    created_at=r.created_at,
                    bid_count=len(rb),
                    bids=rb if include_bids else None,
                    my_bid=next((b for b in rb if b.retailer_id == retailer_id), None)
                    if retailer_id
                    else None,
                )
            )
        return out


async def expire_open_requests(session: AsyncSession) -> int:
    res = await session.execute(
        update(ExchangeRequest)
        .where(
            ExchangeRequest.status == ExchangeRequestStatus.BIDDING_OPEN.value,
            ExchangeRequest.expires_at <= datetime.now(UTC),
        )
        .values(status=ExchangeRequestStatus.EXPIRED.value)
    )
    return res.rowcount or 0
