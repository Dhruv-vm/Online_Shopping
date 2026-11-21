"""Deal assistant: answers only from live catalogue data."""

import uuid

import pytest
from httpx import AsyncClient

from app.modules.assistant.service import parse_intent
from tests.phase3_helpers import add_listing_for_retailer, make_retailer


def test_intent_parsing_budget_quantity_and_flags():
    i = parse_intent("Show me the cheapest wireless headphones under ₹15,000")
    assert i.budget_paise == 1_500_000 and i.wants_cheapest
    assert "headphones" in i.query and "under" not in i.query
    assert parse_intent("air fryer below 8k").budget_paise == 800_000
    assert parse_intent("2 pcs notebook").quantity == 2
    j = parse_intent("can I negotiate a deal on a mixer grinder? alternatives too")
    assert j.wants_negotiation and j.wants_alternatives and "mixer" in j.query


@pytest.mark.asyncio
async def test_assistant_compares_real_listings_and_respects_budget(
    async_client: AsyncClient,
):
    tag = uuid.uuid4().hex[:6]
    cheap, _ = await make_retailer(
        product_name=f"Quixotic{tag} Kettle",
        selling_price_paise=120000,
        original_price_paise=150000,
    )
    other, _ = await make_retailer(selling_price_paise=1000, original_price_paise=1000)
    await add_listing_for_retailer(
        other["retailer_id"], cheap["variant_id"], selling_price_paise=135000
    )

    r = await async_client.post(
        "/api/v1/assistant/chat",
        json={"message": f"compare quixotic{tag} kettle under 1300"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "rule_based" and body["ai_provider_configured"] is False
    assert body["understood"]["budget_paise"] == 130000
    opt = body["options"][0]
    assert [s["price_paise"] for s in opt["sellers"]] == [120000, 135000]
    assert opt["within_budget"] is True
    assert "2 stores sell this" in opt["explanation"]

    over = (
        await async_client.post(
            "/api/v1/assistant/chat",
            json={"message": f"quixotic{tag} kettle under 500"},
        )
    ).json()
    assert over["options"] == []
    assert "over budget" in over["message"]

    none = (
        await async_client.post(
            "/api/v1/assistant/chat", json={"message": f"zzunobtainium{tag}"}
        )
    ).json()
    assert none["options"] == [] and "couldn't find" in none["message"]
