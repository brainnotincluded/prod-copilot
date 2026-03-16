"""Action confirmation endpoints for mutating operations.

Any state-changing action (POST/PUT/DELETE/PATCH) discovered during
orchestration requires explicit confirmation before execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, Role, require_role
from app.db.models import ActionConfirmation
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfirmationResponse(BaseModel):
    id: int
    correlation_id: str
    action: str
    endpoint_method: str
    endpoint_path: str
    payload_summary: str | None
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class CreateConfirmationRequest(BaseModel):
    correlation_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    endpoint_method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    endpoint_path: str = Field(..., min_length=1)
    payload_summary: str | None = None


class ResolveRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    resolver: str = Field(..., min_length=1, description="Name/email of the approving person")


@router.get("/confirmations", response_model=list[ConfirmationResponse])
async def list_confirmations(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    db: AsyncSession = Depends(get_db),
) -> list[ConfirmationResponse]:
    """List pending action confirmations."""
    result = await db.execute(
        select(ActionConfirmation)
        .where(ActionConfirmation.status == status)
        .order_by(ActionConfirmation.created_at.desc())
    )
    confirmations = result.scalars().all()
    return [
        ConfirmationResponse(
            id=c.id,
            correlation_id=c.correlation_id,
            action=c.action,
            endpoint_method=c.endpoint_method,
            endpoint_path=c.endpoint_path,
            payload_summary=c.payload_summary,
            status=c.status,
            created_at=str(c.created_at),
        )
        for c in confirmations
    ]


@router.post("/confirmations/{confirmation_id}/resolve")
async def resolve_confirmation(
    confirmation_id: int,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Approve or reject a pending action confirmation."""
    confirmation = await db.get(ActionConfirmation, confirmation_id)
    if not confirmation:
        raise HTTPException(status_code=404, detail="Confirmation not found.")
    if confirmation.status != "pending":
        raise HTTPException(status_code=409, detail=f"Confirmation already {confirmation.status}.")

    confirmation.status = body.status
    confirmation.resolved_at = datetime.now(timezone.utc)
    confirmation.resolved_by = body.resolver

    logger.info(
        "Confirmation %d %s by %s for %s %s",
        confirmation.id, body.status, body.resolver,
        confirmation.endpoint_method, confirmation.endpoint_path,
    )

    return {"message": f"Action {body.status}.", "id": confirmation.id}


@router.post("/confirmations", response_model=ConfirmationResponse, status_code=201)
async def create_confirmation(
    body: CreateConfirmationRequest,
    db: AsyncSession = Depends(get_db),
) -> ConfirmationResponse:
    """Create a new action confirmation request (called by orchestrator)."""
    confirmation = ActionConfirmation(
        correlation_id=body.correlation_id,
        action=body.action,
        endpoint_method=body.endpoint_method,
        endpoint_path=body.endpoint_path,
        payload_summary=body.payload_summary,
        status="pending",
    )
    db.add(confirmation)
    await db.flush()

    return ConfirmationResponse(
        id=confirmation.id,
        correlation_id=confirmation.correlation_id,
        action=confirmation.action,
        endpoint_method=confirmation.endpoint_method,
        endpoint_path=confirmation.endpoint_path,
        payload_summary=confirmation.payload_summary,
        status=confirmation.status,
        created_at=str(confirmation.created_at),
    )
