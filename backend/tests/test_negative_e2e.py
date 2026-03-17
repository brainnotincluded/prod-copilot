"""Negative, end-to-end, and edge-case tests.

Categories
----------
1. Negative tests — bad inputs that should return proper error codes.
2. E2E workflow tests — multi-step flows across several endpoints.
3. Edge cases — unicode, long strings, SQL injection chars, empty DB, etc.

All tests run without a real database or MLOps service.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import ActionConfirmation, ApiEndpoint, SwaggerSource
from app.schemas.models import ResultResponse
from tests.conftest import (
    PETSTORE_OPENAPI3,
    make_result,
)


# ======================================================================
# Helpers
# ======================================================================

_NOW = datetime.now(timezone.utc)


def _make_swagger_source(*, id: int = 1, name: str = "TestAPI", base_url: str = "http://api.test") -> SwaggerSource:
    return SwaggerSource(
        id=id,
        name=name,
        url=None,
        raw_json="{}",
        base_url=base_url,
        created_at=_NOW,
    )


def _make_endpoint(*, id: int = 10, source_id: int = 1) -> ApiEndpoint:
    return ApiEndpoint(
        id=id,
        swagger_source_id=source_id,
        method="GET",
        path="/items",
        summary="List items",
        description="Returns all items",
        parameters=None,
        request_body=None,
        response_schema=None,
        created_at=_NOW,
    )


def _make_confirmation(*, id: int = 1, status: str = "pending") -> ActionConfirmation:
    return ActionConfirmation(
        id=id,
        correlation_id="corr-001",
        action="create_order",
        endpoint_method="POST",
        endpoint_path="/orders",
        payload_summary="New order for customer 42",
        status=status,
        created_at=_NOW,
    )


# ######################################################################
# 1. NEGATIVE TESTS — bad inputs → proper error codes
# ######################################################################


class TestQueryNegative:
    """POST /api/query bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_empty_body_returns_422(self, client):
        resp = await client.post("/api/v1/query", content=b"{}")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_query_string_returns_422(self, client):
        resp = await client.post("/api/v1/query", json={"query": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_extra_unknown_fields_still_works(self, client, fake_db):
        """Pydantic v2 ignores extra fields by default — request should succeed."""
        with patch("app.api.query.MLOpsClient") as MockMLOps:
            instance = MockMLOps.return_value
            instance.orchestrate = AsyncMock(return_value={
                "type": "text",
                "data": {"content": "ok"},
            })
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await client.post(
                "/api/v1/query",
                json={"query": "hello", "unknown_field": True, "foo": 123},
            )
        assert resp.status_code == 200


class TestSwaggerUploadNegative:
    """POST /api/swagger/upload bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_no_file_no_url_returns_400(self, client):
        resp = await client.post("/api/v1/swagger/upload")
        assert resp.status_code == 400
        assert "file" in resp.json()["detail"].lower() or "url" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_json_file_returns_400(self, client):
        broken = b"<<<not json or yaml at all>>>\x00"
        resp = await client.post(
            "/api/v1/swagger/upload",
            files={"file": ("bad.json", io.BytesIO(broken), "application/json")},
        )
        assert resp.status_code == 400


class TestSwaggerDeleteNegative:
    """DELETE /api/swagger/{id} bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_nonexistent_source_returns_404(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.delete("/api/v1/swagger/999999")
        assert resp.status_code == 404


class TestEndpointGetNegative:
    """GET /api/endpoints/{id} bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_nonexistent_endpoint_returns_404(self, client, fake_db):
        # fake_db.get returns None by default
        resp = await client.get("/api/v1/endpoints/999999")
        assert resp.status_code == 404


class TestEndpointSearchNegative:
    """GET /api/endpoints/search bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/search?q=")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/search")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_zero_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/search?q=test&limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_too_high_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/search?q=test&limit=999")
        assert resp.status_code == 422


class TestEndpointListNegative:
    """GET /api/endpoints/list bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_negative_limit_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/list?limit=-1")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_offset_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/list?offset=-1")
        assert resp.status_code == 422


class TestConfirmationNegative:
    """Confirmation endpoints — bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_status_filter_returns_422(self, client):
        resp = await client.get("/api/v1/confirmations?status=invalid")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_fields_returns_422(self, client):
        resp = await client.post("/api/v1/confirmations", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_method_trace_returns_422(self, client):
        resp = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "x",
                "action": "test",
                "endpoint_method": "TRACE",
                "endpoint_path": "/x",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_returns_404(self, client, fake_db):
        resp = await client.post(
            "/api/v1/confirmations/999/resolve",
            json={"status": "approved", "resolver": "admin@test"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_resolve_with_invalid_status_returns_422(self, client, fake_db):
        conf = _make_confirmation(id=1, status="pending")
        fake_db.register_get(ActionConfirmation, 1, conf)

        resp = await client.post(
            "/api/v1/confirmations/1/resolve",
            json={"status": "maybe", "resolver": "admin@test"},
        )
        assert resp.status_code == 422


class TestSwaggerListNegative:
    """GET /api/swagger/list bad-input scenarios."""

    @pytest.mark.asyncio
    async def test_limit_zero_returns_422(self, client):
        resp = await client.get("/api/v1/swagger/list?limit=0")
        assert resp.status_code == 422


class TestSandboxPathTraversal:
    """GET /api/sandbox/files — path traversal prevention.

    Paths containing ``..`` are normalised by the ASGI framework before
    they reach the handler, so the route may not match at all (404).
    The important assertion is that the request never succeeds (200).
    We also test with characters that *pass* the URL router but are
    caught by the handler's safe_pattern regex.
    """

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, client):
        resp = await client.get("/api/v1/sandbox/files/../../../etc/passwd/x")
        # Either the framework collapses the path (404) or the handler rejects (400)
        assert resp.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_double_dot_session_id_blocked(self, client):
        resp = await client.get("/api/v1/sandbox/files/..%2F..%2Fetc/passwd")
        assert resp.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_special_chars_in_session_id_returns_400(self, client):
        """Characters outside [a-zA-Z0-9._-] are rejected by the handler."""
        resp = await client.get("/api/sandbox/files/abc%3Bls/file.txt")
        # %3B is ';', which fails the safe_pattern regex → 400
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_space_in_filename_returns_400(self, client):
        resp = await client.get("/api/sandbox/files/session1/file%20name.txt")
        assert resp.status_code == 400


class TestNonexistentRoute:
    """Unknown routes should return 404."""

    @pytest.mark.asyncio
    async def test_nonexistent_route_returns_404(self, client):
        resp = await client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_nested_route_returns_404(self, client):
        resp = await client.get("/api/v1/swagger/nonexistent/deep/path")
        assert resp.status_code in (404, 422)  # 422 if path param parsed as int


# ######################################################################
# 2. E2E WORKFLOW TESTS
# ######################################################################


class TestUploadSearchQueryFlow:
    """Full upload -> search -> query flow (mocking OrchestrationService)."""

    @pytest.mark.asyncio
    async def test_full_flow(self, client, fake_db):
        # Step 1: upload a spec
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=4)

            upload_resp = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )

        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert upload_data["endpoints_count"] == 4
        source_id = upload_data["id"]

        # Step 2: search endpoints (mock RAG search)
        ep = _make_endpoint(id=20, source_id=source_id)
        with patch("app.api.endpoints.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.search = AsyncMock(return_value=[ep])

            search_resp = await client.get("/api/v1/endpoints/search?q=list+pets")

        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert len(search_data) >= 1

        # Step 3: query via MLOps orchestration
        # Populate fake_db with an endpoint so the query handler finds it
        ep_for_query = _make_endpoint(id=20, source_id=source_id)
        src_for_query = _make_swagger_source(id=source_id, base_url="https://petstore.example.com/v1")
        fake_db.set_execute_result(make_result(scalars=[ep_for_query]))
        fake_db.register_get(SwaggerSource, source_id, src_for_query)

        with patch("app.api.query.MLOpsClient") as MockMLOps:
            instance = MockMLOps.return_value
            instance.orchestrate = AsyncMock(return_value={
                "type": "table",
                "data": {"columns": ["id", "name"], "rows": [[1, "Buddy"]]},
                "metadata": {"status": "completed"},
            })

            query_resp = await client.post(
                "/api/v1/query",
                json={"query": "show all pets", "swagger_source_ids": [source_id]},
            )

        assert query_resp.status_code == 200
        assert query_resp.json()["type"] == "table"


class TestUploadDuplicateDeleteReupload:
    """Upload duplicate spec -> 409 -> delete -> re-upload succeeds."""

    @pytest.mark.asyncio
    async def test_duplicate_then_delete_then_reupload(self, client, fake_db):
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        # First upload succeeds
        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=4)

            resp1 = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )
        assert resp1.status_code == 200
        source_id = resp1.json()["id"]

        # Second upload of same spec -> 409 (duplicate detected)
        # Set up fake_db to return the existing source on duplicate check
        dup_src = SwaggerSource(
            id=source_id,
            name="Petstore",
            raw_json="{}",
            base_url="https://petstore.example.com/v1",
            created_at=_NOW,
        )
        fake_db.set_execute_result(make_result(scalars=[dup_src]))

        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=4)

            resp2 = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )
        assert resp2.status_code == 409
        assert "already uploaded" in resp2.json()["detail"]

        # Delete the original
        fake_db.set_execute_result(make_result(scalars=[dup_src]))
        del_resp = await client.delete(f"/api/v1/swagger/{source_id}")
        assert del_resp.status_code == 200

        # Re-upload succeeds (no duplicate in DB now)
        # Reset fake_db execute results to return no duplicate
        fake_db._execute_results.clear()

        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=4)

            resp3 = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )
        assert resp3.status_code == 200


