"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Query / Orchestration
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query")
    swagger_source_ids: list[int] | None = Field(
        None,
        description="Optional list of swagger source IDs to limit the search scope",
    )


class ResultResponse(BaseModel):
    type: Literal["text", "list", "table", "map", "chart", "image", "dashboard"]
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


class OrchestrationStep(BaseModel):
    step: int
    action: str
    description: str
    status: Literal["pending", "running", "completed", "error"]
    result: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Swagger Source
# ---------------------------------------------------------------------------


class SwaggerSourceResponse(BaseModel):
    id: int
    name: str
    url: str | None = None
    base_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SwaggerUploadResponse(BaseModel):
    id: int
    name: str
    base_url: str | None = None
    endpoints_count: int
    message: str


# ---------------------------------------------------------------------------
# Endpoint search
# ---------------------------------------------------------------------------


class EndpointSearchResult(BaseModel):
    id: int
    swagger_source_id: int
    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[dict[str, Any]] | None = None
    request_body: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None

    model_config = {"from_attributes": True}
