"""Tests for the /metrics endpoint (Prometheus-compatible)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_metrics_endpoint_returns_text(client: AsyncClient):
    """Test /metrics returns text format and doesn't crash."""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    body = resp.text
    # In test environment with mock DB, metrics may contain error comment
    # but endpoint should still return 200
    assert len(body) > 0


async def test_metrics_endpoint_is_prometheus_format(client: AsyncClient):
    """Test /metrics returns Prometheus-compatible format."""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Each line should be either a metric, a comment, or empty
    for line in body.strip().split("\n"):
        if line:
            assert (
                line.startswith("#")  # comment
                or " " in line  # metric with value
            ), f"Invalid Prometheus line: {line}"
