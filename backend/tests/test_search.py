from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient

from app.core.search.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitState,
    SearchCircuitBreaker,
)
from app.core.search.client import MockOpenSearchClient
from app.modules.search.router import get_search_service
from app.modules.search.service import SearchService


@pytest.fixture
def test_search_client() -> MockOpenSearchClient:
    return MockOpenSearchClient()


@pytest.fixture
def circuit_breaker() -> SearchCircuitBreaker:
    return SearchCircuitBreaker(failure_threshold=3, recovery_seconds=0.1)


# -------------------------------------------------------------------------
# Circuit Breaker Unit Tests
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = SearchCircuitBreaker(failure_threshold=3, recovery_seconds=0.1)
    assert cb.state == CircuitState.CLOSED

    async def faulty_call():
        raise RuntimeError("OpenSearch simulated connection dropped")

    async def successful_call():
        return "success"

    # 1. First 2 failures: still CLOSED
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(faulty_call)
        assert cb.state == CircuitState.CLOSED

    # 2. Third failure trips to OPEN
    with pytest.raises(RuntimeError):
        await cb.call(faulty_call)
    assert cb.state == CircuitState.OPEN

    # 3. Subsequent calls fast-fail with CircuitBreakerOpenError without invoking faulty_call
    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(successful_call)

    # 4. Wait for recovery timeout (0.1s) -> transitions to HALF_OPEN
    await asyncio.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN

    # 5. Successful probe recovers circuit to CLOSED
    res = await cb.call(successful_call)
    assert res == "success"
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_probe_failure_returns_to_open():
    cb = SearchCircuitBreaker(failure_threshold=2, recovery_seconds=0.05)

    async def faulty_call():
        raise RuntimeError("Still down")

    # Trip to OPEN
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(faulty_call)
    assert cb.state == CircuitState.OPEN

    # Wait for HALF_OPEN
    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    # Probe fails -> immediately trips back to OPEN
    with pytest.raises(RuntimeError):
        await cb.call(faulty_call)
    assert cb.state == CircuitState.OPEN


# -------------------------------------------------------------------------
# Search Service & API Integration Tests
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_opensearch_engine_success(
    app_instance,
    async_client: AsyncClient,
    test_search_client: MockOpenSearchClient,
):
    # Setup test index and docs
    await test_search_client.create_index("basket_products_v1")
    await test_search_client.update_aliases(
        actions=[
            {"add": {"index": "basket_products_v1", "alias": "basket_products_search"}},
            {"add": {"index": "basket_products_v1", "alias": "basket_products_write"}},
        ]
    )

    doc1 = {
        "product_id": str(uuid.uuid4()),
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "slug": "sony-wh-1000xm5",
        "brand": "Sony",
        "description": "Industry leading noise canceling headphones",
        "category_id": str(uuid.uuid4()),
        "category_name": "Audio",
        "category_slug": "audio",
        "min_price_paise": 2999000,
        "max_price_paise": 3499000,
        "currency": "INR",
        "is_in_stock": True,
        "total_available_quantity": 8,
        "rating": 4.9,
        "is_active": True,
        "searchable_text": "Sony WH-1000XM5 Wireless Headphones Sony Audio noise canceling",
        "retailers": [{"retailer_id": str(uuid.uuid4()), "retailer_name": "Croma"}],
        "variants": [],
        "attributes": {},
    }
    await test_search_client.index_document(
        "basket_products_write", doc1["product_id"], doc1
    )

    custom_service = SearchService(
        search_client=test_search_client,
        search_alias="basket_products_search",
    )
    app_instance.dependency_overrides[get_search_service] = lambda: custom_service

    try:
        # Search query matching "Sony"
        response = await async_client.get("/api/v1/search?q=Sony")
        assert response.status_code == 200
        data = response.json()

        assert data["engine"] == "opensearch"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Sony WH-1000XM5 Wireless Headphones"
        assert data["items"][0]["brand"] == "Sony"
        assert data["items"][0]["min_price_paise"] == 2999000
    finally:
        app_instance.dependency_overrides.pop(get_search_service, None)


@pytest.mark.asyncio
async def test_search_postgres_sql_fallback(
    app_instance,
    async_client: AsyncClient,
    test_search_client: MockOpenSearchClient,
):
    # Simulate OpenSearch downtime to trigger SQL fallback
    test_search_client.simulate_downtime = True
    custom_service = SearchService(
        search_client=test_search_client,
        search_alias="basket_products_search",
    )
    app_instance.dependency_overrides[get_search_service] = lambda: custom_service

    try:
        # Search for MacBook product via PostgreSQL fallback (ensuring test listing if missing)
        check_resp = await async_client.get("/api/v1/search?q=MacBook")
        if check_resp.status_code == 200 and check_resp.json().get("total", 0) == 0:
            from tests.factories import create_test_listing

            await create_test_listing(product_name="Apple MacBook Air 15-inch M3")

        response = await async_client.get("/api/v1/search?q=MacBook")
        assert response.status_code == 200
        data = response.json()

        assert data["engine"] == "postgres_fallback"
        assert data["total"] >= 1
        found = any("MacBook" in item["name"] for item in data["items"])
        assert found is True
        # Under fallback mode, facets are omitted to protect PostgreSQL CPU
        assert data["facets"] is None
    finally:
        app_instance.dependency_overrides.pop(get_search_service, None)


@pytest.mark.asyncio
async def test_search_force_fallback_flag(
    app_instance,
    async_client: AsyncClient,
    test_search_client: MockOpenSearchClient,
):
    custom_service = SearchService(
        search_client=test_search_client,
        search_alias="basket_products_search",
    )
    app_instance.dependency_overrides[get_search_service] = lambda: custom_service

    try:
        # Request with force_fallback=true routes to PostgreSQL even if OpenSearch is healthy
        response = await async_client.get("/api/v1/search?force_fallback=true")
        assert response.status_code == 200
        data = response.json()
        assert data["engine"] == "postgres_fallback"
    finally:
        app_instance.dependency_overrides.pop(get_search_service, None)


@pytest.mark.asyncio
async def test_search_suggestions_api(
    app_instance,
    async_client: AsyncClient,
    test_search_client: MockOpenSearchClient,
):
    # Setup index
    await test_search_client.create_index("basket_products_v1")
    await test_search_client.update_aliases(
        actions=[
            {"add": {"index": "basket_products_v1", "alias": "basket_products_search"}},
        ]
    )

    doc = {
        "product_id": str(uuid.uuid4()),
        "name": "Apple MacBook Pro M3",
        "slug": "apple-macbook-pro-m3",
        "brand": "Apple",
        "is_active": True,
        "searchable_text": "Apple MacBook Pro M3 laptops computers",
    }
    await test_search_client.index_document(
        "basket_products_v1", doc["product_id"], doc
    )

    custom_service = SearchService(
        search_client=test_search_client,
        search_alias="basket_products_search",
    )
    app_instance.dependency_overrides[get_search_service] = lambda: custom_service

    try:
        response = await async_client.get("/api/v1/search/suggestions?q=MacBook")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "MacBook"
        assert len(data["suggestions"]) >= 1
        assert "MacBook" in data["suggestions"][0]["text"]
    finally:
        app_instance.dependency_overrides.pop(get_search_service, None)
