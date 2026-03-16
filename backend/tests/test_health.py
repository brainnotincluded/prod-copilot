"""Tests for GET /health — dependency-aware health check.

Covers: all-ok, DB down, MLOps down, both down.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHealthCheck:

    @pytest.mark.asyncio
    async def test_all_ok(self, client):
        mock_session_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_http_ctx = AsyncMock()
        mock_http_ctx.get = AsyncMock(return_value=mock_resp)

        mock_http_client = MagicMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=mock_session_ctx),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert body["mlops"] == "ok"
        assert body["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_db_down(self, client):
        mock_session_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http_ctx = AsyncMock()
        mock_http_ctx.get = AsyncMock(return_value=mock_resp)
        mock_http_client = MagicMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=mock_session_ctx),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["db"] == "error"
        assert body["mlops"] == "ok"

    @pytest.mark.asyncio
    async def test_mlops_down(self, client):
        mock_session_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_http_client = MagicMock()
        mock_http_ctx = AsyncMock()
        mock_http_ctx.get = AsyncMock(side_effect=Exception("MLOps down"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=mock_session_ctx),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["db"] == "ok"
        assert body["mlops"] == "error"

    @pytest.mark.asyncio
    async def test_both_down_503(self, client):
        mock_session_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_http_client = MagicMock()
        mock_http_ctx = AsyncMock()
        mock_http_ctx.get = AsyncMock(side_effect=Exception("MLOps down"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=mock_session_ctx),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert body["db"] == "error"
        assert body["mlops"] == "error"

    @pytest.mark.asyncio
    async def test_content_type_json(self, client):
        mock_session_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http_ctx = AsyncMock()
        mock_http_ctx.get = AsyncMock(return_value=mock_resp)
        mock_http_client = MagicMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_ctx)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.db.session.async_session_factory", return_value=mock_session_ctx),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            resp = await client.get("/health")

        assert "application/json" in resp.headers["content-type"]
