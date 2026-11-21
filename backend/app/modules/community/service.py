"""Basket Community Buying / Group Purchasing (Phase 3B)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.events.marketplace_events import enqueue_marketplace_event
from app.core.exceptions import AppException
from app.core.notify import notify_customer
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
)
from app.modules.community.models import (
    GroupBuyCampaign,
    GroupBuyMember,
    GroupBuyMemberStatus,
    GroupBuyStatus,
    GroupBuyTemplate,
)
from app.modules.community.schemas import (
    CampaignItem,
    CustomerStartRequest,
    ShareResponse,
    TemplateItem,
    TemplateUpsertRequest,
)
from app.modules.identity.models import User
from app.modules.pricing.awards import issue_award

logger = logging.getLogger(__name__)
AWARD_TTL = timedelta(hours=48)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class CommunityBuyingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _listing(self, listing_id: uuid.UUID) -> ProductListing:
        listing = (
            await self.session.execute(
                select(ProductListing)
                .options(
                    selectinload(ProductListing.retailer),
                    selectinload(ProductListing.inventory),
                    selectinload(ProductListing.variant)
                    .selectinload(ProductVariant.product)
                    .selectinload(Product.images),
                )
                .where(ProductListing.id == listing_id)
            )
        ).scalar_one_or_none()
        if listing is None:
            raise AppException(
                code="LISTING_NOT_FOUND", message="Listing not found.", status_code=404
            )
        return listing

    async def create(
        self, *, req, actor_user_id: uuid.UUID, retailer: Retailer | None
    ) -> GroupBuyCampaign:
        listing = await self._listing(req.listing_id)
        if retailer is not None:
            if listing.retailer_id != retailer.id:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Listing not found in your store catalogue.",
                    status_code=404,
                )
            if not retailer.is_active or retailer.verification_status != "VERIFIED":
                raise AppException(
                    code="RETAILER_NOT_VERIFIED",
                    message="Only verified, active retailers can run group buys.",
                    status_code=403,
                )
        if not listing.is_active:
            raise AppException(
                code="LISTING_INACTIVE",
                message="Listing is not active.",
                status_code=409,
            )
        bps = int(round(req.discount_percent * 100))
        list_price = int(listing.selling_price_paise)
        group_price = list_price - (list_price * bps) // 10000
        if group_price <= 0:
            raise AppException(
                code="INVALID_DISCOUNT",
                message="Group price must stay above zero.",
                status_code=422,
            )
        c = GroupBuyCampaign(
            id=uuid.uuid4(),
            listing_id=listing.id,
            retailer_id=listing.retailer_id,
            created_by_user_id=actor_user_id,
            title=(req.title or f"Group buy: {listing.variant.product.name}")[:160],
            min_participants=req.min_participants,
            max_participants=req.max_participants,
            max_quantity_per_member=req.max_quantity_per_member,
            discount_bps=bps,
            list_price_paise=list_price,
            group_price_paise=group_price,
            status=GroupBuyStatus.OPEN.value,
            expires_at=datetime.now(UTC) + timedelta(hours=req.duration_hours),
        )
        self.session.add(c)
        await self.session.flush()
        await enqueue_marketplace_event(
            self.session,
            event_type="group_buy.created",
            aggregate_type="group_buy",
            aggregate_id=c.id,
            payload={
                "campaign_id": c.id,
                "listing_id": c.listing_id,
                "group_price_paise": group_price,
            },
        )
        return c

    async def _locked(self, campaign_id: uuid.UUID) -> GroupBuyCampaign:
        c = await self.session.get(GroupBuyCampaign, campaign_id, with_for_update=True)
        if c is None:
            raise AppException(
                code="CAMPAIGN_NOT_FOUND",
                message="Group buy not found.",
                status_code=404,
            )
        return c

    async def join(
        self, campaign_id: uuid.UUID, user_id: uuid.UUID, quantity: int
    ) -> GroupBuyCampaign:
        c = await self._locked(campaign_id)
        if c.status == GroupBuyStatus.OPEN.value and _aware(
            c.expires_at
        ) <= datetime.now(UTC):
            await self._settle(c)
        if c.status != GroupBuyStatus.OPEN.value:
            raise AppException(
                code="CAMPAIGN_CLOSED",
                message="This group buy is closed.",
                status_code=409,
            )
        if quantity > c.max_quantity_per_member:
            raise AppException(
                code="QUANTITY_LIMIT",
                message=f"At most {c.max_quantity_per_member} units per member.",
                status_code=422,
            )
        member = (
            await self.session.execute(
                select(GroupBuyMember).where(
                    GroupBuyMember.campaign_id == c.id,
                    GroupBuyMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if member and member.status == GroupBuyMemberStatus.JOINED.value:
            raise AppException(
                code="ALREADY_JOINED",
                message="You already joined this group.",
                status_code=409,
            )
        if c.current_participants >= c.max_participants:
            raise AppException(
                code="CAMPAIGN_FULL", message="This group is full.", status_code=409
            )
        listing = await self._listing(c.listing_id)
        inv = listing.inventory
        available = max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
        if not listing.is_active or available < c.total_quantity + quantity:
            raise AppException(
                code="INSUFFICIENT_STOCK",
                message="Not enough stock for the group at this quantity.",
                status_code=409,
            )
        if member:
            member.status = GroupBuyMemberStatus.JOINED.value
            member.quantity = quantity
        else:
            self.session.add(
                GroupBuyMember(
                    id=uuid.uuid4(),
                    campaign_id=c.id,
                    user_id=user_id,
                    quantity=quantity,
                )
            )
        c.current_participants += 1
        c.total_quantity += quantity
        await self.session.flush()
        if c.current_participants >= c.max_participants:
            await self._settle(c)
        return c

    async def leave(
        self, campaign_id: uuid.UUID, user_id: uuid.UUID
    ) -> GroupBuyCampaign:
        c = await self._locked(campaign_id)
        if c.status != GroupBuyStatus.OPEN.value:
            raise AppException(
                code="CAMPAIGN_CLOSED",
                message="This group buy is closed.",
                status_code=409,
            )
        member = (
            await self.session.execute(
                select(GroupBuyMember).where(
                    GroupBuyMember.campaign_id == c.id,
                    GroupBuyMember.user_id == user_id,
                    GroupBuyMember.status == GroupBuyMemberStatus.JOINED.value,
                )
            )
        ).scalar_one_or_none()
        if member is None:
            raise AppException(
                code="NOT_A_MEMBER",
                message="You are not in this group.",
                status_code=404,
            )
        member.status = GroupBuyMemberStatus.LEFT.value
        c.current_participants -= 1
        c.total_quantity -= member.quantity
        await self.session.flush()
        return c

    async def cancel(
        self, campaign_id: uuid.UUID, *, retailer: Retailer | None
    ) -> GroupBuyCampaign:
        c = await self._locked(campaign_id)
        if retailer is not None and c.retailer_id != retailer.id:
            raise AppException(
                code="CAMPAIGN_NOT_FOUND",
                message="Group buy not found.",
                status_code=404,
            )
        if c.status != GroupBuyStatus.OPEN.value:
            raise AppException(
                code="CAMPAIGN_CLOSED",
                message="Only open group buys can be cancelled.",
                status_code=409,
            )
        c.status = GroupBuyStatus.CANCELLED.value
        c.settled_at = datetime.now(UTC)
        for m in await self._active_members(c.id):
            m.status = GroupBuyMemberStatus.NOT_FULFILLED.value
            notify_customer(
                self.session,
                customer_id=m.user_id,
                title="Group buy cancelled",
                message=f"'{c.title}' was cancelled. You have not been charged.",
                event_type="GROUP_BUY_CANCELLED",
            )
        await enqueue_marketplace_event(
            self.session,
            event_type="group_buy.cancelled",
            aggregate_type="group_buy",
            aggregate_id=c.id,
            payload={"campaign_id": c.id},
        )
        await self.session.flush()
        return c

    async def _active_members(self, campaign_id: uuid.UUID) -> list[GroupBuyMember]:
        return list(
            (
                await self.session.execute(
                    select(GroupBuyMember).where(
                        GroupBuyMember.campaign_id == campaign_id,
                        GroupBuyMember.status == GroupBuyMemberStatus.JOINED.value,
                    )
                )
            ).scalars()
        )

    async def _settle(self, c: GroupBuyCampaign) -> None:
        """Close an OPEN campaign (caller holds the row lock)."""
        members = await self._active_members(c.id)
        now = datetime.now(UTC)
        c.settled_at = now
        if c.current_participants >= c.min_participants:
            c.status = GroupBuyStatus.SUCCESSFUL.value
            # Never award more units than the store can actually supply: allocate
            # in join order up to the stock available at settlement.
            listing = await self._listing(c.listing_id)
            inv = listing.inventory
            remaining = (
                max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            )
            members = sorted(members, key=lambda mm: mm.joined_at)
            unfulfilled = []
            allocated = []
            for m in members:
                if m.quantity <= remaining:
                    remaining -= m.quantity
                    allocated.append(m)
                else:
                    unfulfilled.append(m)
            for m in unfulfilled:
                m.status = GroupBuyMemberStatus.NOT_FULFILLED.value
                notify_customer(
                    self.session,
                    customer_id=m.user_id,
                    title="Group buy sold out",
                    message=f"'{c.title}' succeeded but the store ran out of stock before your turn. You have not been charged.",
                    event_type="GROUP_BUY_SOLD_OUT",
                )
            members = allocated
            for m in members:
                award = await issue_award(
                    self.session,
                    customer_id=m.user_id,
                    listing_id=c.listing_id,
                    unit_price_paise=c.group_price_paise,
                    max_quantity=m.quantity,
                    source="GROUP_BUY",
                    source_id=c.id,
                    ttl=AWARD_TTL,
                )
                await self.session.flush()
                m.award_id = award.id
                m.status = GroupBuyMemberStatus.AWARDED.value
                notify_customer(
                    self.session,
                    customer_id=m.user_id,
                    title="Group discount unlocked!",
                    message=(
                        f"'{c.title}' reached {c.current_participants} members. Add the item to your "
                        f"basket and check out within 48 hours to pay ₹{c.group_price_paise / 100:.2f} each."
                    ),
                    event_type="GROUP_BUY_SUCCEEDED",
                )
            event = "group_buy.succeeded"
        else:
            c.status = GroupBuyStatus.FAILED.value
            for m in members:
                m.status = GroupBuyMemberStatus.NOT_FULFILLED.value
                notify_customer(
                    self.session,
                    customer_id=m.user_id,
                    title="Group buy did not reach its target",
                    message=f"'{c.title}' needed {c.min_participants} members. You have not been charged.",
                    event_type="GROUP_BUY_FAILED",
                )
            event = "group_buy.failed"
        await enqueue_marketplace_event(
            self.session,
            event_type=event,
            aggregate_type="group_buy",
            aggregate_id=c.id,
            payload={
                "campaign_id": c.id,
                "participants": c.current_participants,
                "status": c.status,
            },
        )
        await self.session.flush()

    async def serialize(
        self, campaigns: list[GroupBuyCampaign], user_id: uuid.UUID | None = None
    ) -> list[CampaignItem]:
        if not campaigns:
            return []
        listings = {
            lst.id: lst
            for lst in (
                await self.session.execute(
                    select(ProductListing)
                    .options(
                        selectinload(ProductListing.retailer),
                        selectinload(ProductListing.variant)
                        .selectinload(ProductVariant.product)
                        .selectinload(Product.images),
                    )
                    .where(ProductListing.id.in_([c.listing_id for c in campaigns]))
                )
            ).scalars()
        }
        mine: dict[uuid.UUID, GroupBuyMember] = {}
        if user_id:
            for m in (
                await self.session.execute(
                    select(GroupBuyMember).where(
                        GroupBuyMember.user_id == user_id,
                        GroupBuyMember.campaign_id.in_([c.id for c in campaigns]),
                    )
                )
            ).scalars():
                mine[m.campaign_id] = m
        initials: dict[uuid.UUID, list[str]] = {}
        for cid, full_name in (
            await self.session.execute(
                select(GroupBuyMember.campaign_id, User.full_name)
                .join(User, User.id == GroupBuyMember.user_id)
                .where(
                    GroupBuyMember.campaign_id.in_([c.id for c in campaigns]),
                    GroupBuyMember.status.in_(
                        [
                            GroupBuyMemberStatus.JOINED.value,
                            GroupBuyMemberStatus.AWARDED.value,
                            GroupBuyMemberStatus.PURCHASED.value,
                        ]
                    ),
                )
                .order_by(GroupBuyMember.joined_at)
            )
        ).all():
            letter = (full_name or "?").strip()[:1].upper() or "?"
            initials.setdefault(cid, []).append(letter)
        now = datetime.now(UTC)
        out = []
        for c in campaigns:
            lst = listings[c.listing_id]
            product = lst.variant.product
            imgs = sorted(
                product.images or [], key=lambda i: (not i.is_primary, i.sort_order)
            )
            m = mine.get(c.id)
            out.append(
                CampaignItem(
                    id=c.id,
                    listing_id=c.listing_id,
                    retailer_id=c.retailer_id,
                    retailer_name=lst.retailer.name,
                    product_name=product.name,
                    image_url=imgs[0].url if imgs else None,
                    title=c.title,
                    min_participants=c.min_participants,
                    max_participants=c.max_participants,
                    current_participants=c.current_participants,
                    participants_needed=max(
                        0, c.min_participants - c.current_participants
                    ),
                    total_quantity=c.total_quantity,
                    max_quantity_per_member=c.max_quantity_per_member,
                    discount_percent=c.discount_bps / 100,
                    list_price_paise=c.list_price_paise,
                    group_price_paise=c.group_price_paise,
                    status=c.status,
                    expires_at=c.expires_at,
                    seconds_remaining=max(
                        0, int((_aware(c.expires_at) - now).total_seconds())
                    )
                    if c.status == "OPEN"
                    else 0,
                    started_by_customer=c.template_id is not None,
                    participant_initials=initials.get(c.id, []),
                    my_membership={
                        "status": m.status,
                        "quantity": m.quantity,
                        "order_id": str(m.order_id) if m.order_id else None,
                    }
                    if m
                    else None,
                )
            )
        return out

    async def list(
        self,
        *,
        status: str | None,
        retailer_id: uuid.UUID | None,
        limit: int,
        offset: int,
        public: bool = False,
    ):
        conds = []
        if public:
            # Only show campaigns from live, verified stores with active listings.
            conds.append(
                GroupBuyCampaign.listing_id.in_(
                    select(ProductListing.id)
                    .join(Retailer, Retailer.id == ProductListing.retailer_id)
                    .where(
                        ProductListing.is_active.is_(True),
                        Retailer.is_active.is_(True),
                        Retailer.verification_status == "VERIFIED",
                    )
                )
            )
        if status:
            conds.append(GroupBuyCampaign.status == status)
        if retailer_id:
            conds.append(GroupBuyCampaign.retailer_id == retailer_id)
        if status == "OPEN":
            conds.append(GroupBuyCampaign.expires_at > datetime.now(UTC))
        total = (
            await self.session.execute(
                select(func.count()).select_from(GroupBuyCampaign).where(*conds)
            )
        ).scalar() or 0
        rows = (
            (
                await self.session.execute(
                    select(GroupBuyCampaign)
                    .where(*conds)
                    .order_by(GroupBuyCampaign.expires_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    # ------------------------------------------------------------------ templates
    async def upsert_template(
        self, retailer: Retailer, req: TemplateUpsertRequest
    ) -> GroupBuyTemplate:
        if not retailer.is_active or retailer.verification_status != "VERIFIED":
            raise AppException(
                code="RETAILER_NOT_VERIFIED",
                message="Only verified, active retailers can offer group buys.",
                status_code=403,
            )
        listing = await self._listing(req.listing_id)
        if listing.retailer_id != retailer.id:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Listing not found in your store catalogue.",
                status_code=404,
            )
        if not listing.is_active:
            raise AppException(
                code="LISTING_INACTIVE",
                message="Listing is not active.",
                status_code=409,
            )
        for old in (
            await self.session.execute(
                select(GroupBuyTemplate)
                .where(
                    GroupBuyTemplate.listing_id == listing.id,
                    GroupBuyTemplate.is_active.is_(True),
                )
                .with_for_update()
            )
        ).scalars():
            old.is_active = False
        await self.session.flush()
        t = GroupBuyTemplate(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            listing_id=listing.id,
            min_participants=req.min_participants,
            max_participants=req.max_participants,
            discount_bps=int(round(req.discount_percent * 100)),
            duration_hours=req.duration_hours,
            max_quantity_per_member=req.max_quantity_per_member,
            max_open_campaigns=req.max_open_campaigns,
            is_active=True,
        )
        self.session.add(t)
        await self.session.flush()
        return t

    async def deactivate_template(
        self, template_id: uuid.UUID, retailer: Retailer
    ) -> GroupBuyTemplate:
        t = await self.session.get(GroupBuyTemplate, template_id, with_for_update=True)
        if t is None or t.retailer_id != retailer.id:
            raise AppException(
                code="TEMPLATE_NOT_FOUND",
                message="Template not found.",
                status_code=404,
            )
        t.is_active = False
        await self.session.flush()
        return t

    async def list_templates(
        self, *, retailer_id: uuid.UUID | None, public: bool
    ) -> list[GroupBuyTemplate]:
        stmt = select(GroupBuyTemplate).order_by(GroupBuyTemplate.created_at.desc())
        if retailer_id:
            stmt = stmt.where(GroupBuyTemplate.retailer_id == retailer_id)
        if public:
            stmt = stmt.where(
                GroupBuyTemplate.is_active.is_(True),
                GroupBuyTemplate.listing_id.in_(
                    select(ProductListing.id)
                    .join(Retailer, Retailer.id == ProductListing.retailer_id)
                    .where(
                        ProductListing.is_active.is_(True),
                        Retailer.is_active.is_(True),
                        Retailer.verification_status == "VERIFIED",
                    )
                ),
            )
        return list((await self.session.execute(stmt.limit(200))).scalars())

    async def serialize_templates(
        self, templates: list[GroupBuyTemplate]
    ) -> list[TemplateItem]:
        out: list[TemplateItem] = []
        for t in templates:
            lst = await self._listing(t.listing_id)
            product = lst.variant.product
            imgs = sorted(
                product.images or [], key=lambda i: (not i.is_primary, i.sort_order)
            )
            open_count = (
                await self.session.execute(
                    select(func.count())
                    .select_from(GroupBuyCampaign)
                    .where(
                        GroupBuyCampaign.template_id == t.id,
                        GroupBuyCampaign.status == GroupBuyStatus.OPEN.value,
                    )
                )
            ).scalar() or 0
            price = int(lst.selling_price_paise)
            out.append(
                TemplateItem(
                    id=t.id,
                    listing_id=t.listing_id,
                    retailer_id=t.retailer_id,
                    retailer_name=lst.retailer.name,
                    product_name=product.name,
                    image_url=imgs[0].url if imgs else None,
                    min_participants=t.min_participants,
                    max_participants=t.max_participants,
                    discount_percent=t.discount_bps / 100,
                    duration_hours=t.duration_hours,
                    max_quantity_per_member=t.max_quantity_per_member,
                    max_open_campaigns=t.max_open_campaigns,
                    open_campaigns=int(open_count),
                    list_price_paise=price,
                    group_price_paise=price - (price * t.discount_bps) // 10000,
                    is_active=t.is_active,
                )
            )
        return out

    async def start_by_customer(
        self, user_id: uuid.UUID, req: CustomerStartRequest
    ) -> GroupBuyCampaign:
        """A customer starts a group buy on retailer-published terms and joins it."""
        t = await self.session.get(
            GroupBuyTemplate, req.template_id, with_for_update=True
        )
        if t is None or not t.is_active:
            raise AppException(
                code="TEMPLATE_NOT_FOUND",
                message="This product is not open for customer group buys.",
                status_code=404,
            )
        open_q = (
            select(func.count())
            .select_from(GroupBuyCampaign)
            .where(
                GroupBuyCampaign.template_id == t.id,
                GroupBuyCampaign.status == GroupBuyStatus.OPEN.value,
            )
        )
        if ((await self.session.execute(open_q)).scalar() or 0) >= t.max_open_campaigns:
            raise AppException(
                code="TOO_MANY_OPEN_GROUPS",
                message="There are already open groups for this product — join one of them instead.",
                status_code=409,
            )
        mine = (
            await self.session.execute(
                open_q.where(GroupBuyCampaign.created_by_user_id == user_id)
            )
        ).scalar() or 0
        if mine:
            raise AppException(
                code="ALREADY_STARTED",
                message="You already have an open group for this product.",
                status_code=409,
            )
        if req.quantity > t.max_quantity_per_member:
            raise AppException(
                code="QUANTITY_LIMIT",
                message=f"At most {t.max_quantity_per_member} units per member.",
                status_code=422,
            )
        listing = await self._listing(t.listing_id)
        retailer = listing.retailer
        if (
            not listing.is_active
            or not retailer.is_active
            or retailer.verification_status != "VERIFIED"
        ):
            raise AppException(
                code="LISTING_INACTIVE",
                message="This product is currently unavailable.",
                status_code=409,
            )
        list_price = int(listing.selling_price_paise)
        c = GroupBuyCampaign(
            id=uuid.uuid4(),
            listing_id=listing.id,
            retailer_id=listing.retailer_id,
            created_by_user_id=user_id,
            template_id=t.id,
            title=(req.title or f"Group buy: {listing.variant.product.name}")[:160],
            min_participants=t.min_participants,
            max_participants=t.max_participants,
            max_quantity_per_member=t.max_quantity_per_member,
            discount_bps=t.discount_bps,
            list_price_paise=list_price,
            group_price_paise=list_price - (list_price * t.discount_bps) // 10000,
            status=GroupBuyStatus.OPEN.value,
            expires_at=datetime.now(UTC) + timedelta(hours=t.duration_hours),
        )
        self.session.add(c)
        await self.session.flush()
        await enqueue_marketplace_event(
            self.session,
            event_type="group_buy.created",
            aggregate_type="group_buy",
            aggregate_id=c.id,
            payload={
                "campaign_id": c.id,
                "listing_id": c.listing_id,
                "group_price_paise": c.group_price_paise,
                "started_by": "customer",
            },
        )
        return await self.join(c.id, user_id, req.quantity)

    async def get(self, campaign_id: uuid.UUID) -> GroupBuyCampaign:
        c = await self.session.get(GroupBuyCampaign, campaign_id)
        if c is None:
            raise AppException(
                code="CAMPAIGN_NOT_FOUND",
                message="Group buy not found.",
                status_code=404,
            )
        return c

    async def share(self, campaign_id: uuid.UUID, user_id: uuid.UUID) -> ShareResponse:
        c = await self.get(campaign_id)
        if c.status != GroupBuyStatus.OPEN.value:
            raise AppException(
                code="CAMPAIGN_CLOSED",
                message="This group buy is closed.",
                status_code=409,
            )
        url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/community-buying/{c.id}?ref={str(user_id)[:8]}"
        needed = max(0, c.min_participants - c.current_participants)
        msg = (
            f"Join my BASKET group buy '{c.title}' and pay ₹{c.group_price_paise / 100:.2f} "
            f"instead of ₹{c.list_price_paise / 100:.2f}"
            + (f" — {needed} more people needed!" if needed else "!")
            + f" {url}"
        )
        return ShareResponse(
            url=url,
            message=msg,
            whatsapp_url=f"https://wa.me/?text={quote(msg)}",
            sms_url=f"sms:?&body={quote(msg)}",
        )


async def settle_expired_campaigns(session: AsyncSession, limit: int = 50) -> int:
    ids = (
        (
            await session.execute(
                select(GroupBuyCampaign.id)
                .where(
                    GroupBuyCampaign.status == GroupBuyStatus.OPEN.value,
                    GroupBuyCampaign.expires_at <= datetime.now(UTC),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    svc = CommunityBuyingService(session)
    n = 0
    for cid in ids:
        c = await session.get(
            GroupBuyCampaign, cid, with_for_update=True, populate_existing=True
        )
        if c and c.status == GroupBuyStatus.OPEN.value:
            await svc._settle(c)
            n += 1
    return n
