"""Tests for WebSocket /api/ws/query — thin controller over OrchestrationService.

Covers protocol-level concerns: JSON validation, missing fields,
event forwarding from service to client, done signal.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FakeAsyncSession


class TestWebSocketQuery:

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self, app):
        from starlette.testclient import TestClient
        with TestClient(app) as tc:
            with tc.websocket_connect("/api/ws/query") as ws:
                ws.send_text("not json at all")
                data = ws.receive_json()
                assert "error" in data
                assert "Invalid JSON" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_query_field_returns_error(self, app):
        from starlette.testclient import TestClient
        with TestClient(app) as tc:
            with tc.websocket_connect("/api/ws/query") as ws:
                ws.send_json({"not_query": "oops"})
                data = ws.receive_json()
                assert "error" in data
                assert "query" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_happy_path_forwarding(self, app):
        """Service events are forwarded to the WS client, then done is sent."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=FakeAsyncSession())
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        async def fake_stream(**kwargs):
            yield {"type": "step", "data": {"step": 1, "action": "search", "status": "completed", "description": "ok"}}
            yield {"type": "result", "data": {"type": "text", "data": {"content": "done"}}}

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.OrchestrationService") as MockSvc,
        ):
            instance = MockSvc.return_value
            instance.execute_stream = MagicMock(return_value=fake_stream())

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect("/api/ws/query") as ws:
                    ws.send_json({"query": "test"})

                    msg1 = ws.receive_json()
                    assert msg1["type"] == "step"

                    msg2 = ws.receive_json()
                    assert msg2["type"] == "result"

                    msg3 = ws.receive_json()
                    assert msg3["type"] == "done"

    @pytest.mark.asyncio
    async def test_history_forwarded_to_service(self, app):
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=FakeAsyncSession())
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        captured = {}

        async def capturing_stream(**kwargs):
            captured.update(kwargs)
            yield {"type": "result", "data": {"type": "text", "data": {"content": "ok"}}}

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.OrchestrationService") as MockSvc,
        ):
            instance = MockSvc.return_value
            instance.execute_stream = MagicMock(side_effect=lambda **kw: capturing_stream(**kw))

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect("/api/ws/query") as ws:
                    ws.send_json({
                        "query": "q",
                        "history": [{"role": "user", "content": "hi"}],
                    })
                    ws.receive_json()  # result
                    ws.receive_json()  # done

        assert captured["history"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_swagger_source_ids_forwarded(self, app):
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=FakeAsyncSession())
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        captured = {}

        async def capturing_stream(**kwargs):
            captured.update(kwargs)
            yield {"type": "result", "data": {}}

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.OrchestrationService") as MockSvc,
        ):
            instance = MockSvc.return_value
            instance.execute_stream = MagicMock(side_effect=lambda **kw: capturing_stream(**kw))

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect("/api/ws/query") as ws:
                    ws.send_json({"query": "q", "swagger_source_ids": [1, 3]})
                    ws.receive_json()
                    ws.receive_json()

        assert captured["swagger_source_ids"] == [1, 3]
