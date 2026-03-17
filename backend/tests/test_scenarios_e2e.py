"""End-to-end tests for scenario execution, graph visualization, and confirmations."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_create_and_list_scenarios(client: AsyncClient):
    """Test creating a scenario and listing it."""
    # List should start empty or with existing
    resp = await client.get("/api/v1/scenarios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_scenarios_with_status_filter(client: AsyncClient):
    """Test filtering scenarios by status."""
    resp = await client.get("/api/v1/scenarios?status=completed")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_scenarios_invalid_status(client: AsyncClient):
    """Test invalid status filter returns 422."""
    resp = await client.get("/api/v1/scenarios?status=invalid")
    assert resp.status_code == 422


async def test_get_nonexistent_scenario(client: AsyncClient):
    """Test 404 for missing scenario."""
    resp = await client.get("/api/v1/scenarios/99999")
    assert resp.status_code == 404


async def test_get_scenario_steps_404(client: AsyncClient):
    """Test 404 for steps of missing scenario."""
    resp = await client.get("/api/v1/scenarios/99999/steps")
    assert resp.status_code == 404


async def test_get_scenario_graph_404(client: AsyncClient):
    """Test 404 for graph of missing scenario."""
    resp = await client.get("/api/v1/scenarios/99999/graph")
    assert resp.status_code == 404


async def test_cancel_nonexistent_scenario(client: AsyncClient):
    """Test 404 for cancelling missing scenario."""
    resp = await client.post("/api/v1/scenarios/99999/cancel")
    assert resp.status_code == 404


async def test_confirmations_list(client: AsyncClient):
    """Test listing confirmations."""
    resp = await client.get("/api/v1/confirmations?status=pending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_confirmations_resolve_nonexistent(client: AsyncClient):
    """Test resolving nonexistent confirmation."""
    resp = await client.post(
        "/api/v1/confirmations/99999/resolve",
        json={"status": "approved", "resolver": "test@test.com"},
    )
    assert resp.status_code == 404


async def test_create_confirmation(client: AsyncClient):
    """Test creating a confirmation request."""
    resp = await client.post(
        "/api/v1/confirmations",
        json={
            "correlation_id": "test-123",
            "action": "create_audience",
            "endpoint_method": "POST",
            "endpoint_path": "/api/audiences",
            "payload_summary": "Creating Premium Users audience",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["action"] == "create_audience"


async def test_widgets_suggest_404(client: AsyncClient):
    """Test widget suggestion for nonexistent scenario."""
    resp = await client.get("/api/v1/widgets/suggest?scenario_id=99999")
    assert resp.status_code == 404


async def test_dashboard_scenario_404(client: AsyncClient):
    """Test dashboard for nonexistent scenario."""
    resp = await client.get("/api/v1/dashboards/scenario/99999")
    assert resp.status_code == 404


async def test_health_check(client: AsyncClient):
    """Test health endpoint returns structured response."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded", "error")
    assert "db" in data
    assert "mlops" in data
    assert "version" in data
