from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, description="List of texts to embed")


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]


class IndexRequest(BaseModel):
    swagger_source_id: int = Field(..., description="ID of the swagger source")
    endpoints: list[dict] = Field(..., min_length=1, description="List of endpoint definitions")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query")
    swagger_source_ids: list[int] | None = Field(
        default=None, description="Optional filter by swagger source IDs"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")


class SearchResult(BaseModel):
    endpoint: dict
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")


class SearchResponse(BaseModel):
    results: list[SearchResult]


class OrchestrationRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query")
    endpoints: list[dict] = Field(
        default_factory=list, description="Available API endpoints (legacy, prefer swagger_source_ids)"
    )
    swagger_source_ids: list[int] | None = Field(
        default=None, description="Swagger source IDs for RAG endpoint search"
    )
    context: dict | None = Field(
        default=None, description="Additional context for orchestration"
    )


class OrchestrationStep(BaseModel):
    step: int = Field(..., ge=1, description="Step number in the plan")
    action: str = Field(..., description="Action to perform (api_call, data_process, aggregate, etc.)")
    description: str = Field(..., description="Human-readable description of the step")
    endpoint: dict | None = Field(default=None, description="Endpoint definition for api_call actions")
    parameters: dict | None = Field(default=None, description="Parameters for the action")
    status: Literal["pending", "running", "completed", "error"] = Field(
        default="pending"
    )
    result: dict | None = None
    error: str | None = None

    @field_validator("result", mode="before")
    @classmethod
    def coerce_result_to_dict(cls, v: Any) -> dict | None:
        """Ensure result is always dict or None, never list/str/number."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            return {"items": v}
        return {"content": str(v)}


class ResultResponse(BaseModel):
    type: Literal["text", "list", "table", "map", "chart", "image", "dashboard"] = Field(
        ..., description="Type of the response data"
    )
    data: dict = Field(..., description="Response data payload")
    metadata: dict | None = Field(
        default=None, description="Optional metadata about the response"
    )


class OrchestrationStreamEvent(BaseModel):
    event: Literal["step_start", "step_complete", "step_error", "plan", "result"] = (
        Field(..., description="Type of stream event")
    )
    data: dict = Field(..., description="Event data payload")
