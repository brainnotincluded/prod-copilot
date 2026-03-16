import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.orchestrator.planner import create_plan, _classify_intent
from app.schemas.models import OrchestrationStep


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_returns_chat_for_greeting(self, mock_settings):
        """LLM classifier should return chat intent for a greeting."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value='{"intent": "chat", "response": "Hello!"}'
        )

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            result = await _classify_intent("bonjour")

        assert result["intent"] == "chat"
        assert "Hello" in result["response"]

    @pytest.mark.asyncio
    async def test_returns_api_query_for_data_request(self, mock_settings):
        """LLM classifier should return api_query for data requests."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value='{"intent": "api_query"}'
        )

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            result = await _classify_intent("show all users")

        assert result["intent"] == "api_query"

    @pytest.mark.asyncio
    async def test_defaults_to_api_query_on_failure(self, mock_settings):
        """If classification fails, default to api_query to avoid blocking real requests."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(side_effect=Exception("LLM down"))

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            result = await _classify_intent("some query")

        assert result["intent"] == "api_query"

    @pytest.mark.asyncio
    async def test_defaults_on_invalid_json(self, mock_settings):
        """If LLM returns invalid JSON, default to api_query."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value="not json at all")

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            result = await _classify_intent("some query")

        assert result["intent"] == "api_query"


class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="Query must not be empty"):
            await create_plan(query="", endpoints=[{"method": "GET", "path": "/test"}])

    @pytest.mark.asyncio
    async def test_whitespace_query_raises(self):
        with pytest.raises(ValueError, match="Query must not be empty"):
            await create_plan(query="   ", endpoints=[{"method": "GET", "path": "/test"}])

    @pytest.mark.asyncio
    async def test_instant_greeting_bypasses_llm(self, mock_settings):
        """Trivial greetings ('hi', 'hello', 'hey') return instantly without LLM call."""
        steps = await create_plan(query="hi", endpoints=[{"method": "GET", "path": "/test"}])

        assert len(steps) == 1
        assert steps[0].action == "chat_response"
        assert "API Copilot" in steps[0].description

    @pytest.mark.asyncio
    async def test_chat_intent_returns_chat_response(self, mock_settings, sample_endpoints):
        """When LLM classifies as chat, return a chat_response step without enrichment."""
        mock_client = MagicMock()
        # Only one LLM call: the classifier. No enrichment call.
        mock_client.chat = AsyncMock(
            return_value='{"intent": "chat", "response": "I am doing great!"}'
        )

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            steps = await create_plan(query="how are you?", endpoints=sample_endpoints)

        assert len(steps) == 1
        assert steps[0].action == "chat_response"
        assert steps[0].result["content"] == "I am doing great!"
        # Verify only one LLM call was made (classifier only, no enrichment)
        assert mock_client.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_api_query_intent_creates_plan(self, mock_settings, sample_endpoints):
        """When LLM classifies as api_query, proceed with plan creation."""
        mock_client = MagicMock()
        # First call: classifier returns api_query
        # Second call (plan_query): returns plan steps
        mock_client.chat = AsyncMock(
            return_value='{"intent": "api_query"}'
        )
        mock_client.plan_query = AsyncMock(return_value=[
            OrchestrationStep(step=1, action="api_call", description="Call API", status="pending"),
            OrchestrationStep(step=2, action="format_output", description="Format", status="pending"),
        ])

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            steps = await create_plan(query="list all users", endpoints=sample_endpoints)

        assert len(steps) == 2
        assert steps[0].step == 1
        assert steps[-1].action == "format_output"

    @pytest.mark.asyncio
    async def test_adds_format_output_if_missing(self, mock_settings, sample_endpoints):
        """If LLM doesn't include format_output step, planner adds it."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value='{"intent": "api_query"}')
        mock_client.plan_query = AsyncMock(return_value=[
            OrchestrationStep(step=1, action="api_call", description="Call API", status="pending"),
        ])

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            steps = await create_plan(query="get users", endpoints=sample_endpoints)

        assert len(steps) == 2
        assert steps[-1].action == "format_output"
        assert steps[-1].step == 2

    @pytest.mark.asyncio
    async def test_fixes_step_numbers(self, mock_settings, sample_endpoints):
        """Step numbers should be sequential starting from 1."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value='{"intent": "api_query"}')
        mock_client.plan_query = AsyncMock(return_value=[
            OrchestrationStep(step=5, action="api_call", description="Call API", status="pending"),
            OrchestrationStep(step=10, action="format_output", description="Format", status="pending"),
        ])

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            steps = await create_plan(query="get users", endpoints=sample_endpoints)

        for i, step in enumerate(steps):
            assert step.step == i + 1

    @pytest.mark.asyncio
    async def test_plan_query_receives_stripped_query(self, mock_settings, sample_endpoints):
        """Query should be stripped before passing to client."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value='{"intent": "api_query"}')
        mock_client.plan_query = AsyncMock(return_value=[
            OrchestrationStep(step=1, action="format_output", description="Format", status="pending"),
        ])

        with patch("app.orchestrator.planner.get_kimi_client", return_value=mock_client):
            await create_plan(query="  list users  ", endpoints=sample_endpoints)

        mock_client.plan_query.assert_called_once_with("list users", sample_endpoints, history=None)
