import uuid
import pytest
from httpx import AsyncClient

from tests.factories import create_test_listing


async def register_customer(
    async_client: AsyncClient, name_prefix: str = "mission_user"
) -> tuple[dict, str]:
    email = f"{name_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": f"{name_prefix.capitalize()} Tester",
            "phone": f"+919{uuid.uuid4().int % 1000000000:09d}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["user"], data["access_token"]


@pytest.mark.asyncio
async def test_regression_scenario_1_exact_screenshot_inputs(async_client: AsyncClient):
    """Scenario 1: Exact screenshot inputs reproduce and succeed with valid plan.
    Shopping goal: Work-from-home productivity desk
    Budget: ₹20,000 (2000000 paise)
    Household: 1 Person (Individual)
    Category: Electronics
    Preferences: ergonomic, minimalist, cable management
    Excluded Brands: blank
    """
    user, token = await register_customer(async_client, "wfh_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Ensure electronics category exists and has listings
    await create_test_listing(
        retailer_name="ElectroTech Hub",
        product_name="Logitech Ergo Desk Kit",
        category_slug="electronics",
        category_name="Electronics",
        selling_price_paise=450000,
        on_hand_quantity=15,
    )

    cat_resp = await async_client.get("/api/v1/categories")
    assert cat_resp.status_code == 200
    cats = cat_resp.json()
    electronics_cat = next(c for c in cats if c["slug"] == "electronics")

    payload = {
        "title": "Work-from-home productivity desk",
        "description": None,
        "budget_paise": 2000000,
        "people_count": 1,
        "category_id": electronics_cat["id"],
        "preferences": ["ergonomic", "minimalist", "cable management"],
        "excluded_brands": [],
    }

    resp = await async_client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["title"] == "Work-from-home productivity desk"
    assert data["budget_paise"] == 2000000
    assert data["people_count"] == 1
    assert data["category_id"] == electronics_cat["id"]
    assert data["status"] == "ACTIVE"
    assert len(data["groups"]) > 0
    assert len(data["items"]) > 0
    assert data["is_over_budget"] is False
    assert "Work-from-home productivity desk" in data["summary_explanation"] or "Planned" in data["summary_explanation"]


@pytest.mark.asyncio
async def test_regression_scenario_2_custom_budget_limits(async_client: AsyncClient):
    """Scenario 2: Custom budget limits (tight budget, generous budget) handled correctly."""
    user, token = await register_customer(async_client, "budget_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    await create_test_listing(
        retailer_name="Budget Electronics",
        product_name="Budget USB Adapter",
        category_slug="electronics",
        category_name="Electronics",
        selling_price_paise=50000,
        on_hand_quantity=10,
    )

    # 1. Very low budget (₹100 -> 10000 paise)
    tight_payload = {
        "title": "Ultra Low Budget Desk",
        "budget_paise": 10000,
        "people_count": 1,
        "preferences": [],
        "excluded_brands": [],
    }
    resp_tight = await async_client.post("/api/v1/missions", json=tight_payload, headers=headers)
    assert resp_tight.status_code == 201
    tight_data = resp_tight.json()
    assert tight_data["budget_paise"] == 10000

    # 2. Generous budget (₹5,00,000 -> 50000000 paise)
    generous_payload = {
        "title": "Generous Executive Setup",
        "budget_paise": 50000000,
        "people_count": 1,
        "preferences": ["premium"],
        "excluded_brands": [],
    }
    resp_gen = await async_client.post("/api/v1/missions", json=generous_payload, headers=headers)
    assert resp_gen.status_code == 201
    gen_data = resp_gen.json()
    assert gen_data["is_over_budget"] is False
    assert gen_data["remaining_budget_paise"] > 0


@pytest.mark.asyncio
async def test_regression_scenario_3_empty_excluded_brands(async_client: AsyncClient):
    """Scenario 3: Empty excluded brands list or whitespace entries handled safely."""
    user, token = await register_customer(async_client, "brand_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": "Desk Setup with Empty Excluded Brands",
        "budget_paise": 1500000,
        "people_count": 1,
        "preferences": ["ergonomic"],
        "excluded_brands": ["", "   "],
    }
    resp = await async_client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["excluded_brands"] == []


@pytest.mark.asyncio
async def test_regression_scenario_4_missing_optional_fields(async_client: AsyncClient):
    """Scenario 4: Missing optional fields (no description, no category_id, defaults)."""
    user, token = await register_customer(async_client, "minimal_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": "Minimal Setup Mission",
        "budget_paise": 1000000,
    }
    resp = await async_client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Minimal Setup Mission"
    assert data["category_id"] is None
    assert data["description"] is None
    assert data["people_count"] == 1
    assert data["preferences"] == []
    assert data["excluded_brands"] == []


@pytest.mark.asyncio
async def test_regression_scenario_5_large_and_small_household_counts(async_client: AsyncClient):
    """Scenario 5: Large and small household counts correctly scaled."""
    user, token = await register_customer(async_client, "family_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Small household (1 person)
    resp1 = await async_client.post(
        "/api/v1/missions",
        json={"title": "Household 1 Person", "budget_paise": 2000000, "people_count": 1},
        headers=headers,
    )
    assert resp1.status_code == 201
    assert resp1.json()["people_count"] == 1

    # Large household (5 people)
    resp5 = await async_client.post(
        "/api/v1/missions",
        json={"title": "Household 5 People", "budget_paise": 2000000, "people_count": 5},
        headers=headers,
    )
    assert resp5.status_code == 201
    assert resp5.json()["people_count"] == 5


@pytest.mark.asyncio
async def test_regression_scenario_6_sparse_category_fallback(async_client: AsyncClient):
    """Scenario 6: Categories with sparse products fall back gracefully without failure."""
    user, token = await register_customer(async_client, "sparse_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Get a category from active categories
    cat_resp = await async_client.get("/api/v1/categories")
    cats = cat_resp.json()
    cat = cats[0]

    resp = await async_client.post(
        "/api/v1/missions",
        json={
            "title": "Sparse Category Mission",
            "budget_paise": 3000000,
            "category_id": cat["id"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_regression_scenario_7_deterministic_ai_fallback(async_client: AsyncClient):
    """Scenario 7: Generates valid plan deterministically even when external AI is unconfigured."""
    user, token = await register_customer(async_client, "no_ai_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.post(
        "/api/v1/missions",
        json={
            "title": "Clean Deterministic Plan",
            "budget_paise": 1500000,
            "preferences": ["reliable", "quality"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert len(data["groups"]) > 0
    assert data["total_cost_paise"] > 0


@pytest.mark.asyncio
async def test_regression_scenario_8_unauthenticated_and_invalid_inputs(async_client: AsyncClient):
    """Scenario 8: Unauthenticated requests and invalid inputs return clean HTTP 401 / 400 / 422."""
    # 1. Unauthenticated
    resp_unauth = await async_client.post(
        "/api/v1/missions",
        json={"title": "Unauthenticated Plan", "budget_paise": 100000},
    )
    assert resp_unauth.status_code == 401

    user, token = await register_customer(async_client, "invalid_input_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Negative budget
    resp_neg = await async_client.post(
        "/api/v1/missions",
        json={"title": "Negative Budget", "budget_paise": -500},
        headers=headers,
    )
    assert resp_neg.status_code in (400, 422)

    # 3. Zero budget
    resp_zero = await async_client.post(
        "/api/v1/missions",
        json={"title": "Zero Budget", "budget_paise": 0},
        headers=headers,
    )
    assert resp_zero.status_code in (400, 422)

    # 4. Non-existent category UUID
    fake_cat_id = str(uuid.uuid4())
    resp_fake_cat = await async_client.post(
        "/api/v1/missions",
        json={"title": "Fake Category", "budget_paise": 100000, "category_id": fake_cat_id},
        headers=headers,
    )
    assert resp_fake_cat.status_code == 400
    assert resp_fake_cat.json()["error"]["code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_regression_scenario_9_empty_brand_or_filter_matches(async_client: AsyncClient):
    """Scenario 9: When brand exclusions filter out all candidates, returns clean mission without 500."""
    user, token = await register_customer(async_client, "all_excluded_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Exclude all known brands by specifying wild exclusions
    payload = {
        "title": "Excluding all possible brands",
        "budget_paise": 1000000,
        "excluded_brands": ["Logitech", "Apple", "Dell", "BudgetBrand", "Partner", "Store", "Brand"],
    }
    resp = await async_client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    # May have 0 items, but must not crash with 500 internal error
    assert data["total_cost_paise"] >= 0
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_regression_scenario_10_e2e_plan_generation_and_retrieval(async_client: AsyncClient):
    """Scenario 10: End-to-end plan generation, item persistence, and detail retrieval."""
    user, token = await register_customer(async_client, "e2e_mission_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Preview
    preview_resp = await async_client.post(
        "/api/v1/missions/preview",
        json={
            "title": "E2E WFH Office Desk",
            "budget_paise": 2000000,
            "people_count": 1,
            "preferences": ["ergonomic"],
        },
        headers=headers,
    )
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert "groups" in preview_data
    assert "total_cost_paise" in preview_data

    # 2. Create
    create_resp = await async_client.post(
        "/api/v1/missions",
        json={
            "title": "E2E WFH Office Desk",
            "budget_paise": 2000000,
            "people_count": 1,
            "preferences": ["ergonomic"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    mission = create_resp.json()
    mission_id = mission["id"]

    # 3. Retrieve Detail
    get_resp = await async_client.get(f"/api/v1/missions/{mission_id}", headers=headers)
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == mission_id
    assert detail["title"] == "E2E WFH Office Desk"
    assert detail["status"] == "ACTIVE"
    assert len(detail["groups"]) > 0
    assert len(detail["items"]) > 0
