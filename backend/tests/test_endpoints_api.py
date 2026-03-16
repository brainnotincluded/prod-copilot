"""Tests for /api/endpoints/* endpoints.

Covers:
  - List with filters (method, path_contains, search, has_parameters, has_request_body)
  - Global stats
  - List unique methods
  - List paths
  - Get single endpoint by ID
  - Semantic search (mocked RAG)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import ApiEndpoint
from tests.conftest import make_result


# -----------------------------------------------------------------------
# List endpoints
# -----------------------------------------------------------------------

class TestListEndpoints:

    @pytest.mark.asyncio
    async def test_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_returns_endpoints(self, client, fake_db):
        now = datetime.now(timezone.utc)
        ep = ApiEndpoint(
            id=1, swagger_source_id=1, method="GET", path="/users",
            summary="List users", description=None, parameters=None,
            request_body=None, response_schema=None, created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.get("/api/endpoints/list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["method"] == "GET"
        assert data[0]["path"] == "/users"

    @pytest.mark.asyncio
    async def test_filter_by_method(self, client, fake_db):
        """Endpoint accepts ?method=POST and passes it to the query."""
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"method": "POST"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_by_path_contains(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"path_contains": "user"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_by_search(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"search": "create"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_by_swagger_source_id(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"swagger_source_id": 1})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_has_parameters(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"has_parameters": True})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_has_request_body(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/endpoints/list", params={"has_request_body": True})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Global stats
# -----------------------------------------------------------------------

class TestEndpointStats:

    @pytest.mark.asyncio
    async def test_returns_stats_structure(self, client, fake_db):
        fake_db._scalar_result = 10
        # by_method
        fake_db.set_execute_result(make_result(rows=[("GET", 7), ("POST", 3)]))
        # by_source
        fake_db.set_execute_result(make_result(rows=[("PetAPI", 10)]))

        resp = await client.get("/api/endpoints/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert "by_method" in body
        assert "by_source" in body

    @pytest.mark.asyncio
    async def test_empty_stats(self, client, fake_db):
        fake_db._scalar_result = 0
        fake_db.set_execute_result(make_result(rows=[]))
        fake_db.set_execute_result(make_result(rows=[]))

        resp = await client.get("/api/endpoints/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["by_method"] == {}
        assert body["by_source"] == {}


# -----------------------------------------------------------------------
# List methods
# -----------------------------------------------------------------------

class TestListMethods:

    @pytest.mark.asyncio
    async def test_returns_methods(self, client, fake_db):
        fake_db.set_execute_result(make_result(rows=[("GET",), ("POST",), ("DELETE",)]))
        resp = await client.get("/api/endpoints/methods")
        assert resp.status_code == 200
        methods = resp.json()
        assert set(methods) == {"GET", "POST", "DELETE"}

    @pytest.mark.asyncio
    async def test_empty_methods(self, client, fake_db):
        fake_db.set_execute_result(make_result(rows=[]))
        resp = await client.get("/api/endpoints/methods")
        assert resp.status_code == 200
        assert resp.json() == []


# -----------------------------------------------------------------------
# List paths
# -----------------------------------------------------------------------

class TestListPaths:

    @pytest.mark.asyncio
    async def test_returns_paths(self, client, fake_db):
        fake_db.set_execute_result(
            make_result(rows=[("GET", "/pets", "List pets"), ("POST", "/pets", "Add pet")])
        )
        resp = await client.get("/api/endpoints/paths")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["method"] == "GET"
        assert data[0]["path"] == "/pets"
        assert data[0]["summary"] == "List pets"

    @pytest.mark.asyncio
    async def test_filter_by_source(self, client, fake_db):
        fake_db.set_execute_result(make_result(rows=[]))
        resp = await client.get("/api/endpoints/paths", params={"swagger_source_id": 1})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Get single endpoint
# -----------------------------------------------------------------------

class TestGetEndpoint:

    @pytest.mark.asyncio
    async def test_found(self, client, fake_db):
        now = datetime.now(timezone.utc)
        ep = ApiEndpoint(
            id=42, swagger_source_id=1, method="PUT", path="/items/{id}",
            summary="Update item", description="Updates an item",
            parameters=[{"name": "id", "in": "path", "required": True, "description": "", "schema": "integer"}],
            request_body={"type": "object"}, response_schema={"type": "object"},
            created_at=now,
        )
        fake_db.register_get(ApiEndpoint, 42, ep)

        resp = await client.get("/api/endpoints/42")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 42
        assert body["method"] == "PUT"
        assert body["path"] == "/items/{id}"
        assert body["summary"] == "Update item"
        assert len(body["parameters"]) == 1

    @pytest.mark.asyncio
    async def test_not_found_404(self, client, fake_db):
        resp = await client.get("/api/endpoints/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------
# Semantic search
# -----------------------------------------------------------------------

class TestSearchEndpoints:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client, fake_db):
        now = datetime.now(timezone.utc)
        ep = ApiEndpoint(
            id=1, swagger_source_id=1, method="GET", path="/pets",
            summary="List pets", description=None, parameters=None,
            request_body=None, response_schema=None, created_at=now,
        )

        with patch("app.api.endpoints.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.search = AsyncMock(return_value=[ep])

            resp = await client.get("/api/endpoints/search", params={"q": "list animals"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["path"] == "/pets"

    @pytest.mark.asyncio
    async def test_search_missing_query_422(self, client):
        resp = await client.get("/api/endpoints/search")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_empty_query_422(self, client):
        resp = await client.get("/api/endpoints/search", params={"q": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_limit_param(self, client, fake_db):
        with patch("app.api.endpoints.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.search = AsyncMock(return_value=[])

            resp = await client.get("/api/endpoints/search", params={"q": "x", "limit": 5})

        assert resp.status_code == 200
        # Verify the limit was passed through
        instance.search.assert_called_once()
        _, kwargs = instance.search.call_args
        assert kwargs.get("limit") == 5 or instance.search.call_args[1].get("limit") == 5

    @pytest.mark.asyncio
    async def test_search_limit_too_high_422(self, client):
        resp = await client.get("/api/endpoints/search", params={"q": "x", "limit": 999})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_limit_zero_422(self, client):
        resp = await client.get("/api/endpoints/search", params={"q": "x", "limit": 0})
        assert resp.status_code == 422
