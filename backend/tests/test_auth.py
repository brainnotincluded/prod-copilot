"""Tests for X-User-Role header authorization.

Roles: viewer (read-only), editor (+ upload, query), admin (+ delete, approve).
Default (no header) = editor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import CurrentUser, Role, get_current_user, require_role


# -----------------------------------------------------------------------
# Unit: Role hierarchy and require_role logic
# -----------------------------------------------------------------------

class TestRoleHierarchy:

    def test_viewer_is_lowest(self):
        from app.auth import _ROLE_WEIGHT
        assert _ROLE_WEIGHT[Role.VIEWER] < _ROLE_WEIGHT[Role.EDITOR] < _ROLE_WEIGHT[Role.ADMIN]

    def test_get_current_user_parses_header(self):
        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers = {"X-User-Role": "viewer"}
        user = get_current_user(request)
        assert user.role == Role.VIEWER

    def test_get_current_user_defaults_to_editor(self):
        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers = {}
        user = get_current_user(request)
        assert user.role == Role.EDITOR

    def test_get_current_user_invalid_role_defaults_editor(self):
        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers = {"X-User-Role": "superadmin"}
        user = get_current_user(request)
        assert user.role == Role.EDITOR

    def test_get_current_user_case_insensitive(self):
        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers = {"X-User-Role": "ADMIN"}
        user = get_current_user(request)
        assert user.role == Role.ADMIN


# -----------------------------------------------------------------------
# Helper to make a client with a specific role
# -----------------------------------------------------------------------

async def _client_with_role(app, role: str) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-User-Role": role},
    )


# -----------------------------------------------------------------------
# API-level: viewer gets 403 on write endpoints
# -----------------------------------------------------------------------

class TestViewerRestrictions:

    @pytest.mark.asyncio
    async def test_viewer_cannot_upload(self, app, fake_db):
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.post("/api/swagger/upload")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete(self, app, fake_db):
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.delete("/api/swagger/1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_query(self, app, fake_db):
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.post("/api/query", json={"query": "test"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_resolve_confirmation(self, app, fake_db):
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.post(
                "/api/confirmations/1/resolve",
                json={"status": "approved", "resolver": "x"},
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_can_list_endpoints(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.get("/api/endpoints/list")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_can_list_swagger(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.get("/api/swagger/list")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_can_list_confirmations(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        async with await _client_with_role(app, "viewer") as c:
            resp = await c.get("/api/confirmations?status=pending")
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# API-level: editor can write but not admin-actions
# -----------------------------------------------------------------------

class TestEditorRestrictions:

    @pytest.mark.asyncio
    async def test_editor_cannot_delete(self, app, fake_db):
        async with await _client_with_role(app, "editor") as c:
            resp = await c.delete("/api/swagger/1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_cannot_resolve_confirmation(self, app, fake_db):
        async with await _client_with_role(app, "editor") as c:
            resp = await c.post(
                "/api/confirmations/1/resolve",
                json={"status": "approved", "resolver": "x"},
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_query(self, app, fake_db):
        with patch("app.api.query.OrchestrationService") as MockSvc:
            from app.schemas.models import ResultResponse
            MockSvc.return_value.execute = AsyncMock(
                return_value=ResultResponse(type="text", data={"content": "ok"})
            )
            async with await _client_with_role(app, "editor") as c:
                resp = await c.post("/api/query", json={"query": "test"})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# API-level: admin can do everything
# -----------------------------------------------------------------------

class TestAdminAccess:

    @pytest.mark.asyncio
    async def test_admin_can_delete(self, client, fake_db):
        from tests.conftest import make_result
        from app.db.models import SwaggerSource
        now = datetime.now(timezone.utc)
        src = SwaggerSource(id=1, name="X", raw_json="{}", created_at=now)
        fake_db.set_execute_result(make_result(scalars=[src]))
        resp = await client.delete("/api/swagger/1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_resolve_confirmation(self, client, fake_db):
        from app.db.models import ActionConfirmation
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=1, correlation_id="x", action="a",
            endpoint_method="POST", endpoint_path="/x",
            status="pending", created_at=now,
        )
        fake_db.register_get(ActionConfirmation, 1, conf)
        resp = await client.post(
            "/api/confirmations/1/resolve",
            json={"status": "approved", "resolver": "admin@co"},
        )
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Default (no header) = editor
# -----------------------------------------------------------------------

class TestDefaultRole:

    @pytest.mark.asyncio
    async def test_no_header_defaults_to_editor(self, app, fake_db):
        """No X-User-Role header → editor → can query, cannot delete."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # editor can query
            with patch("app.api.query.OrchestrationService") as MockSvc:
                from app.schemas.models import ResultResponse
                MockSvc.return_value.execute = AsyncMock(
                    return_value=ResultResponse(type="text", data={"content": "ok"})
                )
                resp = await c.post("/api/query", json={"query": "test"})
            assert resp.status_code == 200

            # but cannot delete (admin only)
            resp = await c.delete("/api/swagger/1")
            assert resp.status_code == 403
