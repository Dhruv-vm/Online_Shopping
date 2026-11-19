from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)


async def create_test_listing(
    *,
    retailer_name: str | None = None,
    retailer_state: str = "MH",
    product_name: str | None = None,
    selling_price_paise: int = 2999000,
    original_price_paise: int = 2999000,
    on_hand_quantity: int = 50,
    reserved_quantity: int = 0,
    hsn_code: str = "8518",
    gst_rate_basis_points: int = 1800,
    category_slug: str = "electronics",
    category_name: str = "Electronics",
) -> dict[str, Any]:
    """Create a fully-formed, isolated product listing with verified inventory in the test database."""
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database session factory is not configured.")

    suffix = uuid.uuid4().hex[:8]
    ret_name = retailer_name or f"Test Retailer {suffix}"
    prod_name = product_name or f"Test Product {suffix}"

    async with session_factory() as session:
        # 1. Category
        cat_stmt = select(Category).where(Category.slug == category_slug)
        cat = (await session.execute(cat_stmt)).scalar_one_or_none()
        if cat is None:
            cat = Category(
                id=uuid.uuid4(),
                name=category_name,
                slug=category_slug,
                is_active=True,
            )
            session.add(cat)
            await session.flush()

        # 2. Retailer
        ret_slug = f"test-ret-{suffix}"
        ret = Retailer(
            id=uuid.uuid4(),
            name=ret_name,
            slug=ret_slug,
            rating=4.8,
            state=retailer_state,
            state_source="TEST_FIXTURE",
            is_active=True,
        )
        session.add(ret)
        await session.flush()

        # 3. Product
        prod_slug = f"test-prod-{suffix}"
        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=prod_name,
            slug=prod_slug,
            brand="TestBrand",
            description=f"Description for {prod_name}",
            is_active=True,
        )
        session.add(prod)
        await session.flush()

        # 4. ProductVariant
        var_sku = f"SKU-{suffix}"
        var = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            name="Standard",
            sku=var_sku,
            attributes={},
            is_active=True,
        )
        session.add(var)
        await session.flush()

        # 5. ProductListing
        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=ret.id,
            variant_id=var.id,
            seller_sku=f"SELLER-{suffix}",
            original_price_paise=original_price_paise,
            selling_price_paise=selling_price_paise,
            currency="INR",
            hsn_code=hsn_code,
            gst_rate_basis_points=gst_rate_basis_points,
            tax_classification_source="TEST_FIXTURE",
            is_tax_verified=True,
            is_active=True,
        )
        session.add(listing)
        await session.flush()

        # 6. StoreInventory
        inv = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing.id,
            on_hand_quantity=on_hand_quantity,
            reserved_quantity=reserved_quantity,
        )
        session.add(inv)
        await session.commit()

        return {
            "id": str(listing.id),
            "retailer_id": str(ret.id),
            "retailer_name": ret.name,
            "retailer_rating": ret.rating,
            "retailer_state": ret.state,
            "variant_id": str(var.id),
            "variant_name": var.name,
            "variant_sku": var.sku,
            "product_id": str(prod.id),
            "product_name": prod.name,
            "original_price_paise": listing.original_price_paise,
            "selling_price_paise": listing.selling_price_paise,
            "currency": listing.currency,
            "available_quantity": on_hand_quantity - reserved_quantity,
            "is_active": True,
            "hsn_code": listing.hsn_code,
            "gst_rate_basis_points": listing.gst_rate_basis_points,
        }


async def get_test_listing(
    async_client: AsyncClient, min_stock: int = 5
) -> dict[str, Any]:
    """Helper to fetch an active product listing with sufficient stock, creating one if needed."""
    response = await async_client.get("/api/v1/products?limit=20")
    if response.status_code == 200:
        for prod in response.json().get("items", []):
            detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
            if detail_resp.status_code == 200:
                for variant in detail_resp.json().get("variants", []):
                    for listing in variant.get("listings", []):
                        if (
                            listing.get("is_active")
                            and listing.get("available_quantity", 0) >= min_stock
                        ):
                            return listing
    return await create_test_listing(on_hand_quantity=max(50, min_stock * 2))


async def get_two_different_retailer_listings(
    async_client: AsyncClient, min_stock: int = 5
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Helper to fetch two listings from distinct retailers with sufficient stock, creating them if needed."""
    response = await async_client.get("/api/v1/products?limit=50")
    found_first: dict[str, Any] | None = None
    if response.status_code == 200:
        for prod in response.json().get("items", []):
            detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
            if detail_resp.status_code == 200:
                for variant in detail_resp.json().get("variants", []):
                    for listing in variant.get("listings", []):
                        if (
                            listing.get("is_active")
                            and listing.get("available_quantity", 0) >= min_stock
                        ):
                            if found_first is None:
                                found_first = listing
                            elif listing.get("retailer_id") != found_first.get(
                                "retailer_id"
                            ):
                                return found_first, listing

    if found_first is None:
        l1 = await create_test_listing(
            retailer_name="Retailer Alpha Test",
            retailer_state="MH",
            on_hand_quantity=max(50, min_stock * 2),
        )
    else:
        l1 = found_first

    l2 = await create_test_listing(
        retailer_name="Retailer Beta Test",
        retailer_state="KA",
        on_hand_quantity=max(50, min_stock * 2),
    )
    return l1, l2


async def get_test_listings(async_client: AsyncClient) -> list[dict[str, Any]]:
    """Helper to fetch active product listings, ensuring at least two distinct listings exist."""
    response = await async_client.get("/api/v1/products?limit=20")
    listings = []
    if response.status_code == 200:
        for prod in response.json().get("items", []):
            detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
            if detail_resp.status_code == 200:
                for variant in detail_resp.json().get("variants", []):
                    for listing in variant.get("listings", []):
                        if listing.get("is_active"):
                            listings.append(listing)
    if len(listings) >= 2:
        return listings

    l1, l2 = await get_two_different_retailer_listings(async_client, min_stock=10)
    return [l1, l2]
