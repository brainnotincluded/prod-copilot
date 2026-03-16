"""Tests for /api/swagger/* endpoints.

Covers:
  - Upload (file, URL, validation errors)
  - List sources
  - Get source endpoints
  - Source stats
  - Delete source
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import ApiEndpoint, SwaggerSource
from tests.conftest import PETSTORE_OPENAPI3, make_result


# -----------------------------------------------------------------------
# Upload
# -----------------------------------------------------------------------

class TestUploadSwagger:

    @pytest.mark.asyncio
    async def test_upload_json_file_success(self, client, fake_db):
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=4)

            resp = await client.post(
                "/api/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Petstore"
        assert body["endpoints_count"] == 4
        assert "base_url" in body
        assert body["base_url"] == "https://petstore.example.com/v1"
        assert "Successfully parsed" in body["message"]

    @pytest.mark.asyncio
    async def test_upload_yaml_file_success(self, client, fake_db):
        yaml_content = b"""
openapi: "3.0.0"
info:
  title: YAML API
  version: "1.0"
servers:
  - url: https://yaml.example.com
paths:
  /items:
    get:
      summary: List items
      responses:
        "200":
          description: OK
"""
        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=1)

            resp = await client.post(
                "/api/swagger/upload",
                files={"file": ("spec.yaml", io.BytesIO(yaml_content), "application/x-yaml")},
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "YAML API"

    @pytest.mark.asyncio
    async def test_upload_custom_name_overrides_spec_title(self, client, fake_db):
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=4)

            resp = await client.post(
                "/api/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
                data={"name": "My Custom Name"},
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "My Custom Name"

    @pytest.mark.asyncio
    async def test_upload_no_file_no_url_400(self, client):
        resp = await client.post("/api/swagger/upload")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_invalid_content_400(self, client):
        # Content that fails JSON parsing and YAML parses to a non-dict (a string)
        # The handler should return 400 because YAML result is not a dict.
        # Use truly broken YAML: tabs in wrong places cause YAMLError
        broken = b"\t\t:\n\t-\t:\n\x00"
        resp = await client.post(
            "/api/swagger/upload",
            files={"file": ("bad.json", io.BytesIO(broken), "application/json")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_empty_spec_no_endpoints_400(self, client, fake_db):
        spec = {"openapi": "3.0.0", "info": {"title": "Empty", "version": "1"}, "paths": {}}
        resp = await client.post(
            "/api/swagger/upload",
            files={"file": ("empty.json", io.BytesIO(json.dumps(spec).encode()), "application/json")},
        )
        assert resp.status_code == 400
        assert "No endpoints" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_from_url_network_error_400(self, client):
        import httpx

        with patch("app.api.swagger.httpx.AsyncClient") as MockClient:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = await client.post(
                "/api/swagger/upload",
                data={"url": "http://nonexistent.local/spec.json"},
            )

        assert resp.status_code == 400
        assert "Failed to fetch" in resp.json()["detail"]


# -----------------------------------------------------------------------
# List sources
# -----------------------------------------------------------------------

class TestListSwaggerSources:

    @pytest.mark.asyncio
    async def test_empty_list(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/swagger/list")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_returns_sources(self, client, fake_db):
        now = datetime.now(timezone.utc)
        src = SwaggerSource(
            id=1, name="PetAPI", url="http://x", raw_json="{}", base_url="http://x", created_at=now
        )
        fake_db.set_execute_result(make_result(scalars=[src]))

        resp = await client.get("/api/swagger/list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "PetAPI"
        assert data[0]["id"] == 1


# -----------------------------------------------------------------------
# Get source endpoints
# -----------------------------------------------------------------------

class TestGetSourceEndpoints:

    @pytest.mark.asyncio
    async def test_source_not_found_404(self, client, fake_db):
        # db.get returns None → 404
        resp = await client.get("/api/swagger/999/endpoints")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_endpoints(self, client, fake_db):
        now = datetime.now(timezone.utc)
        src = SwaggerSource(id=1, name="X", raw_json="{}", created_at=now)
        fake_db.register_get(SwaggerSource, 1, src)

        ep = ApiEndpoint(
            id=10, swagger_source_id=1, method="GET", path="/foo",
            summary="Get foo", description=None, parameters=None,
            request_body=None, response_schema=None, created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.get("/api/swagger/1/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["method"] == "GET"
        assert data[0]["path"] == "/foo"


# -----------------------------------------------------------------------
# Source stats
# -----------------------------------------------------------------------

class TestSourceStats:

    @pytest.mark.asyncio
    async def test_not_found_404(self, client, fake_db):
        resp = await client.get("/api/swagger/999/stats")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_stats(self, client, fake_db):
        now = datetime.now(timezone.utc)
        src = SwaggerSource(id=1, name="X", raw_json="{}", base_url="http://x", created_at=now)
        fake_db.register_get(SwaggerSource, 1, src)

        # method_counts: [("GET", 3), ("POST", 1)]
        fake_db.set_execute_result(make_result(rows=[("GET", 3), ("POST", 1)]))

        resp = await client.get("/api/swagger/1/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_endpoints"] == 4
        assert body["by_method"]["GET"] == 3
        assert body["by_method"]["POST"] == 1


# -----------------------------------------------------------------------
# Delete source
# -----------------------------------------------------------------------

class TestDeleteSource:

    @pytest.mark.asyncio
    async def test_not_found_404(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.delete("/api/swagger/999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_success(self, client, fake_db):
        now = datetime.now(timezone.utc)
        src = SwaggerSource(id=1, name="OldAPI", raw_json="{}", created_at=now)
        fake_db.set_execute_result(make_result(scalars=[src]))

        resp = await client.delete("/api/swagger/1")
        assert resp.status_code == 200
        assert "OldAPI" in resp.json()["message"]
        assert src in fake_db.deleted
