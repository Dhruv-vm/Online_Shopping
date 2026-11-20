"""Phase 3I Handwritten List to Basket (optional)."""

import base64
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.modules.vision.parser import parse_list
from tests.phase3_helpers import make_retailer, make_user

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


def test_parser_quantities_units_and_vernacular():
    items = parse_list(
        "1kg Aashirvaad Atta, 500g Amul Butter\nDettol soap 3pc\n2 x Maggi\n- दूध 2 packets"
    )
    got = [(i.name, i.quantity, i.size) for i in items]
    assert got[0] == ("Aashirvaad Atta", 1, "1kg")
    assert got[1] == ("Amul Butter", 1, "500g")
    assert got[2] == ("Dettol soap", 3, None)
    assert got[3] == ("Maggi", 2, None)
    assert items[4].quantity == 2 and items[4].search_query == "milk"


@pytest.mark.asyncio
async def test_photo_without_provider_never_fabricates(async_client: AsyncClient):
    _, cust = await make_user()
    r = await async_client.post(
        "/api/v1/vision/parse-list",
        headers=cust,
        json={"image_base64": PNG, "content_type": "image/png"},
    )
    assert (
        r.status_code == 503 and r.json()["error"]["code"] == "OCR_PROVIDER_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_image_validation(async_client: AsyncClient):
    _, cust = await make_user()
    url = "/api/v1/vision/parse-list"
    assert (
        await async_client.post(
            url, headers=cust, json={"image_base64": PNG, "content_type": "image/jpeg"}
        )
    ).status_code == 422
    assert (
        await async_client.post(
            url, headers=cust, json={"image_base64": "%%%", "content_type": "image/png"}
        )
    ).status_code == 422
    assert (
        await async_client.post(
            url,
            headers=cust,
            json={"image_base64": PNG, "content_type": "image/png", "text": "milk"},
        )
    ).status_code == 422
    big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024)).decode()
    assert (
        await async_client.post(
            url, headers=cust, json={"image_base64": big, "content_type": "image/png"}
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_text_list_match_review_and_build_cart(async_client: AsyncClient):
    tag = uuid.uuid4().hex[:6]
    listing, _ = await make_retailer(
        product_name=f"Zorbo{tag} Soap",
        selling_price_paise=5000,
        original_price_paise=5000,
    )
    _, cust = await make_user()
    r = await async_client.post(
        "/api/v1/vision/parse-list",
        headers=cust,
        json={"text": f"Zorbo{tag} soap 3pc\nnonexistentthing{tag}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "TEXT" and body["unmatched_count"] == 1
    first = body["items"][0]
    assert first["quantity"] == 3 and first["suggested_listing_id"] == listing["id"]

    b = await async_client.post(
        "/api/v1/vision/build-cart",
        headers=cust,
        json={
            "items": [
                {"listing_id": listing["id"], "quantity": 3},
                {"listing_id": str(uuid.uuid4()), "quantity": 1},
            ]
        },
    )
    assert (
        b.status_code == 200
        and b.json()["added"] == 1
        and b.json()["skipped"][0]["reason"] == "UNAVAILABLE"
    )
    cart = (await async_client.get("/api/v1/cart", headers=cust)).json()
    assert any(
        i["listing_id"] == listing["id"] and i["quantity"] == 3 for i in cart["items"]
    )
    none = await async_client.post(
        "/api/v1/vision/build-cart",
        headers=cust,
        json={"items": [{"listing_id": str(uuid.uuid4()), "quantity": 1}]},
    )
    assert none.status_code == 409


@pytest.mark.asyncio
async def test_http_provider_adapter_and_rbac(async_client: AsyncClient):
    from app.core.config import settings
    from app.modules.vision import providers

    _, cust = await make_user()
    _, ret = await make_user("retailer")
    assert (
        await async_client.post(
            "/api/v1/vision/parse-list", headers=ret, json={"text": "milk"}
        )
    ).status_code == 403
    assert (
        await async_client.post("/api/v1/vision/parse-list", json={"text": "milk"})
    ).status_code == 401

    async def fake_extract(self, image_base64, content_type):
        assert image_base64 == PNG and content_type == "image/png"
        return "2 x milk"

    with (
        patch.object(settings, "OCR_PROVIDER", "http"),
        patch.object(settings, "OCR_PROVIDER_URL", "https://ocr.invalid/v1"),
        patch.object(providers.HttpOCRProvider, "extract_text", fake_extract),
    ):
        r = await async_client.post(
            "/api/v1/vision/parse-list",
            headers=cust,
            json={"image_base64": PNG, "content_type": "image/png"},
        )
    assert (
        r.status_code == 200
        and r.json()["source"] == "OCR"
        and r.json()["provider"] == "http"
    )
    assert r.json()["items"][0]["quantity"] == 2


@pytest.mark.asyncio
async def test_status_and_provider_confidence_passthrough(async_client: AsyncClient):
    from app.core.config import settings
    from app.modules.vision import providers

    st = (await async_client.get("/api/v1/vision/status")).json()
    assert st["ocr_available"] is False and st["manual_fallback"] is True

    _, cust = await make_user()

    async def fake_extract(self, image_base64, content_type):
        return providers.OCRResult(
            text="2 x milk\nsugar 1kg",
            confidence=0.81,
            line_confidence={"2 x milk": 0.93, "sugar 1kg": 0.42},
        )

    with (
        patch.object(settings, "OCR_PROVIDER", "http"),
        patch.object(settings, "OCR_PROVIDER_URL", "https://ocr.invalid/v1"),
        patch.object(providers.HttpOCRProvider, "extract", fake_extract),
    ):
        assert (await async_client.get("/api/v1/vision/status")).json()["ocr_available"]
        r = await async_client.post(
            "/api/v1/vision/parse-list",
            headers=cust,
            json={"image_base64": PNG, "content_type": "image/png"},
        )
    body = r.json()
    assert body["ocr_confidence"] == 0.81 and body["manual_entry"] is False
    by_line = {i["line"]: i for i in body["items"]}
    assert by_line["2 x milk"]["ocr_confidence"] == 0.93
    assert by_line["sugar 1kg"]["ocr_confidence"] == 0.42
    assert by_line["sugar 1kg"]["needs_review"] is True

    typed = await async_client.post(
        "/api/v1/vision/parse-list", headers=cust, json={"text": "milk"}
    )
    assert typed.json()["manual_entry"] is True
    assert typed.json()["items"][0]["ocr_confidence"] is None
