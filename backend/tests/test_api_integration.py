"""Integration tests for complete API workflows.

Covers: end-to-end scenarios combining multiple endpoints.
"""

import io
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.db.models import ApiEndpoint, ActionConfirmation
from tests.conftest import make_result


class TestUploadAndQueryFlow:
    """Complete flow: upload spec → list endpoints → query."""

    @pytest.mark.asyncio
    async def test_upload_then_list_endpoints(self, client, fake_db):
        """Upload spec and then list its endpoints."""
        from tests.conftest import PETSTORE_OPENAPI3
        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        # Step 1: Upload
        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=4)

            fake_db.set_execute_result(make_result(scalars=[]))
            
            resp_upload = await client.post(
                "/api/v1/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )
            assert resp_upload.status_code == 200

        # Step 2: List endpoints would query the DB
        now = datetime.now(timezone.utc)
        ep = ApiEndpoint(
            id=1, swagger_source_id=1, method="GET", path="/v1/pets",
            summary="List pets", description=None, parameters=None,
            request_body=None, response_schema=None, created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp_list = await client.get("/api/v1/endpoints/list")
        assert resp_list.status_code == 200
        data = resp_list.json()
        assert len(data) == 1
        assert data[0]["path"] == "/v1/pets"


class TestConfirmationWorkflow:
    """Complete confirmation workflow."""

    @pytest.mark.asyncio
    async def test_create_then_resolve_confirmation(self, client, fake_db):
        """Create confirmation and then resolve it."""
        # Step 1: Create confirmation
        resp_create = await client.post(
            "/api/v1/confirmations",
            json={
                "correlation_id": "workflow-123",
                "action": "delete_user",
                "endpoint_method": "DELETE",
                "endpoint_path": "/users/42",
                "payload_summary": "Delete user #42",
            },
        )
        assert resp_create.status_code == 201
        confirm_id = resp_create.json()["id"]

        # Step 2: List confirmations (should find it)
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=confirm_id, correlation_id="workflow-123", action="delete_user",
            endpoint_method="DELETE", endpoint_path="/users/42",
            payload_summary="Delete user #42",
            status="pending", created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp_list = await client.get("/api/v1/confirmations?status=pending")
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 1

        # Step 3: Resolve confirmation
        fake_db.register_get(ActionConfirmation, confirm_id, conf)
        resp_resolve = await client.post(
            f"/api/v1/confirmations/{confirm_id}/resolve",
            json={"status": "approved", "resolver": "admin@example.com"},
        )
        assert resp_resolve.status_code == 200


class TestAuthProtectedWorkflow:
    """Workflows requiring different auth levels."""

    @pytest.mark.asyncio
    async def test_viewer_read_only_workflow(self, app, fake_db):
        """Viewer can read but not modify."""
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as client:
            # Can list endpoints
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await client.get("/api/v1/endpoints/list")
            assert resp.status_code == 200

            # Cannot upload
            resp = await client.post("/api/v1/swagger/upload")
            assert resp.status_code == 403

            # Cannot delete
            resp = await client.delete("/api/v1/swagger/1")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_standard_workflow(self, app, fake_db):
        """Editor can read, upload, query but not admin actions."""
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "editor"},
        ) as client:
            # Can list
            fake_db.set_execute_result(make_result(scalars=[]))
            resp = await client.get("/api/v1/endpoints/list")
            assert resp.status_code == 200

            # Cannot delete (admin only)
            resp = await client.delete("/api/v1/swagger/1")
            assert resp.status_code == 403

            # Cannot resolve confirmations (admin only)
            resp = await client.post("/api/v1/confirmations/1/resolve", json={"status": "approved"})
            assert resp.status_code == 403


class TestErrorRecovery:
    """System behavior under errors."""

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible(self, client):
        """Health endpoint should work without auth."""
        resp = await client.get("/health")
        assert resp.status_code == 200

