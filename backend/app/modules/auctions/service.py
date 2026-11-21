"""Dukaan vs Dukaan: 90-second multi-retailer reverse auction (Phase 3E)."""

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
from app.modules.auctions.models import AuctionStatus, BasketAuction, BasketAuctionBid
from app.modules.auctions.schemas import (
    AuctionBidView,
    AuctionView,
    BidLadderEntry,
    SnapshotItem,
)
from app.modules.cart.integration import set_customer_cart_lines
from app.modules.cart.repository import CartRepository
from app.modules.catalogue.models import ProductListing, ProductVariant, Retailer
from app.modules.pricing.awards import issue_award

AUCTION_SECONDS = 90
AWARD_TTL = timedelta(minutes=30)


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AuctionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _close_if_ended(self, a: BasketAuction) -> None:
        if a.status == AuctionStatus.ACTIVE.value and _aware(a.ends_at) <= datetime.now(
            UTC
        ):
            n = (
                await self.session.execute(
                    select(func.count())
                    .select_from(BasketAuctionBid)
                    .where(BasketAuctionBid.auction_id == a.id)
                )
            ).scalar() or 0
            new_status = (
                AuctionStatus.COMPLETED.value if n else AuctionStatus.NO_BIDS.value
            )
            # Close atomically: when the job and a live view race, only the request
            # that actually flips the status emits the event and the notices.
            flipped = (
                await self.session.execute(
                    update(BasketAuction)
                    .where(
                        BasketAuction.id == a.id,
                        BasketAuction.status == AuctionStatus.ACTIVE.value,
                    )
                    .values(status=new_status)
                    .returning(BasketAuction.id)
                    .execution_options(synchronize_session=False)
                )
            ).scalar()
            await self.session.refresh(a, ["status"])
            if flipped is None:
                return
            await enqueue_marketplace_event(
                self.session,
                event_type="auction.closed",
                aggregate_type="basket_auction",
                aggregate_id=a.id,
                payload={"auction_id": a.id, "status": a.status, "bids": int(n)},
            )
            if n:
                from app.core.notify import notify_retailer_users

                bidders = (
                    await self.session.execute(
                        select(BasketAuctionBid.retailer_id)
                        .where(BasketAuctionBid.auction_id == a.id)
                        .distinct()
                    )
                ).scalars()
                await notify_retailer_users(
                    self.session,
                    retailer_ids=list(bidders),
                    title="Auction closed",
                    message=(
                        f"Bidding has ended for the basket in PIN {a.pincode}. "
                        "The shopper is now choosing a store."
                    ),
                    event_type="retailer.auction_closed",
                )
            await self.session.flush()

    # ----------------------------------------------------------- customer
    async def start(self, user_id: uuid.UUID, pincode: str) -> BasketAuction:
        active = (
            (
                await self.session.execute(
                    select(BasketAuction).where(
                        BasketAuction.user_id == user_id,
                        BasketAuction.status == AuctionStatus.ACTIVE.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        for a in active:
            await self._close_if_ended(a)
            if a.status == AuctionStatus.ACTIVE.value:
                raise AppException(
                    code="AUCTION_IN_PROGRESS",
                    message="You already have a live auction.",
                    status_code=409,
                )
        repo = CartRepository(self.session)
        cart = await repo.get_active_cart_by_customer_id(user_id)
        items = await repo.get_cart_items(cart.id) if cart else []
        if not cart or not items:
            raise AppException(
                code="EMPTY_CART",
                message="Add items to your basket first.",
                status_code=400,
            )
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
                    .where(ProductListing.id.in_([i.listing_id for i in items]))
                )
            ).scalars()
        }
        snapshot, total = [], 0
        for i in items:
            lst = listings[i.listing_id]
            snapshot.append(
                {
                    "variant_id": str(lst.variant_id),
                    "reference_listing_id": str(lst.id),
                    "product_name": lst.variant.product.name,
                    "variant_name": lst.variant.name,
                    "quantity": i.quantity,
                    "reference_unit_price_paise": int(lst.selling_price_paise),
                }
            )
            total += int(lst.selling_price_paise) * i.quantity
        now = datetime.now(UTC)
        a = BasketAuction(
            id=uuid.uuid4(),
            user_id=user_id,
            cart_id=cart.id,
            cart_snapshot=snapshot,
            reference_total_paise=total,
            pincode=pincode,
            duration_seconds=AUCTION_SECONDS,
            status=AuctionStatus.ACTIVE.value,
            starts_at=now,
            ends_at=now + timedelta(seconds=AUCTION_SECONDS),
        )
        self.session.add(a)
        await self.session.flush()
        await enqueue_marketplace_event(
            self.session,
            event_type="auction.started",
            aggregate_type="basket_auction",
            aggregate_id=a.id,
            payload={
                "auction_id": a.id,
                "items": len(snapshot),
                "ends_at": a.ends_at.isoformat(),
            },
        )
        from app.core.notify import notify_retailer_users

        # Only stores that serve the PIN *and* can supply every line are told.
        candidates = (
            (
                await self.session.execute(
                    select(Retailer).where(
                        Retailer.is_active.is_(True),
                        Retailer.verification_status == "VERIFIED",
                        Retailer.user_id.is_not(None),
                        Retailer.user_id != user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        eligible = [
            r.id
            for r in candidates
            if retailer_serves(r.service_pincodes, pincode)
            and await self._retailer_lines(a, r) is not None
        ]
        await notify_retailer_users(
            self.session,
            retailer_ids=eligible,
            title="New Dukaan vs Dukaan auction",
            message=(
                f"A basket of {len(snapshot)} item(s) in PIN {pincode} is open for bids "
                f"for {AUCTION_SECONDS // 60} minute(s). Open Auctions to bid."
            ),
            event_type="retailer.auction_started",
        )
        return a

    async def get_active_for_customer(self, user_id: uuid.UUID) -> BasketAuction | None:
        a = (
            await self.session.execute(
                select(BasketAuction)
                .where(
                    BasketAuction.user_id == user_id,
                    BasketAuction.status.in_(
                        [AuctionStatus.ACTIVE.value, AuctionStatus.COMPLETED.value]
                    ),
                )
                .order_by(
                    BasketAuction.starts_at.desc(), BasketAuction.created_at.desc()
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if a:
            await self._close_if_ended(a)
            if a.status not in (
                AuctionStatus.ACTIVE.value,
                AuctionStatus.COMPLETED.value,
            ):
                return None
        return a

    async def get_own(
        self, auction_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> BasketAuction:
        a = await self.session.get(BasketAuction, auction_id, with_for_update=lock)
        if a is None or a.user_id != user_id:
            raise AppException(
                code="AUCTION_NOT_FOUND", message="Auction not found.", status_code=404
            )
        await self._close_if_ended(a)
        return a

    async def cancel(self, auction_id: uuid.UUID, user_id: uuid.UUID) -> BasketAuction:
        a = await self.get_own(auction_id, user_id, lock=True)
        if a.status not in (
            AuctionStatus.ACTIVE.value,
            AuctionStatus.COMPLETED.value,
            AuctionStatus.NO_BIDS.value,
        ):
            raise AppException(
                code="AUCTION_CLOSED",
                message=f"Auction is {a.status}.",
                status_code=409,
            )
        a.status = AuctionStatus.CANCELLED.value
        await self.session.flush()
        return a

    async def accept(
        self, auction_id: uuid.UUID, user_id: uuid.UUID, bid_id: uuid.UUID
    ):
        a = await self.get_own(auction_id, user_id, lock=True)
        if a.status == AuctionStatus.ACTIVE.value:
            raise AppException(
                code="AUCTION_STILL_LIVE",
                message="Wait for the auction to finish.",
                status_code=409,
            )
        if a.status != AuctionStatus.COMPLETED.value:
            raise AppException(
                code="AUCTION_CLOSED",
                message=f"Auction is {a.status}.",
                status_code=409,
            )
        bid = await self.session.get(BasketAuctionBid, bid_id)
        if bid is None or bid.auction_id != a.id:
            raise AppException(
                code="BID_NOT_FOUND", message="Bid not found.", status_code=404
            )
        is_sim = bool(
            getattr(bid, "is_simulated", False)
            or (
                isinstance(bid.line_allocation, list)
                and any(
                    isinstance(ln, dict) and ln.get("is_simulated")
                    for ln in bid.line_allocation
                )
            )
        )
        if is_sim:
            a.status = AuctionStatus.AWARDED.value
            a.winning_bid_id = bid.id
            from app.core.notify import notify_retailer_users

            await notify_retailer_users(
                self.session,
                retailer_ids=[bid.retailer_id],
                title="You won the auction (Demo Simulation)",
                message=(f"The shopper in PIN {a.pincode} chose your simulated bid."),
                event_type="retailer.auction_won",
            )
            others = (
                await self.session.execute(
                    select(BasketAuctionBid.retailer_id)
                    .where(
                        BasketAuctionBid.auction_id == a.id,
                        BasketAuctionBid.retailer_id != bid.retailer_id,
                    )
                    .distinct()
                )
            ).scalars()
            await notify_retailer_users(
                self.session,
                retailer_ids=list(others),
                title="Auction result: not selected",
                message=f"The shopper in PIN {a.pincode} chose another store's bid.",
                event_type="retailer.auction_lost",
            )
            await enqueue_marketplace_event(
                self.session,
                event_type="auction.awarded",
                aggregate_type="basket_auction",
                aggregate_id=a.id,
                payload={
                    "auction_id": a.id,
                    "bid_id": bid.id,
                    "retailer_id": bid.retailer_id,
                    "price_paise": bid.bid_price_paise,
                    "is_simulated": True,
                },
            )
            repo = CartRepository(self.session)
            cart = await repo.get_active_cart_by_customer_id(user_id)
            await self.session.flush()
            a.winning_bid_is_simulated = True
            return a, cart

        lines = bid.line_allocation
        list_total = sum(ln["list_unit_price_paise"] * ln["quantity"] for ln in lines)
        # Allocate the bid across lines in proportion to the retailer's list prices.
        new_lines: list[tuple[uuid.UUID, int]] = []
        for ln in lines:
            unit = max(
                1, (ln["list_unit_price_paise"] * bid.bid_price_paise) // list_total
            )
            listing = await self.session.get(
                ProductListing, uuid.UUID(ln["listing_id"])
            )
            if listing is None or not listing.is_active:
                raise AppException(
                    code="BID_NO_LONGER_AVAILABLE",
                    message="The winning store's listing is unavailable.",
                    status_code=409,
                )
            if unit < listing.selling_price_paise:
                await issue_award(
                    self.session,
                    customer_id=user_id,
                    listing_id=listing.id,
                    unit_price_paise=unit,
                    max_quantity=ln["quantity"],
                    source="AUCTION",
                    source_id=a.id,
                    ttl=AWARD_TTL,
                )
            new_lines.append((listing.id, ln["quantity"]))
        a.status = AuctionStatus.AWARDED.value
        a.winning_bid_id = bid.id
        from app.core.notify import notify_retailer_users

        await notify_retailer_users(
            self.session,
            retailer_ids=[bid.retailer_id],
            title="You won the auction",
            message=(
                f"The shopper in PIN {a.pincode} chose your bid. "
                "Watch Orders for their checkout."
            ),
            event_type="retailer.auction_won",
        )
        others = (
            await self.session.execute(
                select(BasketAuctionBid.retailer_id)
                .where(
                    BasketAuctionBid.auction_id == a.id,
                    BasketAuctionBid.retailer_id != bid.retailer_id,
                )
                .distinct()
            )
        ).scalars()
        await notify_retailer_users(
            self.session,
            retailer_ids=list(others),
            title="Auction result: not selected",
            message=f"The shopper in PIN {a.pincode} chose another store's bid.",
            event_type="retailer.auction_lost",
        )
        cart = await set_customer_cart_lines(
            self.session,
            user_id,
            new_lines,
            remove_listing_ids=[
                uuid.UUID(s["reference_listing_id"]) for s in a.cart_snapshot
            ],
        )
        await enqueue_marketplace_event(
            self.session,
            event_type="auction.awarded",
            aggregate_type="basket_auction",
            aggregate_id=a.id,
            payload={
                "auction_id": a.id,
                "bid_id": bid.id,
                "retailer_id": bid.retailer_id,
                "price_paise": bid.bid_price_paise,
            },
        )
        await self.session.flush()
        return a, cart

    # ----------------------------------------------------------- retailer
    async def _retailer_lines(
        self, a: BasketAuction, retailer: Retailer
    ) -> list[dict] | None:
        variant_ids = [uuid.UUID(s["variant_id"]) for s in a.cart_snapshot]
        listings = (
            (
                await self.session.execute(
                    select(ProductListing)
                    .options(selectinload(ProductListing.inventory))
                    .where(
                        ProductListing.retailer_id == retailer.id,
                        ProductListing.variant_id.in_(variant_ids),
                        ProductListing.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_variant = {lst.variant_id: lst for lst in listings}
        lines = []
        for s in a.cart_snapshot:
            lst = by_variant.get(uuid.UUID(s["variant_id"]))
            inv = lst.inventory if lst else None
            avail = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            if lst is None or avail < s["quantity"]:
                return None
            lines.append(
                {
                    "variant_id": s["variant_id"],
                    "listing_id": str(lst.id),
                    "quantity": s["quantity"],
                    "list_unit_price_paise": int(lst.selling_price_paise),
                }
            )
        return lines

    async def open_for_retailer(
        self, retailer: Retailer
    ) -> list[tuple[BasketAuction, list[dict]]]:
        now = datetime.now(UTC)
        conds = [
            BasketAuction.status == AuctionStatus.ACTIVE.value,
            BasketAuction.ends_at > now,
        ]
        served = list(retailer.service_pincodes or [])
        if served:
            conds.append(BasketAuction.pincode.in_(served))
        rows = (
            (
                await self.session.execute(
                    select(BasketAuction)
                    .where(*conds)
                    .order_by(BasketAuction.ends_at.asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        out = []
        for a in rows:
            if a.user_id == retailer.user_id:
                continue
            lines = await self._retailer_lines(a, retailer)
            if lines is not None:
                out.append((a, lines))
        return out

    async def bid(
        self, auction_id: uuid.UUID, retailer: Retailer, req
    ) -> BasketAuctionBid:
        if not retailer.is_active or retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message="Only verified retailers can bid.",
                status_code=403,
            )
        a = await self.session.get(BasketAuction, auction_id, with_for_update=True)
        if a is None:
            raise AppException(
                code="AUCTION_NOT_FOUND", message="Auction not found.", status_code=404
            )
        await self._close_if_ended(a)
        if a.status != AuctionStatus.ACTIVE.value:
            raise AppException(
                code="AUCTION_CLOSED", message="Bidding has closed.", status_code=409
            )
        if not retailer_serves(retailer.service_pincodes, a.pincode):
            raise AppException(
                code="PINCODE_NOT_SERVICED",
                message="Outside your service area.",
                status_code=403,
            )
        lines = await self._retailer_lines(a, retailer)
        if lines is None:
            raise AppException(
                code="CANNOT_FULFIL_BASKET",
                message="You must stock every item in the basket.",
                status_code=422,
            )
        own_total = sum(ln["list_unit_price_paise"] * ln["quantity"] for ln in lines)
        if req.bid_price_paise > own_total:
            raise AppException(
                code="BID_ABOVE_LIST_PRICE",
                message="Bid cannot exceed your listed basket total.",
                status_code=422,
            )
        prev = (
            await self.session.execute(
                select(func.min(BasketAuctionBid.bid_price_paise)).where(
                    BasketAuctionBid.auction_id == a.id,
                    BasketAuctionBid.retailer_id == retailer.id,
                )
            )
        ).scalar()
        if prev is not None and req.bid_price_paise >= prev:
            raise AppException(
                code="BID_NOT_LOWER",
                message="Each new bid must be lower than your previous bid.",
                status_code=422,
            )
        b = BasketAuctionBid(
            id=uuid.uuid4(),
            auction_id=a.id,
            retailer_id=retailer.id,
            bid_price_paise=req.bid_price_paise,
            delivery_eta_minutes=req.delivery_eta_minutes,
            warranty_note=req.warranty_note,
            line_allocation=lines,
        )
        self.session.add(b)
        await enqueue_marketplace_event(
            self.session,
            event_type="auction.bid_placed",
            aggregate_type="basket_auction",
            aggregate_id=a.id,
            payload={
                "auction_id": a.id,
                "bid_id": b.id,
                "retailer_id": retailer.id,
                "price_paise": req.bid_price_paise,
            },
        )
        await self.session.flush()
        return b

    async def simulate_bid(
        self, auction_id: uuid.UUID, retailer: Retailer
    ) -> BasketAuctionBid:
        if not retailer.is_active or retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message="Only verified retailers can bid.",
                status_code=403,
            )
        a = await self.session.get(BasketAuction, auction_id, with_for_update=True)
        if a is None:
            raise AppException(
                code="AUCTION_NOT_FOUND", message="Auction not found.", status_code=404
            )
        await self._close_if_ended(a)
        if a.status != AuctionStatus.ACTIVE.value:
            raise AppException(
                code="AUCTION_CLOSED", message="Bidding has closed.", status_code=409
            )

        current_best = (
            await self.session.execute(
                select(func.min(BasketAuctionBid.bid_price_paise)).where(
                    BasketAuctionBid.auction_id == a.id
                )
            )
        ).scalar()
        base_price = (
            current_best if current_best is not None else a.reference_total_paise
        )

        prev = (
            await self.session.execute(
                select(func.min(BasketAuctionBid.bid_price_paise)).where(
                    BasketAuctionBid.auction_id == a.id,
                    BasketAuctionBid.retailer_id == retailer.id,
                )
            )
        ).scalar()

        # Competitive simulated undercut: ~4% to 8% below base
        drop = max(5000, int(base_price * 0.05))
        sim_price = max(1000, base_price - drop)
        if prev is not None and sim_price >= prev:
            sim_price = max(1000, prev - 2000)

        lines = await self._retailer_lines(a, retailer)
        if lines is None:
            lines = [
                {
                    "variant_id": s["variant_id"],
                    "listing_id": s.get("reference_listing_id", str(uuid.uuid4())),
                    "quantity": s["quantity"],
                    "list_unit_price_paise": s.get("reference_unit_price_paise", 0),
                    "is_simulated": True,
                }
                for s in a.cart_snapshot
            ]
        else:
            for ln in lines:
                ln["is_simulated"] = True

        b = BasketAuctionBid(
            id=uuid.uuid4(),
            auction_id=a.id,
            retailer_id=retailer.id,
            bid_price_paise=sim_price,
            delivery_eta_minutes=25,
            warranty_note="[SIMULATED] Demo Offer · 7-day replacement",
            line_allocation=lines,
            is_simulated=True,
        )
        self.session.add(b)
        await enqueue_marketplace_event(
            self.session,
            event_type="auction.bid_placed",
            aggregate_type="basket_auction",
            aggregate_id=a.id,
            payload={
                "auction_id": a.id,
                "bid_id": b.id,
                "retailer_id": retailer.id,
                "price_paise": sim_price,
                "is_simulated": True,
            },
        )
        await self.session.flush()
        return b

    # ----------------------------------------------------------- views
    async def view(
        self,
        a: BasketAuction,
        *,
        include_bids: bool,
        retailer: Retailer | None = None,
        retailer_lines: list[dict] | None = None,
    ) -> AuctionView:
        rows = (
            await self.session.execute(
                select(BasketAuctionBid, Retailer)
                .join(Retailer, Retailer.id == BasketAuctionBid.retailer_id)
                .where(BasketAuctionBid.auction_id == a.id)
                .order_by(
                    BasketAuctionBid.bid_price_paise.asc(),
                    BasketAuctionBid.delivery_eta_minutes.asc(),
                    BasketAuctionBid.created_at.asc(),
                )
            )
        ).all()
        best_per_retailer: dict[uuid.UUID, tuple] = {}
        for b, r in rows:
            best_per_retailer.setdefault(b.retailer_id, (b, r))
        ranked = list(best_per_retailer.values())
        now = datetime.now(UTC)
        return AuctionView(
            id=a.id,
            status=a.status,
            pincode=a.pincode,
            items=[
                SnapshotItem(
                    variant_id=uuid.UUID(s["variant_id"]),
                    product_name=s["product_name"],
                    variant_name=s["variant_name"],
                    quantity=s["quantity"],
                    reference_unit_price_paise=s["reference_unit_price_paise"],
                )
                for s in a.cart_snapshot
            ],
            reference_total_paise=a.reference_total_paise,
            duration_seconds=a.duration_seconds,
            starts_at=a.starts_at,
            ends_at=a.ends_at,
            seconds_remaining=max(0, int((_aware(a.ends_at) - now).total_seconds()))
            if a.status == "ACTIVE"
            else 0,
            bid_count=len(rows),
            best_bid_paise=ranked[0][0].bid_price_paise if ranked else None,
            winning_bid_id=a.winning_bid_id,
            bids=[
                AuctionBidView(
                    id=b.id,
                    rank=i + 1,
                    retailer_id=b.retailer_id,
                    retailer_name=r.name,
                    retailer_rating=float(r.rating),
                    bid_price_paise=b.bid_price_paise,
                    savings_paise=a.reference_total_paise - b.bid_price_paise,
                    delivery_eta_minutes=b.delivery_eta_minutes,
                    warranty_note=b.warranty_note,
                    is_simulated=bool(
                        getattr(b, "is_simulated", False)
                        or (
                            isinstance(b.line_allocation, list)
                            and any(
                                isinstance(ln, dict) and ln.get("is_simulated")
                                for ln in b.line_allocation
                            )
                        )
                    ),
                    created_at=b.created_at,
                )
                for i, (b, r) in enumerate(ranked)
            ]
            if include_bids
            else None,
            my_best_bid_paise=(
                best_per_retailer[retailer.id][0].bid_price_paise
                if retailer and retailer.id in best_per_retailer
                else None
            ),
            my_list_total_paise=(
                sum(
                    ln["list_unit_price_paise"] * ln["quantity"]
                    for ln in retailer_lines
                )
                if retailer_lines
                else None
            ),
            **(self._retailer_extras(a, rows, ranked, retailer) if retailer else {}),
        )

    @staticmethod
    def _retailer_extras(a, rows, ranked, retailer) -> dict:
        """Position, outbid state, anonymised price ladder and outcome for one store."""
        mine = retailer.id
        rank = next(
            (i + 1 for i, (b, _r) in enumerate(ranked) if b.retailer_id == mine), None
        )
        ladder = sorted(rows, key=lambda br: br[0].created_at)
        winner_retailer = next(
            (b.retailer_id for b, _r in rows if b.id == a.winning_bid_id), None
        )
        bid_any = rank is not None
        outcome = None
        if a.status == AuctionStatus.AWARDED.value and bid_any:
            outcome = "WON" if winner_retailer == mine else "NOT_SELECTED"
        elif a.status == AuctionStatus.COMPLETED.value and bid_any:
            outcome = "AWAITING_CHOICE"
        elif a.status in (
            AuctionStatus.NO_BIDS.value,
            AuctionStatus.CANCELLED.value,
        ) or (a.status == AuctionStatus.AWARDED.value and not bid_any):
            outcome = "CLOSED"
        return {
            "my_rank": rank,
            "competing_stores": len(ranked),
            "is_winning": rank == 1,
            "outbid": bool(bid_any and rank != 1),
            "bid_ladder": [
                BidLadderEntry(
                    price_paise=b.bid_price_paise,
                    at=b.created_at,
                    mine=b.retailer_id == mine,
                )
                for b, _r in ladder
            ],
            "my_outcome": outcome,
        }

    async def recent_for_retailer(
        self, retailer: Retailer, hours: int = 24
    ) -> list[BasketAuction]:
        """Auctions this store bid in whose bidding has ended (for outcomes)."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        rows = (
            (
                await self.session.execute(
                    select(BasketAuction)
                    .where(
                        BasketAuction.ends_at > since,
                        BasketAuction.id.in_(
                            select(BasketAuctionBid.auction_id).where(
                                BasketAuctionBid.retailer_id == retailer.id
                            )
                        ),
                    )
                    .order_by(BasketAuction.ends_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        out = []
        for a in rows:
            await self._close_if_ended(a)
            if a.status != AuctionStatus.ACTIVE.value:
                out.append(a)
        return out

    async def list_admin(self, status, limit, offset):
        conds = [BasketAuction.status == status] if status else []
        total = (
            await self.session.execute(
                select(func.count()).select_from(BasketAuction).where(*conds)
            )
        ).scalar() or 0
        rows = (
            (
                await self.session.execute(
                    select(BasketAuction)
                    .where(*conds)
                    .order_by(BasketAuction.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total


async def close_ended_auctions(session: AsyncSession) -> int:
    # Claim ended auctions with FOR UPDATE SKIP LOCKED: rows another worker (or a
    # customer request) is closing right now are left for the next cycle.
    ids = (
        (
            await session.execute(
                select(BasketAuction.id)
                .where(
                    BasketAuction.status == AuctionStatus.ACTIVE.value,
                    BasketAuction.ends_at <= datetime.now(UTC),
                )
                .limit(200)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    svc = AuctionService(session)
    for aid in ids:
        a = await session.get(
            BasketAuction, aid, with_for_update=True, populate_existing=True
        )
        if a is None or a.status != AuctionStatus.ACTIVE.value:
            continue  # already closed elsewhere: do not notify twice
        await svc._close_if_ended(a)
        # Only this run's ACTIVE → COMPLETED transition notifies the customer.
        if a.status == AuctionStatus.COMPLETED.value:
            notify_customer(
                session,
                customer_id=a.user_id,
                title="Your Dukaan vs Dukaan auction ended",
                message="Shops have bid on your basket. Choose the best offer.",
                event_type="AUCTION_COMPLETED",
            )
    return len(ids)
