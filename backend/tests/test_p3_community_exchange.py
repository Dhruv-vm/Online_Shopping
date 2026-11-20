"""Phase 3C Basket Community Exchange (customer RFQs)."""

import pytest
from httpx import AsyncClient

from tests.phase3_helpers import make_retailer, make_user, place_order

PIN = "560034"


def _rfq(**over):
    return {
        "title": "Diwali party supplies",
        "delivery_pincode": PIN,
        "budget_limit_paise": 500000,
        "items": [
            {"name": "Basmati rice 5kg", "quantity": 2},
            {"name": "Cooking oil 1L", "quantity": 3},
        ],
        **over,
    }


@pytest.mark.asyncio
async def test_rfq_bid_accept_and_checkout(async_client: AsyncClient):
    _, cust = await make_user()
    r = await async_client.post("/api/v1/exchange/requests", headers=cust, json=_rfq())
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    a, ah = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=60000, original_price_paise=70000
    )
    b, bh = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=55000, original_price_paise=70000
    )
    open_a = (
        await async_client.get("/api/v1/retailer/exchange/requests", headers=ah)
    ).json()
    assert rid in {i["id"] for i in open_a["items"]}

    bid_a = await async_client.post(
        f"/api/v1/retailer/exchange/requests/{rid}/bids",
        headers=ah,
        json={
            "lines": [
                {"manifest_index": 0, "listing_id": a["id"], "unit_price_paise": 50000}
            ],
            "estimated_delivery_hours": 4,
        },
    )
    assert bid_a.status_code == 201, bid_a.text
    assert (
        bid_a.json()["bid_amount_paise"] == 100000
        and bid_a.json()["items_covered"] == 1
    )
    # Revision replaces the earlier bid (one bid per retailer)
    rev = await async_client.post(
        f"/api/v1/retailer/exchange/requests/{rid}/bids",
        headers=ah,
        json={
            "lines": [
                {"manifest_index": 0, "listing_id": a["id"], "unit_price_paise": 45000}
            ],
            "estimated_delivery_hours": 3,
        },
    )
    assert rev.json()["bid_amount_paise"] == 90000
    bid_b = await async_client.post(
        f"/api/v1/retailer/exchange/requests/{rid}/bids",
        headers=bh,
        json={
            "lines": [
                {"manifest_index": 0, "listing_id": b["id"], "unit_price_paise": 48000}
            ],
            "estimated_delivery_hours": 2,
        },
    )
    assert bid_b.status_code == 201

    # Retailers never see competitors' bids
    view_b = (
        await async_client.get("/api/v1/retailer/exchange/requests", headers=bh)
    ).json()["items"]
    item_b = next(i for i in view_b if i["id"] == rid)
    assert (
        item_b["bids"] is None and item_b["my_bid"]["retailer_id"] == b["retailer_id"]
    )

    mine = (
        await async_client.get(f"/api/v1/exchange/requests/{rid}", headers=cust)
    ).json()
    assert [x["bid_amount_paise"] for x in mine["bids"]] == [90000, 96000]

    acc = await async_client.post(
        f"/api/v1/exchange/requests/{rid}/accept-bid",
        headers=cust,
        json={"bid_id": rev.json()["id"]},
    )
    assert acc.status_code == 200, acc.text
    body = acc.json()
    assert body["request"]["status"] == "AWARDED"
    statuses = {x["retailer_id"]: x["status"] for x in body["request"]["bids"]}
    assert (
        statuses[a["retailer_id"]] == "ACCEPTED"
        and statuses[b["retailer_id"]] == "REJECTED"
    )

    quote, order = await place_order(async_client, cust)
    line = next(i for i in quote["items"] if i["listing_id"] == a["id"])
    assert line["quantity"] == 2 and line["unit_discounted_price_paise"] == 45000
    assert order["status"] in ("PENDING_PAYMENT", "CONFIRMED")

    again = await async_client.post(
        f"/api/v1/exchange/requests/{rid}/accept-bid",
        headers=cust,
        json={"bid_id": bid_b.json()["id"]},
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_bid_validation_rules(async_client: AsyncClient):
    _, cust = await make_user()
    rid = (
        await async_client.post(
            "/api/v1/exchange/requests",
            headers=cust,
            json=_rfq(budget_limit_paise=50000),
        )
    ).json()["id"]
    mine, mh = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=30000, original_price_paise=30000
    )
    other, _ = await make_retailer(service_pincodes=[PIN])
    far, fh = await make_retailer(service_pincodes=["110001"])
    url = f"/api/v1/retailer/exchange/requests/{rid}/bids"

    def body(listing, price, idx=0):
        return {
            "lines": [
                {
                    "manifest_index": idx,
                    "listing_id": listing,
                    "unit_price_paise": price,
                }
            ],
            "estimated_delivery_hours": 5,
        }

    assert (
        await async_client.post(url, headers=mh, json=body(mine["id"], 35000))
    ).json()["error"]["code"] == "BID_ABOVE_LIST_PRICE"
    assert (
        await async_client.post(url, headers=mh, json=body(other["id"], 1000))
    ).status_code == 404
    assert (
        await async_client.post(url, headers=mh, json=body(mine["id"], 30000))
    ).json()["error"]["code"] == "BID_OVER_BUDGET"
    assert (
        await async_client.post(url, headers=mh, json=body(mine["id"], 1000, idx=7))
    ).status_code == 422
    assert (
        await async_client.post(url, headers=fh, json=body(far["id"], 1000))
    ).status_code == 403
    dup = {
        "lines": [
            {"manifest_index": 0, "listing_id": mine["id"], "unit_price_paise": 1000}
        ]
        * 2,
        "estimated_delivery_hours": 5,
    }
    assert (await async_client.post(url, headers=mh, json=dup)).status_code == 422


