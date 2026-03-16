"""Tests for LLM client JSON parsing, including _merge_json_fragments."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.kimi_client import _merge_json_fragments, LLMClient


class TestMergeJsonFragments:
    """Tests for the _merge_json_fragments helper that handles granite4 split-array output."""

    def test_two_separate_arrays(self):
        """granite4 outputs two separate arrays instead of one combined array."""
        text = (
            '[\n  {\n    "step": 1,\n    "action": "api_call"\n  }\n]\n'
            '[\n  {\n    "step": 2,\n    "action": "format_output"\n  }\n]'
        )
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["step"] == 1
        assert result[1]["step"] == 2

    def test_two_separate_objects(self):
        """Two separate JSON objects (no array wrapper)."""
        text = '{"step": 1, "action": "api_call"}\n{"step": 2, "action": "format_output"}'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["action"] == "api_call"
        assert result[1]["action"] == "format_output"

    def test_single_valid_array(self):
        """A single valid array should be flattened into a list."""
        text = '[{"step": 1}, {"step": 2}]'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2

    def test_single_valid_object(self):
        """A single valid object should be wrapped in a list."""
        text = '{"step": 1, "action": "api_call"}'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["step"] == 1

    def test_empty_text(self):
        """Empty text returns None."""
        assert _merge_json_fragments("") is None

    def test_no_json(self):
        """Text with no JSON returns None."""
        assert _merge_json_fragments("just plain text") is None

    def test_with_whitespace_between_fragments(self):
        """Fragments separated by arbitrary whitespace."""
        text = '  {"a": 1}  \n\n\n  {"b": 2}  '
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2

    def test_nested_braces_in_strings(self):
        """Braces inside JSON strings should not confuse the parser."""
        text = '{"desc": "use {curly} braces"}\n{"desc": "and [square] too"}'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["desc"] == "use {curly} braces"

    def test_escaped_quotes_in_strings(self):
        """Escaped quotes should be handled correctly."""
        text = r'{"desc": "say \"hello\""}'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["desc"] == 'say "hello"'

    def test_array_then_object(self):
        """Mix of array and object fragments."""
        text = '[{"step": 1}]\n{"step": 2}'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2

    def test_three_fragments(self):
        """Three separate arrays merged."""
        text = '[{"s":1}]\n[{"s":2}]\n[{"s":3}]'
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 3

    def test_realistic_granite4_output(self):
        """Realistic granite4 output that caused the original bug."""
        text = """[
  {
    "step": 1,
    "action": "api_call",
    "description": "List all users",
    "endpoint": {
      "method": "GET",
      "path": "/users"
    },
    "parameters": {}
  }
]
[
  {
    "step": 2,
    "action": "format_output",
    "description": "Display as table",
    "parameters": {
      "output_type": "table"
    }
  }
]"""
        result = _merge_json_fragments(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["action"] == "api_call"
        assert result[0]["endpoint"]["method"] == "GET"
        assert result[1]["action"] == "format_output"
        assert result[1]["parameters"]["output_type"] == "table"


class TestReasoningExtraction:
    """Tests for extracting answers from thinking model reasoning field."""

    @pytest.mark.asyncio
    async def test_extracts_json_from_reasoning(self, mock_settings):
        """When content is empty and reasoning has JSON, extract the JSON."""
        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = None
        mock_choice.message.model_dump.return_value = {
            "reasoning": 'The user wants users... I will return {"intent": "api_query"} as the answer.',
        }
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == '{"intent": "api_query"}'

    @pytest.mark.asyncio
    async def test_extracts_quoted_string_from_reasoning(self, mock_settings):
        """When reasoning has no JSON but has quoted strings, extract the last one."""
        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = None
        mock_choice.message.model_dump.return_value = {
            "reasoning": 'The user wants to translate... "show all tasks" is the translation.',
        }
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "show all tasks"

    @pytest.mark.asyncio
    async def test_extracts_last_line_from_reasoning(self, mock_settings):
        """When reasoning has no JSON and no quotes, extract the last short line."""
        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = None
        mock_choice.message.model_dump.return_value = {
            "reasoning": "Let me think about this...\nThe answer is 42.\nFinal answer: list all users",
        }
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "Final answer: list all users"

    @pytest.mark.asyncio
    async def test_content_takes_priority_over_reasoning(self, mock_settings):
        """When content is present, return it even if reasoning exists."""
        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "direct answer"
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        result = await client.chat([{"role": "user", "content": "test"}])
        assert result == "direct answer"


class TestPlanQueryParsing:
    """Tests for plan_query JSON parsing, including the multi-array fix."""

    @pytest.mark.asyncio
    async def test_parses_separate_arrays_from_llm(self, mock_settings):
        """plan_query should handle LLM returning two separate JSON arrays."""
        # Simulate granite4 returning two separate arrays
        llm_response = (
            '[\n  {"step": 1, "action": "api_call", "description": "List users", '
            '"endpoint": {"method": "GET", "path": "/users"}, "parameters": {}}\n]\n'
            '[\n  {"step": 2, "action": "format_output", "description": "Display as table", '
            '"parameters": {"output_type": "table"}}\n]'
        )

        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = llm_response
        mock_response.choices[0].message.tool_calls = None
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        steps = await client.plan_query("list users", [{"method": "GET", "path": "/users"}])

        assert len(steps) == 2
        assert steps[0].action == "api_call"
        assert steps[0].endpoint == {"method": "GET", "path": "/users"}
        assert steps[1].action == "format_output"

    @pytest.mark.asyncio
    async def test_parses_single_valid_array(self, mock_settings):
        """plan_query should handle a single valid array (normal case)."""
        llm_response = json.dumps([
            {"step": 1, "action": "api_call", "description": "Call", "endpoint": {"method": "GET", "path": "/x"}},
            {"step": 2, "action": "format_output", "description": "Format", "parameters": {"output_type": "table"}},
        ])

        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = llm_response
        mock_response.choices[0].message.tool_calls = None
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        steps = await client.plan_query("do something", [])

        assert len(steps) == 2
        assert steps[0].action == "api_call"
        assert steps[1].action == "format_output"

    @pytest.mark.asyncio
    async def test_parses_markdown_fenced_response(self, mock_settings):
        """plan_query should strip markdown code fences."""
        llm_response = '```json\n[{"step": 1, "action": "api_call", "description": "Call"}]\n```'

        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = llm_response
        mock_response.choices[0].message.tool_calls = None
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient.__new__(LLMClient)
        client._client = mock_openai_client
        client._model = "test-model"
        client._max_retries = 1
        client._retry_delay = 0.1

        steps = await client.plan_query("do something", [])

        assert len(steps) == 1
        assert steps[0].action == "api_call"
