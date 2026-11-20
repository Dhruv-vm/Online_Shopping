"""Retailer onboarding: register -> pending -> documents -> admin approval ->
selling, plus validated media uploads."""

import base64
import uuid

import pytest
from httpx import AsyncClient

from tests.phase3_helpers import make_retailer, make_user

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
PDF = base64.b64encode(b"%PDF-1.4\n%demo\n").decode()


@pytest.mark.asyncio
async def test_onboarding_pending_documents_approval(
    async_client: AsyncClient, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path / "pub"))
    monkeypatch.setattr(settings, "MEDIA_PRIVATE_ROOT", str(tmp_path / "priv"))
    email = f"shop_{uuid.uuid4().hex[:8]}@example.com"
    reg = await async_client.post(
        "/api/v1/auth/retailer/register",
        json={
            "email": email,
            "password": "Str0ngPass!word",
            "full_name": "Anita Rao",
            "phone": "+919811111111",
            "store_name": f"Anita Stores {uuid.uuid4().hex[:4]}",
            "state": "KA",
            "business_address": "12 MG Road, Bengaluru 560001",
        },
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["user"]["role"] == "retailer"
    assert body["user"]["verification_status"] == "PENDING"
    h = {"Authorization": f"Bearer {body['access_token']}"}

    # Pending stores cannot sell yet...
    blocked = await async_client.post(
        "/api/v1/retailer/offers",
        headers=h,
        json={
            "name": "Too early",
            "discount_type": "PERCENTAGE",
            "discount_value": 1000,
        },
    )
    assert blocked.status_code == 403

    # ...but can complete their profile and submit documents.
    bad = await async_client.put(
        "/api/v1/retailer/profile", headers=h, json={"gstin": "12345"}
    )
    assert bad.status_code == 422
    ok = await async_client.put(
        "/api/v1/retailer/profile", headers=h, json={"gstin": "29abcde1234f1z5"}
    )
    assert ok.status_code == 200 and ok.json()["gstin"] == "29ABCDE1234F1Z5"
    doc = await async_client.post(
        "/api/v1/retailer/documents",
        headers=h,
        json={
            "document_type": "GSTIN_CERTIFICATE",
            "document_number": "29ABCDE1234F1Z5",
            "content_base64": PDF,
            "content_type": "application/pdf",
        },
    )
    assert doc.status_code == 201, doc.text
    assert doc.json()["has_file"] is True and doc.json()["status"] == "PENDING"
    fake = await async_client.post(
        "/api/v1/retailer/documents",
        headers=h,
        json={
            "document_type": "PAN",
            "content_base64": PNG,
            "content_type": "application/pdf",
        },
    )
    assert fake.status_code == 422  # declared PDF, content is PNG

    retailer_id = (
        await async_client.get("/api/v1/retailer/profile", headers=h)
    ).json()["id"]
    _, admin = await make_user("admin")
    _, other = await make_user("customer")
    dl = await async_client.get(
        f"/api/v1/admin/retailers/{retailer_id}/documents/{doc.json()['id']}/file",
        headers=admin,
    )
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF-")
    assert (
        await async_client.get(
            f"/api/v1/admin/retailers/{retailer_id}/documents/{doc.json()['id']}/file",
            headers=other,
        )
    ).status_code == 403

    rej = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        headers=admin,
        json={"status": "REJECTED", "rejection_reason": "Address proof missing"},
    )
    assert rej.status_code == 200, rej.text
    prof = (await async_client.get("/api/v1/retailer/profile", headers=h)).json()
    assert prof["verification_status"] == "REJECTED"
    assert prof["rejection_reason"] == "Address proof missing"
    re = await async_client.post("/api/v1/retailer/verification/resubmit", headers=h)
    assert re.status_code == 200 and re.json()["verification_status"] == "PENDING"

    appr = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        headers=admin,
        json={"status": "VERIFIED"},
    )
    assert appr.status_code == 200
    now_ok = await async_client.post(
        "/api/v1/retailer/offers",
        headers=h,
        json={
            "name": "Welcome offer",
            "discount_type": "PERCENTAGE",
            "discount_value": 1000,
        },
    )
    assert now_ok.status_code == 201


@pytest.mark.asyncio
async def test_listing_and_canonical_image_uploads(
    async_client: AsyncClient, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path / "pub"))
    listing, h = await make_retailer(selling_price_paise=10000)
    up = await async_client.put(
        f"/api/v1/retailer/listings/{listing['id']}/image",
        headers=h,
        json={"content_base64": PNG, "content_type": "image/png"},
    )
    assert up.status_code == 200, up.text
    url = up.json()["image_url"]
    assert url.startswith(settings.MEDIA_PUBLIC_BASE_URL) and url.endswith(".png")
    assert (tmp_path / "pub" / "listings" / url.rsplit("/", 1)[1]).is_file()

    wrong = await async_client.put(
        f"/api/v1/retailer/listings/{listing['id']}/image",
        headers=h,
        json={
            "content_base64": base64.b64encode(b"GIF89a....").decode(),
            "content_type": "image/png",
        },
    )
    assert wrong.status_code == 422

    _, admin = await make_user("admin")
    img = await async_client.post(
        f"/api/v1/admin/catalogue/products/{listing['product_id']}/images",
        headers=admin,
        json={"content_base64": PNG, "content_type": "image/png", "make_primary": True},
    )
    assert img.status_code == 201, img.text
    assert img.json()["is_primary"] is True

    monkeypatch.setattr(settings, "MEDIA_STORAGE", "none")
    off = await async_client.put(
        f"/api/v1/retailer/listings/{listing['id']}/image",
        headers=h,
        json={"content_base64": PNG, "content_type": "image/png"},
    )
    assert (
        off.status_code == 503
        and off.json()["error"]["code"] == "MEDIA_STORAGE_UNAVAILABLE"
    )
