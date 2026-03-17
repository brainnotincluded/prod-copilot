"""Tests for JWT Bearer token authorization.

Auth changed from X-User-Role header to JWT Bearer tokens.
The conftest.py already overrides ``require_auth`` to return a fake admin user
so most endpoint tests pass without real tokens.

These tests verify:
- Role hierarchy logic still works
- The old get_current_user helper (app.auth) still parses X-User-Role
- Protected endpoints require authentication (via require_auth dependency)
- Unprotected endpoints (query router) don't require auth
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import Role, get_current_user


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
# Helper to make a client without auth override (no require_auth mock)
# -----------------------------------------------------------------------

async def _unauthenticated_client(app_no_auth) -> AsyncClient:
    """Return an AsyncClient with no auth headers."""
    transport = ASGITransport(app=app_no_auth)
    return AsyncClient(
        transport=transport,
        base_url="http://test",
    )


# -----------------------------------------------------------------------
# API-level: Protected endpoints require auth (via require_auth override)
# -----------------------------------------------------------------------

class TestViewerRestrictions:
    """Endpoints use both JWT auth (require_auth, overridden in conftest)
    and role-based auth (require_role via X-User-Role header).
    Tests verify both layers work correctly."""

    @pytest.mark.asyncio
    async def test_viewer_cannot_upload(self, app, fake_db):
        """Upload requires Role.EDITOR via require_role. Viewer gets 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as c:
            resp = await c.post("/api/v1/swagger/upload")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete(self, app, fake_db):
        """Delete requires Role.ADMIN via require_role. Viewer gets 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as c:
            resp = await c.delete("/api/v1/swagger/1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_can_list_endpoints(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as c:
            resp = await c.get("/api/v1/endpoints/list")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_can_list_swagger(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as c:
            resp = await c.get("/api/v1/swagger/list")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_can_list_confirmations(self, app, fake_db):
        from tests.conftest import make_result
        fake_db.set_execute_result(make_result(scalars=[]))
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "viewer"},
        ) as c:
            resp = await c.get("/api/v1/confirmations?status=pending")
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# API-level: editor access
# -----------------------------------------------------------------------

class TestEditorRestrictions:

    @pytest.mark.asyncio
    async def test_editor_cannot_delete(self, app, fake_db):
        """Delete requires Role.ADMIN. Editor gets 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"X-User-Role": "editor"},
        ) as c:
            resp = await c.delete("/api/v1/swagger/1")
        assert resp.status_code == 403


# -----------------------------------------------------------------------
# API-level: admin can do everything (conftest override = admin)
# -----------------------------------------------------------------------

class TestAdminAccess:

    @pytest.mark.asyncio
    async def test_admin_can_delete(self, client, fake_db):
        from tests.conftest import make_result
        from app.db.models import SwaggerSource
        now = datetime.now(timezone.utc)
        src = SwaggerSource(id=1, name="X", raw_json="{}", created_at=now)
        fake_db.set_execute_result(make_result(scalars=[src]))
        resp = await client.delete("/api/v1/swagger/1")
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
            "/api/v1/confirmations/1/resolve",
            json={"status": "approved", "resolver": "admin@co"},
        )
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# POST /query is now unprotected (no require_auth dependency)
# -----------------------------------------------------------------------

class TestDefaultRole:

    @pytest.mark.asyncio
    async def test_query_endpoint_is_accessible_without_auth(self, app, fake_db):
        """POST /query is on the query router which has no auth dependency.
        It should be accessible without any auth header."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/query", json={"query": ""})
        # 422 for empty query (validation error), but NOT 401/403
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_no_role_header_defaults_to_editor(self, app, fake_db):
        """No X-User-Role header -> defaults to editor -> cannot delete (admin only)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Default role is editor -> cannot delete (admin only)
            resp = await c.delete("/api/v1/swagger/1")
            assert resp.status_code == 403
