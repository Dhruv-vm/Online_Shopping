"""Version 2.0 Phase B (roadmap P0-2): discount codes, the stacking policy
(best single platform deal + best single retailer offer), minimum order on the
basket subtotal, and concurrency-safe usage limits.

Every case runs through the real API and the real test database. Each test
uses its own category, retailers and discounts, so leftovers in the shared
test database cannot change the expected totals (see ``_quiet_platform_deals``).
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.database import get_session_factory
from app.modules.catalogue.models import Category
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import Order
from app.modules.pricing.discount_service import retailer_scope
from app.modules.pricing.models import (
    CheckoutQuote,
    Discount,
    DiscountRedemption,
)
from app.modules.pricing.redemptions import release_discount_usage
from tests.phase3_helpers import make_retailer, make_user
from tests.test_payments import get_internal_auth_headers

ADDRESS = {
    "recipient_name": "Phase B",
    "phone": "+919876543210",
    "line1": "12 MG Road",
    "city": "Bengaluru",
    "state": "KA",
    "postal_code": "560001",
    "is_default": True,
}


# ------------------------------------------------------------------ helpers
@pytest.fixture(autouse=True)
async def _quiet_platform_deals():
    """Other tests can leave uncoded PLATFORM_WIDE deals active in the shared
    test database; they would compete in "best platform deal" and change the
    expected totals. Pause them for the duration of each test, then restore."""
    async with get_session_factory()() as s:
        ids = (
            (
                await s.execute(
                    select(Discount.id).where(
                        Discount.scope == "PLATFORM_WIDE",
                        Discount.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if ids:
            await s.execute(
                update(Discount).where(Discount.id.in_(ids)).values(is_active=False)
            )
            await s.commit()
    yield
    if ids:
        async with get_session_factory()() as s:
            await s.execute(
                update(Discount).where(Discount.id.in_(ids)).values(is_active=True)
            )
            await s.commit()


def _slug() -> str:
    return f"v2b-{uuid.uuid4().hex[:10]}"


async def _seller(price: int, slug: str, *, stock: int = 50):
    listing, headers = await make_retailer(
        selling_price_paise=price,
        original_price_paise=price,
        on_hand_quantity=stock,
        category_slug=slug,
        category_name=slug,
    )
    return listing, headers


async def _category_id(slug: str) -> uuid.UUID:
    async with get_session_factory()() as s:
        return (
            await s.execute(select(Category.id).where(Category.slug == slug))
        ).scalar_one()


async def _discount(**kw) -> uuid.UUID:
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "name": f"V2B {uuid.uuid4().hex[:6]}",
        "discount_type": "PERCENTAGE",
        "is_active": True,
        "valid_from": now - timedelta(minutes=5),
        "valid_to": now + timedelta(days=1),
        "min_order_paise": 0,
        "times_used": 0,
    }
    values.update(kw)
    async with get_session_factory()() as s:
        s.add(Discount(**values))
        await s.commit()
    return values["id"]


async def _customer(client):
    _, h = await make_user()
    r = await client.post("/api/v1/addresses", headers=h, json=ADDRESS)
    assert r.status_code == 201, r.text
    return h, r.json()["id"]


async def _basket(client, h, *lines):
    for listing_id, qty in lines:
        r = await client.post(
            "/api/v1/cart/items",
            headers=h,
            json={"listing_id": listing_id, "quantity": qty},
        )
        assert r.status_code in (200, 201), r.text


async def _set_qty(client, h, listing_id, qty):
    cart = (await client.get("/api/v1/cart", headers=h)).json()
    item = next(i for i in cart["items"] if i["listing_id"] == listing_id)
    r = await client.patch(
        f"/api/v1/cart/items/{item['id']}", headers=h, json={"quantity": qty}
    )
    assert r.status_code == 200, r.text


async def _quote(client, h, addr, code=None):
    body = {"delivery_address_id": addr}
    if code is not None:
        body["discount_code"] = code
    return await client.post("/api/v1/quotes", headers=h, json=body)


async def _order(client, h, addr, code=None):
    q = await _quote(client, h, addr, code)
    assert q.status_code == 201, q.text
    r = await client.post(
        "/api/v1/reservations", headers=h, json={"quote_id": q.json()["id"]}
    )
    assert r.status_code == 201, r.text
    o = await client.post(
        "/api/v1/orders",
        headers=h,
        json={
            "quote_id": q.json()["id"],
            "reservation_id": r.json()["id"],
            "delivery_address_id": addr,
        },
    )
    return q.json(), r.json(), o


async def _times_used(discount_id) -> int:
    async with get_session_factory()() as s:
        return (await s.get(Discount, discount_id)).times_used


async def _redemptions(discount_id) -> list[tuple[uuid.UUID, str]]:
    async with get_session_factory()() as s:
        rows = (
            await s.execute(
                select(DiscountRedemption.order_id, DiscountRedemption.status).where(
                    DiscountRedemption.discount_id == discount_id
                )
            )
        ).all()
        return [(r[0], r[1]) for r in rows]


def _line(quote, listing_id):
    return next(i for i in quote["items"] if i["listing_id"] == listing_id)


# --------------------------------------------------------------- B1 codes
@pytest.mark.asyncio
async def test_coded_deal_needs_its_code_and_matches_case_insensitively(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(100000, slug)
    code = f"V2B{uuid.uuid4().hex[:6].upper()}"
    did = await _discount(
        code=code,
        scope="CATEGORY",
        category_id=await _category_id(slug),
        discount_value=1000,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))

    none = (await _quote(async_client, h, addr)).json()
    assert none["discount_total_paise"] == 0 and none["applied_discount_ids"] == []
    assert none["discount_code"] is None and none["discount_code_applied"] is False

    for supplied in (code.lower(), code, f"  {code.title()} "):
        q = await _quote(async_client, h, addr, supplied)
        assert q.status_code == 201, q.text
        body = q.json()
        assert body["applied_discount_ids"] == [str(did)]
        assert _line(body, listing["id"])["unit_discounted_price_paise"] == 90000
        assert body["discount_code"] == code and body["discount_code_applied"] is True


@pytest.mark.asyncio
async def test_wrong_expired_inactive_future_and_used_up_codes_return_422(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(100000, slug)
    cat = await _category_id(slug)
    now = datetime.now(UTC)
    tag = uuid.uuid4().hex[:6].upper()
    await _discount(
        code=f"EXP{tag}",
        scope="CATEGORY",
        category_id=cat,
        discount_value=500,
        valid_from=now - timedelta(days=3),
        valid_to=now - timedelta(days=1),
    )
    await _discount(
        code=f"OFF{tag}",
        scope="CATEGORY",
        category_id=cat,
        discount_value=500,
        is_active=False,
    )
    await _discount(
        code=f"FUT{tag}",
        scope="CATEGORY",
        category_id=cat,
        discount_value=500,
        valid_from=now + timedelta(days=1),
        valid_to=now + timedelta(days=2),
    )
    await _discount(
        code=f"USED{tag}",
        scope="CATEGORY",
        category_id=cat,
        discount_value=500,
        usage_limit=1,
        times_used=1,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    for bad in (f"NOPE{tag}", f"exp{tag}", f"OFF{tag}", f"FUT{tag}", f"USED{tag}"):
        r = await _quote(async_client, h, addr, bad)
        assert r.status_code == 422, (bad, r.text)
        assert r.json()["error"]["code"] == "INVALID_DISCOUNT_CODE"
        # Same generic message for every reason: nothing about the deal leaks.
        assert r.json()["error"]["message"] == "This discount code is not valid."
    # an empty / blank code is the same as no code
    assert (await _quote(async_client, h, addr, "   ")).status_code == 201


@pytest.mark.asyncio
async def test_code_cannot_bypass_eligibility(async_client: AsyncClient):
    slug, other = _slug(), _slug()
    listing, _ = await _seller(100000, slug)
    await _seller(100000, other)  # creates the other category
    code = f"ELSE{uuid.uuid4().hex[:6].upper()}"
    await _discount(
        code=code,
        scope="CATEGORY",
        category_id=await _category_id(other),
        discount_value=2000,
    )
    tight = f"MIN{uuid.uuid4().hex[:6].upper()}"
    await _discount(
        code=tight,
        scope="CATEGORY",
        category_id=await _category_id(slug),
        discount_value=2000,
        min_order_paise=500000,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    for c in (code, tight):
        q = await _quote(async_client, h, addr, c)
        assert q.status_code == 201, q.text  # valid code, just not applicable
        assert q.json()["discount_total_paise"] == 0
        assert q.json()["discount_code_applied"] is False


# ------------------------------------------------------------ B2 stacking
@pytest.mark.asyncio
async def test_only_the_best_platform_deal_applies(async_client: AsyncClient):
    slug = _slug()
    listing, _ = await _seller(20000, slug)  # ₹200
    cat = await _category_id(slug)
    # Displays "20 %" but is capped at ₹10; a flat ₹15 is better for the customer.
    pct = await _discount(
        scope="CATEGORY", category_id=cat, discount_value=2000, max_discount_paise=1000
    )
    flat = await _discount(
        scope="PRODUCT",
        product_id=uuid.UUID(listing["product_id"]),
        discount_type="FIXED_AMOUNT",
        discount_value=1500,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 2))
    q = (await _quote(async_client, h, addr)).json()
    line = _line(q, listing["id"])
    assert line["applied_discount_ids"] == [str(flat)]
    assert str(pct) not in q["applied_discount_ids"]
    assert line["unit_discount_paise"] == 1500  # not 2500 (no stacking)
    assert q["discount_total_paise"] == 3000


@pytest.mark.asyncio
async def test_platform_deal_and_retailer_offer_apply_together(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(100000, slug)
    rid = uuid.UUID(listing["retailer_id"])
    platform = await _discount(
        scope="CATEGORY", category_id=await _category_id(slug), discount_value=500
    )
    own = await _discount(
        scope=retailer_scope(rid),
        listing_id=uuid.UUID(listing["id"]),
        discount_value=1000,
    )
    weaker_store = await _discount(scope=retailer_scope(rid), discount_value=300)
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    q = (await _quote(async_client, h, addr)).json()
    line = _line(q, listing["id"])
    assert sorted(line["applied_discount_ids"]) == sorted([str(platform), str(own)])
    assert str(weaker_store) not in q["applied_discount_ids"]  # one retailer offer
    assert line["unit_discounted_price_paise"] == 100000 - 10000 - 5000


@pytest.mark.asyncio
async def test_coded_platform_deal_competes_only_with_its_code(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(100000, slug)
    cat = await _category_id(slug)
    auto = await _discount(scope="CATEGORY", category_id=cat, discount_value=500)
    code = f"BIG{uuid.uuid4().hex[:6].upper()}"
    coded = await _discount(
        code=code, scope="CATEGORY", category_id=cat, discount_value=1500
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    plain = (await _quote(async_client, h, addr)).json()
    assert plain["applied_discount_ids"] == [str(auto)]
    with_code = (await _quote(async_client, h, addr, code.lower())).json()
    assert with_code["applied_discount_ids"] == [str(coded)]  # replaces, not stacks
    assert _line(with_code, listing["id"])["unit_discounted_price_paise"] == 85000


# ----------------------------------------------------------- B3 min order
@pytest.mark.asyncio
async def test_minimum_order_uses_basket_subtotal_before_tax_and_delivery(
    async_client: AsyncClient,
):
    """Prices stay under the ₹499 free-delivery threshold so a delivery fee is
    charged and can be shown not to count towards the minimum."""
    slug = _slug()
    a, _ = await _seller(20000, slug)
    b, _ = await _seller(15000, slug)
    cat = await _category_id(slug)
    deal = await _discount(
        scope="CATEGORY", category_id=cat, discount_value=1000, min_order_paise=40000
    )
    strict = await _discount(
        scope="PRODUCT",
        product_id=uuid.UUID(a["product_id"]),
        discount_type="FIXED_AMOUNT",
        discount_value=100,
        min_order_paise=40001,
    )
    h, addr = await _customer(async_client)

    await _basket(async_client, h, (a["id"], 1))
    q = (await _quote(async_client, h, addr)).json()
    assert q["discount_total_paise"] == 0  # 20000 < 40000

    await _set_qty(async_client, h, a["id"], 2)  # exactly 40000 → qualifies
    q = (await _quote(async_client, h, addr)).json()
    assert _line(q, a["id"])["applied_discount_ids"] == [str(deal)]
    # No circularity: the discounted subtotal (36000) is below the minimum.
    assert q["subtotal_paise"] == 36000
    # Delivery is excluded: subtotal + delivery (40900) passes 40001, but the
    # ₹400.01-minimum deal still does not apply. GST is inside the prices and
    # is not added on top.
    assert q["delivery_fee_paise"] > 0
    assert q["total_payable_paise"] == 36000 + q["delivery_fee_paise"] > 40001
    assert q["total_tax_paise"] > 0
    assert str(strict) not in q["applied_discount_ids"]

    await _set_qty(async_client, h, a["id"], 1)
    await _basket(async_client, h, (b["id"], 2))  # 20000 + 30000 across products
    q = (await _quote(async_client, h, addr)).json()
    assert _line(q, a["id"])["applied_discount_ids"] == [str(deal)]
    assert _line(q, b["id"])["applied_discount_ids"] == [str(deal)]
    assert q["discount_total_paise"] == 2000 + 2 * 1500


@pytest.mark.asyncio
async def test_store_wide_retailer_offer_minimum_uses_that_retailers_lines(
    async_client: AsyncClient,
):
    slug = _slug()
    mine, _ = await _seller(60000, slug)
    other, _ = await _seller(90000, slug)  # another retailer
    code = f"STORE{uuid.uuid4().hex[:6].upper()}"
    offer = await _discount(
        code=code,
        scope=retailer_scope(uuid.UUID(mine["retailer_id"])),
        discount_value=1000,
        min_order_paise=99900,
        max_discount_paise=50000,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (mine["id"], 1), (other["id"], 1))
    # Basket is ₹1,500 but this store's lines are only ₹600: not eligible.
    q = (await _quote(async_client, h, addr, code)).json()
    assert q["discount_total_paise"] == 0 and q["discount_code_applied"] is False
    await _set_qty(async_client, h, mine["id"], 2)  # store subtotal ₹1,200
    q = (await _quote(async_client, h, addr, code)).json()
    assert _line(q, mine["id"])["applied_discount_ids"] == [str(offer)]
    assert _line(q, other["id"])["applied_discount_ids"] == []
    assert q["discount_total_paise"] == 2 * 6000


# --------------------------------------------------------- B4 usage limits
@pytest.mark.asyncio
async def test_usage_reserved_at_order_and_released_once_on_unpaid_cancel(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(50000, slug)
    did = await _discount(
        scope="CATEGORY",
        category_id=await _category_id(slug),
        discount_value=1000,
        usage_limit=5,
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    quote, _, o = await _order(async_client, h, addr)
    assert o.status_code == 201, o.text
    order = o.json()
    assert order["total_payable_paise"] == quote["total_payable_paise"]
    assert await _times_used(did) == 1
    assert await _redemptions(did) == [(uuid.UUID(order["id"]), "RESERVED")]

    for _ in range(2):  # second cancel is idempotent
        c = await async_client.post(
            f"/api/v1/orders/{order['id']}/cancel", headers=h, json={"reason": "test"}
        )
        assert c.status_code == 200, c.text
    assert await _times_used(did) == 0
    assert await _redemptions(did) == [(uuid.UUID(order["id"]), "RELEASED")]
    # A late duplicate release (e.g. the expiry job) changes nothing.
    async with get_session_factory()() as s:
        assert (
            await release_discount_usage(
                s, order_id=uuid.UUID(order["id"]), reason="DUPLICATE"
            )
            == 0
        )
        await s.commit()
    assert await _times_used(did) == 0


@pytest.mark.asyncio
async def test_payment_window_expiry_releases_usage_once(async_client: AsyncClient):
    slug = _slug()
    listing, _ = await _seller(50000, slug)
    did = await _discount(
        scope="CATEGORY", category_id=await _category_id(slug), discount_value=1000
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    _, _, o = await _order(async_client, h, addr)
    oid = uuid.UUID(o.json()["id"])
    assert await _times_used(did) == 1
    past = datetime.now(UTC) - timedelta(minutes=80)
    async with get_session_factory()() as s:
        await s.execute(
            update(Order)
            .where(Order.id == oid)
            .values(
                created_at=past - timedelta(days=30), payment_window_expires_at=past
            )
        )
        await s.commit()
    for _ in range(2):  # the job runs again: nothing more to release
        r = await async_client.post(
            "/api/v1/internal/payments/sla-escalation",
            headers=get_internal_auth_headers(),
        )
        assert r.status_code == 200, r.text
    async with get_session_factory()() as s:
        assert (await s.get(Order, oid)).status == "CANCELLED"
    assert await _times_used(did) == 0
    assert await _redemptions(did) == [(oid, "RELEASED")]
    # The customer cancelling after expiry does not decrement again.
    c = await async_client.post(
        f"/api/v1/orders/{oid}/cancel", headers=h, json={"reason": "late"}
    )
    assert c.status_code == 200
    assert await _times_used(did) == 0


@pytest.mark.asyncio
async def test_paid_order_keeps_its_usage_when_cancelled(async_client: AsyncClient):
    slug = _slug()
    listing, _ = await _seller(50000, slug)
    did = await _discount(
        scope="CATEGORY", category_id=await _category_id(slug), discount_value=1000
    )
    h, addr = await _customer(async_client)
    await _basket(async_client, h, (listing["id"], 1))
    _, _, o = await _order(async_client, h, addr)
    oid = uuid.UUID(o.json()["id"])
    async with get_session_factory()() as s:
        await s.execute(
            update(Order)
            .where(Order.id == oid)
            .values(status="CONFIRMED", payment_status="SUCCEEDED")
        )
        await s.commit()
    c = await async_client.post(
        f"/api/v1/orders/{oid}/cancel", headers=h, json={"reason": "changed mind"}
    )
    assert c.status_code == 200, c.text
    assert await _times_used(did) == 1
    assert await _redemptions(did) == [(oid, "RESERVED")]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,buyers", [(1, 2), (2, 5)])
async def test_concurrent_orders_never_exceed_usage_limit(
    async_client: AsyncClient, limit: int, buyers: int
):
    """Real concurrent transactions: every buyer has a quote priced with the
    deal (times_used was 0 for all of them); only ``limit`` orders succeed, the
    rest roll back completely with 409."""
    slug = _slug()
    listing, _ = await _seller(50000, slug, stock=50)
    did = await _discount(
        scope="CATEGORY",
        category_id=await _category_id(slug),
        discount_value=1000,
        usage_limit=limit,
    )
    prepared = []
    for _ in range(buyers):
        h, addr = await _customer(async_client)
        await _basket(async_client, h, (listing["id"], 1))
        q = (await _quote(async_client, h, addr)).json()
        assert q["applied_discount_ids"] == [str(did)]
        r = (
            await async_client.post(
                "/api/v1/reservations", headers=h, json={"quote_id": q["id"]}
            )
        ).json()
        prepared.append((h, addr, q, r))

    responses = await asyncio.gather(
        *[
            async_client.post(
                "/api/v1/orders",
                headers=h,
                json={
                    "quote_id": q["id"],
                    "reservation_id": r["id"],
                    "delivery_address_id": addr,
                },
            )
            for h, addr, q, r in prepared
        ]
    )
    ok = [x for x in responses if x.status_code == 201]
    refused = [x for x in responses if x.status_code != 201]
    assert len(ok) == limit, [x.text for x in responses]
    assert all(
        x.status_code == 409
        and x.json()["error"]["code"] == "DISCOUNT_USAGE_LIMIT_REACHED"
        for x in refused
    )
    assert await _times_used(did) == limit
    assert len(await _redemptions(did)) == limit

    # Rollback: losers have no order, an unconsumed quote and an active hold.
    ok_quotes = {x.json()["quote_id"] for x in ok}
    async with get_session_factory()() as s:
        for _h, _a, q, r in prepared:
            if q["id"] in ok_quotes:
                continue
            quote = await s.get(CheckoutQuote, uuid.UUID(q["id"]))
            hold = await s.get(InventoryReservation, uuid.UUID(r["id"]))
            assert quote.is_consumed is False and quote.status == "ACTIVE"
            assert hold.status == "ACTIVE" and hold.order_id is None
            orders = (
                await s.execute(
                    select(Order.id).where(Order.quote_id == uuid.UUID(q["id"]))
                )
            ).all()
            assert orders == []


@pytest.mark.asyncio
async def test_deactivated_after_quote_blocks_order_and_old_orders_keep_totals(
    async_client: AsyncClient,
):
    slug = _slug()
    listing, _ = await _seller(50000, slug)
    did = await _discount(
        scope="CATEGORY", category_id=await _category_id(slug), discount_value=1000
    )
    # An order placed while the deal was live keeps its stored totals.
    h1, a1 = await _customer(async_client)
    await _basket(async_client, h1, (listing["id"], 1))
    _, _, first = await _order(async_client, h1, a1)
    assert first.status_code == 201
    stored = first.json()["total_payable_paise"]

    h2, a2 = await _customer(async_client)
    await _basket(async_client, h2, (listing["id"], 1))
    q = (await _quote(async_client, h2, a2)).json()
    r = (
        await async_client.post(
            "/api/v1/reservations", headers=h2, json={"quote_id": q["id"]}
        )
    ).json()
    async with get_session_factory()() as s:
        await s.execute(
            update(Discount).where(Discount.id == did).values(is_active=False)
        )
        await s.commit()
    o = await async_client.post(
        "/api/v1/orders",
        headers=h2,
        json={
            "quote_id": q["id"],
            "reservation_id": r["id"],
            "delivery_address_id": a2,
        },
    )
    assert o.status_code == 409 and o.json()["error"]["code"] == (
        "DISCOUNT_NO_LONGER_AVAILABLE"
    )
    again = (
        await async_client.get(f"/api/v1/orders/{first.json()['id']}", headers=h1)
    ).json()
    assert again["total_payable_paise"] == stored
    assert await _times_used(did) == 1  # only the first order holds a use


@pytest.mark.asyncio
async def test_admin_codes_are_unique_case_insensitively(async_client: AsyncClient):
    _, admin = await make_user("admin")
    code = f"Mixed{uuid.uuid4().hex[:6]}"
    await _discount(code=code.lower(), scope="PLATFORM_WIDE", discount_value=100)
    r = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin,
        json={
            "name": "Dup in another case",
            "code": code.upper(),
            "discount_type": "PERCENTAGE",
            "discount_value": 500,
            "scope": "PLATFORM_WIDE",
        },
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == (
        "COUPON_CODE_ALREADY_EXISTS"
    )
