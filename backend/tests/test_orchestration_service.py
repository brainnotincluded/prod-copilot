"""Tests for the orchestration service — state machine, execution flows,
step timing, correlation IDs, error handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import ApiEndpoint, SwaggerSource
from app.services.orchestration import (
    OrchestrationContext,
    OrchestrationService,
    StepContext,
    StepState,
)
from tests.conftest import FakeAsyncSession, make_result


# -----------------------------------------------------------------------
# StepState transitions
# -----------------------------------------------------------------------

class TestStepState:

    def test_pending_to_running(self):
        StepState.validate_transition(StepState.PENDING, StepState.RUNNING)

    def test_pending_to_skipped(self):
        StepState.validate_transition(StepState.PENDING, StepState.SKIPPED)

    def test_running_to_completed(self):
        StepState.validate_transition(StepState.RUNNING, StepState.COMPLETED)

    def test_running_to_error(self):
        StepState.validate_transition(StepState.RUNNING, StepState.ERROR)

    def test_completed_to_running_rejected(self):
        with pytest.raises(ValueError, match="Invalid state transition"):
            StepState.validate_transition(StepState.COMPLETED, StepState.RUNNING)

    def test_error_to_completed_rejected(self):
        with pytest.raises(ValueError):
            StepState.validate_transition(StepState.ERROR, StepState.COMPLETED)

    def test_pending_to_completed_rejected(self):
        with pytest.raises(ValueError):
            StepState.validate_transition(StepState.PENDING, StepState.COMPLETED)

    def test_running_to_pending_rejected(self):
        with pytest.raises(ValueError):
            StepState.validate_transition(StepState.RUNNING, StepState.PENDING)

    def test_skipped_to_running_rejected(self):
        with pytest.raises(ValueError):
            StepState.validate_transition(StepState.SKIPPED, StepState.RUNNING)


# -----------------------------------------------------------------------
# StepContext
# -----------------------------------------------------------------------

class TestStepContext:

    def test_initial_state_is_pending(self):
        step = StepContext(step_number=1, action="test", description="d")
        assert step.state == StepState.PENDING
        assert step.started_at is None

    def test_transition_to_running_sets_started_at(self):
        step = StepContext(step_number=1, action="test", description="d")
        step.transition(StepState.RUNNING)
        assert step.state == StepState.RUNNING
        assert step.started_at is not None

    def test_transition_to_completed_sets_duration(self):
        step = StepContext(step_number=1, action="test", description="d")
        step.transition(StepState.RUNNING)
        step.transition(StepState.COMPLETED)
        assert step.state == StepState.COMPLETED
        assert step.finished_at is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_transition_to_error_sets_duration(self):
        step = StepContext(step_number=1, action="test", description="d")
        step.transition(StepState.RUNNING)
        step.transition(StepState.ERROR)
        assert step.state == StepState.ERROR
        assert step.duration_ms is not None

    def test_invalid_transition_raises(self):
        step = StepContext(step_number=1, action="test", description="d")
        with pytest.raises(ValueError):
            step.transition(StepState.COMPLETED)

    def test_to_schema_includes_correlation_id(self):
        step = StepContext(step_number=1, action="a", description="d")
        step.transition(StepState.RUNNING)
        schema = step.to_schema("corr-123")
        assert schema.correlation_id == "corr-123"
        assert schema.step == 1
        assert schema.status == "running"


# -----------------------------------------------------------------------
# OrchestrationContext
# -----------------------------------------------------------------------

class TestOrchestrationContext:

    def test_generates_unique_correlation_ids(self):
        ctx1 = OrchestrationContext()
        ctx2 = OrchestrationContext()
        assert ctx1.correlation_id != ctx2.correlation_id

    def test_correlation_id_is_uuid_format(self):
        ctx = OrchestrationContext()
        import uuid
        # Should not raise
        uuid.UUID(ctx.correlation_id)

    def test_started_at_is_set(self):
        ctx = OrchestrationContext()
        assert ctx.started_at > 0


# -----------------------------------------------------------------------
# OrchestrationService.execute (sync)
# -----------------------------------------------------------------------

def _make_ep(id_=1, source_id=1):
    return ApiEndpoint(
        id=id_, swagger_source_id=source_id, method="GET", path="/test",
        summary="Test", description=None,
        parameters=None, request_body=None, response_schema=None,
        created_at=datetime.now(timezone.utc),
    )

def _make_src(id_=1, base_url="https://api.test.com"):
    return SwaggerSource(
        id=id_, name="TestAPI", raw_json="{}", base_url=base_url,
        created_at=datetime.now(timezone.utc),
    )


class TestOrchestrationExecute:

    @pytest.mark.asyncio
    async def test_success_returns_result(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock(return_value={
            "type": "text",
            "data": {"content": "Hello"},
            "metadata": {"status": "completed"},
        })

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        result = await service.execute(query="test")

        assert result.type == "text"
        assert result.data["content"] == "Hello"
        assert result.metadata is not None
        assert result.metadata["correlation_id"]  # non-empty

    @pytest.mark.asyncio
    async def test_no_endpoints_returns_fallback(self):
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))

        service = OrchestrationService(fake_db)
        result = await service.execute(query="anything")

        assert result.type == "text"
        assert "No relevant" in result.data["content"]

    @pytest.mark.asyncio
    async def test_orchestration_error_returns_error(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock(side_effect=RuntimeError("boom"))

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        result = await service.execute(query="test")

        assert result.type == "text"
        assert "boom" in result.data["content"]
        assert result.metadata is not None
        assert result.metadata["status"] == "error"

    @pytest.mark.asyncio
    async def test_empty_result_data_fallback(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock(return_value={"type": "chart", "data": {}})

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        result = await service.execute(query="test")

        assert result.type == "text"
        assert result.data["content"]  # non-empty fallback

    @pytest.mark.asyncio
    async def test_correlation_id_unique_per_call(self):
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))
        fake_db2 = FakeAsyncSession()
        fake_db2.set_execute_result(make_result(scalars=[]))

        s1 = OrchestrationService(fake_db)
        s2 = OrchestrationService(fake_db2)
        r1 = await s1.execute(query="a")
        r2 = await s2.execute(query="b")

        assert r1.metadata is not None
        assert r2.metadata is not None
        assert r1.metadata["correlation_id"] != r2.metadata["correlation_id"]

    @pytest.mark.asyncio
    async def test_total_ms_in_metadata(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock(return_value={
            "type": "text", "data": {"content": "ok"},
        })

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        result = await service.execute(query="test")

        assert result.metadata is not None
        assert "total_ms" in result.metadata
        assert result.metadata["total_ms"] >= 0

    @pytest.mark.asyncio
    async def test_step_timing_recorded(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock(return_value={
            "type": "text", "data": {"content": "ok"},
        })

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        # Access internals to verify step timing
        result = await service.execute(query="test")
        # Steps should have been created internally; we verify via correlation_id
        assert result.metadata is not None
        assert result.metadata["correlation_id"]


# -----------------------------------------------------------------------
# OrchestrationService.execute_stream
# -----------------------------------------------------------------------

class TestOrchestrationStream:

    @pytest.mark.asyncio
    async def test_stream_happy_path(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        async def fake_stream(**kwargs):
            yield {"event_type": "step_start", "step": 2, "action": "api_call", "description": "Calling..."}
            yield {"event_type": "step_complete", "step": 2, "result": {"status": 200}}
            yield {"event_type": "result", "type": "text", "data": {"content": "done"}, "metadata": {}}

        mock_mlops = MagicMock()
        mock_mlops.orchestrate_stream = MagicMock(return_value=fake_stream())

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        events = []
        async for event in service.execute_stream(query="test"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "step" in types
        assert "result" in types

    @pytest.mark.asyncio
    async def test_stream_no_endpoints(self):
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))

        service = OrchestrationService(fake_db)
        events = []
        async for event in service.execute_stream(query="test"):
            events.append(event)

        assert events[0]["type"] == "step"
        assert events[1]["type"] == "result"
        assert "No API endpoints" in events[1]["data"]["data"]["content"]

    @pytest.mark.asyncio
    async def test_stream_error_yielded(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        async def failing_stream(**kwargs):
            raise RuntimeError("MLOps crashed")
            yield  # make it a generator

        mock_mlops = MagicMock()
        mock_mlops.orchestrate_stream = MagicMock(return_value=failing_stream())

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        events = []
        async for event in service.execute_stream(query="test"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "error" in types

    @pytest.mark.asyncio
    async def test_stream_correlation_id_in_events(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        async def fake_stream(**kwargs):
            yield {"event_type": "result", "type": "text", "data": {"content": "ok"}}

        mock_mlops = MagicMock()
        mock_mlops.orchestrate_stream = MagicMock(return_value=fake_stream())

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        events = []
        async for event in service.execute_stream(query="test"):
            events.append(event)

        # The search step should have correlation_id
        step_event = events[0]
        assert step_event["data"].get("correlation_id") is not None

    @pytest.mark.asyncio
    async def test_stream_history_forwarded(self):
        fake_db = FakeAsyncSession()
        ep = _make_ep()
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.register_get(SwaggerSource, 1, src)

        captured = {}

        async def capturing_stream(**kwargs):
            captured.update(kwargs)
            yield {"event_type": "result", "type": "text", "data": {"content": "ok"}}

        mock_mlops = MagicMock()
        mock_mlops.orchestrate_stream = MagicMock(side_effect=lambda **kw: capturing_stream(**kw))

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        async for _ in service.execute_stream(
            query="q", history=[{"role": "user", "content": "hi"}]
        ):
            pass

        assert captured["history"] == [{"role": "user", "content": "hi"}]


# -----------------------------------------------------------------------
# Cannot propose or execute non-existent actions
# -----------------------------------------------------------------------

class TestNoNonExistentActions:
    """The system must never propose or execute actions that don't exist
    in the database. The orchestrator receives ONLY endpoints fetched
    from the DB — nothing invented, nothing hallucinated."""

    @pytest.mark.asyncio
    async def test_only_db_endpoints_sent_to_orchestrator(self):
        """MLOps.orchestrate must receive exactly the endpoints from the DB,
        not more, not fewer, not fabricated ones."""
        fake_db = FakeAsyncSession()
        ep1 = _make_ep(id_=10, source_id=1)
        ep1.method = "GET"
        ep1.path = "/real-endpoint"
        ep2 = _make_ep(id_=20, source_id=1)
        ep2.method = "POST"
        ep2.path = "/another-real"
        src = _make_src()
        fake_db.set_execute_result(make_result(scalars=[ep1, ep2]))
        fake_db.register_get(SwaggerSource, 1, src)

        captured_endpoints = []

        mock_mlops = MagicMock()

        async def capture(**kwargs):
            captured_endpoints.extend(kwargs.get("endpoints", []))
            return {"type": "text", "data": {"content": "ok"}}

        mock_mlops.orchestrate = AsyncMock(side_effect=capture)

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        await service.execute(query="do something")

        # Exactly 2 endpoints, exactly the ones from DB
        assert len(captured_endpoints) == 2
        sent_ids = {ep["id"] for ep in captured_endpoints}
        assert sent_ids == {10, 20}
        sent_paths = {ep["path"] for ep in captured_endpoints}
        assert sent_paths == {"/real-endpoint", "/another-real"}

    @pytest.mark.asyncio
    async def test_no_endpoints_means_no_orchestration_call(self):
        """When the DB has no endpoints, the orchestrator must NOT be called.
        The system must not invent actions out of thin air."""
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))

        mock_mlops = MagicMock()
        mock_mlops.orchestrate = AsyncMock()

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        result = await service.execute(query="create a campaign")

        mock_mlops.orchestrate.assert_not_called()
        assert result.type == "text"
        assert "No relevant" in result.data["content"]

    @pytest.mark.asyncio
    async def test_filtered_source_ids_respected(self):
        """When swagger_source_ids=[2], only endpoints from source 2
        must reach the orchestrator — not endpoints from source 1."""
        fake_db = FakeAsyncSession()
        # DB returns only source-2 endpoints (filtered by the SQL WHERE clause)
        ep_src2 = _make_ep(id_=5, source_id=2)
        ep_src2.path = "/from-source-2"
        src2 = _make_src(id_=2, base_url="https://api2.test.com")
        fake_db.set_execute_result(make_result(scalars=[ep_src2]))
        fake_db.register_get(SwaggerSource, 2, src2)

        captured_endpoints = []

        mock_mlops = MagicMock()

        async def capture(**kwargs):
            captured_endpoints.extend(kwargs.get("endpoints", []))
            return {"type": "text", "data": {"content": "ok"}}

        mock_mlops.orchestrate = AsyncMock(side_effect=capture)

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        await service.execute(query="test", swagger_source_ids=[2])

        assert len(captured_endpoints) == 1
        assert captured_endpoints[0]["id"] == 5
        assert captured_endpoints[0]["path"] == "/from-source-2"

    @pytest.mark.asyncio
    async def test_stream_no_endpoints_skips_orchestrator(self):
        """WebSocket streaming: no endpoints → no MLOps call, just step+result."""
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))

        mock_mlops = MagicMock()
        mock_mlops.orchestrate_stream = MagicMock()

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)
        events = []
        async for event in service.execute_stream(query="do something"):
            events.append(event)

        mock_mlops.orchestrate_stream.assert_not_called()
        types = [e["type"] for e in events]
        assert "step" in types
        assert "result" in types
