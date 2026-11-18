import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_categories(async_client: AsyncClient):
    response = await async_client.get("/api/v1/categories")
    assert response.status_code == 200
    categories = response.json()
    assert isinstance(categories, list)
    assert len(categories) >= 7

    # Validate category structure
    first = categories[0]
    assert "id" in first
    assert "name" in first
    assert "slug" in first
    assert "product_count" in first
    assert first["product_count"] >= 0


@pytest.mark.asyncio
async def test_list_retailers(async_client: AsyncClient):
    response = await async_client.get("/api/v1/retailers")
    assert response.status_code == 200
    retailers = response.json()
    assert isinstance(retailers, list)
    assert len(retailers) >= 7

    # Validate retailer structure
    first = retailers[0]
    assert "id" in first
    assert "name" in first
    assert "slug" in first
    assert "rating" in first
    assert first["is_active"] is True


@pytest.mark.asyncio
async def test_list_products_pagination(async_client: AsyncClient):
    response = await async_client.get("/api/v1/products?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert "pages" in data

    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["items"]) <= 5
    assert data["total"] >= 10
    assert data["pages"] >= 2


@pytest.mark.asyncio
async def test_list_products_category_filter(async_client: AsyncClient):
    response = await async_client.get("/api/v1/products?category_slug=electronics")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    for item in data["items"]:
        assert item["category_slug"] == "electronics"


@pytest.mark.asyncio
async def test_list_products_search_filter(async_client: AsyncClient):
    response = await async_client.get("/api/v1/products?search=Sony")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    found_sony = any(
        "Sony" in item["name"] or "Sony" in item["brand"] for item in data["items"]
    )
    assert found_sony


@pytest.mark.asyncio
async def test_list_products_price_filter(async_client: AsyncClient):
    # Filter between ₹1000 (100,000 paise) and ₹5000 (500,000 paise)
    response = await async_client.get(
        "/api/v1/products?min_price=100000&max_price=500000"
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["min_price_paise"] <= 500000


@pytest.mark.asyncio
async def test_list_products_in_stock_filter(async_client: AsyncClient):
    response = await async_client.get("/api/v1/products?in_stock=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["is_in_stock"] is True


@pytest.mark.asyncio
async def test_list_products_sorting(async_client: AsyncClient):
    # Price ascending
    res_asc = await async_client.get("/api/v1/products?sort_by=price_asc&limit=10")
    assert res_asc.status_code == 200
    items_asc = res_asc.json()["items"]
    prices_asc = [item["min_price_paise"] for item in items_asc]
    assert prices_asc == sorted(prices_asc)

    # Price descending
    res_desc = await async_client.get("/api/v1/products?sort_by=price_desc&limit=10")
    assert res_desc.status_code == 200
    items_desc = res_desc.json()["items"]
    prices_desc = [item["min_price_paise"] for item in items_desc]
    assert prices_desc == sorted(prices_desc, reverse=True)


@pytest.mark.asyncio
async def test_get_product_detail_by_slug(async_client: AsyncClient):
    slug = "sony-wh-1000xm5-wireless-headphones"
    response = await async_client.get(f"/api/v1/products/{slug}")
    assert response.status_code == 200
    product = response.json()
    assert product["slug"] == slug
    assert product["name"].startswith("Sony")
    assert len(product["variants"]) >= 2
    assert len(product["images"]) >= 1
    assert product["is_in_stock"] is True
    assert product["total_available_stock"] > 0

    # Verify nested listings and inventory
    first_variant = product["variants"][0]
    assert len(first_variant["listings"]) >= 1
    listing = first_variant["listings"][0]
    assert "retailer_name" in listing
    assert "selling_price_paise" in listing
    assert "available_quantity" in listing
    assert listing["available_quantity"] > 0


@pytest.mark.asyncio
async def test_get_product_detail_by_uuid(async_client: AsyncClient):
    # Fetch list first to obtain a valid UUID
    list_res = await async_client.get("/api/v1/products?limit=1")
    assert list_res.status_code == 200
    item = list_res.json()["items"][0]
    prod_id = item["id"]

    # Fetch by UUID
    response = await async_client.get(f"/api/v1/products/{prod_id}")
    assert response.status_code == 200
    product = response.json()
    assert product["id"] == prod_id
    assert product["name"] == item["name"]


@pytest.mark.asyncio
async def test_get_product_not_found(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/products/non-existent-product-slug-12345"
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]
    assert "not found" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_list_products_invalid_sort(async_client: AsyncClient):
    response = await async_client.get("/api/v1/products?sort_by=invalid_sort_param")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
