"""Comprehensive tests for the scenarios API (app.api.scenarios).

Covers all 7 endpoints:
  POST /scenarios          — create scenario
  GET  /scenarios          — list with filters
  GET  /scenarios/{id}     — get by id
  GET  /scenarios/{id}/steps  — get steps with enrichment
  POST /scenarios/{id}/cancel — cancel running/pending
  GET  /scenarios/{id}/graph  — get graph, auto-generate from steps
  POST /scenarios/{id}/confirm/{step_id} — confirm step
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import (
    ActionConfirmation,
    ApiEndpoint,
    ScenarioRun,
    ScenarioStep,
)
from tests.conftest import make_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def _scenario(
    id: int = 1,
    *,
    correlation_id: str = "corr-001",
    query: str = "Get all users",
    status: str = "running",
    graph_nodes: list | None = None,
    graph_edges: list | None = None,
    summary: dict | None = None,
    created_at: datetime = NOW,
    finished_at: datetime | None = None,
    steps: list | None = None,
) -> ScenarioRun:
    s = ScenarioRun()
    s.id = id
    s.correlation_id = correlation_id
    s.query = query
    s.status = status
    s.graph_nodes = graph_nodes or []
    s.graph_edges = graph_edges or []
    s.summary = summary or {"total_steps": 0, "completed": 0}
    s.created_at = created_at
    s.finished_at = finished_at
    s.steps = steps if steps is not None else []
    return s


def _step(
    id: int = 10,
    *,
    scenario_id: int = 1,
    step_number: int = 1,
    action: str = "api_call",
    description: str = "Fetch users",
    status: str = "completed",
    endpoint_id: int | None = None,
    request_payload: dict | None = None,
    response_data: dict | None = None,
    reasoning: str | None = "Best match for query",
    alternatives: list | None = None,
    started_at: datetime | None = NOW,
    finished_at: datetime | None = NOW,
    duration_ms: int | None = 120,
    error_message: str | None = None,
) -> ScenarioStep:
    st = ScenarioStep()
    st.id = id
    st.scenario_id = scenario_id
    st.step_number = step_number
    st.action = action
    st.description = description
    st.status = status
    st.endpoint_id = endpoint_id
    st.request_payload = request_payload
    st.response_data = response_data
    st.reasoning = reasoning
    st.alternatives = alternatives
    st.started_at = started_at
    st.finished_at = finished_at
    st.duration_ms = duration_ms
    st.error_message = error_message
    st.created_at = NOW
    return st


def _endpoint(
    id: int = 100,
    *,
    method: str = "GET",
    path: str = "/users",
    swagger_source: object | None = None,
) -> ApiEndpoint:
    ep = ApiEndpoint()
    ep.id = id
    ep.method = method
    ep.path = path
    # Bypass SQLAlchemy relationship descriptor by writing directly to __dict__
    # so we can use lightweight fakes instead of real SwaggerSource instances.
    ep.__dict__["swagger_source"] = swagger_source
    return ep


def _confirmation(
    id: int = 50,
    *,
    scenario_step_id: int = 10,
    status: str = "pending",
) -> ActionConfirmation:
    c = ActionConfirmation()
    c.id = id
    c.correlation_id = "corr-001"
    c.scenario_step_id = scenario_step_id
    c.action = "api_call"
    c.endpoint_method = "POST"
    c.endpoint_path = "/users"
    c.status = status
    c.created_at = NOW
    c.resolved_at = None
    c.resolved_by = None
    return c


# ===================================================================
# POST /scenarios — create scenario
# ===================================================================


class TestCreateScenario:

    @pytest.mark.asyncio
    @patch("app.api.scenarios.OrchestrationService")
    async def test_create_scenario_happy_path(
        self, MockOrchService, client, fake_db,
    ):
        """A valid request creates a scenario and returns 201."""
        mock_instance = MockOrchService.return_value
        mock_instance.execute_scenario = AsyncMock(return_value={"ok": True})

        # After flush the object gets an id from FakeAsyncSession.
        # After refresh the handler re-reads the scenario — simulate by
        # populating correlation_id (normally set by DB default / orchestration).
        async def _fake_refresh(obj):
            if not getattr(obj, "correlation_id", None):
                obj.correlation_id = "test-corr-id"

        fake_db.refresh = _fake_refresh

        resp = await client.post(
            "/api/v1/scenarios",
            json={"query": "List all pets", "swagger_source_ids": [1, 2]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["query"] == "List all pets"
        assert body["status"] == "running"
        assert "id" in body
        assert body["graph_nodes"] == []
        assert body["graph_edges"] == []
        assert body["correlation_id"] == "test-corr-id"

        # OrchestrationService must have been called
        mock_instance.execute_scenario.assert_awaited_once()
        call_kwargs = mock_instance.execute_scenario.call_args.kwargs
        assert call_kwargs["query"] == "List all pets"
        assert call_kwargs["swagger_source_ids"] == [1, 2]

    @pytest.mark.asyncio
    @patch("app.api.scenarios.OrchestrationService")
    async def test_create_scenario_without_swagger_ids(
        self, MockOrchService, client, fake_db,
    ):
        """swagger_source_ids is optional."""
        mock_instance = MockOrchService.return_value
        mock_instance.execute_scenario = AsyncMock(return_value={})

        async def _fake_refresh(obj):
            if not getattr(obj, "correlation_id", None):
                obj.correlation_id = "test-corr-id-2"

        fake_db.refresh = _fake_refresh

        resp = await client.post(
            "/api/v1/scenarios",
            json={"query": "Show me metrics"},
        )
        assert resp.status_code == 201
        call_kwargs = mock_instance.execute_scenario.call_args.kwargs
        assert call_kwargs["swagger_source_ids"] is None

    @pytest.mark.asyncio
    async def test_create_scenario_empty_query_rejected(self, client, fake_db):
        """Empty query must be rejected (min_length=1)."""
        resp = await client.post(
            "/api/v1/scenarios",
            json={"query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_scenario_missing_query_rejected(self, client, fake_db):
        """Missing query field must be rejected."""
        resp = await client.post("/api/v1/scenarios", json={})
        assert resp.status_code == 422


# ===================================================================
# GET /scenarios — list scenarios
# ===================================================================


class TestListScenarios:

    @pytest.mark.asyncio
    async def test_list_returns_scenarios(self, client, fake_db):
        s1 = _scenario(id=1, query="q1", status="running")
        s2 = _scenario(id=2, query="q2", status="completed", correlation_id="corr-002")
        fake_db.set_execute_result(make_result(scalars=[s1, s2]))

        resp = await client.get("/api/v1/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["query"] == "q1"
        assert data[1]["query"] == "q2"

    @pytest.mark.asyncio
    async def test_list_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/v1/scenarios")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, client, fake_db):
        s = _scenario(id=3, status="completed", correlation_id="corr-003")
        fake_db.set_execute_result(make_result(scalars=[s]))

        resp = await client.get("/api/v1/scenarios?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_invalid_status_rejected(self, client, fake_db):
        """A status value outside the allowed set must be rejected (422)."""
        resp = await client.get("/api/v1/scenarios?status=banana")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, client, fake_db):
        s = _scenario(id=5, correlation_id="corr-005")
        fake_db.set_execute_result(make_result(scalars=[s]))

        resp = await client.get("/api/v1/scenarios?limit=10&offset=5")
        assert resp.status_code == 200
        # Just verify the request was accepted and returned data
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_limit_out_of_range(self, client, fake_db):
        """limit > 100 should be rejected."""
        resp = await client.get("/api/v1/scenarios?limit=200")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_negative_offset(self, client, fake_db):
        """offset < 0 should be rejected."""
        resp = await client.get("/api/v1/scenarios?offset=-1")
        assert resp.status_code == 422


# ===================================================================
# GET /scenarios/{id} — get scenario by id
# ===================================================================


class TestGetScenario:

    @pytest.mark.asyncio
    async def test_get_existing_scenario(self, client, fake_db):
        s = _scenario(id=7, query="Fetch orders", correlation_id="corr-007")
        fake_db.register_get(ScenarioRun, 7, s)

        resp = await client.get("/api/v1/scenarios/7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 7
        assert body["query"] == "Fetch orders"
        assert body["correlation_id"] == "corr-007"

    @pytest.mark.asyncio
    async def test_get_nonexistent_scenario_returns_404(self, client, fake_db):
        resp = await client.get("/api/v1/scenarios/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_scenario_with_finished_at(self, client, fake_db):
        s = _scenario(id=8, status="completed", finished_at=NOW, correlation_id="corr-008")
        fake_db.register_get(ScenarioRun, 8, s)

        resp = await client.get("/api/v1/scenarios/8")
        assert resp.status_code == 200
        assert resp.json()["finished_at"] is not None


# ===================================================================
# GET /scenarios/{id}/steps — get steps with enrichment
# ===================================================================


class TestGetScenarioSteps:

    @pytest.mark.asyncio
    async def test_steps_happy_path_no_endpoint(self, client, fake_db):
        """Steps without endpoint_id still return correctly."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        step = _step(id=10, scenario_id=1, action="transform", endpoint_id=None)
        fake_db.set_execute_result(make_result(scalars=[step]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 10
        assert data[0]["endpoint_method"] is None
        assert data[0]["endpoint_path"] is None
        assert data[0]["confirmation_status"] is None

    @pytest.mark.asyncio
    async def test_steps_with_endpoint_enrichment(self, client, fake_db):
        """Steps with endpoint_id get method/path enriched."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        ep = _endpoint(id=100, method="GET", path="/users")
        fake_db.register_get(ApiEndpoint, 100, ep)

        step = _step(id=11, scenario_id=1, endpoint_id=100)
        fake_db.set_execute_result(make_result(scalars=[step]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["endpoint_method"] == "GET"
        assert data[0]["endpoint_path"] == "/users"

    @pytest.mark.asyncio
    async def test_steps_with_confirmation_status(self, client, fake_db):
        """Mutating steps show confirmation_status when a record exists."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        step = _step(id=12, scenario_id=1, action="api_call", endpoint_id=None)
        fake_db.set_execute_result(make_result(scalars=[step]))

        conf = _confirmation(id=50, scenario_step_id=12, status="pending")
        # Second execute call will return the confirmation
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["confirmation_status"] == "pending"

    @pytest.mark.asyncio
    async def test_steps_mutating_action_no_confirmation_record(self, client, fake_db):
        """Mutating action but no confirmation record -> confirmation_status is None."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        step = _step(id=13, scenario_id=1, action="mutating_action", endpoint_id=None)
        fake_db.set_execute_result(make_result(scalars=[step]))
        # Second execute returns empty
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        assert resp.json()[0]["confirmation_status"] is None

    @pytest.mark.asyncio
    async def test_steps_empty_list(self, client, fake_db):
        """Scenario exists but has no steps."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_steps_scenario_not_found(self, client, fake_db):
        resp = await client.get("/api/v1/scenarios/999/steps")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_steps_multiple_ordered(self, client, fake_db):
        """Multiple steps are returned correctly."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        s1 = _step(id=20, scenario_id=1, step_number=1, action="transform",
                    description="Step A")
        s2 = _step(id=21, scenario_id=1, step_number=2, action="transform",
                    description="Step B")
        fake_db.set_execute_result(make_result(scalars=[s1, s2]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["step_number"] == 1
        assert data[1]["step_number"] == 2

    @pytest.mark.asyncio
    async def test_steps_with_endpoint_and_confirmation(self, client, fake_db):
        """Step has both endpoint enrichment and confirmation."""
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        ep = _endpoint(id=200, method="POST", path="/orders")
        fake_db.register_get(ApiEndpoint, 200, ep)

        step = _step(id=30, scenario_id=1, action="api_call", endpoint_id=200)
        fake_db.set_execute_result(make_result(scalars=[step]))

        conf = _confirmation(id=60, scenario_step_id=30, status="approved")
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["endpoint_method"] == "POST"
        assert data[0]["endpoint_path"] == "/orders"
        assert data[0]["confirmation_status"] == "approved"


# ===================================================================
# POST /scenarios/{id}/cancel — cancel scenario
# ===================================================================


class TestCancelScenario:

    @pytest.mark.asyncio
    async def test_cancel_running_scenario(self, client, fake_db):
        pending_step = _step(id=40, status="pending")
        running_step = _step(id=41, status="running")
        scenario = _scenario(id=1, status="running", steps=[pending_step, running_step])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.post("/api/v1/scenarios/1/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Scenario cancelled"
        assert body["id"] == 1
        assert scenario.status == "cancelled"
        assert pending_step.status == "skipped"
        assert running_step.status == "skipped"

    @pytest.mark.asyncio
    async def test_cancel_pending_scenario(self, client, fake_db):
        scenario = _scenario(id=2, status="pending", correlation_id="corr-002")
        scenario.steps = []
        fake_db.register_get(ScenarioRun, 2, scenario)

        resp = await client.post("/api/v1/scenarios/2/cancel")
        assert resp.status_code == 200
        assert scenario.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_completed_scenario_returns_409(self, client, fake_db):
        scenario = _scenario(id=3, status="completed", correlation_id="corr-003")
        fake_db.register_get(ScenarioRun, 3, scenario)

        resp = await client.post("/api/v1/scenarios/3/cancel")
        assert resp.status_code == 409
        assert "Cannot cancel" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cancel_error_scenario_returns_409(self, client, fake_db):
        scenario = _scenario(id=4, status="error", correlation_id="corr-004")
        fake_db.register_get(ScenarioRun, 4, scenario)

        resp = await client.post("/api/v1/scenarios/4/cancel")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_cancelled_scenario_returns_409(self, client, fake_db):
        scenario = _scenario(id=5, status="cancelled", correlation_id="corr-005")
        fake_db.register_get(ScenarioRun, 5, scenario)

        resp = await client.post("/api/v1/scenarios/5/cancel")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_scenario_returns_404(self, client, fake_db):
        resp = await client.post("/api/v1/scenarios/999/cancel")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_only_marks_pending_and_running_steps(self, client, fake_db):
        """Already completed/error steps should NOT be changed to skipped."""
        completed_step = _step(id=50, status="completed")
        error_step = _step(id=51, status="error")
        pending_step = _step(id=52, status="pending")
        scenario = _scenario(
            id=6,
            status="running",
            correlation_id="corr-006",
            steps=[completed_step, error_step, pending_step],
        )
        fake_db.register_get(ScenarioRun, 6, scenario)

        resp = await client.post("/api/v1/scenarios/6/cancel")
        assert resp.status_code == 200
        assert completed_step.status == "completed"  # unchanged
        assert error_step.status == "error"  # unchanged
        assert pending_step.status == "skipped"  # changed


# ===================================================================
# GET /scenarios/{id}/graph — get graph
# ===================================================================


class TestGetScenarioGraph:

    @pytest.mark.asyncio
    async def test_graph_returns_stored_nodes_edges(self, client, fake_db):
        """When graph_nodes/graph_edges are stored, return them directly."""
        nodes = [{"id": "n1", "type": "api_call", "label": "Fetch"}]
        edges = [{"id": "e1", "from": "n1", "to": "n2"}]
        scenario = _scenario(id=1, graph_nodes=nodes, graph_edges=edges)
        scenario.steps = []
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/scenarios/1/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == nodes
        assert body["edges"] == edges
        assert body["layout"] == "dagre"
        assert body["direction"] == "TB"

    @pytest.mark.asyncio
    async def test_graph_auto_generates_from_steps(self, client, fake_db):
        """When graph_nodes are empty, generate from steps."""
        step1 = _step(id=10, step_number=1, action="api_call",
                       description="Fetch users from API", endpoint_id=100)
        step2 = _step(id=11, step_number=2, action="transform",
                       description="Transform data", endpoint_id=None)

        scenario = _scenario(id=2, graph_nodes=None, graph_edges=None,
                             correlation_id="corr-002", steps=[step1, step2])
        fake_db.register_get(ScenarioRun, 2, scenario)

        # Endpoint lookup for step1
        source = SimpleNamespace(name="Petstore")
        ep = _endpoint(id=100, method="GET", path="/users", swagger_source=source)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/scenarios/2/graph")
        assert resp.status_code == 200
        body = resp.json()

        nodes = body["nodes"]
        edges = body["edges"]

        assert len(nodes) == 2
        assert nodes[0]["id"] == "step_10"
        assert nodes[0]["type"] == "api_call"
        assert nodes[0]["status"] == "completed"
        assert nodes[0]["endpoint"] == "GET /users"
        assert nodes[0]["api_source"] == "Petstore"

        assert nodes[1]["id"] == "step_11"
        assert nodes[1]["type"] == "transform"
        # No endpoint for step2
        assert "endpoint" not in nodes[1]

        assert len(edges) == 1
        assert edges[0]["from"] == "step_10"
        assert edges[0]["to"] == "step_11"
        assert edges[0]["type"] == "sequence"

    @pytest.mark.asyncio
    async def test_graph_empty_when_no_nodes_and_no_steps(self, client, fake_db):
        """Empty graph when nothing stored and no steps."""
        scenario = _scenario(id=3, graph_nodes=None, graph_edges=None,
                             correlation_id="corr-003")
        scenario.steps = []
        fake_db.register_get(ScenarioRun, 3, scenario)

        resp = await client.get("/api/v1/scenarios/3/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []

    @pytest.mark.asyncio
    async def test_graph_nonexistent_scenario_returns_404(self, client, fake_db):
        resp = await client.get("/api/v1/scenarios/999/graph")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_graph_auto_generate_single_step_no_edges(self, client, fake_db):
        """Single step produces one node and zero edges."""
        step = _step(id=20, step_number=1, action="decision",
                     description="Decide next action", endpoint_id=None)
        scenario = _scenario(id=4, graph_nodes=None, graph_edges=None,
                             correlation_id="corr-004", steps=[step])
        fake_db.register_get(ScenarioRun, 4, scenario)

        resp = await client.get("/api/v1/scenarios/4/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["nodes"]) == 1
        assert len(body["edges"]) == 0

    @pytest.mark.asyncio
    async def test_graph_auto_generate_endpoint_without_swagger_source(
        self, client, fake_db,
    ):
        """Endpoint exists but swagger_source is None -> api_source is None."""
        step = _step(id=25, step_number=1, action="api_call",
                     description="Call external API", endpoint_id=300)
        scenario = _scenario(id=5, graph_nodes=None, graph_edges=None,
                             correlation_id="corr-005", steps=[step])
        fake_db.register_get(ScenarioRun, 5, scenario)

        ep = _endpoint(id=300, method="DELETE", path="/items/1", swagger_source=None)
        fake_db.register_get(ApiEndpoint, 300, ep)

        resp = await client.get("/api/v1/scenarios/5/graph")
        assert resp.status_code == 200
        node = resp.json()["nodes"][0]
        assert node["endpoint"] == "DELETE /items/1"
        assert node["api_source"] is None


# ===================================================================
# POST /scenarios/{id}/confirm/{step_id} — confirm step
# ===================================================================


class TestConfirmScenarioStep:

    @pytest.mark.asyncio
    @patch("app.api.scenarios.OrchestrationService")
    async def test_confirm_step_happy_path(
        self, MockOrchService, client, fake_db,
    ):
        mock_instance = MockOrchService.return_value
        mock_instance.resume_scenario = AsyncMock()

        scenario = _scenario(id=1, status="running")
        step = _step(id=10, scenario_id=1, action="api_call")
        conf = _confirmation(id=50, scenario_step_id=10, status="pending")

        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.register_get(ScenarioStep, 10, step)
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Step confirmed and scenario resumed"
        assert body["step_id"] == 10

        assert conf.status == "approved"
        assert conf.resolved_by == "admin@example.com"
        assert conf.resolved_at is not None

        mock_instance.resume_scenario.assert_awaited_once_with(
            1, from_step_id=10,
        )

    @pytest.mark.asyncio
    async def test_confirm_scenario_not_found(self, client, fake_db):
        resp = await client.post(
            "/api/v1/scenarios/999/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 404
        assert "Scenario not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_step_not_found(self, client, fake_db):
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)
        # Step 999 not registered -> returns None from db.get

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/999?resolver=admin@example.com"
        )
        assert resp.status_code == 404
        assert "Step not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_step_wrong_scenario(self, client, fake_db):
        """Step exists but belongs to a different scenario."""
        scenario = _scenario(id=1)
        step = _step(id=10, scenario_id=99)  # different scenario_id
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.register_get(ScenarioStep, 10, step)

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 404
        assert "Step not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_no_confirmation_required(self, client, fake_db):
        """Step has no ActionConfirmation record."""
        scenario = _scenario(id=1)
        step = _step(id=10, scenario_id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.register_get(ScenarioStep, 10, step)
        fake_db.set_execute_result(make_result(scalars=[]))  # no confirmation

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 404
        assert "No confirmation required" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_already_approved_returns_409(self, client, fake_db):
        scenario = _scenario(id=1)
        step = _step(id=10, scenario_id=1)
        conf = _confirmation(id=50, scenario_step_id=10, status="approved")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.register_get(ScenarioStep, 10, step)
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 409
        assert "already approved" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_already_rejected_returns_409(self, client, fake_db):
        scenario = _scenario(id=1)
        step = _step(id=10, scenario_id=1)
        conf = _confirmation(id=50, scenario_step_id=10, status="rejected")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.register_get(ScenarioStep, 10, step)
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.post(
            "/api/v1/scenarios/1/confirm/10?resolver=admin@example.com"
        )
        assert resp.status_code == 409
        assert "already rejected" in resp.json()["detail"]


# ===================================================================
# Response shape validation
# ===================================================================


class TestResponseShape:

    @pytest.mark.asyncio
    async def test_scenario_response_has_all_fields(self, client, fake_db):
        s = _scenario(id=1, finished_at=NOW)
        fake_db.register_get(ScenarioRun, 1, s)

        resp = await client.get("/api/v1/scenarios/1")
        body = resp.json()
        expected_keys = {
            "id", "correlation_id", "query", "status",
            "graph_nodes", "graph_edges", "summary",
            "created_at", "finished_at",
        }
        assert expected_keys == set(body.keys())

    @pytest.mark.asyncio
    async def test_step_response_has_all_fields(self, client, fake_db):
        scenario = _scenario(id=1)
        fake_db.register_get(ScenarioRun, 1, scenario)

        step = _step(id=10, scenario_id=1, action="transform", endpoint_id=None)
        fake_db.set_execute_result(make_result(scalars=[step]))

        resp = await client.get("/api/v1/scenarios/1/steps")
        body = resp.json()[0]
        expected_keys = {
            "id", "step_number", "action", "description", "status",
            "endpoint_id", "endpoint_method", "endpoint_path",
            "request_payload", "response_data", "reasoning",
            "alternatives", "started_at", "finished_at",
            "duration_ms", "error_message", "confirmation_status",
        }
        assert expected_keys == set(body.keys())

    @pytest.mark.asyncio
    async def test_graph_response_has_layout_fields(self, client, fake_db):
        scenario = _scenario(id=1)
        scenario.steps = []
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/scenarios/1/graph")
        body = resp.json()
        assert "layout" in body
        assert "direction" in body
        assert "nodes" in body
        assert "edges" in body