class TestConfirmationWorkflow:
    """Create confirmation -> list pending -> resolve -> list approved."""

    @pytest.mark.asyncio
    async def test_full_confirmation_lifecycle(self, client, fake_db):
        # Step 1: create a confirmation
        create_resp = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "wf-001",
                "action": "send_email",
                "endpoint_method": "POST",
                "endpoint_path": "/emails/send",
                "payload_summary": "Send to 500 users",
            },
        )
        assert create_resp.status_code == 201
        conf_data = create_resp.json()
        conf_id = conf_data["id"]
        assert conf_data["status"] == "pending"

        # Step 2: list pending — should include our confirmation
        pending_conf = _make_confirmation(id=conf_id, status="pending")
        pending_conf.correlation_id = "wf-001"
        pending_conf.action = "send_email"
        pending_conf.endpoint_path = "/emails/send"
        fake_db.set_execute_result(make_result(scalars=[pending_conf]))

        list_resp = await client.get("/api/v1/confirmations?status=pending")
        assert list_resp.status_code == 200
        pending_list = list_resp.json()
        assert len(pending_list) >= 1
        assert any(c["correlation_id"] == "wf-001" for c in pending_list)

        # Step 3: resolve (approve)
        # Register the confirmation for get()
        pending_conf_for_get = ActionConfirmation(
            id=conf_id,
            correlation_id="wf-001",
            action="send_email",
            endpoint_method="POST",
            endpoint_path="/emails/send",
            payload_summary="Send to 500 users",
            status="pending",
            created_at=_NOW,
        )
        fake_db.register_get(ActionConfirmation, conf_id, pending_conf_for_get)

        resolve_resp = await client.post(
            f"/api/v1/confirmations/{conf_id}/resolve",
            json={"status": "approved", "resolver": "admin@company.com"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["message"] == "Action approved."

        # Step 4: list approved
        approved_conf = ActionConfirmation(
            id=conf_id,
            correlation_id="wf-001",
            action="send_email",
            endpoint_method="POST",
            endpoint_path="/emails/send",
            payload_summary="Send to 500 users",
            status="approved",
            created_at=_NOW,
        )
        fake_db.set_execute_result(make_result(scalars=[approved_conf]))

        approved_resp = await client.get("/api/v1/confirmations?status=approved")
        assert approved_resp.status_code == 200
        approved_list = approved_resp.json()
        assert len(approved_list) >= 1
        assert approved_list[0]["status"] == "approved"


class TestViewerFullWorkflow:
    """Viewer can read but is blocked on write/admin operations.
    Uses X-User-Role header for role-based access control."""

    @pytest.mark.asyncio
    async def test_viewer_can_read_blocked_on_write_and_admin(self, app, fake_db):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as viewer:
            # CAN read: list endpoints
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await viewer.get("/api/v1/endpoints/list")
            assert resp.status_code == 200

            # CAN read: list swagger sources
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await viewer.get("/api/v1/swagger/list")
            assert resp.status_code == 200

            # CAN read: list confirmations
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await viewer.get("/api/v1/confirmations?status=pending")
            assert resp.status_code == 200

            # BLOCKED on write: upload swagger (editor+)
            resp = await viewer.post("/api/v1/swagger/upload")
            assert resp.status_code == 403

            # BLOCKED on admin: delete swagger (admin only)
            resp = await viewer.delete("/api/v1/swagger/1")
            assert resp.status_code == 403

            # BLOCKED on admin: resolve confirmation (admin only)
            resp = await viewer.post(
                "/api/v1/confirmations/1/resolve",
                json={"status": "approved", "resolver": "x"},
            )
            assert resp.status_code == 403


class TestEditorFullWorkflow:
    """Editor can read+write but is blocked on admin operations.
    Uses X-User-Role header for role-based access control."""

    @pytest.mark.asyncio
    async def test_editor_can_write_blocked_on_admin(self, app, fake_db):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "editor"},
        ) as editor:
            # CAN write: query (unprotected endpoint)
            with patch("app.api.query.MLOpsClient") as MockMLOps:
                MockMLOps.return_value.orchestrate = AsyncMock(return_value={
                    "type": "text", "data": {"content": "ok"},
                })
                fake_db.set_execute_result(make_result(scalars=[]))
                resp = await editor.post("/api/v1/query", json={"query": "hello"})
            assert resp.status_code == 200

            # CAN write: upload spec (editor+)
            spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()
            with patch("app.api.swagger.RAGService") as MockRAG:
                MockRAG.return_value.index_endpoints = AsyncMock(return_value=4)
                resp = await editor.post(
                    "/api/v1/swagger/upload",
                    files={"file": ("p.json", io.BytesIO(spec_bytes), "application/json")},
                )
            assert resp.status_code == 200

            # BLOCKED on admin: delete swagger
            resp = await editor.delete("/api/v1/swagger/1")
            assert resp.status_code == 403

            # BLOCKED on admin: resolve confirmation
            resp = await editor.post(
                "/api/v1/confirmations/1/resolve",
                json={"status": "approved", "resolver": "x"},
            )
            assert resp.status_code == 403


