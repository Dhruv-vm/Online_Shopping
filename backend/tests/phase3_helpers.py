"""Shared fixtures/helpers for Phase 3 feature tests."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_session_factory
from app.modules.catalogue.models import Retailer
from app.modules.identity.models import User
from app.modules.identity.security import create_access_token
from tests.factories import create_test_listing

_PW_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2FsdA$0000000000000000000000000000000000000000000"


async def make_user(role: str = "customer") -> tuple[uuid.UUID, dict[str, str]]:
    async with get_session_factory()() as session:
        user = User(
            email=f"p3_{role}_{uuid.uuid4().hex[:10]}@example.com",
            hashed_password=_PW_HASH,
            full_name=f"Phase3 {role.title()}",
            role=role,
        )
        session.add(user)
        await session.commit()
        token = create_access_token(user.id, role=role)
        return user.id, {"Authorization": f"Bearer {token}"}


async def make_retailer(
    *,
    service_pincodes: list[str] | None = None,
    **listing_kwargs: Any,
) -> tuple[dict[str, Any], dict[str, str]]:
    """A verified retailer with a portal user and one listing."""
    listing = await create_test_listing(**listing_kwargs)
    user_id, headers = await make_user("retailer")
    async with get_session_factory()() as session:
        ret = await session.get(Retailer, uuid.UUID(listing["retailer_id"]))
        ret.user_id = user_id
        ret.verification_status = "VERIFIED"
        ret.is_active = True
        ret.service_pincodes = service_pincodes or []
        await session.commit()
    listing["retailer_user_id"] = str(user_id)
    return listing, headers


async def add_listing_for_retailer(
    retailer_id: str, variant_id: str, *, selling_price_paise: int, on_hand: int = 50
) -> str:
    from app.modules.catalogue.models import ProductListing, StoreInventory

    async with get_session_factory()() as session:
        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=uuid.UUID(retailer_id),
            variant_id=uuid.UUID(variant_id),
            seller_sku=f"SELLER-{uuid.uuid4().hex[:8]}",
            original_price_paise=max(selling_price_paise, 100),
            selling_price_paise=selling_price_paise,
            currency="INR",
            hsn_code="8518",
            gst_rate_basis_points=1800,
            tax_classification_source="TEST_FIXTURE",
            is_tax_verified=True,
            is_active=True,
        )
        session.add(listing)
        await session.flush()
        session.add(
            StoreInventory(
                id=uuid.uuid4(), listing_id=listing.id, on_hand_quantity=on_hand
            )
        )
        await session.commit()
        return str(listing.id)


async def quote_cart(client, headers: dict[str, str]) -> tuple[dict, str]:
    """Create a default address (if needed) and a quote for the customer's cart."""
    addr = await client.post(
        "/api/v1/addresses",
        headers=headers,
        json={
            "recipient_name": "Phase Three",
            "phone": "+919876543210",
            "line1": "12 MG Road",
            "city": "Bengaluru",
            "state": "KA",
            "postal_code": "560001",
            "is_default": True,
        },
    )
    assert addr.status_code == 201, addr.text
    addr_id = addr.json()["id"]
    q = await client.post(
        "/api/v1/quotes", headers=headers, json={"delivery_address_id": addr_id}
    )
    assert q.status_code == 201, q.text
    return q.json(), addr_id


async def place_order(client, headers: dict[str, str]) -> tuple[dict, dict]:
    quote, addr_id = await quote_cart(client, headers)
    r = await client.post(
        "/api/v1/reservations", headers=headers, json={"quote_id": quote["id"]}
    )
    assert r.status_code == 201, r.text
    o = await client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "quote_id": quote["id"],
            "reservation_id": r.json()["id"],
            "delivery_address_id": addr_id,
        },
    )
    assert o.status_code == 201, o.text
    return quote, o.json()
