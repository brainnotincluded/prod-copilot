"""Tests for POST /api/query — now a thin controller over OrchestrationService.

Patches the service at the route level to verify controller behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.models import ResultResponse


class TestQueryEndpoint:

    @pytest.mark.asyncio
    async def test_successful_text_response(self, client, fake_db):
        with patch("app.api.query.OrchestrationService") as MockSvc:
            instance = MockSvc.return_value
            instance.execute = AsyncMock(return_value=ResultResponse(
                type="text",
                data={"content": "Here are your results"},
                metadata={"status": "completed", "correlation_id": "abc"},
            ))

            resp = await client.post("/api/query", json={"query": "show users"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "text"
        assert body["data"]["content"] == "Here are your results"

    @pytest.mark.asyncio
    async def test_successful_table_response(self, client, fake_db):
        with patch("app.api.query.OrchestrationService") as MockSvc:
            instance = MockSvc.return_value
            instance.execute = AsyncMock(return_value=ResultResponse(
                type="table",
                data={"columns": ["id"], "rows": [[1]]},
            ))

            resp = await client.post("/api/query", json={"query": "list users"})

        assert resp.status_code == 200
        assert resp.json()["type"] == "table"

    @pytest.mark.asyncio
    async def test_successful_chart_response(self, client, fake_db):
        with patch("app.api.query.OrchestrationService") as MockSvc:
            instance = MockSvc.return_value
            instance.execute = AsyncMock(return_value=ResultResponse(
                type="chart",
                data={"chart_type": "bar"},
            ))

            resp = await client.post("/api/query", json={"query": "chart"})

        assert resp.status_code == 200
        assert resp.json()["type"] == "chart"

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, client):
        resp = await client.post("/api/query", json={"query": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_query_rejected(self, client):
        resp = await client.post("/api/query", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_passes_source_ids_to_service(self, client, fake_db):
        with patch("app.api.query.OrchestrationService") as MockSvc:
            instance = MockSvc.return_value
            instance.execute = AsyncMock(return_value=ResultResponse(
                type="text", data={"content": "ok"},
            ))

            await client.post(
                "/api/query",
                json={"query": "test", "swagger_source_ids": [1, 2]},
            )

        instance.execute.assert_called_once()
        call_kwargs = instance.execute.call_args.kwargs
        assert call_kwargs["swagger_source_ids"] == [1, 2]

    @pytest.mark.asyncio
    async def test_service_error_propagated(self, client, fake_db):
        """If the service returns an error-type response, it should still be 200."""
        with patch("app.api.query.OrchestrationService") as MockSvc:
            instance = MockSvc.return_value
            instance.execute = AsyncMock(return_value=ResultResponse(
                type="text",
                data={"content": "Orchestration error: boom"},
                metadata={"status": "error"},
            ))

            resp = await client.post("/api/query", json={"query": "test"})

        assert resp.status_code == 200
        assert "error" in resp.json()["metadata"]["status"]
