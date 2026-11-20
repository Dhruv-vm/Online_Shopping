"""Phase 3D AI Negotiator (rule-bound deal assistant)."""

import pytest
from httpx import AsyncClient

from tests.phase3_helpers import make_retailer, make_user, place_order

PRICE = 100000  # ₹1000


async def _setup(client, *, rule=None, qty=1):
    listing, rh = await make_retailer(
        selling_price_paise=PRICE, original_price_paise=PRICE
    )
    if rule is not None:
        r = await client.put(
            "/api/v1/retailer/negotiation-rules",
            headers=rh,
            json={"listing_id": listing["id"], **rule},
        )
        assert r.status_code == 200, r.text
    _, cust = await make_user()
    await client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": listing["id"], "quantity": qty},
    )
    return listing, rh, cust


@pytest.mark.asyncio
async def test_ladder_floor_and_accept_into_order(async_client: AsyncClient):
    listing, _, cust = await _setup(
        async_client, rule={"max_auto_discount_percent": 10}
    )
    s = (
        await async_client.post("/api/v1/negotiate/start", headers=cust, json={})
    ).json()
    assert s["status"] == "IN_PROGRESS" and s["list_total_paise"] == PRICE
    assert s["current_offer_paise"] == 96000  # 40% of the 10% concession
    assert "floor" not in str(s).lower()

    c1 = (
        await async_client.post(
            "/api/v1/negotiate/counter-offer",
            headers=cust,
            json={"session_id": s["id"], "proposed_price_paise": 50000},
        )
    ).json()
    assert c1["current_round"] == 2 and c1["current_offer_paise"] == 93000
    c2 = (
        await async_client.post(
            "/api/v1/negotiate/counter-offer",
            headers=cust,
            json={"session_id": s["id"], "proposed_price_paise": 50000},
        )
    ).json()
    assert c2["current_round"] == 3 and c2["current_offer_paise"] == 90000
    c3 = (
        await async_client.post(
            "/api/v1/negotiate/counter-offer",
            headers=cust,
            json={"session_id": s["id"], "proposed_price_paise": 50000},
        )
    ).json()
    assert c3["current_offer_paise"] == 90000  # never below floor

    acc = await async_client.post(
        "/api/v1/negotiate/accept", headers=cust, json={"session_id": s["id"]}
    )
    assert acc.status_code == 200, acc.text
    body = acc.json()
    assert (
        body["status"] == "ACCEPTED"
        and body["final_accepted_price_paise"] == 90000
        and body["quote_id"]
    )
    quote, order = await place_order(async_client, cust)
    assert (
        next(i for i in quote["items"] if i["listing_id"] == listing["id"])[
            "unit_discounted_price_paise"
        ]
        == 90000
    )
    assert (
        await async_client.post(
            "/api/v1/negotiate/accept", headers=cust, json={"session_id": s["id"]}
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_customer_price_above_floor_is_agreed(async_client: AsyncClient):
    _, _, cust = await _setup(async_client, rule={"max_auto_discount_percent": 20})
    s = (
        await async_client.post(
            "/api/v1/negotiate/start", headers=cust, json={"target_price_paise": 85000}
        )
    ).json()
    assert s["current_offer_paise"] == 85000
    assert s["messages"][-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_listing_floor_price_and_bundle_bonus(async_client: AsyncClient):
    _, _, cust = await _setup(
        async_client,
        rule={"max_auto_discount_percent": 30, "min_floor_price_paise": 95000},
    )
    s = (
        await async_client.post(
            "/api/v1/negotiate/start", headers=cust, json={"target_price_paise": 1}
        )
    ).json()
    for _ in range(3):
        s = (
            await async_client.post(
                "/api/v1/negotiate/counter-offer",
                headers=cust,
                json={"session_id": s["id"], "proposed_price_paise": 1},
            )
        ).json()
    assert s["current_offer_paise"] == 95000

    _, _, bulk = await _setup(
        async_client,
        qty=3,
        rule={
            "max_auto_discount_percent": 10,
            "bundle_quantity_threshold": 3,
            "bundle_extra_discount_percent": 5,
        },
    )
    b = (
        await async_client.post(
            "/api/v1/negotiate/start", headers=bulk, json={"target_price_paise": 1}
        )
    ).json()
    for _ in range(3):
        b = (
            await async_client.post(
                "/api/v1/negotiate/counter-offer",
                headers=bulk,
                json={"session_id": b["id"], "proposed_price_paise": 1},
            )
        ).json()
    assert b["current_offer_paise"] == 3 * 85000  # 10% + 5% bundle concession


@pytest.mark.asyncio
async def test_no_rule_no_negotiation_and_hindi(async_client: AsyncClient):
    _, _, cust = await _setup(async_client, rule=None)
    s = (
        await async_client.post(
            "/api/v1/negotiate/start", headers=cust, json={"language": "hi"}
        )
    ).json()
    assert s["status"] == "REJECTED" and s["current_offer_paise"] == PRICE
    assert "विक्रेताओं" in s["messages"][0]["text"] and s["language_fallback"] is False
    _, _, ta = await _setup(async_client, rule={"max_auto_discount_percent": 5})
    t = (
        await async_client.post(
            "/api/v1/negotiate/start", headers=ta, json={"language": "ta"}
        )
    ).json()
    assert t["language_fallback"] is True
    assert (
        await async_client.post(
            "/api/v1/negotiate/start", headers=ta, json={"language": "xx"}
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_cart_change_voids_session_and_rbac(async_client: AsyncClient):
    listing, rh, cust = await _setup(
        async_client, rule={"max_auto_discount_percent": 10}
    )
    s = (
        await async_client.post("/api/v1/negotiate/start", headers=cust, json={})
    ).json()
    cart = (await async_client.get("/api/v1/cart", headers=cust)).json()
    item_id = cart["items"][0]["id"]
    await async_client.patch(
        f"/api/v1/cart/items/{item_id}", headers=cust, json={"quantity": 2}
    )
    r = await async_client.post(
        "/api/v1/negotiate/accept", headers=cust, json={"session_id": s["id"]}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "CART_CHANGED"

    _, other = await make_user()
    assert (
        await async_client.get(f"/api/v1/negotiate/sessions/{s['id']}", headers=other)
    ).status_code == 404
    assert (
        await async_client.post("/api/v1/negotiate/start", headers=rh, json={})
    ).status_code == 403
    assert (
        await async_client.post("/api/v1/negotiate/start", headers=other, json={})
    ).status_code == 400  # empty cart
    other_listing, other_rh = await make_retailer()
    bad = await async_client.put(
        "/api/v1/retailer/negotiation-rules",
        headers=other_rh,
        json={"listing_id": listing["id"], "max_auto_discount_percent": 10},
    )
    assert bad.status_code == 404
    too_much = await async_client.put(
        "/api/v1/retailer/negotiation-rules",
        headers=rh,
        json={"max_auto_discount_percent": 80},
    )
    assert too_much.status_code == 422
    assert (
        await async_client.put(
            "/api/v1/retailer/negotiation-rules",
            headers=cust,
            json={"max_auto_discount_percent": 5},
        )
    ).status_code == 403
    rules = (
        await async_client.get("/api/v1/retailer/negotiation-rules", headers=rh)
    ).json()
    assert len(rules) == 1
    assert (
        await async_client.delete(
            f"/api/v1/retailer/negotiation-rules/{rules[0]['id']}", headers=other_rh
        )
    ).status_code == 404
