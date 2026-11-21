"""Basket Monthly Essentials (final cycle, Part 8).

Scheduling and a safe pre-order check only. This module never creates an order
and never charges anyone: before each scheduled date the customer gets an in-app
notice with the checked basket (current price, stock, live offers, delivery),
loads it into the cart and checks out through the normal flow. Automatic
payment needs an approved provider mandate and is not implemented.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.notify import notify_customer
from app.core.pincode import retailer_serves
from app.modules.cart.models import CartItem
from app.modules.cart.repository import CartRepository
from app.modules.catalogue.models import ProductListing, ProductVariant
from app.modules.identity.models import Address
from app.modules.recurring.models import RecurringBasket, RecurringBasketRun
from app.modules.recurring.schemas import (
    CheckLine,
    LoadToCartResult,
    PreOrderCheck,
    RecurringBasketCreate,
    RecurringBasketOut,
    RecurringBasketUpdate,
    RecurringItem,
    RecurringRun,
)

PREPARE_DAYS_AHEAD = 1  # pre-order check and notice one day before the date


def _occurrence(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def next_occurrence(b: RecurringBasket, today: date) -> date | None:
    """First scheduled date on/after max(today, start) that is not skipped and
    not after the end date."""
    start = max(today, b.start_date)
    skips = set(b.skip_dates or [])
    y, m = start.year, start.month
    for _ in range(36):
        d = _occurrence(y, m, b.day_of_month)
        if d >= start and d.isoformat() not in skips:
            if b.end_date is not None and d > b.end_date:
                return None
            return d
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return None


class RecurringBasketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------ helpers
    async def _own(self, customer_id, basket_id) -> RecurringBasket:
        b = await self.session.get(RecurringBasket, basket_id)
        if b is None or b.customer_id != customer_id:
            raise AppException(
                code="RECURRING_BASKET_NOT_FOUND",
                message="Recurring basket not found.",
                status_code=404,
            )
        return b

    async def _check_address(self, customer_id, address_id) -> None:
        if address_id is None:
            return
        a = await self.session.get(Address, address_id)
        if a is None or a.user_id != customer_id:
            raise AppException(
                code="ADDRESS_NOT_FOUND", message="Address not found.", status_code=404
            )

    async def _out(self, b: RecurringBasket) -> RecurringBasketOut:
        runs = (
            (
                await self.session.execute(
                    select(RecurringBasketRun)
                    .where(RecurringBasketRun.recurring_basket_id == b.id)
                    .order_by(RecurringBasketRun.scheduled_for.desc())
                    .limit(6)
                )
            )
            .scalars()
            .all()
        )
        return RecurringBasketOut(
            id=b.id,
            name=b.name,
            status=b.status,
            day_of_month=b.day_of_month,
            start_date=b.start_date,
            end_date=b.end_date,
            next_run_date=b.next_run_date,
            skip_dates=[date.fromisoformat(d) for d in (b.skip_dates or [])],
            delivery_address_id=b.delivery_address_id,
            items=[RecurringItem(**i) for i in b.items],
            recent_runs=[
                RecurringRun(
                    scheduled_for=r.scheduled_for,
                    status=r.status,
                    items_total_paise=(r.check or {}).get("items_total_paise"),
                    changes=len((r.check or {}).get("changes", [])),
                    created_at=r.created_at,
                )
                for r in runs
            ],
            created_at=b.created_at,
        )

    def _reschedule(self, b: RecurringBasket, today: date | None = None) -> None:
        if b.status in ("CANCELLED", "ENDED"):
            b.next_run_date = None
            return
        nxt = next_occurrence(b, today or date.today())
        b.next_run_date = nxt
        if nxt is None and b.status == "ACTIVE":
            b.status = "ENDED"

    async def _flush_out(self, b: RecurringBasket) -> RecurringBasketOut:
        await self.session.flush()
        await self.session.refresh(b)
        return await self._out(b)

    # ------------------------------------------------------------ create / edit
    async def create_from_cart(
        self, customer_id: uuid.UUID, req: RecurringBasketCreate
    ) -> RecurringBasketOut:
        await self._check_address(customer_id, req.delivery_address_id)
        cart = await CartRepository(self.session).get_active_cart_by_customer_id(
            customer_id
        )
        lines = []
        if cart is not None:
            lines = (
                (
                    await self.session.execute(
                        select(CartItem).where(CartItem.cart_id == cart.id)
                    )
                )
                .scalars()
                .all()
            )
        if not lines:
            raise AppException(
                code="CART_EMPTY",
                message="Add the items you buy every month to your cart first.",
                status_code=422,
            )
        listings = await self._listings([ln.listing_id for ln in lines])
        items = []
        for ln in lines:
            lst = listings.get(ln.listing_id)
            if lst is None:
                continue
            items.append(
                RecurringItem(
                    listing_id=lst.id,
                    quantity=ln.quantity,
                    product_name=lst.variant.product.name,
                    variant_name=lst.variant.name,
                    retailer_name=lst.retailer.name,
                    unit_price_paise_at_setup=int(lst.selling_price_paise),
                ).model_dump(mode="json")
            )
        b = RecurringBasket(
            id=uuid.uuid4(),
            customer_id=customer_id,
            name=req.name.strip(),
            items=items,
            day_of_month=req.day_of_month,
            start_date=req.start_date,
            end_date=req.end_date,
            delivery_address_id=req.delivery_address_id,
            status="ACTIVE",
            skip_dates=[],
        )
        self._reschedule(b)
        self.session.add(b)
        return await self._flush_out(b)

    async def update(self, customer_id, basket_id, req: RecurringBasketUpdate):
        b = await self._own(customer_id, basket_id)
        if b.status == "CANCELLED":
            raise AppException(
                code="RECURRING_BASKET_CANCELLED",
                message="This recurring basket was cancelled.",
                status_code=409,
            )
        if req.name is not None:
            b.name = req.name.strip()
        if req.day_of_month is not None:
            b.day_of_month = req.day_of_month
        if req.start_date is not None:
            b.start_date = req.start_date
        if req.clear_end_date:
            b.end_date = None
        elif req.end_date is not None:
            b.end_date = req.end_date
        if b.end_date is not None and b.end_date < b.start_date:
            raise AppException(
                code="INVALID_SCHEDULE",
                message="End date must be on or after the start date.",
                status_code=422,
            )
        if req.delivery_address_id is not None:
            await self._check_address(customer_id, req.delivery_address_id)
            b.delivery_address_id = req.delivery_address_id
        if req.quantities:
            items = []
            for it in b.items:
                q = req.quantities.get(uuid.UUID(it["listing_id"]), it["quantity"])
                if q > 0:
                    items.append({**it, "quantity": min(int(q), 50)})
            if not items:
                raise AppException(
                    code="RECURRING_BASKET_EMPTY",
                    message="Keep at least one item, or cancel the recurring basket.",
                    status_code=422,
                )
            b.items = items
        if b.status == "ENDED":
            b.status = "ACTIVE"
        self._reschedule(b)
        return await self._flush_out(b)

    async def set_status(self, customer_id, basket_id, action: str):
        b = await self._own(customer_id, basket_id)
        if b.status == "CANCELLED":
            raise AppException(
                code="RECURRING_BASKET_CANCELLED",
                message="This recurring basket was cancelled.",
                status_code=409,
            )
        if action == "pause":
            b.status = "PAUSED"
            b.next_run_date = None
        elif action == "resume":
            b.status = "ACTIVE"
            self._reschedule(b)
        elif action == "cancel":
            b.status = "CANCELLED"
            b.next_run_date = None
        elif action == "skip":
            if b.status != "ACTIVE" or b.next_run_date is None:
                raise AppException(
                    code="NOTHING_TO_SKIP",
                    message="There is no upcoming date to skip.",
                    status_code=409,
                )
            skipped = b.next_run_date
            b.skip_dates = sorted({*(b.skip_dates or []), skipped.isoformat()})
            existing = await self._run(b.id, skipped)
            if existing is None:
                self.session.add(
                    RecurringBasketRun(
                        id=uuid.uuid4(),
                        recurring_basket_id=b.id,
                        scheduled_for=skipped,
                        status="SKIPPED",
                    )
                )
            else:
                existing.status = "SKIPPED"
            self._reschedule(b)
        return await self._flush_out(b)

    async def list_baskets(self, customer_id) -> list[RecurringBasketOut]:
        rows = (
            (
                await self.session.execute(
                    select(RecurringBasket)
                    .where(RecurringBasket.customer_id == customer_id)
                    .order_by(RecurringBasket.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [await self._out(b) for b in rows]

    async def get(self, customer_id, basket_id) -> RecurringBasketOut:
        return await self._out(await self._own(customer_id, basket_id))

    # ------------------------------------------------------------ pre-order check
    async def _listings(self, ids) -> dict[uuid.UUID, ProductListing]:
        rows = (
            (
                await self.session.execute(
                    select(ProductListing)
                    .options(
                        selectinload(ProductListing.inventory),
                        selectinload(ProductListing.retailer),
                        selectinload(ProductListing.variant).selectinload(
                            ProductVariant.product
                        ),
                    )
                    .where(ProductListing.id.in_(list(ids)))
                )
            )
            .scalars()
            .all()
        )
        return {r.id: r for r in rows}

    async def check(
        self, b: RecurringBasket, scheduled_for: date | None
    ) -> PreOrderCheck:
        from app.modules.pricing.discount_service import DiscountLine, DiscountService

        listings = await self._listings(uuid.UUID(i["listing_id"]) for i in b.items)
        pincode = None
        if b.delivery_address_id:
            addr = await self.session.get(Address, b.delivery_address_id)
            pincode = addr.postal_code if addr else None
        lines: list[CheckLine] = []
        priceable: list[tuple[CheckLine, ProductListing]] = []
        for it in b.items:
            lst = listings.get(uuid.UUID(it["listing_id"]))
            line = CheckLine(
                listing_id=it["listing_id"],
                product_name=it["product_name"],
                retailer_name=it["retailer_name"],
                quantity=it["quantity"],
                status="OK",
                previous_unit_price_paise=it["unit_price_paise_at_setup"],
            )
            lines.append(line)
            if (
                lst is None
                or not lst.is_active
                or not lst.retailer.is_active
                or lst.retailer.verification_status != "VERIFIED"
            ):
                line.status, line.note = "UNAVAILABLE", "No longer sold by this store."
                continue
            inv = lst.inventory
            available = (
                max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            )
            line.available_quantity = available
            line.current_unit_price_paise = int(lst.selling_price_paise)
            if pincode and not retailer_serves(lst.retailer.service_pincodes, pincode):
                line.status, line.note = (
                    "NOT_DELIVERABLE",
                    f"Store does not deliver to {pincode}.",
                )
                continue
            if available == 0:
                line.status, line.note = "OUT_OF_STOCK", "Out of stock right now."
                continue
            if available < it["quantity"]:
                line.status = "LOW_STOCK"
                line.note = f"Only {available} available; {available} will be loaded."
            priceable.append((line, lst))

        if priceable:
            result = await DiscountService(self.session).resolve_basket_discounts(
                [
                    DiscountLine(
                        listing_id=lst.id,
                        retailer_id=lst.retailer_id,
                        product_id=lst.variant.product_id,
                        category_id=lst.variant.product.category_id,
                        unit_price_paise=int(lst.selling_price_paise),
                        quantity=min(line.quantity, line.available_quantity),
                    )
                    for line, lst in priceable
                ]
            )
            for line, lst in priceable:
                d = result.lines.get(lst.id)
                qty = min(line.quantity, line.available_quantity)
                line.offer_unit_discount_paise = d.unit_discount_paise if d else 0
                line.final_unit_price_paise = (
                    d.unit_price_paise if d else int(lst.selling_price_paise)
                )
                line.offers = [x.name for x in (d.applied if d else [])]
                line.line_total_paise = line.final_unit_price_paise * qty
                if (
                    line.status == "OK"
                    and line.current_unit_price_paise != line.previous_unit_price_paise
                ):
                    line.status = "PRICE_CHANGED"

        changes = []
        for ln in lines:
            if ln.status == "PRICE_CHANGED":
                changes.append(
                    f"{ln.product_name}: ₹{ln.previous_unit_price_paise / 100:,.2f} → "
                    f"₹{(ln.current_unit_price_paise or 0) / 100:,.2f}"
                )
            elif ln.status != "OK":
                changes.append(f"{ln.product_name}: {ln.note}")
            if ln.offers:
                changes.append(
                    f"{ln.product_name}: offer applied ({', '.join(ln.offers)})"
                )
        orderable = [ln for ln in lines if ln.line_total_paise > 0]
        return PreOrderCheck(
            checked_at=datetime.now(UTC),
            scheduled_for=scheduled_for,
            lines=lines,
            orderable_lines=len(orderable),
            items_total_paise=sum(ln.line_total_paise for ln in orderable),
            previous_total_paise=sum(
                ln.previous_unit_price_paise * min(ln.quantity, ln.available_quantity)
                for ln in orderable
            ),
            changes=changes,
            delivery_address_set=pincode is not None,
        )

    async def preview(self, customer_id, basket_id) -> PreOrderCheck:
        b = await self._own(customer_id, basket_id)
        return await self.check(b, b.next_run_date)

    async def _run(self, basket_id, d: date) -> RecurringBasketRun | None:
        return (
            await self.session.execute(
                select(RecurringBasketRun).where(
                    RecurringBasketRun.recurring_basket_id == basket_id,
                    RecurringBasketRun.scheduled_for == d,
                )
            )
        ).scalar_one_or_none()

    async def load_to_cart(self, customer_id, basket_id) -> LoadToCartResult:
        """Put the checked, orderable items into the cart. No order, no charge."""
        from app.modules.cart.integration import set_customer_cart_lines

        b = await self._own(customer_id, basket_id)
        result = await self.check(b, b.next_run_date)
        lines = [
            (ln.listing_id, min(ln.quantity, ln.available_quantity))
            for ln in result.lines
            if ln.line_total_paise > 0
        ]
        skipped = [ln.product_name for ln in result.lines if ln.line_total_paise == 0]
        if not lines:
            raise AppException(
                code="NOTHING_TO_ADD",
                message="None of the items can be ordered right now.",
                status_code=409,
            )
        await set_customer_cart_lines(self.session, customer_id, lines)
        if b.next_run_date is not None:
            run = await self._run(b.id, b.next_run_date)
            if run is None:
                run = RecurringBasketRun(
                    id=uuid.uuid4(),
                    recurring_basket_id=b.id,
                    scheduled_for=b.next_run_date,
                    status="LOADED_TO_CART",
                    check=result.model_dump(mode="json"),
                )
                self.session.add(run)
            else:
                run.status = "LOADED_TO_CART"
        await self.session.flush()
        msg = f"Loaded {len(lines)} item(s) into your cart. Review the total and check out."
        if skipped:
            msg += f" Not available: {', '.join(skipped)}."
        return LoadToCartResult(loaded=len(lines), skipped=skipped, message=msg)


async def prepare_due_recurring_baskets(
    session: AsyncSession, today: date | None = None
) -> int:
    """Scheduled job: one pre-order check + in-app notice per basket per date.

    Idempotent: the unique (basket, date) run means a date is prepared once,
    however often the job runs. Dates that have passed roll forward.
    """
    today = today or date.today()
    svc = RecurringBasketService(session)
    rows = (
        (
            await session.execute(
                select(RecurringBasket)
                .where(
                    RecurringBasket.status == "ACTIVE",
                    RecurringBasket.next_run_date.is_not(None),
                    RecurringBasket.next_run_date
                    <= today + timedelta(days=PREPARE_DAYS_AHEAD),
                )
                .with_for_update(skip_locked=True)
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    prepared = 0
    for b in rows:
        if b.next_run_date < today:  # date passed: move to the next one
            svc._reschedule(b, today)
            if b.next_run_date is None or b.next_run_date > today + timedelta(
                days=PREPARE_DAYS_AHEAD
            ):
                continue
        if await svc._run(b.id, b.next_run_date) is not None:
            continue
        result = await svc.check(b, b.next_run_date)
        session.add(
            RecurringBasketRun(
                id=uuid.uuid4(),
                recurring_basket_id=b.id,
                scheduled_for=b.next_run_date,
                status="PREPARED",
                check=result.model_dump(mode="json"),
            )
        )
        n_changes = len(result.changes)
        notify_customer(
            session,
            customer_id=b.customer_id,
            title=f"{b.name} is ready to review",
            message=(
                f"Your basket for {b.next_run_date:%d %b} is checked: items "
                f"₹{result.items_total_paise / 100:,.2f}"
                + (f", {n_changes} change(s)" if n_changes else ", no changes")
                + ". Nothing is charged until you check out."
            ),
            event_type="RECURRING_BASKET_READY",
        )
        prepared += 1
    await session.flush()
    return prepared
