import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "basket-backend"
    assert "environment" in data


@pytest.mark.asyncio
async def test_readiness_check(async_client: AsyncClient):
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    # In dev without DB configured, status is degraded or ready
    assert data["status"] in ("ready", "degraded")
    assert "checks" in data
    assert "database" in data["checks"]


@pytest.mark.asyncio
async def test_api_v1_info(async_client: AsyncClient):
    response = await async_client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v1"
    assert "project" in data
