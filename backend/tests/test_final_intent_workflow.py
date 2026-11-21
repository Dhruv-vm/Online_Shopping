"""Final cycle Part 6: the customer intent workflow uses only real data."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import get_session_factory
from app.modules.demand.models import DemandSignal
from tests.phase3_helpers import make_retailer, make_user

PIN = "560034"


@pytest.mark.asyncio
async def test_grocery_intent_matches_real_listings_and_records_gaps_once(
    async_client: AsyncClient,
):
    tag = uuid.uuid4().hex[:6]
    rice, _ = await make_retailer(
        service_pincodes=[PIN],
        product_name=f"Zorbix Rice {tag}",
        selling_price_paise=60000,
        original_price_paise=65000,
    )
    # A store that does not serve the PIN must not count as a match.
    await make_retailer(service_pincodes=["110001"], product_name=f"Zorbix Atta {tag}")
    _, cust = await make_user()
    body = {
        "title": "Monthly groceries",
        "items": [
            {"name": f"Zorbix Rice {tag}", "quantity": 2},
            {"name": f"Zorbix Atta {tag}", "quantity": 1},
            {"name": f"Qelvane dal {tag}", "quantity": 1},
        ],
        "budget_paise": 400000,
        "frequency": "MONTHLY",
        "pincode": PIN,
    }
    r = await async_client.post("/api/v1/intent/workflow", headers=cust, json=body)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] == "PARTIALLY_MATCHED" and j["updated_existing"] is False
    by = {i["name"]: i for i in j["items"]}
    rice_r = by[f"Zorbix Rice {tag}"]
    assert (
        rice_r["status"] == "AVAILABLE"
        and rice_r["matches"][0]["listing_id"] == rice["id"]
    )
    assert rice_r["retailer_count"] == 1 and rice_r["demand"] is None
    atta = by[f"Zorbix Atta {tag}"]
    assert (
        atta["status"] == "NOT_AVAILABLE" and atta["matches"] == []
    )  # store outside the PIN
    assert atta["demand"]["signal_recorded_now"] is True
    assert j["cheapest_total_paise"] == 120000 and j["within_budget"] is True
    assert j["can_create_basket"] is True

    # Resubmitting the same intent updates it and does not add demand records.
    again = (
        await async_client.post("/api/v1/intent/workflow", headers=cust, json=body)
    ).json()
    assert (
        again["updated_existing"] is True
        and again["intention"]["id"] == j["intention"]["id"]
    )
    assert all(
        (i["demand"] is None) or i["demand"]["signal_recorded_now"] is False
        for i in again["items"]
    )
    async with get_session_factory()() as s:
        n = (
            await s.execute(
                select(func.count())
                .select_from(DemandSignal)
                .where(DemandSignal.query_text.like(f"%{tag}%"))
            )
        ).scalar()
    assert n == 2  # atta + dal, once each

    # Viewing never records demand; creating the basket adds only real matches.
    view = (
        await async_client.get(
            f"/api/v1/intent/workflow/{j['intention']['id']}", headers=cust
        )
    ).json()
    assert view["status"] == "PARTIALLY_MATCHED"
    b = await async_client.post(
        f"/api/v1/intent/workflow/{j['intention']['id']}/basket", headers=cust
    )
    assert b.status_code == 200, b.text
    assert [a["listing_id"] for a in b.json()["added"]] == [rice["id"]]
    cart = (await async_client.get("/api/v1/cart", headers=cust)).json()
    assert {(i["listing_id"], i["quantity"]) for i in cart["items"]} == {
        (rice["id"], 2)
    }


@pytest.mark.asyncio
async def test_single_item_budget_caps_price_and_other_customers_are_isolated(
    async_client: AsyncClient,
):
    tag = uuid.uuid4().hex[:6]
    await make_retailer(
        product_name=f"Kestrova Laptop {tag}",
        selling_price_paise=7500000,
        original_price_paise=8000000,
    )
    cheap, _ = await make_retailer(
        product_name=f"Kestrova Laptop {tag} Lite",
        selling_price_paise=5500000,
        original_price_paise=5900000,
    )
    _, cust = await make_user()
    j = (
        await async_client.post(
            "/api/v1/intent/workflow",
            headers=cust,
            json={
                "title": "Laptop",
                "items": [
                    {
                        "name": f"Kestrova Laptop {tag}",
                        "quantity": 1,
                        "specs": "16GB RAM, 512GB SSD",
                    }
                ],
                "budget_paise": 6000000,
                "frequency": "ONCE",
                "purchase_by": "2026-12-31",
            },
        )
    ).json()
    item = j["items"][0]
    assert item["understood_as"].endswith("(16GB RAM, 512GB SSD)")
    assert [m["listing_id"] for m in item["matches"]] == [
        cheap["id"]
    ]  # over-budget model excluded
    assert j["status"] == "MATCHED" and j["purchase_by"] == "2026-12-31"

    _, other = await make_user()
    r = await async_client.get(
        f"/api/v1/intent/workflow/{j['intention']['id']}", headers=other
    )
    assert r.status_code == 404
