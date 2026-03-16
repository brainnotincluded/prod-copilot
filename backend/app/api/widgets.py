"""API for auto-generated UI widgets (KPIs, charts, tables, cards).

Generates working interfaces based on API data — not just step logs,
but actual business views: segments, audiences, campaigns, KPIs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WidgetConfig, ScenarioRun, ApiEndpoint
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class WidgetCreateRequest(BaseModel):
    widget_type: str = Field(..., pattern="^(kpi|chart|table|card|timeline|list)$")
    title: str = Field(..., min_length=1)
    data_source: dict[str, Any]  # {"endpoint_id": 123, "field_mapping": {...}}
    config: dict[str, Any] | None = None  # Chart type, columns, etc.
    position: dict[str, int] | None = None  # {"x": 0, "y": 0, "w": 6, "h": 4}


class WidgetResponse(BaseModel):
    id: int
    scenario_id: int | None
    widget_type: str
    title: str
    data_source: dict[str, Any]
    config: dict[str, Any] | None
    position: dict[str, int] | None
    created_at: str

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    """Auto-assembled dashboard for a scenario."""

    scenario_id: int
    title: str
    description: str
    widgets: list[WidgetResponse]
    layout: dict[str, Any]  # Grid layout configuration
    filters: list[dict[str, Any]]  # Available filters


@router.get("/dashboards/scenario/{scenario_id}", response_model=DashboardResponse)
async def get_scenario_dashboard(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Get auto-assembled dashboard for a scenario.

    Generates KPIs, charts, and tables based on:
    - Query intent (marketing campaign, user analysis, etc.)
    - Available API data
    - Response schemas
    """
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Get or generate widgets for this scenario
    result = await db.execute(
        select(WidgetConfig).where(WidgetConfig.scenario_id == scenario_id)
    )
    widgets = result.scalars().all()

    # If no widgets stored, generate from scenario data
    if not widgets:
        widgets = await _generate_widgets_for_scenario(scenario, db)

    # Build dashboard structure
    widget_responses = [
        WidgetResponse(
            id=w.id,
            scenario_id=w.scenario_id,
            widget_type=w.widget_type,
            title=w.title,
            data_source=w.data_source,
            config=w.config,
            position=w.position or _default_position(i),
            created_at=str(w.created_at),
        )
        for i, w in enumerate(widgets)
    ]

    # Determine dashboard type based on query
    dashboard_type = _detect_dashboard_type(scenario.query)

    return DashboardResponse(
        scenario_id=scenario_id,
        title=f"{dashboard_type}: {scenario.query[:50]}...",
        description=_generate_description(scenario),
        widgets=widget_responses,
        layout={
            "cols": 12,
            "row_height": 80,
            "breakpoints": {"mobile": 480, "tablet": 768, "desktop": 1024},
        },
        filters=_extract_filters(scenario),
    )


