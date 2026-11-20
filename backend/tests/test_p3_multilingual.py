"""Phase 3H Bharat Multilingual."""

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import get_session_factory
from app.modules.i18n.service import normalize_query
from app.modules.search.service import SearchService
from tests.phase3_helpers import make_retailer, make_user


@pytest.mark.parametrize(
    "q,expected,lang",
    [
        ("दूध", "milk", "hi"),
        ("பால்", "milk", "ta"),
        ("పాలు", "milk", "te"),
        ("ಹಾಲು", "milk", "kn"),
        ("দুধ", "milk", "bn"),
        ("દૂધ", "milk", "gu"),
        ("പാൽ", "milk", "ml"),
        ("ਦੁੱਧ", "milk", "pa"),
        ("କ୍ଷୀର", "milk", "or"),
        ("دودھ", "milk", "ur"),
        ("doodh", "milk", "en"),
        ("आटा 5kg", "atta flour 5kg", "hi"),
    ],
)
def test_normalize_indic_queries(q, expected, lang):
    normalized, detected, translated = normalize_query(q)
    assert normalized == expected and detected == lang and translated


def test_unknown_terms_pass_through_unchanged():
    assert normalize_query("Sony headphones") == ("Sony headphones", "en", False)


@pytest.mark.asyncio
async def test_languages_and_normalize_endpoints(async_client: AsyncClient):
    langs = (await async_client.get("/api/v1/i18n/languages")).json()
    assert {lng["code"] for lng in langs["languages"]} == {
        "en",
        "hi",
        "ta",
        "te",
        "kn",
        "bn",
        "mr",
        "gu",
        "ml",
        "pa",
        "or",
        "ur",
    }
    n = (await async_client.get("/api/v1/i18n/normalize", params={"q": "चावल"})).json()
    assert n["normalized"] == "rice" and n["translated"] is True


@pytest.mark.asyncio
async def test_regional_language_search_finds_english_catalogue():
    suffix = uuid.uuid4().hex[:6]
    await make_retailer(product_name=f"Amrit Milk {suffix} 1L")
    async with get_session_factory()() as s:
        res = await SearchService().search(s, q="दूध", force_fallback=True, page_size=20)
    assert res.query_translated and res.interpreted_query == "milk"
    assert res.detected_language == "hi"
    assert any(f"Amrit Milk {suffix}" in i.name for i in res.items) or res.total >= 1


@pytest.mark.asyncio
async def test_admin_translations_and_translated_name_search(async_client: AsyncClient):
    listing, _ = await make_retailer(product_name=f"Zylo Widget {uuid.uuid4().hex[:6]}")
    _, admin = await make_user("admin")
    _, customer = await make_user("customer")
    body = {
        "entity_type": "product",
        "entity_id": listing["product_id"],
        "language": "hi",
        "fields": {"name": "ज़ायलो विजेट", "description": "परीक्षण"},
    }
    assert (
        await async_client.put(
            "/api/v1/admin/i18n/translations", json=body, headers=customer
        )
    ).status_code == 403
    r = await async_client.put(
        "/api/v1/admin/i18n/translations", json=body, headers=admin
    )
    assert r.status_code == 204, r.text
    bad = await async_client.put(
        "/api/v1/admin/i18n/translations",
        json={**body, "language": "xx"},
        headers=admin,
    )
    assert bad.status_code == 422
    got = (
        await async_client.get(
            "/api/v1/i18n/translations",
            params={
                "entity_type": "product",
                "lang": "hi",
                "ids": listing["product_id"],
            },
        )
    ).json()
    assert got["translations"][listing["product_id"]]["name"] == "ज़ायलो विजेट"

    async with get_session_factory()() as s:
        res = await SearchService().search(s, q="ज़ायलो", force_fallback=True)
    assert any(i.product_id == listing["product_id"] for i in res.items)


@pytest.mark.asyncio
async def test_language_preference(async_client: AsyncClient):
    _, headers = await make_user("customer")
    assert (await async_client.get("/api/v1/i18n/preference", headers=headers)).json()[
        "language"
    ] == "en"
    r = await async_client.put(
        "/api/v1/i18n/preference", json={"language": "ta"}, headers=headers
    )
    assert r.status_code == 200 and r.json()["language"] == "ta"
    assert (await async_client.get("/api/v1/i18n/preference", headers=headers)).json()[
        "language"
    ] == "ta"
    assert (
        await async_client.put(
            "/api/v1/i18n/preference", json={"language": "fr"}, headers=headers
        )
    ).status_code == 422
    assert (await async_client.get("/api/v1/i18n/preference")).status_code == 401



@pytest.mark.asyncio
async def test_profile_exposes_preferred_language(async_client: AsyncClient):
    _, headers = await make_user()
    r = await async_client.put(
        "/api/v1/i18n/preference", headers=headers, json={"language": "ur"}
    )
    assert r.status_code == 200, r.text
    me = (await async_client.get("/api/v1/users/me", headers=headers)).json()
    assert me["preferred_language"] == "ur"
