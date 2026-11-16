from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """Liveness check remains 200 OK regardless of dependency state."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "basket-backend"
    assert "environment" in data


@pytest.mark.asyncio
async def test_readiness_connected(async_client: AsyncClient):
    """Scenario 1: Database is connected -> 200 OK, status ready."""
    with patch(
        "app.main.check_db_readiness",
        return_value={"status": "connected"},
    ):
        response = await async_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"]["status"] == "connected"


@pytest.mark.asyncio
async def test_readiness_unconfigured_development(async_client: AsyncClient):
    """Scenario 2: Database unconfigured in dev -> 200 OK, status degraded."""
    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "development"
        with patch(
            "app.main.check_db_readiness",
            return_value={
                "status": "unconfigured",
                "message": "DATABASE_URL is not set.",
            },
        ):
            response = await async_client.get("/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["database"]["status"] == "unconfigured"
    finally:
        settings.ENVIRONMENT = original_env


@pytest.mark.asyncio
async def test_readiness_unconfigured_production(async_client: AsyncClient):
    """Scenario 3: Database unconfigured in production -> 503 Service Unavailable."""
    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        with patch(
            "app.main.check_db_readiness",
            return_value={
                "status": "unconfigured",
                "message": "DATABASE_URL is not set.",
            },
        ):
            response = await async_client.get("/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["database"]["status"] == "unconfigured"
    finally:
        settings.ENVIRONMENT = original_env


@pytest.mark.asyncio
async def test_readiness_unreachable(async_client: AsyncClient):
    """Scenario 4: Database unreachable -> 503 Service Unavailable, status not_ready."""
    with patch(
        "app.main.check_db_readiness",
        return_value={
            "status": "unreachable",
            "message": "Failed to connect to database.",
        },
    ):
        response = await async_client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "unreachable"


@pytest.mark.asyncio
async def test_readiness_db_check_error(async_client: AsyncClient):
    """Scenario 5: Database check produces an error -> 503 Service Unavailable, status not_ready."""
    with patch(
        "app.main.check_db_readiness",
        return_value={
            "status": "error",
            "message": "Database engine could not be initialized.",
        },
    ):
        response = await async_client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "error"


@pytest.mark.asyncio
async def test_api_v1_info(async_client: AsyncClient):
    response = await async_client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v1"
    assert "project" in data
