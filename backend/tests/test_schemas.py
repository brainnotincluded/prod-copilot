"""Strict validation tests for Pydantic schemas.

Every schema is tested for:
  - valid construction
  - required field enforcement
  - type / Literal constraints
  - optional fields default to None
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.models import (
    EndpointSearchResult,
    OrchestrationStep,
    QueryRequest,
    ResultResponse,
    SwaggerSourceResponse,
    SwaggerUploadResponse,
)


# -----------------------------------------------------------------------
# QueryRequest
# -----------------------------------------------------------------------

class TestQueryRequest:

    def test_valid(self):
        qr = QueryRequest(query="show users")
        assert qr.query == "show users"
        assert qr.swagger_source_ids is None

    def test_with_source_ids(self):
        qr = QueryRequest(query="x", swagger_source_ids=[1, 2])
        assert qr.swagger_source_ids == [1, 2]

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_missing_query_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest()


# -----------------------------------------------------------------------
# ResultResponse
# -----------------------------------------------------------------------

class TestResultResponse:

    VALID_TYPES = ("text", "list", "table", "map", "chart", "image", "dashboard")

    @pytest.mark.parametrize("t", VALID_TYPES)
    def test_all_valid_types(self, t):
        r = ResultResponse(type=t, data={"key": "val"})
        assert r.type == t

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ResultResponse(type="unknown", data={})

    def test_metadata_optional(self):
        r = ResultResponse(type="text", data={})
        assert r.metadata is None

    def test_metadata_accepted(self):
        r = ResultResponse(type="text", data={}, metadata={"x": 1})
        assert r.metadata == {"x": 1}

    def test_missing_data_rejected(self):
        with pytest.raises(ValidationError):
            ResultResponse(type="text")

    def test_missing_type_rejected(self):
        with pytest.raises(ValidationError):
            ResultResponse(data={})


# -----------------------------------------------------------------------
# OrchestrationStep
# -----------------------------------------------------------------------

class TestOrchestrationStep:

    def test_valid(self):
        s = OrchestrationStep(step=1, action="search", description="Searching", status="running")
        assert s.step == 1
        assert s.result is None

    @pytest.mark.parametrize("status", ("pending", "running", "completed", "error"))
    def test_valid_statuses(self, status):
        s = OrchestrationStep(step=1, action="a", description="d", status=status)
        assert s.status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            OrchestrationStep(step=1, action="a", description="d", status="unknown")

    def test_result_optional(self):
        s = OrchestrationStep(step=1, action="a", description="d", status="completed", result={"data": 1})
        assert s.result == {"data": 1}


# -----------------------------------------------------------------------
# SwaggerSourceResponse
# -----------------------------------------------------------------------

class TestSwaggerSourceResponse:

    def test_valid(self):
        now = datetime.now(timezone.utc)
        r = SwaggerSourceResponse(id=1, name="API", created_at=now)
        assert r.url is None
        assert r.base_url is None

    def test_all_fields(self):
        now = datetime.now(timezone.utc)
        r = SwaggerSourceResponse(
            id=1, name="API", url="http://x", base_url="http://y", created_at=now
        )
        assert r.url == "http://x"

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            SwaggerSourceResponse(id=1, created_at=datetime.now(timezone.utc))

    def test_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            SwaggerSourceResponse(name="X", created_at=datetime.now(timezone.utc))


# -----------------------------------------------------------------------
# SwaggerUploadResponse
# -----------------------------------------------------------------------

class TestSwaggerUploadResponse:

    def test_valid(self):
        r = SwaggerUploadResponse(id=1, name="API", endpoints_count=5, message="ok")
        assert r.base_url is None

    def test_missing_message_rejected(self):
        with pytest.raises(ValidationError):
            SwaggerUploadResponse(id=1, name="API", endpoints_count=5)

    def test_zero_endpoints_allowed(self):
        r = SwaggerUploadResponse(id=1, name="X", endpoints_count=0, message="m")
        assert r.endpoints_count == 0


# -----------------------------------------------------------------------
# EndpointSearchResult
# -----------------------------------------------------------------------

class TestEndpointSearchResult:

    def test_valid_minimal(self):
        r = EndpointSearchResult(id=1, swagger_source_id=1, method="GET", path="/x")
        assert r.summary is None
        assert r.description is None
        assert r.parameters is None
        assert r.request_body is None
        assert r.response_schema is None

    def test_valid_full(self):
        r = EndpointSearchResult(
            id=1,
            swagger_source_id=2,
            method="POST",
            path="/y",
            summary="Create",
            description="Creates a resource",
            parameters=[{"name": "q", "in": "query", "required": False, "description": "", "schema": "string"}],
            request_body={"type": "object"},
            response_schema={"type": "object"},
        )
        assert r.method == "POST"
        assert len(r.parameters) == 1

    def test_missing_method_rejected(self):
        with pytest.raises(ValidationError):
            EndpointSearchResult(id=1, swagger_source_id=1, path="/x")

    def test_missing_path_rejected(self):
        with pytest.raises(ValidationError):
            EndpointSearchResult(id=1, swagger_source_id=1, method="GET")
