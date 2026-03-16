import pytest
from pydantic import ValidationError
from app.schemas.models import (
    EmbeddingRequest, EmbeddingResponse,
    SearchRequest, OrchestrationRequest,
    OrchestrationStep, ResultResponse,
    OrchestrationStreamEvent,
)


class TestEmbeddingRequest:
    def test_valid(self):
        r = EmbeddingRequest(texts=["hello"])
        assert r.texts == ["hello"]

    def test_empty_list_invalid(self):
        with pytest.raises(ValidationError):
            EmbeddingRequest(texts=[])

    def test_multiple_texts(self):
        r = EmbeddingRequest(texts=["hello", "world"])
        assert len(r.texts) == 2


class TestEmbeddingResponse:
    def test_valid(self):
        r = EmbeddingResponse(embeddings=[[0.1, 0.2], [0.3, 0.4]])
        assert len(r.embeddings) == 2


class TestSearchRequest:
    def test_valid(self):
        r = SearchRequest(query="find users")
        assert r.query == "find users"
        assert r.limit == 10  # default
        assert r.swagger_source_ids is None

    def test_empty_query_invalid(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_custom_limit(self):
        r = SearchRequest(query="test", limit=5)
        assert r.limit == 5

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=101)


class TestOrchestrationStep:
    def test_valid(self):
        s = OrchestrationStep(step=1, action="api_call", description="Test")
        assert s.status == "pending"

    def test_with_all_fields(self):
        s = OrchestrationStep(
            step=1, action="api_call", description="Test",
            endpoint={"method": "GET"}, parameters={"limit": 10},
            status="completed", result={"data": "ok"}, error=None,
        )
        assert s.result == {"data": "ok"}

    def test_step_number_must_be_positive(self):
        with pytest.raises(ValidationError):
            OrchestrationStep(step=0, action="api_call", description="Test")

    def test_valid_statuses(self):
        for status in ("pending", "running", "completed", "error"):
            s = OrchestrationStep(step=1, action="test", description="Test", status=status)
            assert s.status == status

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            OrchestrationStep(step=1, action="test", description="Test", status="invalid")

    def test_result_list_coerced_to_dict(self):
        """A list result should be wrapped in {'items': list}."""
        s = OrchestrationStep(step=1, action="test", description="Test", result=[1, 2, 3])
        assert s.result == {"items": [1, 2, 3]}

    def test_result_string_coerced_to_dict(self):
        """A string result should be wrapped in {'content': str}."""
        s = OrchestrationStep(step=1, action="test", description="Test", result="hello")
        assert s.result == {"content": "hello"}

    def test_result_number_coerced_to_dict(self):
        """A numeric result should be wrapped in {'content': str(num)}."""
        s = OrchestrationStep(step=1, action="test", description="Test", result=42)
        assert s.result == {"content": "42"}

    def test_result_none_stays_none(self):
        """None result should remain None."""
        s = OrchestrationStep(step=1, action="test", description="Test", result=None)
        assert s.result is None

    def test_result_dict_stays_dict(self):
        """Dict result should pass through unchanged."""
        s = OrchestrationStep(step=1, action="test", description="Test", result={"key": "val"})
        assert s.result == {"key": "val"}


class TestResultResponse:
    def test_valid_types(self):
        for t in ("text", "list", "table", "chart", "map", "dashboard"):
            r = ResultResponse(type=t, data={"key": "value"})
            assert r.type == t

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            ResultResponse(type="invalid", data={})

    def test_with_metadata(self):
        r = ResultResponse(type="text", data={"key": "val"}, metadata={"steps": 3})
        assert r.metadata["steps"] == 3

    def test_metadata_optional(self):
        r = ResultResponse(type="text", data={"key": "val"})
        assert r.metadata is None


class TestOrchestrationRequest:
    def test_empty_endpoints_allowed(self):
        r = OrchestrationRequest(query="test")
        assert r.endpoints == []

    def test_with_context(self):
        r = OrchestrationRequest(query="test", endpoints=[], context={"base_url": "https://example.com"})
        assert r.context["base_url"] == "https://example.com"

    def test_empty_query_invalid(self):
        with pytest.raises(ValidationError):
            OrchestrationRequest(query="")


class TestOrchestrationStreamEvent:
    def test_valid_events(self):
        for event_type in ("step_start", "step_complete", "step_error", "plan", "result"):
            e = OrchestrationStreamEvent(event=event_type, data={"key": "value"})
            assert e.event == event_type

    def test_invalid_event(self):
        with pytest.raises(ValidationError):
            OrchestrationStreamEvent(event="invalid", data={})
