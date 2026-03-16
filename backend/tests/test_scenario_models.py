"""Tests for ScenarioRun and ScenarioStep models.

Covers: table structure, relationships, state constraints.
"""

import pytest

from app.db.models import ScenarioRun, ScenarioStep


class TestScenarioRunModel:
    """SQLAlchemy ScenarioRun model validation."""

    def test_table_name(self):
        assert ScenarioRun.__tablename__ == "scenario_runs"

    def test_correlation_id_indexed(self):
        """correlation_id should be indexed for fast lookups."""
        col = ScenarioRun.__table__.columns["correlation_id"]
        assert col.index is True
        assert col.unique is True

    def test_status_default(self):
        cols = {c.name: c for c in ScenarioRun.__table__.columns}
        assert cols["status"].default.arg == "running"

    def test_required_columns(self):
        cols = {c.name: c for c in ScenarioRun.__table__.columns}
        assert cols["correlation_id"].nullable is False
        assert cols["query"].nullable is False

    def test_json_columns_nullable(self):
        """Graph and summary columns should be nullable."""
        cols = {c.name: c for c in ScenarioRun.__table__.columns}
        assert cols["graph_nodes"].nullable is True
        assert cols["graph_edges"].nullable is True
        assert cols["summary"].nullable is True

    def test_finished_at_nullable(self):
        cols = {c.name: c for c in ScenarioRun.__table__.columns}
        assert cols["finished_at"].nullable is True


class TestScenarioStepModel:
    """SQLAlchemy ScenarioStep model validation."""

    def test_table_name(self):
        assert ScenarioStep.__tablename__ == "scenario_steps"

    def test_status_default(self):
        cols = {c.name: c for c in ScenarioStep.__table__.columns}
        assert cols["status"].default.arg == "pending"

    def test_required_columns(self):
        cols = {c.name: c for c in ScenarioStep.__table__.columns}
        assert cols["scenario_id"].nullable is False
        assert cols["step_number"].nullable is False
        assert cols["action"].nullable is False
        assert cols["description"].nullable is False

    def test_endpoint_id_nullable(self):
        """endpoint_id can be null (e.g., for transform steps)."""
        cols = {c.name: c for c in ScenarioStep.__table__.columns}
        assert cols["endpoint_id"].nullable is True

    def test_timing_columns_nullable(self):
        """Timing columns are filled during execution."""
        cols = {c.name: c for c in ScenarioStep.__table__.columns}
        assert cols["started_at"].nullable is True
        assert cols["finished_at"].nullable is True
        assert cols["duration_ms"].nullable is True

    def test_error_message_nullable(self):
        cols = {c.name: c for c in ScenarioStep.__table__.columns}
        assert cols["error_message"].nullable is True


class TestScenarioStepStatuses:
    """Valid status values for ScenarioStep."""

    VALID_STATUSES = ["pending", "running", "completed", "error", "skipped"]

    def test_all_valid_statuses_can_be_created(self):
        """Verify each valid status can be assigned."""
        for i, status in enumerate(self.VALID_STATUSES):
            step = ScenarioStep(
                id=i,
                scenario_id=1,
                step_number=i,
                action="test",
                description="Test step",
                status=status,
            )
            assert step.status == status
