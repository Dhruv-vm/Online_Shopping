from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.identity.models import User
from app.modules.identity.security import create_access_token, hash_password

_created_test_listing_ids: set[uuid.UUID] = set()


@pytest.fixture(autouse=True)
async def cleanup_passport_test_listings():
    assert settings.ENVIRONMENT != "production", (
        "Passport tests cannot run against production environment"
    )
    yield
    session_factory = get_session_factory()
    if session_factory and _created_test_listing_ids:
        async with session_factory() as session:
            stmt = (
                update(ProductListing)
                .where(ProductListing.id.in_(list(_created_test_listing_ids)))
                .values(is_active=False)
            )
            await session.execute(stmt)
            await session.commit()
        _created_test_listing_ids.clear()


async def create_user_with_role(
    role: str = "customer", prefix: str = "user"
) -> tuple[User, str]:
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    user_id = uuid.uuid4()
    email = f"{prefix}_{suffix}@example.com"

    async with session_factory() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password=hash_password("SecurePassword123!"),
            full_name=f"{prefix.capitalize()} Tester",
            phone=f"+919{uuid.uuid4().int % 1000000000:09d}",
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role=role)
    return user, token


async def create_retailer_store(user: User, name: str = "Test Store") -> Retailer:
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:6]
    async with session_factory() as session:
        retailer = Retailer(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"{name} {suffix}",
            slug=f"store-{suffix}",
            description="A verified partner store",
            rating=4.9,
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        session.add(retailer)
        await session.commit()
        await session.refresh(retailer)
        return retailer


async def create_test_product_and_listing(
    retailer: Retailer,
    product_name: str = "Premium Organic Coffee",
    brand: str = "Blue Mountain",
) -> tuple[Product, ProductListing]:
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]

    async with session_factory() as session:
        cat_res = await session.execute(select(Category).limit(1))
        category = cat_res.scalar_one_or_none()
        if not category:
            category = Category(
                name="Beverages",
                slug=f"beverages-{suffix}",
                description="Hot and cold drinks",
                is_active=True,
            )
            session.add(category)
            await session.flush()

        product = Product(
            category_id=category.id,
            name=f"{product_name} {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            description="Artisanal freshly roasted whole beans.",
            is_active=True,
        )
        session.add(product)
        await session.flush()

        variant = ProductVariant(
            product_id=product.id,
            name="500g Pack",
            sku=f"SKU-{suffix}",
            attributes={"weight": "500g"},
            is_active=True,
        )
        session.add(variant)
        await session.flush()

        listing = ProductListing(
            retailer_id=retailer.id,
            variant_id=variant.id,
            seller_sku=f"SELLER-{suffix}",
            original_price_paise=120000,
            selling_price_paise=99900,
            currency="INR",
            is_active=True,
        )
        session.add(listing)
        await session.flush()

        inv = StoreInventory(
            listing_id=listing.id,
            on_hand_quantity=50,
            reserved_quantity=0,
            low_stock_threshold=5,
        )
        session.add(inv)
        await session.commit()

        _created_test_listing_ids.add(listing.id)
        return product, listing


@pytest.mark.asyncio
async def test_public_passport_missing_returns_safe_empty(async_client: AsyncClient):
    """Customer retrieving a product without a passport gets a safe empty baseline."""
    user, _ = await create_user_with_role(role="retailer", prefix="ret1")
    retailer = await create_retailer_store(user, name="Coffee Roasters")
    product, listing = await create_test_product_and_listing(retailer)

    resp = await async_client.get(f"/api/v1/products/{product.id}/passport")
    assert resp.status_code == 200
    data = resp.json()

    assert data["product_id"] == str(product.id)
    assert data["product_name"] == product.name
    assert data["brand"] == product.brand
    assert data["manufacturer"] is None
    assert data["materials"] == []
    assert data["technical_specs"] == {}
    assert data["claims"] == []
    assert len(data["available_listings"]) >= 1
    assert data["available_listings"][0]["listing_id"] == str(listing.id)


