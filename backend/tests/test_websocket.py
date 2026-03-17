"""Tests for WebSocket /api/v1/ws/query — streaming orchestration.

The WS endpoint now:
- Requires JWT token via ``?token=`` query parameter
- Directly uses MLOpsClient (no OrchestrationService)
- Streams step/result/done events to the client
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.auth import create_access_token


def _make_valid_token() -> str:
    """Create a valid JWT token for WS auth."""
    return create_access_token(data={"sub": "1", "email": "test@test.com", "role": "admin"})


class TestWebSocketQuery:

    @pytest.mark.asyncio
    async def test_no_token_rejected(self, app):
        """Connecting without a token should close the WS."""
        from starlette.testclient import TestClient
        with TestClient(app) as tc:
            with pytest.raises(Exception):
                with tc.websocket_connect("/api/v1/ws/query") as ws:
                    ws.receive_json()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self, app):
        from starlette.testclient import TestClient
        token = _make_valid_token()
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/api/v1/ws/query?token={token}") as ws:
                ws.send_text("not json at all")
                data = ws.receive_json()
                assert "error" in data
                assert "Invalid JSON" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_query_field_returns_error(self, app):
        from starlette.testclient import TestClient
        token = _make_valid_token()
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/api/v1/ws/query?token={token}") as ws:
                ws.send_json({"not_query": "oops"})
                data = ws.receive_json()
                assert "error" in data
                assert "query" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_happy_path_forwarding(self, app):
        """MLOps stream events are forwarded to the WS client, then done is sent."""
        token = _make_valid_token()

        async def fake_stream(**kwargs):
            yield {"event_type": "step_start", "step": 1, "action": "search", "description": "Searching..."}
            yield {"event_type": "step_complete", "step": 1, "action": "search", "description": "Done"}
            yield {"event_type": "result", "type": "text", "data": {"content": "done"}, "metadata": {}}

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        # Mock the session to return empty sources
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.MLOpsClient") as MockMLOps,
        ):
            instance = MockMLOps.return_value
            instance.orchestrate_stream = MagicMock(return_value=fake_stream())

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect(f"/api/v1/ws/query?token={token}") as ws:
                    ws.send_json({"query": "test"})

                    msg1 = ws.receive_json()
                    assert msg1["type"] == "step"

                    msg2 = ws.receive_json()
                    assert msg2["type"] == "step"

                    msg3 = ws.receive_json()
                    assert msg3["type"] == "result"

                    msg4 = ws.receive_json()
                    assert msg4["type"] == "done"

    @pytest.mark.asyncio
    async def test_history_forwarded_to_mlops(self, app):
        token = _make_valid_token()
        captured = {}

        async def capturing_stream(**kwargs):
            captured.update(kwargs)
            yield {"event_type": "result", "type": "text", "data": {"content": "ok"}}

        mock_session_ctx = AsyncMock()
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.MLOpsClient") as MockMLOps,
        ):
            instance = MockMLOps.return_value
            instance.orchestrate_stream = MagicMock(side_effect=lambda **kw: capturing_stream(**kw))

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect(f"/api/v1/ws/query?token={token}") as ws:
                    ws.send_json({
                        "query": "q",
                        "history": [{"role": "user", "content": "hi"}],
                    })
                    ws.receive_json()  # result
                    ws.receive_json()  # done

        assert captured["history"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_swagger_source_ids_forwarded(self, app):
        token = _make_valid_token()
        captured = {}

        async def capturing_stream(**kwargs):
            captured.update(kwargs)
            yield {"event_type": "result", "type": "text", "data": {"content": "ok"}}

        mock_session_ctx = AsyncMock()
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.query.async_session_factory", return_value=mock_session_ctx),
            patch("app.api.query.MLOpsClient") as MockMLOps,
        ):
            instance = MockMLOps.return_value
            instance.orchestrate_stream = MagicMock(side_effect=lambda **kw: capturing_stream(**kw))

            from starlette.testclient import TestClient
            with TestClient(app) as tc:
                with tc.websocket_connect(f"/api/v1/ws/query?token={token}") as ws:
                    ws.send_json({"query": "q", "swagger_source_ids": [1, 3]})
                    ws.receive_json()  # result
                    ws.receive_json()  # done

        # swagger_source_ids are resolved against DB, but since DB returns
        # no sources, the forwarded value should be None (no matching sources)
        assert captured.get("swagger_source_ids") is None
