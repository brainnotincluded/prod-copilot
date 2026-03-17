"""Tests for audit logging and observability.

Covers: log format, correlation IDs, sensitive data handling, step timing.
"""

import time
import logging

from app.services.orchestration import (
    OrchestrationContext,
    OrchestrationService,
    StepContext,
    StepState,
)


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


class TestSensitiveDataHandling:
    """Sensitive data should not appear in logs."""

    def test_password_not_in_logs(self, caplog):
        """Passwords should never appear in logs."""
        ctx = OrchestrationContext()

        with caplog.at_level(logging.INFO):
            OrchestrationService._log(ctx, "auth.login", email="user@example.com")

        for record in caplog.records:
            assert "password" not in record.getMessage().lower()
            assert "secret" not in record.getMessage().lower()


class TestStepTiming:
    """Step timing and performance logging."""

    def test_duration_ms_recorded(self):
        """Step execution duration should be recorded."""
        step = StepContext(step_number=1, action="test", description="Test step")

        step.transition(StepState.RUNNING)
        time.sleep(0.01)  # Small delay
        step.transition(StepState.COMPLETED)

        assert step.duration_ms is not None
        assert step.duration_ms >= 10  # At least 10ms

    def test_duration_not_set_without_running(self):
        """Duration should not be set if step never ran."""
        step = StepContext(step_number=1, action="test", description="Test step")

        # Transition directly to skipped (valid from pending)
        step.transition(StepState.SKIPPED)

        # duration_ms should still be None since it never ran
        assert step.duration_ms is None