# ######################################################################
# 3. EDGE CASES
# ######################################################################


class TestLargeSpecName:
    """Upload spec with a very long name (255+ characters)."""

    @pytest.mark.asyncio
    async def test_very_long_name_accepted(self, client, fake_db):
        long_name = "A" * 300
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=4)

            resp = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("spec.json", io.BytesIO(spec_bytes), "application/json")},
                data={"name": long_name},
            )

        # Should succeed — the endpoint doesn't enforce a max name length
        assert resp.status_code == 200
        assert resp.json()["name"] == long_name


class TestUnicodeQuery:
    """Query with unicode/emoji characters."""

    @pytest.mark.asyncio
    async def test_unicode_query(self, client, fake_db):
        with patch("app.api.query.MLOpsClient") as MockMLOps:
            MockMLOps.return_value.orchestrate = AsyncMock(return_value={
                "type": "text",
                "data": {"content": "result"},
            })
            fake_db.set_execute_result(make_result(scalars=[]))

            resp = await client.post(
                "/api/v1/query",
                json={"query": "Покажи пользователей с эмодзи 🎉🚀"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_emoji_only_query(self, client, fake_db):
        with patch("app.api.query.MLOpsClient") as MockMLOps:
            MockMLOps.return_value.orchestrate = AsyncMock(return_value={
                "type": "text",
                "data": {"content": "dunno"},
            })
            fake_db.set_execute_result(make_result(scalars=[]))

            resp = await client.post("/api/v1/query", json={"query": "🤔"})

        assert resp.status_code == 200


class TestSpecialSQLCharsInSearch:
    """Search with special SQL characters (%, _, ')."""

    @pytest.mark.asyncio
    async def test_percent_in_search(self, client, fake_db):
        """SQL wildcard % should be escaped, not cause errors."""
        with patch("app.api.endpoints.RAGService") as MockRAG:
            MockRAG.return_value.search = AsyncMock(return_value=[])
            resp = await client.get("/api/v1/endpoints/search?q=%25drop+table")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_underscore_in_search(self, client, fake_db):
        with patch("app.api.endpoints.RAGService") as MockRAG:
            MockRAG.return_value.search = AsyncMock(return_value=[])
            resp = await client.get("/api/v1/endpoints/search?q=user_id")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_apostrophe_in_search(self, client, fake_db):
        with patch("app.api.endpoints.RAGService") as MockRAG:
            MockRAG.return_value.search = AsyncMock(return_value=[])
            resp = await client.get("/api/v1/endpoints/search?q=O'Reilly")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sql_injection_attempt_in_list_filter(self, client, fake_db):
        """path_contains with injection payload should be safely escaped."""
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/v1/endpoints/list?path_contains='; DROP TABLE api_endpoints;--")
        assert resp.status_code == 200
        assert resp.json() == []


class TestConcurrentUploads:
    """Two uploads of different specs — both should succeed."""

    @pytest.mark.asyncio
    async def test_two_different_specs(self, client, fake_db):
        spec1 = {
            "openapi": "3.0.0",
            "info": {"title": "Service A", "version": "1.0"},
            "servers": [{"url": "https://a.example.com"}],
            "paths": {
                "/a": {"get": {"summary": "A endpoint", "responses": {"200": {"description": "ok"}}}}
            },
        }
        spec2 = {
            "openapi": "3.0.0",
            "info": {"title": "Service B", "version": "1.0"},
            "servers": [{"url": "https://b.example.com"}],
            "paths": {
                "/b": {"post": {"summary": "B endpoint", "responses": {"201": {"description": "created"}}}}
            },
        }

        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=1)

            resp1 = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("a.json", io.BytesIO(json.dumps(spec1).encode()), "application/json")},
            )
        assert resp1.status_code == 200
        assert resp1.json()["name"] == "Service A"

        with patch("app.api.swagger.RAGService") as MockRAG:
            MockRAG.return_value.index_endpoints = AsyncMock(return_value=1)

            resp2 = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("b.json", io.BytesIO(json.dumps(spec2).encode()), "application/json")},
            )
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Service B"


