"""Comprehensive tests for the widgets API (app.api.widgets).

Covers all 5 endpoints:
  GET    /dashboards/scenario/{scenario_id}  — auto-assembled dashboard
  POST   /widgets                            — create widget
  GET    /widgets/{widget_id}/data            — get widget data
  GET    /widgets/suggest                     — suggest widgets for scenario
  DELETE /widgets/{widget_id}                 — delete widget

Plus unit tests for all helper functions:
  _detect_widget_type, _detect_dashboard_type, _generate_description,
  _extract_filters, _default_position, _generate_mock_widget_data,
  _is_marketing_scenario, _suggest_for_endpoint
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import ApiEndpoint, ScenarioRun, ScenarioStep, WidgetConfig
from tests.conftest import make_result


# ---------------------------------------------------------------------------
# Helpers — lightweight model factories
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def _scenario(
    id: int = 1,
    *,
    correlation_id: str = "corr-w-001",
    query: str = "Get all users",
    status: str = "completed",
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
    response_data: dict | list | None = None,
    reasoning: str | None = "Best match",
    created_at: datetime = NOW,
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
    st.started_at = NOW
    st.finished_at = NOW
    st.duration_ms = 100
    st.error_message = None
    st.alternatives = None
    st.created_at = created_at
    return st


def _endpoint(
    id: int = 100,
    *,
    method: str = "GET",
    path: str = "/users",
    summary: str | None = "List users",
    swagger_source_id: int = 1,
) -> ApiEndpoint:
    ep = ApiEndpoint()
    ep.id = id
    ep.method = method
    ep.path = path
    ep.summary = summary
    ep.swagger_source_id = swagger_source_id
    ep.created_at = NOW
    return ep


def _widget(
    id: int = 1,
    *,
    scenario_id: int | None = 1,
    widget_type: str = "kpi",
    title: str = "Active Users",
    data_source: dict | None = None,
    config: dict | None = None,
    position: dict | None = None,
    created_at: datetime = NOW,
) -> WidgetConfig:
    w = WidgetConfig()
    w.id = id
    w.scenario_id = scenario_id
    w.widget_type = widget_type
    w.title = title
    w.data_source = data_source or {"endpoint_id": 100}
    w.config = config or {}
    w.position = position
    w.created_at = created_at
    return w


# ===================================================================
# Unit tests for helper functions (no HTTP, no DB)
# ===================================================================


class TestDetectWidgetType:
    """Tests for _detect_widget_type."""

    def test_list_of_dicts_returns_table(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type([{"name": "Alice"}, {"name": "Bob"}]) == "table"

    def test_empty_list_returns_list(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type([]) == "list"

    def test_list_of_non_dicts_returns_list(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type(["a", "b", "c"]) == "list"

    def test_dict_with_count_returns_kpi(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"count": 42}) == "kpi"

    def test_dict_with_total_returns_kpi(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"total": 999, "items": []}) == "kpi"

    def test_dict_with_sum_returns_kpi(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"sum": 100.5}) == "kpi"

    def test_dict_with_labels_returns_chart(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"labels": ["a", "b"], "values": [1, 2]}) == "chart"

    def test_dict_with_datasets_returns_chart(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"datasets": [{"data": [1, 2]}]}) == "chart"

    def test_dict_with_series_returns_chart(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"series": [1, 2, 3]}) == "chart"

    def test_plain_dict_returns_card(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"name": "Alice", "age": 30}) == "card"

    def test_string_input_returns_card(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type("just a string") == "card"

    def test_integer_input_returns_card(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type(42) == "card"

    def test_none_input_returns_card(self):
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type(None) == "card"

    def test_dict_with_count_and_labels_prefers_kpi(self):
        """count is checked before labels, so kpi wins."""
        from app.api.widgets import _detect_widget_type
        assert _detect_widget_type({"count": 10, "labels": ["a"]}) == "kpi"


class TestDetectDashboardType:
    """Tests for _detect_dashboard_type."""

    def test_segment_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Show segment analysis") == "Audience Analysis"

    def test_audience_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Build audience report") == "Audience Analysis"

    def test_user_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("List all user data") == "Audience Analysis"

    def test_customer_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Customer retention") == "Audience Analysis"

    def test_campaign_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Launch email campaign") == "Campaign Dashboard"

    def test_push_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Send push notifications") == "Campaign Dashboard"

    def test_notification_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Notification history") == "Campaign Dashboard"

    def test_kpi_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Show KPI dashboard") == "Performance Metrics"

    def test_metric_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Key metric analysis") == "Performance Metrics"

    def test_performance_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Performance overview") == "Performance Metrics"

    def test_analytics_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Marketing analytics") == "Performance Metrics"

    def test_order_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("List all orders") == "Transaction Overview"

    def test_payment_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Payment processing") == "Transaction Overview"

    def test_transaction_query(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Recent transactions") == "Transaction Overview"

    def test_generic_query_returns_api_explorer(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("Fetch data from API") == "API Explorer"

    def test_empty_query_returns_api_explorer(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("") == "API Explorer"

    def test_case_insensitive(self):
        from app.api.widgets import _detect_dashboard_type
        assert _detect_dashboard_type("SEGMENT ANALYSIS") == "Audience Analysis"


class TestGenerateDescription:
    """Tests for _generate_description."""

    def test_with_completed_steps(self):
        from app.api.widgets import _generate_description

        step1 = _step(id=1, status="completed")
        step2 = _step(id=2, status="completed")
        step3 = _step(id=3, status="error")
        scenario = _scenario(query="Fetch users", status="completed", steps=[step1, step2, step3])

        desc = _generate_description(scenario)
        assert "Query: Fetch users" in desc
        assert "Steps: 2/3 completed" in desc
        assert "Status: completed" in desc

    def test_with_no_steps(self):
        from app.api.widgets import _generate_description

        scenario = _scenario(query="Empty run", status="running", steps=[])
        desc = _generate_description(scenario)
        assert "Steps: 0/0 completed" in desc
        assert "Status: running" in desc

    def test_with_endpoint_ids(self):
        from app.api.widgets import _generate_description

        step = _step(id=1, status="completed", endpoint_id=100)
        scenario = _scenario(query="API call", status="completed", steps=[step])
        desc = _generate_description(scenario)
        assert "Steps: 1/1 completed" in desc


class TestExtractFilters:
    """Tests for _extract_filters."""

    def test_extracts_unique_params(self):
        from app.api.widgets import _extract_filters

        step1 = _step(id=1, request_payload={"limit": 10, "offset": 0})
        step2 = _step(id=2, request_payload={"limit": 20, "status": "active"})
        scenario = _scenario(steps=[step1, step2])

        filters = _extract_filters(scenario)
        field_names = {f["field"] for f in filters}
        assert field_names == {"limit", "offset", "status"}
        for f in filters:
            assert "type" in f
            assert "label" in f
            assert f["type"] == "string"

    def test_empty_when_no_payloads(self):
        from app.api.widgets import _extract_filters

        step = _step(id=1, request_payload=None)
        scenario = _scenario(steps=[step])
        assert _extract_filters(scenario) == []

    def test_empty_when_no_steps(self):
        from app.api.widgets import _extract_filters

        scenario = _scenario(steps=[])
        assert _extract_filters(scenario) == []

    def test_label_formatting(self):
        from app.api.widgets import _extract_filters

        step = _step(id=1, request_payload={"user_name": "Alice"})
        scenario = _scenario(steps=[step])
        filters = _extract_filters(scenario)
        assert len(filters) == 1
        assert filters[0]["label"] == "User Name"


class TestDefaultPosition:
    """Tests for _default_position."""

    def test_index_zero(self):
        from app.api.widgets import _default_position
        pos = _default_position(0)
        assert pos == {"x": 0, "y": 0, "w": 6, "h": 4}

    def test_index_one(self):
        from app.api.widgets import _default_position
        pos = _default_position(1)
        assert pos == {"x": 6, "y": 0, "w": 6, "h": 4}

    def test_index_two(self):
        from app.api.widgets import _default_position
        pos = _default_position(2)
        assert pos == {"x": 0, "y": 4, "w": 6, "h": 4}

    def test_index_three(self):
        from app.api.widgets import _default_position
        pos = _default_position(3)
        assert pos == {"x": 6, "y": 4, "w": 6, "h": 4}

    def test_index_four(self):
        from app.api.widgets import _default_position
        pos = _default_position(4)
        assert pos == {"x": 0, "y": 8, "w": 6, "h": 4}

    def test_large_index(self):
        from app.api.widgets import _default_position
        pos = _default_position(10)
        assert pos == {"x": 0, "y": 20, "w": 6, "h": 4}


class TestGenerateMockWidgetData:
    """Tests for _generate_mock_widget_data."""

    def test_kpi_widget(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="kpi", title="Active Users")
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)

        assert "value" in data
        assert data["label"] == "Active Users"
        assert "change" in data
        assert "trend" in data
        assert "last_updated" in data

    def test_chart_widget_default_bar(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="chart", config={})
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)

        assert data["chart_type"] == "bar"
        assert "labels" in data
        assert "datasets" in data
        assert len(data["datasets"]) > 0

    def test_chart_widget_custom_chart_type(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="chart", config={"chart_type": "pie"})
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)
        assert data["chart_type"] == "pie"

    def test_chart_widget_none_config(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="chart", config=None)
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)
        assert data["chart_type"] == "bar"

    def test_table_widget(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="table")
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)

        assert "columns" in data
        assert "rows" in data
        assert "total_rows" in data
        assert len(data["rows"]) == 3

    def test_card_widget(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="card", title="Overview")
        endpoint = _endpoint(method="POST", path="/campaigns")
        data = _generate_mock_widget_data(widget, endpoint)

        assert data["title"] == "Overview"
        assert "POST" in data["content"]
        assert "/campaigns" in data["content"]
        assert "metadata" in data

    def test_other_widget_type(self):
        from app.api.widgets import _generate_mock_widget_data

        widget = _widget(widget_type="timeline")
        endpoint = _endpoint()
        data = _generate_mock_widget_data(widget, endpoint)
        assert data == {"data": "Widget data placeholder"}


class TestIsMarketingScenario:
    """Tests for _is_marketing_scenario."""

    def test_segment_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Build a user segment") is True

    def test_audience_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Target audience analysis") is True

    def test_campaign_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Create email campaign") is True

    def test_push_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Send push to users") is True

    def test_notification_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Notification stats") is True

    def test_email_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Send email blast") is True

    def test_sms_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("SMS campaign") is True

    def test_marketing_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("marketing strategy") is True

    def test_conversion_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("conversion funnel") is True

    def test_retention_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("retention report") is True

    def test_non_marketing_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("Fetch all pets from API") is False

    def test_empty_query(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("") is False

    def test_case_insensitive(self):
        from app.api.widgets import _is_marketing_scenario
        assert _is_marketing_scenario("AUDIENCE TARGETING") is True


class TestSuggestForEndpoint:
    """Tests for _suggest_for_endpoint."""

    def test_list_response_suggests_table(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint(summary="Users")
        suggestions = _suggest_for_endpoint(ep, [{"id": 1}, {"id": 2}])
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "table"
        assert "Users" in suggestions[0]["title"]

    def test_list_response_no_summary_uses_data(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint(summary=None)
        suggestions = _suggest_for_endpoint(ep, [{"id": 1}])
        assert suggestions[0]["title"] == "Data List"

    def test_dict_with_count_suggests_kpi(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint()
        suggestions = _suggest_for_endpoint(ep, {"count": 42, "data": []})
        assert any(s["type"] == "kpi" for s in suggestions)

    def test_dict_with_total_suggests_kpi(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint()
        suggestions = _suggest_for_endpoint(ep, {"total": 100})
        assert any(s["type"] == "kpi" for s in suggestions)

    def test_dict_without_aggregation_no_kpi(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint()
        suggestions = _suggest_for_endpoint(ep, {"name": "test"})
        assert not any(s["type"] == "kpi" for s in suggestions)

    def test_non_list_non_matching_dict_empty(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint()
        suggestions = _suggest_for_endpoint(ep, {"name": "test", "value": 1})
        assert suggestions == []

    def test_empty_dict_returns_empty(self):
        from app.api.widgets import _suggest_for_endpoint

        ep = _endpoint()
        suggestions = _suggest_for_endpoint(ep, {})
        assert suggestions == []


# ===================================================================
# GET /dashboards/scenario/{scenario_id} — auto-assembled dashboard
# ===================================================================


class TestGetScenarioDashboard:

    @pytest.mark.asyncio
    async def test_dashboard_with_existing_widgets(self, client, fake_db):
        """When widgets already exist for the scenario, return them directly."""
        scenario = _scenario(id=1, query="Show user segments", status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)

        w1 = _widget(id=10, scenario_id=1, widget_type="kpi", title="Total Users",
                      position={"x": 0, "y": 0, "w": 6, "h": 4})
        w2 = _widget(id=11, scenario_id=1, widget_type="table", title="User List",
                      position={"x": 6, "y": 0, "w": 6, "h": 4})
        fake_db.set_execute_result(make_result(scalars=[w1, w2]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        assert resp.status_code == 200
        body = resp.json()

        assert body["scenario_id"] == 1
        assert "Audience Analysis" in body["title"]
        assert len(body["widgets"]) == 2
        assert body["widgets"][0]["id"] == 10
        assert body["widgets"][0]["widget_type"] == "kpi"
        assert body["widgets"][1]["id"] == 11
        assert body["widgets"][1]["widget_type"] == "table"
        assert body["layout"]["cols"] == 12
        assert isinstance(body["filters"], list)

    @pytest.mark.asyncio
    async def test_dashboard_generates_widgets_when_none_stored(self, client, fake_db):
        """When no widgets stored, auto-generate from scenario steps."""
        ep = _endpoint(id=100, method="GET", path="/users", summary="List users")
        fake_db.register_get(ApiEndpoint, 100, ep)

        step = _step(
            id=10, scenario_id=1, status="completed",
            endpoint_id=100,
            response_data=[{"name": "Alice"}, {"name": "Bob"}],
        )
        scenario = _scenario(id=1, query="Get API data", status="completed", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)

        # First execute returns empty (no stored widgets)
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        assert resp.status_code == 200
        body = resp.json()

        assert body["scenario_id"] == 1
        # Should have at least the timeline widget + data widget
        assert len(body["widgets"]) >= 1
        # The first added widget is the timeline
        widget_types = [w["widget_type"] for w in body["widgets"]]
        assert "timeline" in widget_types
        # Widgets got IDs assigned by FakeAsyncSession
        for w in body["widgets"]:
            assert w["id"] is not None

    @pytest.mark.asyncio
    async def test_dashboard_scenario_not_found(self, client, fake_db):
        """Non-existent scenario returns 404."""
        resp = await client.get("/api/v1/dashboards/scenario/999")
        assert resp.status_code == 404
        assert "Scenario not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_dashboard_default_positions_when_widget_has_no_position(self, client, fake_db):
        """Widgets without stored position get default grid positions."""
        scenario = _scenario(id=1, query="Generic query", status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)

        w = _widget(id=10, scenario_id=1, position=None)
        fake_db.set_execute_result(make_result(scalars=[w]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        assert resp.status_code == 200
        widget = resp.json()["widgets"][0]
        # Default position for index 0
        assert widget["position"] == {"x": 0, "y": 0, "w": 6, "h": 4}

    @pytest.mark.asyncio
    async def test_dashboard_layout_structure(self, client, fake_db):
        """Dashboard layout has required fields."""
        scenario = _scenario(id=1, query="test", status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[_widget(id=1)]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        layout = resp.json()["layout"]
        assert layout["cols"] == 12
        assert layout["row_height"] == 80
        assert "breakpoints" in layout
        assert "mobile" in layout["breakpoints"]
        assert "tablet" in layout["breakpoints"]
        assert "desktop" in layout["breakpoints"]

    @pytest.mark.asyncio
    async def test_dashboard_description_contains_query(self, client, fake_db):
        """Dashboard description includes the scenario query."""
        scenario = _scenario(id=1, query="Analyze retention metrics", status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[_widget(id=1)]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        desc = resp.json()["description"]
        assert "Analyze retention metrics" in desc

    @pytest.mark.asyncio
    async def test_dashboard_filters_from_step_payloads(self, client, fake_db):
        """Filters are extracted from step request_payloads."""
        step = _step(id=10, request_payload={"status": "active", "limit": 50})
        scenario = _scenario(id=1, query="test", status="completed", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[_widget(id=1)]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        filters = resp.json()["filters"]
        field_names = {f["field"] for f in filters}
        assert "status" in field_names
        assert "limit" in field_names

    @pytest.mark.asyncio
    async def test_dashboard_title_truncated(self, client, fake_db):
        """Dashboard title truncates long queries to 50 chars."""
        long_query = "A" * 100
        scenario = _scenario(id=1, query=long_query, status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[_widget(id=1)]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        title = resp.json()["title"]
        # Title format: "{dashboard_type}: {query[:50]}..."
        assert title.endswith("...")
        # The query portion should be at most 50 chars
        assert len(title) < 100


# ===================================================================
# POST /widgets — create widget
# ===================================================================


class TestCreateWidget:

    @pytest.mark.asyncio
    async def test_create_kpi_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "Total Revenue",
            "data_source": {"endpoint_id": 100, "field_mapping": {"value": "total"}},
            "config": {"icon": "dollar"},
            "position": {"x": 0, "y": 0, "w": 3, "h": 2},
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["widget_type"] == "kpi"
        assert body["title"] == "Total Revenue"
        assert body["data_source"]["endpoint_id"] == 100
        assert body["config"]["icon"] == "dollar"
        assert body["position"]["w"] == 3
        assert "id" in body
        assert "created_at" in body

    @pytest.mark.asyncio
    async def test_create_chart_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "chart",
            "title": "Revenue Over Time",
            "data_source": {"endpoint_id": 200},
            "config": {"chart_type": "line"},
        })
        assert resp.status_code == 201
        assert resp.json()["widget_type"] == "chart"

    @pytest.mark.asyncio
    async def test_create_table_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "table",
            "title": "User List",
            "data_source": {"endpoint_id": 100},
        })
        assert resp.status_code == 201
        assert resp.json()["widget_type"] == "table"

    @pytest.mark.asyncio
    async def test_create_card_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "card",
            "title": "Summary",
            "data_source": {"endpoint_id": 100},
        })
        assert resp.status_code == 201
        assert resp.json()["widget_type"] == "card"

    @pytest.mark.asyncio
    async def test_create_timeline_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "timeline",
            "title": "Execution Log",
            "data_source": {"type": "scenario_steps"},
        })
        assert resp.status_code == 201
        assert resp.json()["widget_type"] == "timeline"

    @pytest.mark.asyncio
    async def test_create_list_widget(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "list",
            "title": "Recent Items",
            "data_source": {"endpoint_id": 100},
        })
        assert resp.status_code == 201
        assert resp.json()["widget_type"] == "list"

    @pytest.mark.asyncio
    async def test_create_widget_with_scenario_id(self, client, fake_db):
        resp = await client.post("/api/v1/widgets?scenario_id=5", json={
            "widget_type": "kpi",
            "title": "Metric",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 201
        assert resp.json()["scenario_id"] == 5

    @pytest.mark.asyncio
    async def test_create_widget_without_scenario_id(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "Standalone Widget",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 201
        assert resp.json()["scenario_id"] is None

    @pytest.mark.asyncio
    async def test_create_widget_optional_config_defaults_to_empty(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "Simple KPI",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 201
        assert resp.json()["config"] == {}

    @pytest.mark.asyncio
    async def test_create_widget_optional_position_defaults_to_none(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "No Position",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 201
        assert resp.json()["position"] is None

    @pytest.mark.asyncio
    async def test_create_widget_invalid_type_rejected(self, client, fake_db):
        """Widget type not in allowed set is rejected with 422."""
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "invalid",
            "title": "Bad Widget",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_empty_title_rejected(self, client, fake_db):
        """Empty title is rejected (min_length=1)."""
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_missing_title_rejected(self, client, fake_db):
        """Missing required field 'title' returns 422."""
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_missing_widget_type_rejected(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "title": "No Type",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_missing_data_source_rejected(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "No Source",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_empty_body_rejected(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_widget_assigns_id(self, client, fake_db):
        """FakeAsyncSession assigns auto-increment IDs."""
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "Widget A",
            "data_source": {"endpoint_id": 1},
        })
        assert resp.status_code == 201
        assert resp.json()["id"] >= 1

    @pytest.mark.asyncio
    async def test_create_widget_db_add_and_flush_called(self, client, fake_db):
        """Verify the handler adds the widget to the session and flushes."""
        await client.post("/api/v1/widgets", json={
            "widget_type": "table",
            "title": "Test",
            "data_source": {"endpoint_id": 1},
        })
        assert len(fake_db.added) == 1
        assert fake_db.flushed is True
        assert isinstance(fake_db.added[0], WidgetConfig)


# ===================================================================
# GET /widgets/{widget_id}/data — get widget data
# ===================================================================


class TestGetWidgetData:

    @pytest.mark.asyncio
    async def test_kpi_widget_data(self, client, fake_db):
        widget = _widget(id=1, widget_type="kpi", data_source={"endpoint_id": 100})
        ep = _endpoint(id=100)
        fake_db.register_get(WidgetConfig, 1, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/widgets/1/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "value" in data
        assert data["label"] == "Active Users"
        assert "trend" in data

    @pytest.mark.asyncio
    async def test_chart_widget_data(self, client, fake_db):
        widget = _widget(id=2, widget_type="chart", data_source={"endpoint_id": 100},
                         config={"chart_type": "pie"})
        ep = _endpoint(id=100)
        fake_db.register_get(WidgetConfig, 2, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/widgets/2/data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chart_type"] == "pie"
        assert "labels" in data
        assert "datasets" in data

    @pytest.mark.asyncio
    async def test_table_widget_data(self, client, fake_db):
        widget = _widget(id=3, widget_type="table", data_source={"endpoint_id": 100})
        ep = _endpoint(id=100)
        fake_db.register_get(WidgetConfig, 3, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/widgets/3/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "columns" in data
        assert "rows" in data
        assert "total_rows" in data

    @pytest.mark.asyncio
    async def test_card_widget_data(self, client, fake_db):
        widget = _widget(id=4, widget_type="card", title="API Card",
                         data_source={"endpoint_id": 100})
        ep = _endpoint(id=100, method="GET", path="/users")
        fake_db.register_get(WidgetConfig, 4, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/widgets/4/data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "API Card"
        assert "GET" in data["content"]
        assert "/users" in data["content"]

    @pytest.mark.asyncio
    async def test_other_widget_type_data(self, client, fake_db):
        widget = _widget(id=5, widget_type="timeline", data_source={"endpoint_id": 100})
        ep = _endpoint(id=100)
        fake_db.register_get(WidgetConfig, 5, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get("/api/v1/widgets/5/data")
        assert resp.status_code == 200
        assert resp.json() == {"data": "Widget data placeholder"}

    @pytest.mark.asyncio
    async def test_widget_not_found(self, client, fake_db):
        resp = await client.get("/api/v1/widgets/999/data")
        assert resp.status_code == 404
        assert "Widget not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_widget_no_endpoint_id_in_data_source(self, client, fake_db):
        """Widget with no endpoint_id in data_source returns error dict."""
        widget = _widget(id=6, data_source={"type": "scenario_steps"})
        fake_db.register_get(WidgetConfig, 6, widget)

        resp = await client.get("/api/v1/widgets/6/data")
        assert resp.status_code == 200
        assert resp.json()["error"] == "No data source configured"

    @pytest.mark.asyncio
    async def test_widget_endpoint_not_found(self, client, fake_db):
        """Widget references an endpoint_id that does not exist."""
        widget = _widget(id=7, data_source={"endpoint_id": 999})
        fake_db.register_get(WidgetConfig, 7, widget)
        # ApiEndpoint 999 not registered -> db.get returns None

        resp = await client.get("/api/v1/widgets/7/data")
        assert resp.status_code == 200
        assert resp.json()["error"] == "Endpoint not found"

    @pytest.mark.asyncio
    async def test_widget_data_with_filters_param(self, client, fake_db):
        """Filters query param is accepted (even if not used in mock)."""
        widget = _widget(id=8, widget_type="kpi", data_source={"endpoint_id": 100})
        ep = _endpoint(id=100)
        fake_db.register_get(WidgetConfig, 8, widget)
        fake_db.register_get(ApiEndpoint, 100, ep)

        resp = await client.get('/api/widgets/8/data?filters={"status":"active"}')
        assert resp.status_code == 200
        assert "value" in resp.json()


# ===================================================================
# GET /widgets/suggest — suggest widgets for scenario
# ===================================================================


class TestSuggestWidgets:

    @pytest.mark.asyncio
    async def test_suggest_for_marketing_scenario(self, client, fake_db):
        """Marketing query triggers additional marketing-specific suggestions."""
        ep = _endpoint(id=100, summary="List audiences")
        fake_db.register_get(ApiEndpoint, 100, ep)

        step = _step(
            id=10, endpoint_id=100,
            response_data=[{"name": "Premium", "size": 5000}],
        )
        scenario = _scenario(
            id=1, query="Build audience segment for campaign",
            steps=[step],
        )
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        suggestions = resp.json()

        # Should have endpoint-based suggestions + marketing suggestions
        types = [s["type"] for s in suggestions]
        assert "table" in types  # from list response_data
        assert "kpi" in types   # from marketing extras
        assert "chart" in types  # from marketing extras
        assert len(suggestions) <= 8  # Max 8 suggestions

    @pytest.mark.asyncio
    async def test_suggest_for_non_marketing_scenario(self, client, fake_db):
        """Non-marketing query does not add marketing-specific suggestions."""
        ep = _endpoint(id=100, summary="List pets")
        fake_db.register_get(ApiEndpoint, 100, ep)

        step = _step(id=10, endpoint_id=100, response_data={"count": 42})
        scenario = _scenario(id=1, query="Fetch all pets", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        suggestions = resp.json()

        # Only kpi suggestion from response data with "count"
        types = [s["type"] for s in suggestions]
        assert "kpi" in types
        # No marketing extras like "Total Audience"
        titles = [s.get("title", "") for s in suggestions]
        assert "Total Audience" not in titles

    @pytest.mark.asyncio
    async def test_suggest_scenario_not_found(self, client, fake_db):
        resp = await client.get("/api/v1/widgets/suggest?scenario_id=999")
        assert resp.status_code == 404
        assert "Scenario not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_suggest_scenario_no_steps(self, client, fake_db):
        """Scenario with no steps returns empty suggestions."""
        scenario = _scenario(id=1, query="Empty scenario", steps=[])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_suggest_steps_without_endpoint_id(self, client, fake_db):
        """Steps without endpoint_id are skipped."""
        step = _step(id=10, endpoint_id=None, response_data={"count": 1})
        scenario = _scenario(id=1, query="No endpoint steps", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_suggest_steps_without_response_data(self, client, fake_db):
        """Steps without response_data are skipped."""
        step = _step(id=10, endpoint_id=100, response_data=None)
        scenario = _scenario(id=1, query="No response", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_suggest_endpoint_not_found_skipped(self, client, fake_db):
        """Step references an endpoint that doesn't exist -> skipped."""
        step = _step(id=10, endpoint_id=999, response_data={"data": "test"})
        scenario = _scenario(id=1, query="Missing endpoint", steps=[step])
        fake_db.register_get(ScenarioRun, 1, scenario)
        # ApiEndpoint 999 not registered

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_suggest_max_8_results(self, client, fake_db):
        """Suggestions are capped at 8."""
        # Create marketing scenario with many steps to generate > 8 suggestions
        steps = []
        for i in range(10):
            ep = _endpoint(id=100 + i, summary=f"Endpoint {i}")
            fake_db.register_get(ApiEndpoint, 100 + i, ep)
            step = _step(id=10 + i, endpoint_id=100 + i,
                         response_data=[{"id": j} for j in range(5)])
            steps.append(step)

        scenario = _scenario(id=1, query="Build audience segment", steps=steps)
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        assert len(resp.json()) <= 8

    @pytest.mark.asyncio
    async def test_suggest_missing_scenario_id_param(self, client, fake_db):
        """Missing scenario_id query param returns 422."""
        resp = await client.get("/api/v1/widgets/suggest")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_suggest_marketing_extras_structure(self, client, fake_db):
        """Marketing extras have correct structure."""
        scenario = _scenario(id=1, query="email campaign performance", steps=[])
        fake_db.register_get(ScenarioRun, 1, scenario)

        resp = await client.get("/api/v1/widgets/suggest?scenario_id=1")
        assert resp.status_code == 200
        suggestions = resp.json()

        # Marketing extras: kpi Total Audience, kpi Estimated Reach,
        # chart Audience by Segment, table Top Segments
        assert len(suggestions) == 4
        kpi_suggestions = [s for s in suggestions if s["type"] == "kpi"]
        assert len(kpi_suggestions) == 2
        chart_suggestions = [s for s in suggestions if s["type"] == "chart"]
        assert len(chart_suggestions) == 1
        assert chart_suggestions[0]["chart_type"] == "pie"
        table_suggestions = [s for s in suggestions if s["type"] == "table"]
        assert len(table_suggestions) == 1
        assert "columns" in table_suggestions[0]