@pytest.mark.asyncio
async def test_rfq_rbac_and_lifecycle(async_client: AsyncClient):
    _, cust = await make_user()
    _, other = await make_user()
    _, admin = await make_user("admin")
    listing, rh = await make_retailer(service_pincodes=[PIN])
    assert (
        await async_client.post("/api/v1/exchange/requests", headers=rh, json=_rfq())
    ).status_code == 403
    assert (
        await async_client.post("/api/v1/exchange/requests", json=_rfq())
    ).status_code == 401
    assert (
        await async_client.post(
            "/api/v1/exchange/requests",
            headers=cust,
            json=_rfq(delivery_pincode="000000"),
        )
    ).status_code == 422
    assert (
        await async_client.post(
            "/api/v1/exchange/requests", headers=cust, json=_rfq(items=[])
        )
    ).status_code == 422
    rid = (
        await async_client.post("/api/v1/exchange/requests", headers=cust, json=_rfq())
    ).json()["id"]
    assert (
        await async_client.get(f"/api/v1/exchange/requests/{rid}", headers=other)
    ).status_code == 404
    assert (
        await async_client.get("/api/v1/retailer/exchange/requests", headers=cust)
    ).status_code == 403
    assert (
        await async_client.post(
            f"/api/v1/exchange/requests/{rid}/cancel", headers=other
        )
    ).status_code == 404
    c = await async_client.post(f"/api/v1/exchange/requests/{rid}/cancel", headers=cust)
    assert c.json()["status"] == "CANCELLED"
    late = await async_client.post(
        f"/api/v1/retailer/exchange/requests/{rid}/bids",
        headers=rh,
        json={
            "lines": [
                {
                    "manifest_index": 0,
                    "listing_id": listing["id"],
                    "unit_price_paise": 100,
                }
            ],
            "estimated_delivery_hours": 1,
        },
    )
    assert late.status_code == 409
    adm = (
        await async_client.get(
            "/api/v1/admin/exchange/requests",
            headers=admin,
            params={"status": "CANCELLED"},
        )
    ).json()
    assert any(i["id"] == rid for i in adm["items"])
