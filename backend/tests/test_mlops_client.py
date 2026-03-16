"""Tests for MLOpsClient — all HTTP calls are mocked via respx.

Covers:
  - translate: success, fallback on error
  - get_embedding: success, unexpected format
  - orchestrate: success, payload structure
  - orchestrate_stream: SSE parsing, event types
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.mlops_client import MLOpsClient


@pytest.fixture()
def mlops():
    with patch("app.services.mlops_client.settings") as mock_settings:
        mock_settings.mlops_base_url = "http://test-mlops:8001"
        return MLOpsClient()


# -----------------------------------------------------------------------
# translate
# -----------------------------------------------------------------------

class TestTranslate:

    @pytest.mark.asyncio
    async def test_returns_translated(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"translated": "list all users"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.translate("показать всех пользователей")

        assert result == "list all users"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, mlops):
        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.translate("original text")

        assert result == "original text"

    @pytest.mark.asyncio
    async def test_fallback_when_no_translated_key(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.translate("my query")

        assert result == "my query"


# -----------------------------------------------------------------------
# get_embedding
# -----------------------------------------------------------------------

class TestGetEmbedding:

    @pytest.mark.asyncio
    async def test_returns_vector(self, mlops):
        embedding = [0.1] * 384
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [embedding]}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.get_embedding("test text")

        assert result == embedding
        assert len(result) == 384

    @pytest.mark.asyncio
    async def test_returns_none_on_unexpected_format(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": None}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.get_embedding("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_list(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.get_embedding("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, mlops):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
        )

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await mlops.get_embedding("test")


# -----------------------------------------------------------------------
# orchestrate
# -----------------------------------------------------------------------

class TestOrchestrate:

    @pytest.mark.asyncio
    async def test_success(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"type": "text", "data": {"content": "result"}}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await mlops.orchestrate(
                query="show users",
                endpoints=[{"id": 1, "method": "GET", "path": "/users"}],
                base_url="https://api.example.com",
            )

        assert result["type"] == "text"
        # Verify the payload structure
        call_args = ctx.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["query"] == "show users"
        assert payload["endpoints"] == [{"id": 1, "method": "GET", "path": "/users"}]
        assert payload["context"]["base_url"] == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_no_base_url_omits_context(self, mlops):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"type": "text", "data": {}}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await mlops.orchestrate(query="q", endpoints=[], base_url=None)

        call_args = ctx.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "context" not in payload


# -----------------------------------------------------------------------
# orchestrate_stream (SSE parsing)
# -----------------------------------------------------------------------

class TestOrchestrateStream:

    @pytest.mark.asyncio
    async def test_parses_sse_events(self, mlops):
        """Verify SSE lines are correctly parsed into typed dicts."""
        sse_text = (
            "event: step_start\n"
            'data: {"step": 1, "action": "api_call", "description": "Calling GET /users"}\n'
            "\n"
            "event: step_complete\n"
            'data: {"step": 1, "result": {"status": 200}}\n'
            "\n"
            "event: result\n"
            'data: {"type": "text", "data": {"content": "done"}, "metadata": {}}\n'
            "\n"
        )

        # Simulate httpx streaming response
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def fake_aiter_text():
            yield sse_text

        mock_response.aiter_text = fake_aiter_text

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.stream = MagicMock(return_value=mock_stream_ctx)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            events = []
            async for event in mlops.orchestrate_stream(query="q", endpoints=[]):
                events.append(event)

        assert len(events) == 3
        assert events[0]["event_type"] == "step_start"
        assert events[0]["action"] == "api_call"
        assert events[1]["event_type"] == "step_complete"
        assert events[1]["result"]["status"] == 200
        assert events[2]["event_type"] == "result"
        assert events[2]["data"]["content"] == "done"

    @pytest.mark.asyncio
    async def test_history_included_in_payload(self, mlops):
        """When history is provided, it must be in the context."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def fake_aiter_text():
            yield 'event: result\ndata: {"type":"text","data":{}}\n\n'

        mock_response.aiter_text = fake_aiter_text

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.stream = MagicMock(return_value=mock_stream_ctx)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            async for _ in mlops.orchestrate_stream(
                query="q", endpoints=[], history=[{"role": "user", "content": "hi"}]
            ):
                pass

        call_args = ctx.stream.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "context" in payload
        assert payload["context"]["history"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_malformed_sse_data_skipped(self, mlops):
        """Malformed JSON in SSE data lines should be silently skipped."""
        sse_text = (
            "event: step_start\n"
            "data: NOT-JSON-AT-ALL\n"
            "\n"
            "event: result\n"
            'data: {"type": "text", "data": {"content": "ok"}}\n'
            "\n"
        )

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def fake_aiter_text():
            yield sse_text

        mock_response.aiter_text = fake_aiter_text

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.mlops_client.httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.stream = MagicMock(return_value=mock_stream_ctx)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            events = []
            async for event in mlops.orchestrate_stream(query="q", endpoints=[]):
                events.append(event)

        # Only the valid event should come through
        assert len(events) == 1
        assert events[0]["event_type"] == "result"