# ===================================================================
# DELETE /widgets/{widget_id} — delete widget
# ===================================================================


class TestDeleteWidget:

    @pytest.mark.asyncio
    async def test_delete_widget_happy_path(self, client, fake_db):
        widget = _widget(id=1)
        fake_db.register_get(WidgetConfig, 1, widget)

        resp = await client.delete("/api/v1/widgets/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Widget deleted"
        assert body["id"] == 1
        # Verify delete was called on session
        assert len(fake_db.deleted) == 1
        assert fake_db.deleted[0] is widget

    @pytest.mark.asyncio
    async def test_delete_widget_not_found(self, client, fake_db):
        resp = await client.delete("/api/v1/widgets/999")
        assert resp.status_code == 404
        assert "Widget not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_widget_does_not_affect_other_widgets(self, client, fake_db):
        """Deleting one widget doesn't remove others from the fake session."""
        w1 = _widget(id=1)
        w2 = _widget(id=2)
        fake_db.register_get(WidgetConfig, 1, w1)
        fake_db.register_get(WidgetConfig, 2, w2)

        resp = await client.delete("/api/v1/widgets/1")
        assert resp.status_code == 200

        # w2 should still be retrievable
        assert fake_db._get_store.get((WidgetConfig, 2)) is w2


# ===================================================================
# Response shape validation
# ===================================================================


class TestWidgetResponseShape:

    @pytest.mark.asyncio
    async def test_widget_response_has_all_fields(self, client, fake_db):
        resp = await client.post("/api/v1/widgets", json={
            "widget_type": "kpi",
            "title": "Test Widget",
            "data_source": {"endpoint_id": 1},
            "config": {"icon": "star"},
            "position": {"x": 0, "y": 0, "w": 6, "h": 4},
        })
        assert resp.status_code == 201
        body = resp.json()
        expected_keys = {
            "id", "scenario_id", "widget_type", "title",
            "data_source", "config", "position", "created_at",
        }
        assert expected_keys == set(body.keys())

    @pytest.mark.asyncio
    async def test_dashboard_response_has_all_fields(self, client, fake_db):
        scenario = _scenario(id=1, query="test query", status="completed")
        fake_db.register_get(ScenarioRun, 1, scenario)
        fake_db.set_execute_result(make_result(scalars=[_widget(id=1)]))

        resp = await client.get("/api/v1/dashboards/scenario/1")
        assert resp.status_code == 200
        body = resp.json()
        expected_keys = {
            "scenario_id", "title", "description",
            "widgets", "layout", "filters",
        }
        assert expected_keys == set(body.keys())
