from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.metrics import (
    Counter,
    Gauge,
    Histogram,
    normalize_metric_path,
)


def test_path_normalization():
    # UUID normalization
    assert (
        normalize_metric_path("/api/v1/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6")
        == "/api/v1/orders/{id}"
    )
    # Integer normalization
    assert (
        normalize_metric_path("/api/v1/items/42/details")
        == "/api/v1/items/{id}/details"
    )
    # Root path
    assert normalize_metric_path("/") == "/"
    # Trailing slash removal
    assert normalize_metric_path("/api/v1/products/") == "/api/v1/products"


def test_counter_metric():
    c = Counter("test_counter_total", "Test counter", label_names=("method", "status"))
    c.inc(method="GET", status="200")
    c.inc(value=2.0, method="GET", status="200")
    c.inc(method="POST", status="201")

    assert c.get(method="GET", status="200") == 3.0
    assert c.get(method="POST", status="201") == 1.0

    with pytest.raises(ValueError, match="non-negative"):
        c.inc(-1.0, method="GET", status="200")

    lines = c.collect()
    assert "# HELP test_counter_total Test counter" in lines
    assert "# TYPE test_counter_total counter" in lines
    assert 'test_counter_total{method="GET",status="200"} 3.0' in lines
    assert 'test_counter_total{method="POST",status="201"} 1.0' in lines


def test_gauge_metric():
    g = Gauge("test_gauge", "Test gauge", label_names=("component",))
    g.set(10.0, component="db_pool")
    assert g.get(component="db_pool") == 10.0

    g.inc(2.0, component="db_pool")
    assert g.get(component="db_pool") == 12.0

    g.dec(5.0, component="db_pool")
    assert g.get(component="db_pool") == 7.0

    lines = g.collect()
    assert "# TYPE test_gauge gauge" in lines
    assert 'test_gauge{component="db_pool"} 7.0' in lines


def test_histogram_metric():
    h = Histogram(
        "test_latency_seconds",
        "Test latency",
        label_names=("route",),
        buckets=(0.01, 0.05, 0.1, 0.5),
    )
    h.observe(0.005, route="/api/v1/search")
    h.observe(0.04, route="/api/v1/search")
    h.observe(0.08, route="/api/v1/search")

    lines = h.collect()
    assert "# TYPE test_latency_seconds histogram" in lines
    assert 'test_latency_seconds_bucket{route="/api/v1/search",le="0.01"} 1' in lines
    assert 'test_latency_seconds_bucket{route="/api/v1/search",le="0.05"} 2' in lines
    assert 'test_latency_seconds_bucket{route="/api/v1/search",le="0.1"} 3' in lines
    assert 'test_latency_seconds_bucket{route="/api/v1/search",le="0.5"} 3' in lines
    assert 'test_latency_seconds_bucket{route="/api/v1/search",le="+Inf"} 3' in lines
    assert 'test_latency_seconds_count{route="/api/v1/search"} 3' in lines


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    response = await async_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text

    # Core platform metrics exposed in output
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "kafka_events_published_total" in body
    assert "consumer_events_processed_total" in body
    assert "circuit_breaker_state" in body


@pytest.mark.asyncio
async def test_metrics_middleware_tracking(async_client: AsyncClient):
    # Make request to health check
    res = await async_client.get("/health")
    assert res.status_code == 200

    # Read metrics
    metrics_res = await async_client.get("/metrics")
    assert metrics_res.status_code == 200
    body = metrics_res.text

    # Verify /health route was counted
    assert 'http_requests_total{method="GET",path="/health",status="200"}' in body


@pytest.mark.asyncio
async def test_readiness_with_dependency_checks(async_client: AsyncClient):
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()

    assert "checks" in data
    assert "database" in data["checks"]
    assert "kafka" in data["checks"]
    assert "opensearch" in data["checks"]
