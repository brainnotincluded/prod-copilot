import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.orchestrator.executor import (
    execute_plan,
    _get_latest_data,
    _determine_output_type,
    _truncate_for_llm,
    _get_mock_result_data,
)
from app.schemas.models import OrchestrationStep, ResultResponse


class TestGetLatestData:
    def test_empty_context(self):
        assert _get_latest_data({}) is None

    def test_no_step_results(self):
        assert _get_latest_data({"step_results": {}}) is None

    def test_single_step_with_data_key(self):
        ctx = {"step_results": {"1": {"data": [1, 2, 3]}}}
        assert _get_latest_data(ctx) == [1, 2, 3]

    def test_single_step_with_body_key(self):
        ctx = {"step_results": {"1": {"body": {"items": [1, 2]}}}}
        assert _get_latest_data(ctx) == {"items": [1, 2]}

    def test_single_step_dict_without_data_or_body(self):
        ctx = {"step_results": {"1": {"custom_key": "value"}}}
        result = _get_latest_data(ctx)
        assert result == {"custom_key": "value"}

    def test_multiple_steps_returns_latest(self):
        ctx = {"step_results": {"1": {"data": "old"}, "2": {"data": "new"}}}
        assert _get_latest_data(ctx) == "new"

    def test_non_dict_result(self):
        ctx = {"step_results": {"1": [1, 2, 3]}}
        assert _get_latest_data(ctx) == [1, 2, 3]


class TestDetermineOutputType:
    def test_empty_context(self):
        assert _determine_output_type({}) == "text"

    def test_empty_step_results(self):
        assert _determine_output_type({"step_results": {}}) == "text"

    def test_table_detection_columns_rows(self):
        ctx = {"step_results": {"1": {"columns": ["a"], "rows": []}}}
        assert _determine_output_type(ctx) == "table"

    def test_chart_detection_labels_datasets(self):
        ctx = {"step_results": {"1": {"labels": ["a"], "datasets": []}}}
        assert _determine_output_type(ctx) == "chart"

    def test_map_detection_markers(self):
        ctx = {"step_results": {"1": {"markers": [{"lat": 0, "lng": 0}], "center": [0, 0]}}}
        assert _determine_output_type(ctx) == "map"

    def test_list_detection_items(self):
        ctx = {"step_results": {"1": {"items": ["a", "b"]}}}
        assert _determine_output_type(ctx) == "list"

    def test_text_detection_content(self):
        ctx = {"step_results": {"1": {"content": "some text"}}}
        assert _determine_output_type(ctx) == "text"

    def test_output_type_key_passthrough(self):
        ctx = {"step_results": {"1": {"output_type": "dashboard"}}}
        assert _determine_output_type(ctx) == "dashboard"

    def test_list_of_dicts_returns_table(self):
        ctx = {"step_results": {"1": {"data": [{"a": 1}, {"a": 2}]}}}
        assert _determine_output_type(ctx) == "table"

    def test_list_of_scalars_returns_list(self):
        ctx = {"step_results": {"1": {"data": ["a", "b", "c"]}}}
        assert _determine_output_type(ctx) == "list"


class TestTruncateForLlm:
    def test_empty_context(self):
        result = _truncate_for_llm({})
        assert result == {"step_results": {}}

    def test_small_data_unchanged(self):
        ctx = {"step_results": {"1": {"data": "small"}}}
        result = _truncate_for_llm(ctx)
        assert result["step_results"]["1"]["data"] == "small"

    def test_large_body_truncated(self):
        large = "x" * 100000
        ctx = {"step_results": {"1": {"body": large}}}
        result = _truncate_for_llm(ctx, max_chars=10000)
        body_str = str(result["step_results"]["1"]["body"])
        assert len(body_str) < 100000
        assert "[truncated]" in body_str

    def test_large_list_truncated(self):
        """A list with >20 items that serializes to more than per_step_limit gets truncated to 20."""
        # per_step_limit = max(max_chars // num_steps, 5000)
        # With max_chars=100, per_step_limit = max(100, 5000) = 5000
        # We need the serialized form to exceed 5000 chars
        big_list = [{"key": "x" * 200, "idx": i} for i in range(50)]
        ctx = {"step_results": {"1": big_list}}
        result = _truncate_for_llm(ctx, max_chars=100)
        assert len(result["step_results"]["1"]) <= 20


class TestExecutePlan:
    @pytest.mark.asyncio
    async def test_mock_mode_execution(self, mock_settings):
        """In mock mode, steps complete with hardcoded data."""
        # Need to also patch get_kimi_client since _execute_single_step calls it
        from app.llm.mock_client import MockKimiClient
        mock_client = MockKimiClient()

        with patch("app.orchestrator.executor.get_kimi_client", return_value=mock_client), \
             patch("app.orchestrator.executor.get_settings", return_value=mock_settings):
            steps = [
                OrchestrationStep(step=1, action="api_call", description="Test", status="pending"),
                OrchestrationStep(step=2, action="format_output", description="Format",
                                  parameters={"output_type": "table"}, status="pending"),
            ]
            result = await execute_plan(steps)

        assert isinstance(result, ResultResponse)
        assert result.metadata["status"] == "completed"

    @pytest.mark.asyncio
    async def test_empty_plan(self, mock_settings):
        with patch("app.orchestrator.executor.get_settings", return_value=mock_settings):
            result = await execute_plan([])
        assert isinstance(result, ResultResponse)
        assert result.metadata["steps_total"] == 0


class TestMockResultData:
    def test_table_type(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "table"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "columns" in data
        assert "rows" in data

    def test_chart_type(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "chart"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "chart_type" in data

    def test_map_type(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "map"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "markers" in data

    def test_list_type(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "list"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "items" in data

    def test_text_type(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "text"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "content" in data

    def test_no_parameters_defaults_to_text(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 status="pending")
        data = _get_mock_result_data(step, {})
        assert "content" in data

    def test_unknown_output_type_defaults_to_text(self):
        step = OrchestrationStep(step=1, action="format_output", description="",
                                 parameters={"output_type": "unknown"}, status="pending")
        data = _get_mock_result_data(step, {})
        assert "content" in data