@router.post("/widgets", response_model=WidgetResponse, status_code=201)
async def create_widget(
    request: WidgetCreateRequest,
    scenario_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> WidgetResponse:
    """Create a custom widget for a dashboard."""
    widget = WidgetConfig(
        scenario_id=scenario_id,
        widget_type=request.widget_type,
        title=request.title,
        data_source=request.data_source,
        config=request.config or {},
        position=request.position,
    )
    db.add(widget)
    await db.flush()

    return WidgetResponse(
        id=widget.id,
        scenario_id=widget.scenario_id,
        widget_type=widget.widget_type,
        title=widget.title,
        data_source=widget.data_source,
        config=widget.config,
        position=widget.position,
        created_at=str(widget.created_at),
    )


@router.get("/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: int,
    filters: str | None = Query(None),  # JSON-encoded filters
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch live data for a widget.

    Calls the underlying API and transforms response for widget display.
    """
    widget = await db.get(WidgetConfig, widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    # Get the endpoint
    endpoint_id = widget.data_source.get("endpoint_id")
    if not endpoint_id:
        return {"error": "No data source configured"}

    endpoint = await db.get(ApiEndpoint, endpoint_id)
    if not endpoint:
        return {"error": "Endpoint not found"}

    # In real implementation, this would:
    # 1. Call the actual API through MLOps client
    # 2. Transform response based on field_mapping
    # 3. Aggregate for KPIs/charts
    # 4. Apply filters

    # Return mock data structure for now
    return _generate_mock_widget_data(widget, endpoint)


@router.get("/widgets/suggest")
async def suggest_widgets(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Suggest widgets based on scenario data and available APIs.

    Analyzes the scenario steps and suggests relevant visualizations.
    """
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    suggestions = []

    # Analyze scenario steps for data sources
    for step in scenario.steps:
        if step.endpoint_id and step.response_data:
            endpoint = await db.get(ApiEndpoint, step.endpoint_id)
            if endpoint:
                # Suggest appropriate widgets based on data structure
                widget_suggestions = _suggest_for_endpoint(endpoint, step.response_data)
                suggestions.extend(widget_suggestions)

    # Add generic KPI widgets for marketing scenarios
    if _is_marketing_scenario(scenario.query):
        suggestions.extend([
            {"type": "kpi", "title": "Total Audience", "metric": "count", "icon": "users"},
            {"type": "kpi", "title": "Estimated Reach", "metric": "reach", "icon": "broadcast"},
            {"type": "chart", "title": "Audience by Segment", "chart_type": "pie"},
            {"type": "table", "title": "Top Segments", "columns": ["name", "size", "conversion"]},
        ])

    return suggestions[:8]  # Max 8 suggestions


@router.delete("/widgets/{widget_id}")
async def delete_widget(
    widget_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a widget from dashboard."""
    widget = await db.get(WidgetConfig, widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    await db.delete(widget)
    return {"message": "Widget deleted", "id": widget_id}


# Helper functions

async def _generate_widgets_for_scenario(
    scenario: ScenarioRun,
    db: AsyncSession,
) -> list[WidgetConfig]:
    """Auto-generate widgets based on scenario execution."""
    widgets: list[WidgetConfig] = []

    # Step 1: Add timeline/journal widget
    widgets.append(WidgetConfig(
        scenario_id=scenario.id,
        widget_type="timeline",
        title="Execution Log",
        data_source={"type": "scenario_steps", "scenario_id": scenario.id},
        config={"show_timestamps": True, "group_by": "step"},
        position={"x": 0, "y": 0, "w": 12, "h": 4},
    ))

    # Step 2: Analyze steps for data widgets
    data_steps = [s for s in scenario.steps if s.response_data and s.status == "completed"]

    for i, step in enumerate(data_steps[:3]):  # Max 3 data widgets
        if step.endpoint_id:
            endpoint = await db.get(ApiEndpoint, step.endpoint_id)
            if endpoint:
                # Determine widget type from response structure
                widget_type = _detect_widget_type(step.response_data)

                widgets.append(WidgetConfig(
                    scenario_id=scenario.id,
                    widget_type=widget_type,
                    title=endpoint.summary or f"{endpoint.method} {endpoint.path}",
                    data_source={
                        "endpoint_id": endpoint.id,
                        "step_id": step.id,
                        "field_mapping": {},
                    },
                    config={"clickable": True, "detail_view": True},
                    position={"x": (i % 2) * 6, "y": 4 + (i // 2) * 4, "w": 6, "h": 4},
                ))

    # Save widgets
    for w in widgets:
        db.add(w)
    await db.flush()

    return widgets


def _detect_widget_type(data: Any) -> str:
    """Detect appropriate widget type from data structure."""
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict):
            return "table"
        return "list"
    if isinstance(data, dict):
        if "count" in data or "total" in data or "sum" in data:
            return "kpi"
        if any(k in data for k in ["labels", "datasets", "series"]):
            return "chart"
    return "card"


def _detect_dashboard_type(query: str) -> str:
    """Detect dashboard type from query intent."""
    query_lower = query.lower()
    if any(k in query_lower for k in ["segment", "audience", "user", "customer"]):
        return "Audience Analysis"
    if any(k in query_lower for k in ["campaign", "push", "notification"]):
        return "Campaign Dashboard"
    if any(k in query_lower for k in ["kpi", "metric", "performance", "analytics"]):
        return "Performance Metrics"
    if any(k in query_lower for k in ["order", "payment", "transaction"]):
        return "Transaction Overview"
    return "API Explorer"


def _generate_description(scenario: ScenarioRun) -> str:
    """Generate human-readable description of the scenario."""
    steps_count = len(scenario.steps)
    completed = sum(1 for s in scenario.steps if s.status == "completed")
    return (
        f"Query: {scenario.query}\n"
        f"Steps: {completed}/{steps_count} completed\n"
        f"Status: {scenario.status}"
    )


def _extract_filters(scenario: ScenarioRun) -> list[dict[str, Any]]:
    """Extract available filters from scenario parameters."""
    filters = []
    # Collect distinct parameter names from API calls
    param_names = set()
    for step in scenario.steps:
        if step.request_payload:
            param_names.update(step.request_payload.keys())

    for param in param_names:
        filters.append({
            "field": param,
            "type": "string",  # Would detect from schema
            "label": param.replace("_", " ").title(),
        })

    return filters


def _default_position(index: int) -> dict[str, int]:
    """Calculate default grid position."""
    return {"x": (index % 2) * 6, "y": (index // 2) * 4, "w": 6, "h": 4}


def _generate_mock_widget_data(
    widget: WidgetConfig,
    endpoint: ApiEndpoint,
) -> dict[str, Any]:
    """Generate mock data for widget demonstration."""
    if widget.widget_type == "kpi":
        return {
            "value": 15420,
            "label": widget.title,
            "change": "+12%",
            "trend": "up",
            "last_updated": "2024-01-15T10:30:00Z",
        }
    elif widget.widget_type == "chart":
        return {
            "chart_type": widget.config.get("chart_type", "bar") if widget.config else "bar",
            "labels": ["Premium", "Active 60+", "High Value", "Regular"],
            "datasets": [
                {"label": "Audience Size", "data": [5230, 8921, 3412, 21857]},
            ],
        }
    elif widget.widget_type == "table":
        return {
            "columns": [
                {"field": "name", "header": "Segment", "sortable": True},
                {"field": "size", "header": "Size", "sortable": True, "type": "number"},
                {"field": "conversion", "header": "Conversion", "sortable": True, "type": "percentage"},
            ],
            "rows": [
                {"name": "Premium Users", "size": 5230, "conversion": 0.24},
                {"name": "Inactive 60+", "size": 8921, "conversion": 0.08},
                {"name": "High Value", "size": 3412, "conversion": 0.31},
            ],
            "total_rows": 3,
        }
    elif widget.widget_type == "card":
        return {
            "title": widget.title,
            "content": f"Data from {endpoint.method} {endpoint.path}",
            "metadata": {"endpoint_id": endpoint.id, "last_call": "2024-01-15T10:30:00Z"},
        }
    else:
        return {"data": "Widget data placeholder"}


def _suggest_for_endpoint(
    endpoint: ApiEndpoint,
    response_data: Any,
) -> list[dict[str, Any]]:
    """Suggest widgets based on endpoint and its response structure."""
    suggestions = []

    # Check response schema for patterns
    if isinstance(response_data, list):
        suggestions.append({
            "type": "table",
            "title": f"{endpoint.summary or 'Data'} List",
            "reason": "List data structure detected",
        })

    if isinstance(response_data, dict):
        if any(k in str(response_data).lower() for k in ["count", "total", "sum"]):
            suggestions.append({
                "type": "kpi",
                "title": "Key Metrics",
                "reason": "Aggregated metrics detected",
            })

    return suggestions


def _is_marketing_scenario(query: str) -> bool:
    """Detect if query is marketing-related."""
    marketing_terms = ["segment", "audience", "campaign", "push", "notification",
                       "email", "sms", "marketing", "conversion", "retention"]
    return any(term in query.lower() for term in marketing_terms)
