"""Demand Gap & Unmet Demand Aggregation (Phase 3A)."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.events.marketplace_events import enqueue_marketplace_event
from app.core.exceptions import AppException
from app.core.notify import notify_customer
from app.core.pincode import retailer_serves
from app.modules.catalogue.models import ProductListing, ProductVariant, Retailer
from app.modules.demand.models import (
    DemandPool,
    DemandPoolResponse,
    DemandPoolStatus,
    DemandSignal,
)
from app.modules.demand.schemas import (
    DemandPoolItem,
    DemandPoolOffer,
    DemandTrendPoint,
    DemandTrendsResponse,
)

logger = logging.getLogger(__name__)

DEDUP_WINDOW = timedelta(hours=24)
POOL_EXPIRY_IDLE = timedelta(days=60)
_PUNCT = re.compile(r"[^\w\sऀ-ൿ]+", re.UNICODE)


def normalize_demand_text(text: str) -> str:
    from app.modules.i18n.service import normalize_query

    normalized, _, _ = normalize_query(text)
    cleaned = _PUNCT.sub(" ", normalized.casefold())
    return " ".join(cleaned.split())[:160]


def caller_identity(request: Request, user) -> tuple[uuid.UUID | None, str | None]:
    from app.modules.cart.dependencies import GUEST_CART_COOKIE_NAME

    if user is not None:
        return user.id, None
    token = request.cookies.get(GUEST_CART_COOKIE_NAME) or request.headers.get(
        "X-Guest-Cart-Token"
    )
    return None, (hashlib.sha256(token.encode()).hexdigest() if token else None)


class DemandService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------- signals
    async def record_signal(
        self,
        *,
        signal_type: str,
        query_text: str | None,
        listing_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        pincode: str | None = None,
        user_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        pool_id: uuid.UUID | None = None,
    ) -> tuple[DemandPool, bool]:
        display = (query_text or "").strip()
        if listing_id is not None:
            listing = (
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
            if listing is None:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Listing not found.",
                    status_code=404,
                )
            product = listing.variant.product
            display = display or product.name
            category_id = category_id or product.category_id
            if signal_type == "OUT_OF_STOCK":
                inv = listing.inventory
                available = (
                    max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
                )
                if listing.is_active and available > 0:
                    raise AppException(
                        code="LISTING_IN_STOCK",
                        message="This item is currently in stock.",
                        status_code=409,
                    )

        if pool_id is not None:
            pool = await self.session.get(DemandPool, pool_id, with_for_update=True)
            if pool is None or pool.status == DemandPoolStatus.EXPIRED.value:
                raise AppException(
                    code="DEMAND_POOL_NOT_FOUND",
                    message="Demand pool not found or expired.",
                    status_code=404,
                )
            display = display or pool.display_name
        else:
            normalized = normalize_demand_text(display)
            if len(normalized) < 2:
                raise AppException(
                    code="INVALID_DEMAND_QUERY",
                    message="Describe the product you are looking for.",
                    status_code=422,
                )
            pool = await self._get_or_create_open_pool(
                normalized, display[:160], category_id, pincode
            )

        now = datetime.now(UTC)
        identity_filter = None
        if user_id is not None:
            identity_filter = DemandSignal.user_id == user_id
        elif guest_token_hash is not None:
            identity_filter = DemandSignal.guest_token_hash == guest_token_hash

        # Guests can mint unlimited cart tokens, so only authenticated customers
        # count as unique shoppers (guests still add to total demand).
        if identity_filter is not None:
            recent = (
                await self.session.execute(
                    select(DemandSignal.id)
                    .where(
                        DemandSignal.pool_id == pool.id,
                        identity_filter,
                        DemandSignal.created_at >= now - DEDUP_WINDOW,
                    )
                    .limit(1)
                )
            ).first()
            if recent:
                return pool, True
            seen_before = (
                user_id is None
                or (
                    await self.session.execute(
                        select(DemandSignal.id)
                        .where(DemandSignal.pool_id == pool.id, identity_filter)
                        .limit(1)
                    )
                ).first()
            )
        else:
            seen_before = True  # anonymous signals never count as unique users

        self.session.add(
            DemandSignal(
                id=uuid.uuid4(),
                pool_id=pool.id,
                user_id=user_id,
                guest_token_hash=guest_token_hash if user_id is None else None,
                query_text=(query_text or display)[:200],
                category_id=category_id,
                listing_id=listing_id,
                pincode=pincode,
                signal_type=signal_type,
            )
        )
        pool.total_demand_count += 1
        pool.last_signal_at = now
        if not seen_before:
            pool.unique_users_count += 1
            if pool.unique_users_count == pool.visibility_threshold:
                await enqueue_marketplace_event(
                    self.session,
                    event_type="demand.pool_threshold_reached",
                    aggregate_type="demand_pool",
                    aggregate_id=pool.id,
                    payload={
                        "pool_id": pool.id,
                        "name": pool.normalized_product_name,
                        "unique_users": pool.unique_users_count,
                    },
                )
        await self.session.flush()
        return pool, False

    async def _get_or_create_open_pool(
        self, normalized: str, display: str, category_id, pincode
    ) -> DemandPool:
        stmt = (
            select(DemandPool)
            .where(
                DemandPool.normalized_product_name == normalized,
                DemandPool.status == DemandPoolStatus.OPEN.value,
                (DemandPool.pincode == pincode)
                if pincode
                else DemandPool.pincode.is_(None),
            )
            .with_for_update()
        )
        pool = (await self.session.execute(stmt)).scalar_one_or_none()
        if pool:
            return pool
        pool = DemandPool(
            id=uuid.uuid4(),
            normalized_product_name=normalized,
            display_name=display or normalized,
            category_id=category_id,
            pincode=pincode,
            visibility_threshold=settings.DEMAND_POOL_DEFAULT_THRESHOLD,
            last_signal_at=datetime.now(UTC),
            status=DemandPoolStatus.OPEN.value,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(pool)
                await self.session.flush()
        except IntegrityError:
            # Concurrent creation of the same OPEN pool: use the winner.
            return (await self.session.execute(stmt)).scalar_one()
        await enqueue_marketplace_event(
            self.session,
            event_type="demand.pool_created",
            aggregate_type="demand_pool",
            aggregate_id=pool.id,
            # No pincode: customer location is PII and the envelope rejects it.
            payload={"pool_id": pool.id, "name": normalized},
        )
        return pool

    # ------------------------------------------------------------- reads
    async def _offers(
        self, pool_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[DemandPoolOffer]]:
        if not pool_ids:
            return {}
        rows = (
            await self.session.execute(
                select(DemandPoolResponse, Retailer.name)
                .join(Retailer, Retailer.id == DemandPoolResponse.retailer_id)
                .where(DemandPoolResponse.pool_id.in_(pool_ids))
                .order_by(DemandPoolResponse.created_at.asc())
            )
        ).all()
        out: dict[uuid.UUID, list[DemandPoolOffer]] = {}
        for r, name in rows:
            out.setdefault(r.pool_id, []).append(
                DemandPoolOffer(
                    retailer_id=r.retailer_id,
                    retailer_name=name,
                    listing_id=r.listing_id,
                    offered_price_paise=r.offered_price_paise,
                    note=r.note,
                    created_at=r.created_at,
                )
            )
        return out

    async def serialize(
        self,
        pools: list[DemandPool],
        *,
        retailer_id: uuid.UUID | None = None,
        with_offers: bool = True,
    ) -> list[DemandPoolItem]:
        offers = await self._offers([p.id for p in pools]) if with_offers else {}
        items = []
        for p in pools:
            o = offers.get(p.id, [])
            items.append(
                DemandPoolItem(
                    id=p.id,
                    display_name=p.display_name,
                    normalized_product_name=p.normalized_product_name,
                    category_id=p.category_id,
                    pincode=p.pincode,
                    total_demand_count=p.total_demand_count,
                    unique_users_count=p.unique_users_count,
                    visibility_threshold=p.visibility_threshold,
                    status=p.status,
                    last_signal_at=p.last_signal_at,
                    fulfilled_at=p.fulfilled_at,
                    created_at=p.created_at,
                    offers=o,
                    responded_by_me=(
                        any(x.retailer_id == retailer_id for x in o)
                        if retailer_id
                        else None
                    ),
                )
            )
        return items

    async def search_pools(
        self, *, q: str | None, pincode: str | None, limit: int, offset: int
    ) -> tuple[list[DemandPool], int]:
        conds = [DemandPool.status == DemandPoolStatus.OPEN.value]
        if q:
            from app.modules.search.service import escape_like

            conds.append(
                DemandPool.normalized_product_name.ilike(
                    f"%{escape_like(normalize_demand_text(q))}%", escape="\\"
                )
            )
        if pincode:
            conds.append(
                or_(DemandPool.pincode == pincode, DemandPool.pincode.is_(None))
            )
        return await self._page(conds, limit, offset)

    async def _page(self, conds, limit, offset, order=None):
        total = (
            await self.session.execute(
                select(func.count()).select_from(DemandPool).where(and_(*conds))
            )
        ).scalar() or 0
        rows = (
            (
                await self.session.execute(
                    select(DemandPool)
                    .where(and_(*conds))
                    .order_by(
                        *(
                            order
                            or [
                                DemandPool.unique_users_count.desc(),
                                DemandPool.last_signal_at.desc(),
                            ]
                        )
                    )
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def my_pools(self, user_id: uuid.UUID) -> list[DemandPool]:
        sub = (
            select(DemandSignal.pool_id)
            .where(DemandSignal.user_id == user_id)
            .distinct()
        )
        return list(
            (
                await self.session.execute(
                    select(DemandPool)
                    .where(DemandPool.id.in_(sub))
                    .order_by(DemandPool.last_signal_at.desc())
                )
            ).scalars()
        )

    async def retailer_gaps(
        self,
        retailer: Retailer,
        *,
        pincode: str | None,
        category_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[DemandPool], int]:
        conds = [
            DemandPool.status.in_(
                [DemandPoolStatus.OPEN.value, DemandPoolStatus.FULFILLED.value]
            ),
            DemandPool.unique_users_count >= DemandPool.visibility_threshold,
        ]
        served = list(retailer.service_pincodes or [])
        if served:
            conds.append(
                or_(DemandPool.pincode.is_(None), DemandPool.pincode.in_(served))
            )
        if pincode:
            conds.append(DemandPool.pincode == pincode)
        if category_id:
            conds.append(DemandPool.category_id == category_id)
        return await self._page(conds, limit, offset)

    # ------------------------------------------------------------- retailer
    async def fulfill(
        self,
        retailer: Retailer,
        pool_id: uuid.UUID,
        listing_id: uuid.UUID,
        note: str | None,
    ) -> DemandPool:
        if not retailer.is_active or retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message="Only verified, active retailers can respond to demand.",
                status_code=403,
            )
        pool = await self.session.get(DemandPool, pool_id, with_for_update=True)
        if pool is None or pool.status == DemandPoolStatus.EXPIRED.value:
            raise AppException(
                code="DEMAND_POOL_NOT_FOUND",
                message="Demand pool not found.",
                status_code=404,
            )
        if pool.unique_users_count < pool.visibility_threshold:
            raise AppException(
                code="DEMAND_POOL_NOT_FOUND",
                message="Demand pool not found.",
                status_code=404,
            )
        if not retailer_serves(retailer.service_pincodes, pool.pincode):
            raise AppException(
                code="PINCODE_NOT_SERVICED",
                message="This demand is outside your service area.",
                status_code=403,
            )
        listing = await self.session.get(ProductListing, listing_id)
        if (
            listing is None
            or listing.retailer_id != retailer.id
            or not listing.is_active
        ):
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )
        existing = (
            await self.session.execute(
                select(DemandPoolResponse).where(
                    DemandPoolResponse.pool_id == pool.id,
                    DemandPoolResponse.retailer_id == retailer.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise AppException(
                code="ALREADY_RESPONDED",
                message="You have already responded to this demand.",
                status_code=409,
            )
        self.session.add(
            DemandPoolResponse(
                id=uuid.uuid4(),
                pool_id=pool.id,
                retailer_id=retailer.id,
                listing_id=listing.id,
                offered_price_paise=int(listing.selling_price_paise),
                note=note,
            )
        )
        now = datetime.now(UTC)
        if pool.status == DemandPoolStatus.OPEN.value:
            pool.status = DemandPoolStatus.FULFILLED.value
            pool.fulfilled_at = now
        user_ids = (
            (
                await self.session.execute(
                    select(DemandSignal.user_id)
                    .where(
                        DemandSignal.pool_id == pool.id,
                        DemandSignal.user_id.isnot(None),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for uid in user_ids:
            notify_customer(
                self.session,
                customer_id=uid,
                title="Now available near you",
                message=f"{retailer.name} now offers '{pool.display_name}' that you requested.",
                event_type="DEMAND_FULFILLED",
            )
        await enqueue_marketplace_event(
            self.session,
            event_type="demand.pool_fulfilled",
            aggregate_type="demand_pool",
            aggregate_id=pool.id,
            payload={
                "pool_id": pool.id,
                "retailer_id": retailer.id,
                "listing_id": listing.id,
                "notified_customers": len(user_ids),
            },
        )
        await self.session.flush()
        return pool

    # ------------------------------------------------------------- admin
    async def admin_list(self, *, status: str | None, limit: int, offset: int):
        conds = [DemandPool.status == status] if status else [DemandPool.id.isnot(None)]
        return await self._page(conds, limit, offset)

    async def admin_update(
        self, pool_id: uuid.UUID, *, status: str | None, threshold: int | None
    ) -> DemandPool:
        pool = await self.session.get(DemandPool, pool_id, with_for_update=True)
        if pool is None:
            raise AppException(
                code="DEMAND_POOL_NOT_FOUND",
                message="Demand pool not found.",
                status_code=404,
            )
        if threshold is not None:
            pool.visibility_threshold = threshold
        if status is not None and status != pool.status:
            if status == DemandPoolStatus.OPEN.value:
                clash = (
                    await self.session.execute(
                        select(DemandPool.id).where(
                            DemandPool.id != pool.id,
                            DemandPool.status == DemandPoolStatus.OPEN.value,
                            DemandPool.normalized_product_name
                            == pool.normalized_product_name,
                            (DemandPool.pincode == pool.pincode)
                            if pool.pincode
                            else DemandPool.pincode.is_(None),
                        )
                    )
                ).first()
                if clash:
                    raise AppException(
                        code="OPEN_POOL_EXISTS",
                        message="Another open pool already aggregates this demand.",
                        status_code=409,
                    )
            pool.status = status
        await self.session.flush()
        return pool

    async def trends(self, days: int = 30) -> DemandTrendsResponse:
        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date_trunc("day", DemandSignal.created_at)
        rows = (
            await self.session.execute(
                select(day, func.count())
                .where(DemandSignal.created_at >= since)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        week = datetime.now(UTC) - timedelta(days=7)
        top_ids = (
            await self.session.execute(
                select(DemandSignal.pool_id, func.count().label("n"))
                .where(DemandSignal.created_at >= week)
                .group_by(DemandSignal.pool_id)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()
        pools = []
        if top_ids:
            by_id = {
                p.id: p
                for p in (
                    await self.session.execute(
                        select(DemandPool).where(
                            DemandPool.id.in_([r[0] for r in top_ids])
                        )
                    )
                ).scalars()
            }
            pools = [by_id[r[0]] for r in top_ids if r[0] in by_id]
        return DemandTrendsResponse(
            daily=[
                DemandTrendPoint(
                    date=d.date()
                    if isinstance(d, datetime)
                    else date.fromisoformat(str(d)[:10]),
                    signals=n,
                )
                for d, n in rows
            ],
            top_pools=await self.serialize(pools, with_offers=False),
        )


async def expire_idle_pools(session: AsyncSession) -> int:
    from sqlalchemy import update

    res = await session.execute(
        update(DemandPool)
        .where(
            DemandPool.status == DemandPoolStatus.OPEN.value,
            DemandPool.last_signal_at < datetime.now(UTC) - POOL_EXPIRY_IDLE,
        )
        .values(status=DemandPoolStatus.EXPIRED.value)
    )
    return res.rowcount or 0
