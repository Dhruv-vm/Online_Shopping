import uuid

import pytest
from httpx import AsyncClient

from app.modules.identity.models import User


async def create_user_with_role(
    async_client: AsyncClient,
    role: str = "customer",
    email: str | None = None,
    password: str = "TestPassword123!",
) -> tuple[dict[str, str], dict]:
    """Helper to register/create a user with a specific role and return auth header and user dict."""
    user_email = email or f"user_{role}_{uuid.uuid4().hex[:8]}@example.com"

    if role == "retailer":
        store_name = f"Store {uuid.uuid4().hex[:6]}"
        resp = await async_client.post(
            "/api/v1/auth/retailer/register",
            json={
                "email": user_email,
                "password": password,
                "full_name": f"Retailer Owner {uuid.uuid4().hex[:4]}",
                "phone": "+919876543210",
                "store_name": store_name,
                "state": "KA",
                "business_address": "456 Commercial Street, Bengaluru",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        token = data["access_token"]
        return {"Authorization": f"Bearer {token}"}, data["user"]

    # Customer registration
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": password,
            "full_name": f"Customer User {uuid.uuid4().hex[:4]}",
            "phone": "+919876543210",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    user = data["user"]

    if role == "admin":
        # Elevate to admin directly in database
        from sqlalchemy import update

        from app.core.database import get_session_factory

        async with get_session_factory()() as session:
            await session.execute(
                update(User)
                .where(User.id == uuid.UUID(user["id"]))
                .values(role="admin")
            )
            await session.commit()
        # Login again to get token with admin role claim
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": password},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        token = login_data["access_token"]
        user = login_data["user"]
        assert user["role"] == "admin"

    return {"Authorization": f"Bearer {token}"}, user


@pytest.mark.asyncio
async def test_customer_cannot_access_admin_or_retailer_portals(
    async_client: AsyncClient,
):
    customer_auth, _ = await create_user_with_role(async_client, role="customer")

    # Attempt admin access
    admin_resp = await async_client.get("/api/v1/admin/overview", headers=customer_auth)
    assert admin_resp.status_code == 403
    assert admin_resp.json()["error"]["code"] == "FORBIDDEN"

    # Attempt retailer access
    retailer_resp = await async_client.get(
        "/api/v1/retailer/overview", headers=customer_auth
    )
    assert retailer_resp.status_code == 403
    assert retailer_resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_retailer_registration_creates_user_and_store_profile(
    async_client: AsyncClient,
):
    retailer_auth, user = await create_user_with_role(async_client, role="retailer")
    assert user["role"] == "retailer"
    assert user["retailer_id"] is not None
    assert user["store_name"] is not None
    assert user["verification_status"] == "PENDING"

    # Verify profile endpoint
    profile_resp = await async_client.get(
        "/api/v1/retailer/profile", headers=retailer_auth
    )
    assert profile_resp.status_code == 200
    profile = profile_resp.json()
    assert profile["id"] == user["retailer_id"]
    assert profile["name"] == user["store_name"]
    assert profile["is_open"] is True
    assert profile["verification_status"] == "PENDING"
    assert profile["business_address"] == "456 Commercial Street, Bengaluru"


@pytest.mark.asyncio
async def test_retailer_can_update_store_profile_and_open_status(
    async_client: AsyncClient,
):
    retailer_auth, user = await create_user_with_role(async_client, role="retailer")

    # Update profile
    update_resp = await async_client.put(
        "/api/v1/retailer/profile",
        json={
            "description": "Updated gourmet organic goods boutique.",
            "is_open": False,
            "contact_email": "hello@updatedstore.com",
            "business_hours": {
                "monday": "09:00 - 20:00",
                "tuesday": "09:00 - 20:00",
            },
        },
        headers=retailer_auth,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["description"] == "Updated gourmet organic goods boutique."
    assert updated["is_open"] is False
    assert updated["contact_email"] == "hello@updatedstore.com"
    assert updated["business_hours"]["monday"] == "09:00 - 20:00"

    # Verify overview
    overview_resp = await async_client.get(
        "/api/v1/retailer/overview", headers=retailer_auth
    )
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["is_open"] is False
    assert overview["retailer_id"] == user["retailer_id"]


@pytest.mark.asyncio
async def test_retailer_tenant_isolation(async_client: AsyncClient):
    retailer_a_auth, user_a = await create_user_with_role(async_client, role="retailer")
    retailer_b_auth, user_b = await create_user_with_role(async_client, role="retailer")

    assert user_a["retailer_id"] != user_b["retailer_id"]

    # Retailer A profile returns Store A
    prof_a = (
        await async_client.get("/api/v1/retailer/profile", headers=retailer_a_auth)
    ).json()
    assert prof_a["id"] == user_a["retailer_id"]

    # Retailer B profile returns Store B
    prof_b = (
        await async_client.get("/api/v1/retailer/profile", headers=retailer_b_auth)
    ).json()
    assert prof_b["id"] == user_b["retailer_id"]


@pytest.mark.asyncio
async def test_admin_can_view_overview_and_verify_retailers(async_client: AsyncClient):
    # 1. Create a retailer
    _, retailer_user = await create_user_with_role(async_client, role="retailer")
    retailer_id = retailer_user["retailer_id"]

    # 2. Create an admin
    admin_auth, admin_user = await create_user_with_role(async_client, role="admin")

    # 3. View admin overview
    overview_resp = await async_client.get("/api/v1/admin/overview", headers=admin_auth)
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["total_retailers"] > 0
    assert overview["pending_verifications"] > 0

    # 4. List retailers with filter
    ret_list_resp = await async_client.get(
        "/api/v1/admin/retailers?status=PENDING", headers=admin_auth
    )
    assert ret_list_resp.status_code == 200
    retailers = ret_list_resp.json()
    matching = [r for r in retailers if r["id"] == retailer_id]
    assert len(matching) == 1
    assert matching[0]["verification_status"] == "PENDING"
    assert matching[0]["owner_name"] is not None

    # 5. Admin approves retailer verification
    verify_resp = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        json={"status": "VERIFIED"},
        headers=admin_auth,
    )
    assert verify_resp.status_code == 200
    verified_data = verify_resp.json()
    assert verified_data["verification_status"] == "VERIFIED"
    assert verified_data["is_active"] is True

    # 6. Admin suspends retailer
    suspend_resp = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        json={"status": "SUSPENDED", "rejection_reason": "Policy violation"},
        headers=admin_auth,
    )
    assert suspend_resp.status_code == 200
    suspended_data = suspend_resp.json()
    assert suspended_data["verification_status"] == "SUSPENDED"
    assert suspended_data["is_active"] is False


@pytest.mark.asyncio
async def test_user_me_profile_returns_retailer_metadata(async_client: AsyncClient):
    retailer_auth, user = await create_user_with_role(async_client, role="retailer")

    me_resp = await async_client.get("/api/v1/users/me", headers=retailer_auth)
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["role"] == "retailer"
    assert me["retailer_id"] == user["retailer_id"]
    assert me["store_name"] == user["store_name"]
    assert me["verification_status"] == "PENDING"