@pytest.mark.asyncio
async def test_admin_upsert_canonical_product_passport(async_client: AsyncClient):
    """Admin can configure canonical product specifications, unauthorized users are blocked."""
    _, admin_token = await create_user_with_role(role="admin", prefix="adm")
    user, cust_token = await create_user_with_role(role="customer", prefix="cust")
    ret_user, _ = await create_user_with_role(role="retailer", prefix="ret2")
    retailer = await create_retailer_store(ret_user, name="Tech Hub")
    product, _ = await create_test_product_and_listing(
        retailer, product_name="Noise Cancelling Headphones", brand="AcoustiQ"
    )

    upsert_payload = {
        "manufacturer": "AcoustiQ Audio Ltd.",
        "country_of_origin": "India",
        "model_number": "AQ-NC900",
        "gtin_ean_upc": "8901234567890",
        "materials": ["Aluminium", "Memory Foam", "Protein Leather"],
        "technical_specs": {
            "driver_size_mm": 40,
            "battery_life_hours": 35,
            "bluetooth_version": "5.3",
        },
        "package_contents": [
            "Headphones",
            "USB-C Cable",
            "3.5mm Audio Cable",
            "Carry Case",
        ],
        "usage_instructions": "Press and hold power button for 3 seconds to pair.",
        "safety_instructions": "Avoid prolonged listening at maximum volume levels.",
        "warranty_info": "1 Year Manufacturer Limited Hardware Warranty",
        "certifications": ["BIS", "CE", "RoHS"],
    }

    # 1. Customer cannot update canonical passport
    cust_resp = await async_client.put(
        f"/api/v1/admin/passport/products/{product.id}",
        json=upsert_payload,
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert cust_resp.status_code == 403

    # 2. Admin successfully updates canonical passport
    admin_resp = await async_client.put(
        f"/api/v1/admin/passport/products/{product.id}",
        json=upsert_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
    data = admin_resp.json()
    assert data["manufacturer"] == "AcoustiQ Audio Ltd."
    assert data["country_of_origin"] == "India"
    assert data["technical_specs"]["battery_life_hours"] == 35

    # 3. Public customer endpoint reflects canonical passport
    public_resp = await async_client.get(f"/api/v1/products/{product.id}/passport")
    assert public_resp.status_code == 200
    pub_data = public_resp.json()
    assert pub_data["manufacturer"] == "AcoustiQ Audio Ltd."
    assert pub_data["model_number"] == "AQ-NC900"
    assert "Aluminium" in pub_data["materials"]


@pytest.mark.asyncio
async def test_retailer_listing_passport_upsert_and_isolation(
    async_client: AsyncClient,
):
    """Retailer can manage own listing passport; cross-retailer access is strictly forbidden."""
    ret1_user, ret1_token = await create_user_with_role(
        role="retailer", prefix="seller1"
    )
    ret1 = await create_retailer_store(ret1_user, name="Retailer One")

    ret2_user, ret2_token = await create_user_with_role(
        role="retailer", prefix="seller2"
    )
    await create_retailer_store(ret2_user, name="Retailer Two")

    product, listing1 = await create_test_product_and_listing(ret1)

    upsert_body = {
        "item_condition": "REFURBISHED",
        "seller_warranty": "6 Months Seller Replacement Warranty",
        "packaging_notes": "Shipped in discreet certified recycled packaging",
        "fulfillment_notes": "Dispatched within 24 hours from Bengaluru warehouse",
    }

    # 1. Retailer 2 cannot mutate Retailer 1's listing passport (Anti-IDOR)
    cross_resp = await async_client.put(
        f"/api/v1/retailer/passport/listings/{listing1.id}",
        json=upsert_body,
        headers={"Authorization": f"Bearer {ret2_token}"},
    )
    assert cross_resp.status_code == 403

    # 2. Retailer 1 can update own listing passport
    own_resp = await async_client.put(
        f"/api/v1/retailer/passport/listings/{listing1.id}",
        json=upsert_body,
        headers={"Authorization": f"Bearer {ret1_token}"},
    )
    assert own_resp.status_code == 200
    data = own_resp.json()
    assert data["item_condition"] == "REFURBISHED"
    assert data["seller_warranty"] == "6 Months Seller Replacement Warranty"

    # 3. Public customer endpoint retrieves listing details when listing_id is queried
    pub_resp = await async_client.get(
        f"/api/v1/products/{product.id}/passport?listing_id={listing1.id}"
    )
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["listing_passport"] is not None
    assert pub_data["listing_passport"]["item_condition"] == "REFURBISHED"
    assert (
        pub_data["listing_passport"]["seller_warranty"]
        == "6 Months Seller Replacement Warranty"
    )


@pytest.mark.asyncio
async def test_retailer_claim_lifecycle_and_retrigger_review(async_client: AsyncClient):
    """Claims start PENDING, admin verifies/rejects, and editing re-triggers PENDING status."""
    _, admin_token = await create_user_with_role(role="admin", prefix="adm_claims")
    ret_user, ret_token = await create_user_with_role(
        role="retailer", prefix="seller_claims"
    )
    retailer = await create_retailer_store(ret_user, name="Spice Emporium")
    product, listing = await create_test_product_and_listing(retailer)

    # 1. Retailer submits a claim
    claim_payload = {
        "claim_scope": "LISTING",
        "claim_type": "CERTIFICATION",
        "claim_key": "agmark_grade",
        "claim_value": "Agmark Special Grade Certified",
        "evidence_url": "https://agmark.gov.in/certificate/AGM-99214.pdf",
        "evidence_type": "CERTIFICATE",
        "evidence_notes": "Official Agmark compliance certificate issued Oct 2026",
        "is_public_evidence": True,
    }

    create_resp = await async_client.post(
        f"/api/v1/retailer/passport/listings/{listing.id}/claims",
        json=claim_payload,
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert create_resp.status_code == 201
    claim_data = create_resp.json()
    claim_id = claim_data["id"]
    assert claim_data["review_status"] == "PENDING"
    assert claim_data["rejection_reason"] is None

    # 2. Retailer cannot self-verify (forbidden on admin endpoint)
    self_verify_resp = await async_client.post(
        f"/api/v1/admin/passport/claims/{claim_id}/verify",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert self_verify_resp.status_code == 403

    # 3. Admin rejects claim with mandatory reason
    reject_fail = await async_client.post(
        f"/api/v1/admin/passport/claims/{claim_id}/reject",
        json={"rejection_reason": "   "},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject_fail.status_code == 422

    reject_resp = await async_client.post(
        f"/api/v1/admin/passport/claims/{claim_id}/reject",
        json={"rejection_reason": "Certificate number mismatch with Agmark portal"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["review_status"] == "REJECTED"
    assert (
        reject_resp.json()["rejection_reason"]
        == "Certificate number mismatch with Agmark portal"
    )

    # Retailer can see rejection reason in retailer portal
    ret_claims_resp = await async_client.get(
        "/api/v1/retailer/passport/claims",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert ret_claims_resp.status_code == 200
    my_claims = ret_claims_resp.json()
    assert any(
        c["id"] == claim_id
        and c["review_status"] == "REJECTED"
        and "mismatch" in c["rejection_reason"]
        for c in my_claims
    )

    # 4. Retailer edits claim -> re-triggers PENDING review status, increments version, preserves prior rejection feedback
    update_resp = await async_client.put(
        f"/api/v1/retailer/passport/claims/{claim_id}",
        json={
            "claim_value": "Agmark Special Grade Certified - Corrected",
            "evidence_url": "https://agmark.gov.in/certificate/AGM-99215-VALID.pdf",
        },
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["review_status"] == "PENDING"
    assert updated_data["version"] == 2
    # Prior rejection feedback is preserved so retailer understands what was corrected
    assert (
        updated_data["rejection_reason"]
        == "Certificate number mismatch with Agmark portal"
    )
    assert len(updated_data["review_history"]) >= 2
    assert updated_data["review_history"][0]["action"] == "REVISED"
    assert updated_data["review_history"][0]["review_status"] == "PENDING"
    assert updated_data["review_history"][1]["action"] == "REJECTED"
    assert updated_data["review_history"][1]["review_status"] == "REJECTED"

    # Retailer can inspect complete claim review history
    ret_hist_resp = await async_client.get(
        f"/api/v1/retailer/passport/claims/{claim_id}/history",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert ret_hist_resp.status_code == 200
    ret_history = ret_hist_resp.json()
    assert len(ret_history) >= 2
    assert ret_history[0]["action"] == "REVISED"

    # 5. Admin verifies the corrected claim
    verify_resp = await async_client.post(
        f"/api/v1/admin/passport/claims/{claim_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["review_status"] == "VERIFIED"
    assert verify_resp.json()["rejection_reason"] is None

    # Admin inspects complete history
    adm_hist_resp = await async_client.get(
        f"/api/v1/admin/passport/claims/{claim_id}/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert adm_hist_resp.status_code == 200
    adm_history = adm_hist_resp.json()
    assert len(adm_history) >= 3
    assert adm_history[0]["action"] == "VERIFIED"
    assert adm_history[0]["review_status"] == "VERIFIED"
    assert adm_history[1]["action"] == "REVISED"
    assert adm_history[2]["action"] == "REJECTED"
    assert (
        adm_history[2]["rejection_reason"]
        == "Certificate number mismatch with Agmark portal"
    )

    # 6. Customer can view verified claim and public evidence
    pub_resp = await async_client.get(
        f"/api/v1/products/{product.id}/passport?listing_id={listing.id}"
    )
    assert pub_resp.status_code == 200
    pub_claims = pub_resp.json()["listing_passport"]["claims"]
    verified_claim = next(c for c in pub_claims if c["id"] == claim_id)
    assert verified_claim["review_status"] == "VERIFIED"
    assert (
        verified_claim["evidence_url"]
        == "https://agmark.gov.in/certificate/AGM-99215-VALID.pdf"
    )
    # Never leak internal metadata
    assert "submitted_by_user_id" not in verified_claim
    assert "rejection_reason" not in verified_claim


@pytest.mark.asyncio
async def test_customer_privacy_private_evidence_not_exposed(async_client: AsyncClient):
    """Claims marked is_public_evidence=False or unverified never expose evidence URLs or reviewer info."""
    _, admin_token = await create_user_with_role(role="admin", prefix="adm_privacy")
    ret_user, ret_token = await create_user_with_role(
        role="retailer", prefix="seller_privacy"
    )
    retailer = await create_retailer_store(ret_user, name="Private Goods")
    product, listing = await create_test_product_and_listing(retailer)

    # Submit claim with is_public_evidence=False (internal invoice or supplier contract)
    create_resp = await async_client.post(
        f"/api/v1/retailer/passport/listings/{listing.id}/claims",
        json={
            "claim_scope": "LISTING",
            "claim_type": "ORIGIN",
            "claim_key": "import_declaration",
            "claim_value": "Customs cleared directly via Nhava Sheva port",
            "evidence_url": "https://internal-supplier-docs.com/contracts/invoice-confidential-998.pdf",
            "evidence_type": "DOCUMENT",
            "is_public_evidence": False,
        },
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert create_resp.status_code == 201
    claim_id = create_resp.json()["id"]

    # Verify claim by admin
    await async_client.post(
        f"/api/v1/admin/passport/claims/{claim_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Check public endpoint
    pub_resp = await async_client.get(
        f"/api/v1/products/{product.id}/passport?listing_id={listing.id}"
    )
    assert pub_resp.status_code == 200
    pub_claims = pub_resp.json()["listing_passport"]["claims"]
    c = next(x for x in pub_claims if x["id"] == claim_id)
    assert c["review_status"] == "VERIFIED"
    assert c["claim_value"] == "Customs cleared directly via Nhava Sheva port"
    # Strict customer privacy: private evidence URL must NOT be exposed
    assert c["evidence_url"] is None
    assert c["is_public_evidence"] is False


@pytest.mark.asyncio
async def test_invalid_payloads_and_url_schemes_rejected(async_client: AsyncClient):
    """Malicious or invalid URLs (e.g. javascript:) and invalid conditions are rejected."""
    ret_user, ret_token = await create_user_with_role(
        role="retailer", prefix="seller_invalid"
    )
    retailer = await create_retailer_store(ret_user, name="Safety Store")
    _, listing = await create_test_product_and_listing(retailer)

    # 1. Non-http URL scheme
    bad_url_resp = await async_client.post(
        f"/api/v1/retailer/passport/listings/{listing.id}/claims",
        json={
            "claim_scope": "LISTING",
            "claim_type": "SPECIFICATION",
            "claim_key": "speed",
            "claim_value": "High speed",
            "evidence_url": "javascript:alert(document.cookie)",
        },
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert bad_url_resp.status_code == 422

    # 2. Invalid condition enum
    bad_cond_resp = await async_client.put(
        f"/api/v1/retailer/passport/listings/{listing.id}",
        json={"item_condition": "TOTALLY_DESTROYED"},
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert bad_cond_resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_claim_queue_pagination_and_filtering(async_client: AsyncClient):
    """Admin claim queue supports pagination and filtering by review status and claim scope."""
    _, admin_token = await create_user_with_role(role="admin", prefix="adm_queue")
    ret_user, ret_token = await create_user_with_role(
        role="retailer", prefix="seller_queue"
    )
    retailer = await create_retailer_store(ret_user, name="Queue Store")
    _, listing = await create_test_product_and_listing(retailer)

    # Submit 3 claims
    for i in range(3):
        await async_client.post(
            f"/api/v1/retailer/passport/listings/{listing.id}/claims",
            json={
                "claim_scope": "LISTING",
                "claim_type": "SPECIFICATION",
                "claim_key": f"queue_feature_{i}",
                "claim_value": f"Value {i}",
            },
            headers={"Authorization": f"Bearer {ret_token}"},
        )

    queue_resp = await async_client.get(
        "/api/v1/admin/passport/queue?status=PENDING&limit=2&page=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert queue_resp.status_code == 200
    q_data = queue_resp.json()
    assert len(q_data["items"]) == 2
    assert q_data["total"] >= 3
    assert q_data["page"] == 1
    assert q_data["pages"] >= 2


@pytest.mark.asyncio
async def test_cross_retailer_claim_mutation_forbidden(async_client: AsyncClient):
    """Retailer cannot edit claims submitted by another retailer."""
    ret1_user, ret1_token = await create_user_with_role(
        role="retailer", prefix="seller_own"
    )
    ret1 = await create_retailer_store(ret1_user, name="Owner Store")

    ret2_user, ret2_token = await create_user_with_role(
        role="retailer", prefix="seller_attacker"
    )
    await create_retailer_store(ret2_user, name="Attacker Store")

    _, listing = await create_test_product_and_listing(ret1)

    create_resp = await async_client.post(
        f"/api/v1/retailer/passport/listings/{listing.id}/claims",
        json={
            "claim_scope": "LISTING",
            "claim_type": "ORIGIN",
            "claim_key": "origin",
            "claim_value": "Wayanad, Kerala",
        },
        headers={"Authorization": f"Bearer {ret1_token}"},
    )
    assert create_resp.status_code == 201
    claim_id = create_resp.json()["id"]

    # Retailer 2 attempts to modify Retailer 1's claim -> 403 Forbidden
    attack_resp = await async_client.put(
        f"/api/v1/retailer/passport/claims/{claim_id}",
        json={"claim_value": "Malicious Tampered Value"},
        headers={"Authorization": f"Bearer {ret2_token}"},
    )
    assert attack_resp.status_code == 403


@pytest.mark.asyncio
async def test_nonexistent_product_or_listing_404(async_client: AsyncClient):
    """Querying non-existent products or listings gracefully returns 404."""
    random_uuid = uuid.uuid4()
    p_resp = await async_client.get(f"/api/v1/products/{random_uuid}/passport")
    assert p_resp.status_code == 404

    lst_resp = await async_client.get(f"/api/v1/passport/listings/{random_uuid}")
    assert lst_resp.status_code == 404


@pytest.mark.asyncio
async def test_public_listing_passport_visibility_rules(async_client: AsyncClient):
    """Public passport strictly enforces catalogue visibility: inactive listings and unverified/suspended retailers are hidden."""
    session_factory = get_session_factory()
    ret_user, _ = await create_user_with_role(role="retailer", prefix="seller_vis")
    retailer = await create_retailer_store(ret_user, name="Visibility Store")
    product, listing = await create_test_product_and_listing(retailer)

    # 1. Active listing and verified retailer: publicly visible
    lst_resp = await async_client.get(f"/api/v1/passport/listings/{listing.id}")
    assert lst_resp.status_code == 200

    p_resp = await async_client.get(f"/api/v1/products/{product.id}/passport")
    assert p_resp.status_code == 200
    assert any(
        item["listing_id"] == str(listing.id)
        for item in p_resp.json()["available_listings"]
    )

    # 2. Deactivate listing: must return 404 and disappear from PDP available listings
    async with session_factory() as session:
        await session.execute(
            update(ProductListing)
            .where(ProductListing.id == listing.id)
            .values(is_active=False)
        )
        await session.commit()

    lst_resp_inactive = await async_client.get(
        f"/api/v1/passport/listings/{listing.id}"
    )
    assert lst_resp_inactive.status_code == 404

    p_resp_inactive = await async_client.get(
        f"/api/v1/products/{product.id}/passport?listing_id={listing.id}"
    )
    assert p_resp_inactive.status_code == 200
    assert p_resp_inactive.json()["listing_passport"] is None
    assert not any(
        item["listing_id"] == str(listing.id)
        for item in p_resp_inactive.json()["available_listings"]
    )

    # 3. Reactivate listing but set retailer verification_status to PENDING: must be hidden
    async with session_factory() as session:
        await session.execute(
            update(ProductListing)
            .where(ProductListing.id == listing.id)
            .values(is_active=True)
        )
        await session.execute(
            update(Retailer)
            .where(Retailer.id == retailer.id)
            .values(verification_status="PENDING")
        )
        await session.commit()

    lst_resp_pending = await async_client.get(f"/api/v1/passport/listings/{listing.id}")
    assert lst_resp_pending.status_code == 404

    # 4. Set retailer verification_status to SUSPENDED: must also be hidden
    async with session_factory() as session:
        await session.execute(
            update(Retailer)
            .where(Retailer.id == retailer.id)
            .values(verification_status="SUSPENDED")
        )
        await session.commit()

    lst_resp_suspended = await async_client.get(
        f"/api/v1/passport/listings/{listing.id}"
    )
    assert lst_resp_suspended.status_code == 404


@pytest.mark.asyncio
async def test_claim_review_history_cross_retailer_authorization(
    async_client: AsyncClient,
):
    """Retailers can only view history for their own claims; cross-retailer history access is 403 Forbidden."""
    ret1_user, ret1_token = await create_user_with_role(
        role="retailer", prefix="hist_own"
    )
    ret1 = await create_retailer_store(ret1_user, name="History Owner Store")

    ret2_user, ret2_token = await create_user_with_role(
        role="retailer", prefix="hist_atk"
    )
    await create_retailer_store(ret2_user, name="History Attacker Store")

    _, listing = await create_test_product_and_listing(ret1)

    create_resp = await async_client.post(
        f"/api/v1/retailer/passport/listings/{listing.id}/claims",
        json={
            "claim_scope": "LISTING",
            "claim_type": "WARRANTY",
            "claim_key": "extended_care",
            "claim_value": "Includes 2-year on-site accidental protection",
        },
        headers={"Authorization": f"Bearer {ret1_token}"},
    )
    assert create_resp.status_code == 201
    claim_id = create_resp.json()["id"]

    # Retailer 2 attempts to view Retailer 1's claim history -> 403 Forbidden
    cross_resp = await async_client.get(
        f"/api/v1/retailer/passport/claims/{claim_id}/history",
        headers={"Authorization": f"Bearer {ret2_token}"},
    )
    assert cross_resp.status_code == 403

    # Retailer 1 can view own claim history
    own_resp = await async_client.get(
        f"/api/v1/retailer/passport/claims/{claim_id}/history",
        headers={"Authorization": f"Bearer {ret1_token}"},
    )
    assert own_resp.status_code == 200
    assert len(own_resp.json()) >= 1