class TestEmptyDatabase:
    """All list endpoints return [] on an empty database."""

    @pytest.mark.asyncio
    async def test_list_endpoints_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/v1/endpoints/list")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_swagger_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/v1/swagger/list")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_confirmations_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(scalars=[]))
        resp = await client.get("/api/v1/confirmations?status=pending")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_endpoint_stats_empty(self, client, fake_db):
        fake_db._scalar_result = 0
        fake_db.set_execute_result(make_result(rows=[]))  # by_method
        fake_db.set_execute_result(make_result(rows=[]))  # by_source
        resp = await client.get("/api/v1/endpoints/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_endpoint_methods_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(rows=[]))
        resp = await client.get("/api/v1/endpoints/methods")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_endpoint_paths_empty(self, client, fake_db):
        fake_db.set_execute_result(make_result(rows=[]))
        resp = await client.get("/api/v1/endpoints/paths")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_search_with_no_results(self, client, fake_db):
        with patch("app.api.endpoints.RAGService") as MockRAG:
            MockRAG.return_value.search = AsyncMock(return_value=[])
            resp = await client.get("/api/v1/endpoints/search?q=nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []


class TestConfirmationEdgeCases:
    """Additional edge cases for confirmations."""

    @pytest.mark.asyncio
    async def test_create_with_empty_correlation_id_returns_422(self, client):
        resp = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "",
                "action": "test",
                "endpoint_method": "POST",
                "endpoint_path": "/x",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_with_empty_action_returns_422(self, client):
        resp = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "x",
                "action": "",
                "endpoint_method": "POST",
                "endpoint_path": "/x",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_with_empty_path_returns_422(self, client):
        resp = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "x",
                "action": "x",
                "endpoint_method": "POST",
                "endpoint_path": "",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_resolve_with_empty_resolver_returns_422(self, client, fake_db):
        conf = _make_confirmation(id=1, status="pending")
        fake_db.register_get(ActionConfirmation, 1, conf)

        resp = await client.post(
            "/api/v1/confirmations/1/resolve",
            json={"status": "approved", "resolver": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_methods_accepted(self, client, fake_db):
        """All valid HTTP methods (GET, POST, PUT, PATCH, DELETE) are accepted."""
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            resp = await client.post(
                "/api/v1/confirmations",
                json={
                    "correlation_id": f"test-{method}",
                    "action": "test",
                    "endpoint_method": method,
                    "endpoint_path": "/test",
                },
            )
            assert resp.status_code == 201, f"Method {method} should be accepted"

    @pytest.mark.asyncio
    async def test_invalid_methods_rejected(self, client):
        """Non-allowed methods (HEAD, OPTIONS, TRACE, CONNECT) are rejected."""
        for method in ("HEAD", "OPTIONS", "TRACE", "CONNECT", "FOOBAR"):
            resp = await client.post(
                "/api/v1/confirmations",
                json={
                    "correlation_id": "x",
                    "action": "test",
                    "endpoint_method": method,
                    "endpoint_path": "/test",
                },
            )
            assert resp.status_code == 422, f"Method {method} should be rejected"


class TestSwaggerListPagination:
    """Pagination edge cases for /api/swagger/list."""

    @pytest.mark.asyncio
    async def test_limit_above_max_returns_422(self, client):
        resp = await client.get("/api/v1/swagger/list?limit=501")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_offset_returns_422(self, client):
        resp = await client.get("/api/v1/swagger/list?offset=-1")
        assert resp.status_code == 422


class TestEndpointListPagination:
    """Pagination edge cases for /api/endpoints/list."""

    @pytest.mark.asyncio
    async def test_limit_above_max_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/list?limit=1001")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_zero_returns_422(self, client):
        resp = await client.get("/api/v1/endpoints/list?limit=0")
        assert resp.status_code == 422


class TestQueryWithSourceIds:
    """Query with specific swagger_source_ids edge cases."""

    @pytest.mark.asyncio
    async def test_query_with_empty_source_ids_list(self, client, fake_db):
        """Empty list should be treated as no filter."""
        with patch("app.api.query.MLOpsClient") as MockMLOps:
            MockMLOps.return_value.orchestrate = AsyncMock(return_value={
                "type": "text",
                "data": {"content": "ok"},
            })
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await client.post(
                "/api/v1/query",
                json={"query": "test", "swagger_source_ids": []},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_query_with_null_source_ids(self, client, fake_db):
        with patch("app.api.query.MLOpsClient") as MockMLOps:
            MockMLOps.return_value.orchestrate = AsyncMock(return_value={
                "type": "text",
                "data": {"content": "ok"},
            })
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await client.post(
                "/api/v1/query",
                json={"query": "test", "swagger_source_ids": None},
            )
        assert resp.status_code == 200


class TestUploadSpecContentEdgeCases:
    """Content edge cases for spec upload."""

    @pytest.mark.asyncio
    async def test_array_content_returns_400(self, client):
        """JSON array (not object) should fail."""
        arr = json.dumps([{"path": "/a"}]).encode()
        resp = await client.post(
            "/api/v1/swagger/upload",
            files={"file": ("arr.json", io.BytesIO(arr), "application/json")},
        )
        assert resp.status_code == 400
        assert "dictionary" in resp.json()["detail"].lower() or "object" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_scalar_json_content_returns_400(self, client):
        """Plain string JSON should fail."""
        scalar = json.dumps("just a string").encode()
        resp = await client.post(
            "/api/v1/swagger/upload",
            files={"file": ("s.json", io.BytesIO(scalar), "application/json")},
        )
        assert resp.status_code == 400
