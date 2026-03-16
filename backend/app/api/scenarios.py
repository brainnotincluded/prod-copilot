"""API for visual scenarios and execution history.

Stores and retrieves scenario runs with their step-by-step execution,
enabling the visual graph view and history of runs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScenarioRun, ScenarioStep, ApiEndpoint, ActionConfirmation
from app.db.session import get_db
from app.schemas.models import ResultResponse
from app.services.orchestration import OrchestrationService

logger = logging.getLogger(__name__)
router = APIRouter()


class ScenarioCreateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    swagger_source_ids: list[int] | None = None


class ScenarioResponse(BaseModel):
    id: int
    correlation_id: str
    query: str
    status: str
    graph_nodes: list[dict[str, Any]] | None
    graph_edges: list[dict[str, Any]] | None
    summary: dict[str, Any] | None
    created_at: str
    finished_at: str | None

    model_config = {"from_attributes": True}


class StepResponse(BaseModel):
    id: int
    step_number: int
    action: str
    description: str
    status: str
    endpoint_id: int | None
    endpoint_method: str | None
    endpoint_path: str | None
    request_payload: dict[str, Any] | None
    response_data: dict[str, Any] | None
    reasoning: str | None
    alternatives: list[dict[str, Any]] | None
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    error_message: str | None
    confirmation_status: str | None  # pending/approved/rejected if mutating

    model_config = {"from_attributes": True}


@router.post("/scenarios", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    request: ScenarioCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """Start a new scenario execution.

    This creates the scenario record and initiates orchestration,
    storing the execution plan for visual display.
    """
    # Create scenario record
    scenario = ScenarioRun(
        query=request.query,
        status="running",
        graph_nodes=[],
        graph_edges=[],
        summary={"total_steps": 0, "completed": 0},
    )
    db.add(scenario)
    await db.flush()

    # Run orchestration (this will populate steps)
    service = OrchestrationService(db)
    result = await service.execute_scenario(
        scenario_id=scenario.id,
        query=request.query,
        swagger_source_ids=request.swagger_source_ids,
    )

    # Reload scenario with updated data
    await db.refresh(scenario)

    return ScenarioResponse(
        id=scenario.id,
        correlation_id=scenario.correlation_id,
        query=scenario.query,
        status=scenario.status,
        graph_nodes=scenario.graph_nodes,
        graph_edges=scenario.graph_edges,
        summary=scenario.summary,
        created_at=str(scenario.created_at),
        finished_at=str(scenario.finished_at) if scenario.finished_at else None,
    )


@router.get("/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
    status: str | None = Query(None, pattern="^(running|completed|error|cancelled)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
    """List scenario execution history."""
    stmt = select(ScenarioRun).order_by(ScenarioRun.created_at.desc())
    if status:
        stmt = stmt.where(ScenarioRun.status == status)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    scenarios = result.scalars().all()

    return [
        ScenarioResponse(
            id=s.id,
            correlation_id=s.correlation_id,
            query=s.query,
            status=s.status,
            graph_nodes=s.graph_nodes,
            graph_edges=s.graph_edges,
            summary=s.summary,
            created_at=str(s.created_at),
            finished_at=str(s.finished_at) if s.finished_at else None,
        )
        for s in scenarios
    ]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """Get scenario details including graph structure."""
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return ScenarioResponse(
        id=scenario.id,
        correlation_id=scenario.correlation_id,
        query=scenario.query,
        status=scenario.status,
        graph_nodes=scenario.graph_nodes,
        graph_edges=scenario.graph_edges,
        summary=scenario.summary,
        created_at=str(scenario.created_at),
        finished_at=str(scenario.finished_at) if scenario.finished_at else None,
    )


@router.get("/scenarios/{scenario_id}/steps", response_model=list[StepResponse])
async def get_scenario_steps(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[StepResponse]:
    """Get detailed steps of a scenario with reasoning chain.

    This powers the UI block showing:
    - Which steps were chosen
    - Why they were chosen
    - Which alternatives were rejected
    """
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    result = await db.execute(
        select(ScenarioStep)
        .where(ScenarioStep.scenario_id == scenario_id)
        .order_by(ScenarioStep.step_number)
    )
    steps = result.scalars().all()

    # Enrich with endpoint info and confirmation status
    responses = []
    for step in steps:
        endpoint_method = None
        endpoint_path = None
        if step.endpoint_id:
            endpoint = await db.get(ApiEndpoint, step.endpoint_id)
            if endpoint:
                endpoint_method = endpoint.method
                endpoint_path = endpoint.path

        # Check for confirmation
        confirmation_status = None
        if step.action in ("api_call", "mutating_action"):
            conf_result = await db.execute(
                select(ActionConfirmation).where(
                    ActionConfirmation.scenario_step_id == step.id
                )
            )
            confirmation = conf_result.scalar_one_or_none()
            if confirmation:
                confirmation_status = confirmation.status

        responses.append(StepResponse(
            id=step.id,
            step_number=step.step_number,
            action=step.action,
            description=step.description,
            status=step.status,
            endpoint_id=step.endpoint_id,
            endpoint_method=endpoint_method,
            endpoint_path=endpoint_path,
            request_payload=step.request_payload,
            response_data=step.response_data,
            reasoning=step.reasoning,
            alternatives=step.alternatives,
            started_at=str(step.started_at) if step.started_at else None,
            finished_at=str(step.finished_at) if step.finished_at else None,
            duration_ms=step.duration_ms,
            error_message=step.error_message,
            confirmation_status=confirmation_status,
        ))

    return responses


@router.post("/scenarios/{scenario_id}/cancel")
async def cancel_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a running scenario."""
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.status not in ("running", "pending"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel {scenario.status} scenario")

    scenario.status = "cancelled"
    # Mark pending steps as skipped
    for step in scenario.steps:
        if step.status in ("pending", "running"):
            step.status = "skipped"

    return {"message": "Scenario cancelled", "id": scenario_id}


@router.get("/scenarios/{scenario_id}/graph")
async def get_scenario_graph(
    scenario_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the visual graph representation of a scenario.

    Returns nodes and edges formatted for graph visualization libraries.
    """
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Build graph from stored nodes/edges or generate from steps
    nodes = scenario.graph_nodes or []
    edges = scenario.graph_edges or []

    # If no stored graph, generate from steps
    if not nodes and scenario.steps:
        nodes = []
        edges = []
        prev_node_id = None

        for step in scenario.steps:
            node_id = f"step_{step.id}"
            node = {
                "id": node_id,
                "type": step.action,  # api_call, transform, decision
                "label": step.description[:50],
                "status": step.status,
                "step_number": step.step_number,
            }
            if step.endpoint_id:
                endpoint = await db.get(ApiEndpoint, step.endpoint_id)
                if endpoint:
                    node["endpoint"] = f"{endpoint.method} {endpoint.path}"
                    node["api_source"] = endpoint.swagger_source.name if endpoint.swagger_source else None

            nodes.append(node)

            if prev_node_id:
                edges.append({
                    "id": f"edge_{prev_node_id}_{node_id}",
                    "from": prev_node_id,
                    "to": node_id,
                    "type": "sequence",
                })
            prev_node_id = node_id

    return {
        "nodes": nodes,
        "edges": edges,
        "layout": "dagre",  # Suggested layout algorithm
        "direction": "TB",  # Top to bottom
    }


@router.post("/scenarios/{scenario_id}/confirm/{step_id}")
async def confirm_scenario_step(
    scenario_id: int,
    step_id: int,
    resolver: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm a mutating step in a scenario.

    Triggers execution of the confirmed step and continues the scenario.
    """
    scenario = await db.get(ScenarioRun, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    step = await db.get(ScenarioStep, step_id)
    if not step or step.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Step not found")

    # Find the confirmation record
    result = await db.execute(
        select(ActionConfirmation).where(
            ActionConfirmation.scenario_step_id == step_id
        )
    )
    confirmation = result.scalar_one_or_none()

    if not confirmation:
        raise HTTPException(status_code=404, detail="No confirmation required for this step")

    if confirmation.status != "pending":
        raise HTTPException(status_code=409, detail=f"Step already {confirmation.status}")

    # Update confirmation
    from datetime import datetime, timezone
    confirmation.status = "approved"
    confirmation.resolved_at = datetime.now(timezone.utc)
    confirmation.resolved_by = resolver

    # Resume scenario execution
    service = OrchestrationService(db)
    await service.resume_scenario(scenario_id, from_step_id=step_id)

    return {"message": "Step confirmed and scenario resumed", "step_id": step_id}
