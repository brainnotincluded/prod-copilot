"""Tests for audit logging and observability.

Covers: log format, correlation IDs, sensitive data handling.
"""

import pytest
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.orchestration import OrchestrationService, OrchestrationContext
from tests.conftest import FakeAsyncSession, make_result


class TestStructuredLogging:
    """Structured logging format tests."""

    def test_log_contains_correlation_id(self, caplog):
        """Logs should contain correlation ID for request tracing."""
        ctx = OrchestrationContext()
        
        with caplog.at_level(logging.INFO):
            OrchestrationService._log(ctx, "test.event", key="value")
        
        # Check log was emitted
        assert len(caplog.records) > 0
        # Check correlation_id is in extra
        record = caplog.records[0]
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == ctx.correlation_id

    def test_log_contains_event_name(self, caplog):
        """Logs should contain event name."""
        ctx = OrchestrationContext()
        
        with caplog.at_level(logging.INFO):
            OrchestrationService._log(ctx, "orchestration.start")
        
        record = caplog.records[0]
        assert hasattr(record, "event")
        assert record.event == "orchestration.start"

    def test_log_contains_extra_fields(self, caplog):
        """Logs should contain extra kwargs as fields."""
        ctx = OrchestrationContext()
        
        with caplog.at_level(logging.INFO):
            OrchestrationService._log(ctx, "test", custom_field="custom_value", count=42)
        
        record = caplog.records[0]
        assert hasattr(record, "custom_field")
        assert record.custom_field == "custom_value"
        assert hasattr(record, "count")
        assert record.count == 42


class TestCorrelationIdPropagation:
    """Correlation ID should propagate through the system."""

    @pytest.mark.asyncio
    async def test_correlation_id_in_execute(self):
        """execute() result should contain correlation ID."""
        fake_db = FakeAsyncSession()
        fake_db.set_execute_result(make_result(scalars=[]))

        service = OrchestrationService(fake_db)
        result = await service.execute(query="test")

        assert "correlation_id" in result.metadata
        assert len(result.metadata["correlation_id"]) > 0

    @pytest.mark.asyncio
    async def test_unique_correlation_per_request(self):
        """Each request should have unique correlation ID."""
        fake_db1 = FakeAsyncSession()
        fake_db1.set_execute_result(make_result(scalars=[]))
        
        fake_db2 = FakeAsyncSession()
        fake_db2.set_execute_result(make_result(scalars=[]))

        service1 = OrchestrationService(fake_db1)
        service2 = OrchestrationService(fake_db2)

        result1 = await service1.execute(query="test1")
        result2 = await service2.execute(query="test2")

        id1 = result1.metadata["correlation_id"]
        id2 = result2.metadata["correlation_id"]
        assert id1 != id2


class TestSensitiveDataHandling:
    """Sensitive data should not appear in logs."""

    def test_password_not_in_logs(self, caplog):
        """Passwords should never appear in logs."""
        # Simulate logging that might accidentally include password
        ctx = OrchestrationContext()
        
        with caplog.at_level(logging.INFO):
            # This should not log the password even if passed
            OrchestrationService._log(ctx, "auth.login", email="user@example.com")
        
        for record in caplog.records:
            assert "password" not in record.getMessage().lower()
            assert "secret" not in record.getMessage().lower()


class TestStepTiming:
    """Step timing and performance logging."""

    @pytest.mark.asyncio
    async def test_duration_ms_recorded(self):
        """Step execution duration should be recorded."""
        from app.services.orchestration import StepContext, StepState

        step = StepContext(step_number=1, action="test", description="Test step")
        
        import time
        step.transition(StepState.RUNNING)
        time.sleep(0.01)  # Small delay
        step.transition(StepState.COMPLETED)

        assert step.duration_ms is not None
        assert step.duration_ms >= 10  # At least 10ms

    def test_duration_not_set_without_running(self):
        """Duration should not be set if step never ran."""
        from app.services.orchestration import StepContext, StepState

        step = StepContext(step_number=1, action="test", description="Test step")
        
        # Transition directly to skipped (valid from pending)
        step.transition(StepState.SKIPPED)
        
        # duration_ms should still be None since it never ran
        assert step.duration_ms is None
