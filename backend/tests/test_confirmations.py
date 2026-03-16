"""Tests for action confirmations workflow.

Mutating actions require explicit approval before execution.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import ActionConfirmation
from tests.conftest import make_result


class TestConfirmationModel:

    def test_table_name(self):
        assert ActionConfirmation.__tablename__ == "action_confirmations"

    def test_status_default(self):
        from app.db.models import ActionConfirmation
        cols = {c.name: c for c in ActionConfirmation.__table__.columns}
        assert cols["status"].default.arg == "pending"


class TestListConfirmations:

    @pytest.mark.asyncio
    async def test_list_pending(self, client, fake_db):
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=1, correlation_id="abc-123", action="send_push",
            endpoint_method="POST", endpoint_path="/notifications",
            payload_summary="Send to 1000 users",
            status="pending", created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=[conf]))

        resp = await client.get("/api/confirmations?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["action"] == "send_push"
        assert data[0]["status"] == "pending"


class TestResolveConfirmation:

    @pytest.mark.asyncio
    async def test_approve_pending(self, client, fake_db):
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=1, correlation_id="abc-123", action="send_push",
            endpoint_method="POST", endpoint_path="/notifications",
            status="pending", created_at=now,
        )
        fake_db.register_get(ActionConfirmation, 1, conf)

        resp = await client.post(
            "/api/confirmations/1/resolve",
            json={"status": "approved", "resolver": "admin@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Action approved."
        assert conf.status == "approved"
        assert conf.resolved_by == "admin@example.com"

    @pytest.mark.asyncio
    async def test_reject_pending(self, client, fake_db):
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=1, correlation_id="abc-123", action="send_push",
            endpoint_method="POST", endpoint_path="/notifications",
            status="pending", created_at=now,
        )
        fake_db.register_get(ActionConfirmation, 1, conf)

        resp = await client.post(
            "/api/confirmations/1/resolve",
            json={"status": "rejected", "resolver": "admin@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Action rejected."
        assert conf.status == "rejected"

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_fails(self, client, fake_db):
        now = datetime.now(timezone.utc)
        conf = ActionConfirmation(
            id=1, correlation_id="abc-123", action="send_push",
            endpoint_method="POST", endpoint_path="/notifications",
            status="approved", created_at=now, resolved_by="other@example.com",
        )
        fake_db.register_get(ActionConfirmation, 1, conf)

        resp = await client.post(
            "/api/confirmations/1/resolve",
            json={"status": "rejected", "resolver": "admin@example.com"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, client, fake_db):
        resp = await client.post(
            "/api/confirmations/999/resolve",
            json={"status": "approved", "resolver": "admin@example.com"},
        )
        assert resp.status_code == 404


class TestCreateConfirmation:

    @pytest.mark.asyncio
    async def test_create_confirmation(self, client, fake_db):
        resp = await client.post(
            "/api/confirmations",
            json={
                "correlation_id": "xyz-789",
                "action": "create_campaign",
                "endpoint_method": "POST",
                "endpoint_path": "/campaigns",
                "payload_summary": "New year campaign",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["correlation_id"] == "xyz-789"
        assert body["action"] == "create_campaign"
        assert body["endpoint_method"] == "POST"
        assert body["endpoint_path"] == "/campaigns"
        assert body["payload_summary"] == "New year campaign"
        assert body["status"] == "pending"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_create_confirmation_without_payload(self, client, fake_db):
        resp = await client.post(
            "/api/confirmations",
            json={
                "correlation_id": "abc-111",
                "action": "delete_segment",
                "endpoint_method": "DELETE",
                "endpoint_path": "/segments/42",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["payload_summary"] is None

    @pytest.mark.asyncio
    async def test_create_confirmation_invalid_method_rejected(self, client, fake_db):
        resp = await client.post(
            "/api/confirmations",
            json={
                "correlation_id": "x",
                "action": "x",
                "endpoint_method": "INVALID",
                "endpoint_path": "/x",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_confirmation_missing_fields_rejected(self, client, fake_db):
        resp = await client.post("/api/confirmations", json={})
        assert resp.status_code == 422
