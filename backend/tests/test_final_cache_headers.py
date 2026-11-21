"""Final cycle Part 12: API responses are never cached by browsers, proxies or tunnels."""

import pytest
from httpx import AsyncClient

from tests.phase3_helpers import make_user


@pytest.mark.asyncio
async def test_api_responses_are_private_no_store(async_client: AsyncClient):
    public = await async_client.get("/api/v1/categories")
    assert public.headers["cache-control"] == "private, no-store"
    _, cust = await make_user()
    private = await async_client.get("/api/v1/cart", headers=cust)
    assert private.status_code == 200
    assert private.headers["cache-control"] == "private, no-store"
    err = await async_client.get("/api/v1/orders/not-a-uuid", headers=cust)
    assert err.headers["cache-control"] == "private, no-store"
