"""Tests for /api/relations/* endpoints and helper functions.

NOTE: The relations router is NOT yet included in app/api/router.py.
      To make the HTTP-level tests pass, add to router.py:

          from app.api.relations import router as relations_router
          api_router.include_router(relations_router, prefix="/relations", tags=["relations"])

Covers:
  - GET  /api/relations/map              (entity map with nodes/edges)
  - GET  /api/relations/relations/{id}/suggestions (connection suggestions)
  - POST /api/relations/relations/analyze (analyze relations across APIs)
  - _format_field_mapping helper
  - _extract_schema_fields helper
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.relations import _extract_schema_fields, _format_field_mapping
from app.db.models import ApiEndpoint, EntityRelation, SwaggerSource
from tests.conftest import FakeAsyncSession, make_result


# ---------------------------------------------------------------------------
# Helper: _format_field_mapping
# ---------------------------------------------------------------------------


class TestFormatFieldMapping:

    def test_both_fields_present(self):
        mapping = {"source_field": "user_id", "target_field": "id"}
        assert _format_field_mapping(mapping) == "user_id → id"

    def test_only_source_field(self):
        mapping = {"source_field": "order_id"}
        assert _format_field_mapping(mapping) == "order_id → ?"

    def test_only_target_field(self):
        mapping = {"target_field": "id"}
        assert _format_field_mapping(mapping) == "? → id"

    def test_empty_dict(self):
        assert _format_field_mapping({}) == "→"

    def test_none_mapping(self):
        assert _format_field_mapping(None) == "→"

    def test_no_relevant_keys(self):
        mapping = {"foo": "bar", "baz": "qux"}
        assert _format_field_mapping(mapping) == "? → ?"

    def test_extra_keys_ignored(self):
        mapping = {
            "source_field": "campaign_id",
            "target_field": "id",
            "extra": "ignored",
        }
        assert _format_field_mapping(mapping) == "campaign_id → id"


# ---------------------------------------------------------------------------
# Helper: _extract_schema_fields
# ---------------------------------------------------------------------------


class TestExtractSchemaFields:

    def test_flat_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
        }
        fields = _extract_schema_fields(schema)
        assert set(fields) == {"id", "name", "email"}

    def test_nested_object(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "zip": {"type": "string"},
                    },
                },
            },
        }
        fields = _extract_schema_fields(schema)
        assert "id" in fields
        assert "address" in fields
        assert "address.city" in fields
        assert "address.zip" in fields

    def test_array_with_object_items(self):
        schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "integer"},
                            "role": {"type": "string"},
                        },
                    },
                },
            },
        }
        fields = _extract_schema_fields(schema)
        assert "users" in fields
        assert "users[].user_id" in fields
        assert "users[].role" in fields

    def test_array_with_primitive_items(self):
        """Array of strings should not recurse into items."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
        fields = _extract_schema_fields(schema)
        assert fields == ["tags"]

    def test_empty_properties(self):
        schema = {"type": "object", "properties": {}}
        assert _extract_schema_fields(schema) == []

    def test_no_properties_key(self):
        schema = {"type": "object"}
        assert _extract_schema_fields(schema) == []

    def test_not_a_dict(self):
        assert _extract_schema_fields("not a dict") == []
        assert _extract_schema_fields(None) == []
        assert _extract_schema_fields(42) == []
        assert _extract_schema_fields([]) == []

    def test_empty_dict(self):
        assert _extract_schema_fields({}) == []

    def test_with_prefix(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        }
        fields = _extract_schema_fields(schema, prefix="root")
        assert fields == ["root.name"]

    def test_deeply_nested(self):
        schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        fields = _extract_schema_fields(schema)
        assert "level1" in fields
        assert "level1.level2" in fields
        assert "level1.level2.value" in fields

    def test_mixed_nested_and_flat(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "meta": {
                    "type": "object",
                    "properties": {
                        "created_at": {"type": "string"},
                    },
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "integer"},
                        },
                    },
                },
                "name": {"type": "string"},
            },
        }
        fields = _extract_schema_fields(schema)
        assert "id" in fields
        assert "meta" in fields
        assert "meta.created_at" in fields
        assert "items" in fields
        assert "items[].item_id" in fields
        assert "name" in fields

    def test_array_with_no_items(self):
        """Array property with missing 'items' key should not crash."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array"},
            },
        }
        fields = _extract_schema_fields(schema)
        assert fields == ["tags"]


# ---------------------------------------------------------------------------
# Shared model factories
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _make_source(id: int = 1, name: str = "PetAPI", base_url: str = "https://api.example.com") -> SwaggerSource:
    return SwaggerSource(
        id=id,
        name=name,
        base_url=base_url,
        url=f"{base_url}/swagger.json",
        raw_json="{}",
        created_at=_NOW,
    )


def _make_endpoint(
    id: int = 1,
    swagger_source_id: int = 1,
    method: str = "GET",
    path: str = "/pets",
    summary: str = "List pets",
    request_body=None,
    response_schema=None,
) -> ApiEndpoint:
    return ApiEndpoint(
        id=id,
        swagger_source_id=swagger_source_id,
        method=method,
        path=path,
        summary=summary,
        description=None,
        parameters=None,
        request_body=request_body,
        response_schema=response_schema,
        created_at=_NOW,
    )


def _make_relation(
    id: int = 1,
    source_endpoint_id: int = 1,
    target_endpoint_id: int = 2,
    relation_type: str = "one_to_many",
    field_mapping: dict | None = None,
    confidence: str = "0.85",
) -> EntityRelation:
    return EntityRelation(
        id=id,
        source_endpoint_id=source_endpoint_id,
        target_endpoint_id=target_endpoint_id,
        relation_type=relation_type,
        field_mapping=field_mapping or {"source_field": "user_id", "target_field": "id"},
        confidence=confidence,
        created_at=_NOW,
    )


# ---------------------------------------------------------------------------
# GET /api/relations/map
# ---------------------------------------------------------------------------


class TestGetEntityMap:

    @pytest.mark.asyncio
    async def test_happy_path_full_map(self, client, fake_db):
        """Returns sources, endpoints, and relations as nodes/edges."""
        source = _make_source(id=1)
        ep1 = _make_endpoint(id=10, swagger_source_id=1, method="GET", path="/users")
        ep2 = _make_endpoint(id=11, swagger_source_id=1, method="POST", path="/orders")
        rel = _make_relation(id=100, source_endpoint_id=10, target_endpoint_id=11)

        # Three execute() calls: sources, endpoints, relations
        fake_db.set_execute_result(make_result(scalars=[source]))
        fake_db.set_execute_result(make_result(scalars=[ep1, ep2]))
        fake_db.set_execute_result(make_result(scalars=[rel]))

        resp = await client.get("/api/relations/map")
        assert resp.status_code == 200
        data = resp.json()

        # Nodes: 1 API source + 2 endpoints
        assert len(data["nodes"]) == 3
        api_nodes = [n for n in data["nodes"] if n["type"] == "api"]
        ep_nodes = [n for n in data["nodes"] if n["type"] == "endpoint"]
        assert len(api_nodes) == 1
        assert len(ep_nodes) == 2

        # Check source node structure
        assert api_nodes[0]["id"] == "source_1"
        assert api_nodes[0]["label"] == "PetAPI"
        assert api_nodes[0]["base_url"] == "https://api.example.com"

        # Check endpoint node structure
        ep_ids = {n["id"] for n in ep_nodes}
        assert "endpoint_10" in ep_ids
        assert "endpoint_11" in ep_ids

        # Edges: 2 "contains" + 1 "relation"
        contains_edges = [e for e in data["edges"] if e["type"] == "contains"]
        relation_edges = [e for e in data["edges"] if e["type"] == "relation"]
        assert len(contains_edges) == 2
        assert len(relation_edges) == 1

        rel_edge = relation_edges[0]
        assert rel_edge["from"] == "endpoint_10"
        assert rel_edge["to"] == "endpoint_11"
        assert rel_edge["confidence"] == 0.85
        assert rel_edge["relation_type"] == "one_to_many"

        # Stats
        assert data["stats"]["total_apis"] == 1
        assert data["stats"]["total_endpoints"] == 2
        assert data["stats"]["total_relations"] == 1

    @pytest.mark.asyncio
    async def test_empty_database(self, client, fake_db):
        """Empty DB returns empty nodes/edges and zero stats."""
        fake_db.set_execute_result(make_result(scalars=[]))
        fake_db.set_execute_result(make_result(scalars=[]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/map")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["stats"] == {
            "total_apis": 0,
            "total_endpoints": 0,
            "total_relations": 0,
        }

    @pytest.mark.asyncio
    async def test_filter_by_source_id(self, client, fake_db):
        """Passing ?source_id= filters sources, endpoints, and relations."""
        source = _make_source(id=5)
        ep = _make_endpoint(id=20, swagger_source_id=5)

        fake_db.set_execute_result(make_result(scalars=[source]))
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/map", params={"source_id": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2  # 1 source + 1 endpoint
        assert data["stats"]["total_apis"] == 1
        assert data["stats"]["total_endpoints"] == 1

    @pytest.mark.asyncio
    async def test_source_id_zero_is_treated_as_no_filter(self, client, fake_db):
        """source_id=0 is falsy, so it should not filter (same as no filter)."""
        fake_db.set_execute_result(make_result(scalars=[]))
        fake_db.set_execute_result(make_result(scalars=[]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/map", params={"source_id": 0})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_endpoint_node_has_request_body_flag(self, client, fake_db):
        """Endpoint nodes include has_request_body and has_response flags."""
        source = _make_source(id=1)
        ep = _make_endpoint(
            id=1, swagger_source_id=1,
            request_body={"type": "object"},
            response_schema={"type": "object", "properties": {"id": {"type": "integer"}}},
        )
        fake_db.set_execute_result(make_result(scalars=[source]))
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/map")
        data = resp.json()
        ep_node = [n for n in data["nodes"] if n["type"] == "endpoint"][0]
        assert ep_node["data"]["has_request_body"] is True
        assert ep_node["data"]["has_response"] is True

    @pytest.mark.asyncio
    async def test_endpoint_node_no_body_no_response(self, client, fake_db):
        """Endpoint without body or response schema has False flags."""
        source = _make_source(id=1)
        ep = _make_endpoint(id=1, swagger_source_id=1, request_body=None, response_schema=None)

        fake_db.set_execute_result(make_result(scalars=[source]))
        fake_db.set_execute_result(make_result(scalars=[ep]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/map")
        data = resp.json()
        ep_node = [n for n in data["nodes"] if n["type"] == "endpoint"][0]
        assert ep_node["data"]["has_request_body"] is False
        assert ep_node["data"]["has_response"] is False

    @pytest.mark.asyncio
    async def test_multiple_sources_and_relations(self, client, fake_db):
        """Multiple sources with cross-source relations."""
        s1 = _make_source(id=1, name="UserAPI")
        s2 = _make_source(id=2, name="OrderAPI", base_url="https://orders.example.com")
        ep1 = _make_endpoint(id=10, swagger_source_id=1, method="GET", path="/users")
        ep2 = _make_endpoint(id=20, swagger_source_id=2, method="GET", path="/orders")
        rel = _make_relation(id=1, source_endpoint_id=10, target_endpoint_id=20)

        fake_db.set_execute_result(make_result(scalars=[s1, s2]))
        fake_db.set_execute_result(make_result(scalars=[ep1, ep2]))
        fake_db.set_execute_result(make_result(scalars=[rel]))

        resp = await client.get("/api/relations/map")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_apis"] == 2
        assert data["stats"]["total_endpoints"] == 2
        assert data["stats"]["total_relations"] == 1

    @pytest.mark.asyncio
    async def test_relation_edge_label_uses_format_helper(self, client, fake_db):
        """Relation edge 'label' is built by _format_field_mapping."""
        source = _make_source(id=1)
        ep1 = _make_endpoint(id=1, swagger_source_id=1)
        ep2 = _make_endpoint(id=2, swagger_source_id=1)
        rel = _make_relation(
            id=1,
            source_endpoint_id=1,
            target_endpoint_id=2,
            field_mapping={"source_field": "order_id", "target_field": "id"},
        )

        fake_db.set_execute_result(make_result(scalars=[source]))
        fake_db.set_execute_result(make_result(scalars=[ep1, ep2]))
        fake_db.set_execute_result(make_result(scalars=[rel]))

        resp = await client.get("/api/relations/map")
        data = resp.json()
        rel_edge = [e for e in data["edges"] if e["type"] == "relation"][0]
        assert rel_edge["label"] == "order_id → id"


# ---------------------------------------------------------------------------
# GET /api/relations/relations/{endpoint_id}/suggestions
# ---------------------------------------------------------------------------


class TestGetConnectionSuggestions:

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, fake_db):
        """Non-existent endpoint_id returns 404."""
        # db.get returns None by default
        resp = await client.get("/api/relations/relations/999/suggestions")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_no_relations_returns_empty(self, client, fake_db):
        """Endpoint exists but has no relations -> empty suggestions."""
        ep = _make_endpoint(id=5)
        fake_db.register_get(ApiEndpoint, 5, ep)
        # Forward relations query
        fake_db.set_execute_result(make_result(scalars=[]))
        # Reverse relations query
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/relations/5/suggestions")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_direct_relation_suggestions(self, client, fake_db):
        """Direct relations (source -> target) appear as 'direct_relation' type."""
        ep_source = _make_endpoint(id=1, method="GET", path="/users")
        ep_target = _make_endpoint(id=2, method="GET", path="/orders")
        rel = _make_relation(
            id=10,
            source_endpoint_id=1,
            target_endpoint_id=2,
            field_mapping={"source_field": "user_id", "target_field": "id"},
            confidence="0.92",
        )

        fake_db.register_get(ApiEndpoint, 1, ep_source)
        fake_db.register_get(ApiEndpoint, 2, ep_target)
        # Forward relations
        fake_db.set_execute_result(make_result(scalars=[rel]))
        # Reverse relations
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/relations/1/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        s = data[0]
        assert s["type"] == "direct_relation"
        assert s["endpoint_id"] == 2
        assert s["endpoint"] == "GET /orders"
        assert s["confidence"] == 0.92
        assert "id" in s["reason"]

    @pytest.mark.asyncio
    async def test_prerequisite_suggestions(self, client, fake_db):
        """Reverse relations appear as 'prerequisite' type."""
        ep_target = _make_endpoint(id=5, method="POST", path="/orders")
        ep_source = _make_endpoint(id=3, method="GET", path="/users")
        rel = _make_relation(
            id=20,
            source_endpoint_id=3,
            target_endpoint_id=5,
            field_mapping={"source_field": "user_id", "target_field": "buyer_id"},
            confidence="0.75",
        )

        fake_db.register_get(ApiEndpoint, 5, ep_target)
        fake_db.register_get(ApiEndpoint, 3, ep_source)
        # Forward relations for endpoint 5
        fake_db.set_execute_result(make_result(scalars=[]))
        # Reverse relations for endpoint 5
        fake_db.set_execute_result(make_result(scalars=[rel]))

        resp = await client.get("/api/relations/relations/5/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        s = data[0]
        assert s["type"] == "prerequisite"
        assert s["endpoint_id"] == 3
        assert s["endpoint"] == "GET /users"
        assert s["confidence"] == 0.75
        assert "user_id" in s["reason"]

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_confidence_descending(self, client, fake_db):
        """Suggestions are sorted by confidence from highest to lowest."""
        ep = _make_endpoint(id=1, method="GET", path="/main")
        ep_low = _make_endpoint(id=2, method="GET", path="/low")
        ep_high = _make_endpoint(id=3, method="GET", path="/high")
        ep_mid = _make_endpoint(id=4, method="GET", path="/mid")

        rel_low = _make_relation(id=1, source_endpoint_id=1, target_endpoint_id=2, confidence="0.5")
        rel_high = _make_relation(id=2, source_endpoint_id=1, target_endpoint_id=3, confidence="0.99")
        rel_mid = _make_relation(id=3, source_endpoint_id=1, target_endpoint_id=4, confidence="0.75")

        fake_db.register_get(ApiEndpoint, 1, ep)
        fake_db.register_get(ApiEndpoint, 2, ep_low)
        fake_db.register_get(ApiEndpoint, 3, ep_high)
        fake_db.register_get(ApiEndpoint, 4, ep_mid)

        # Forward relations
        fake_db.set_execute_result(make_result(scalars=[rel_low, rel_high, rel_mid]))
        # Reverse relations
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/relations/1/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        confidences = [s["confidence"] for s in data]
        assert confidences == sorted(confidences, reverse=True)
        assert confidences[0] == 0.99
        assert confidences[-1] == 0.5

    @pytest.mark.asyncio
    async def test_both_direct_and_prerequisite(self, client, fake_db):
        """Endpoint can have both direct and prerequisite suggestions."""
        ep = _make_endpoint(id=1, method="GET", path="/main")
        ep_target = _make_endpoint(id=2, method="GET", path="/target")
        ep_source = _make_endpoint(id=3, method="GET", path="/source")

        fwd_rel = _make_relation(id=10, source_endpoint_id=1, target_endpoint_id=2, confidence="0.9")
        rev_rel = _make_relation(id=20, source_endpoint_id=3, target_endpoint_id=1, confidence="0.8")

        fake_db.register_get(ApiEndpoint, 1, ep)
        fake_db.register_get(ApiEndpoint, 2, ep_target)
        fake_db.register_get(ApiEndpoint, 3, ep_source)

        fake_db.set_execute_result(make_result(scalars=[fwd_rel]))
        fake_db.set_execute_result(make_result(scalars=[rev_rel]))

        resp = await client.get("/api/relations/relations/1/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        types = {s["type"] for s in data}
        assert "direct_relation" in types
        assert "prerequisite" in types

    @pytest.mark.asyncio
    async def test_relation_target_deleted_is_skipped(self, client, fake_db):
        """If a relation's target endpoint no longer exists, it is skipped."""
        ep = _make_endpoint(id=1)
        rel = _make_relation(id=10, source_endpoint_id=1, target_endpoint_id=999)

        fake_db.register_get(ApiEndpoint, 1, ep)
        # target 999 is NOT registered -> db.get returns None

        fake_db.set_execute_result(make_result(scalars=[rel]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/relations/1/suggestions")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_field_mapping_missing_target_field_key(self, client, fake_db):
        """Field mapping without 'target_field' uses 'related' as fallback in reason."""
        ep = _make_endpoint(id=1, method="GET", path="/a")
        ep2 = _make_endpoint(id=2, method="GET", path="/b")
        rel = _make_relation(
            id=1,
            source_endpoint_id=1,
            target_endpoint_id=2,
            field_mapping={"source_field": "x"},  # no target_field
            confidence="0.8",
        )

        fake_db.register_get(ApiEndpoint, 1, ep)
        fake_db.register_get(ApiEndpoint, 2, ep2)
        fake_db.set_execute_result(make_result(scalars=[rel]))
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.get("/api/relations/relations/1/suggestions")
        data = resp.json()
        assert len(data) == 1
        assert "related" in data[0]["reason"]


# ---------------------------------------------------------------------------
# POST /api/relations/relations/analyze
# ---------------------------------------------------------------------------


class TestAnalyzeRelations:

    @pytest.mark.asyncio
    async def test_happy_path_counts_id_fields(self, client, fake_db):
        """Endpoints with _id or id fields in response schema are counted."""
        ep1 = _make_endpoint(
            id=1,
            response_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "user_id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
        )
        ep2 = _make_endpoint(
            id=2,
            response_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "total": {"type": "number"},
                },
            },
        )
        fake_db.set_execute_result(make_result(scalars=[ep1, ep2]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 2
        # ep1: "id" and "user_id" => 2, ep2: "order_id" => 1
        assert data["discovered_relations"] == 3
        assert "Analyzed 2 endpoints" in data["message"]

    @pytest.mark.asyncio
    async def test_no_endpoints(self, client, fake_db):
        """No endpoints in DB -> zero analyzed and zero discovered."""
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 0
        assert data["discovered_relations"] == 0

    @pytest.mark.asyncio
    async def test_endpoints_without_response_schema(self, client, fake_db):
        """Endpoints with no response_schema are skipped."""
        ep = _make_endpoint(id=1, response_schema=None)
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 1
        assert data["discovered_relations"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_source_ids(self, client, fake_db):
        """source_ids query body filters which endpoints are analyzed."""
        ep = _make_endpoint(
            id=1,
            swagger_source_id=7,
            response_schema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
            },
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.post(
            "/api/relations/relations/analyze",
            params={"source_ids": [7]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 1
        assert data["discovered_relations"] == 1

    @pytest.mark.asyncio
    async def test_nested_id_fields_are_counted(self, client, fake_db):
        """Nested ID fields (e.g., address.zip_id) are also found."""
        ep = _make_endpoint(
            id=1,
            response_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "object",
                        "properties": {
                            "city_id": {"type": "integer"},
                            "street": {"type": "string"},
                        },
                    },
                },
            },
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        # "address" (no _id), "address.city_id" (ends with _id) => 1
        assert data["discovered_relations"] == 1

    @pytest.mark.asyncio
    async def test_response_schema_with_no_id_fields(self, client, fake_db):
        """Response schema without any id-like fields discovers nothing."""
        ep = _make_endpoint(
            id=1,
            response_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                },
            },
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 1
        assert data["discovered_relations"] == 0

    @pytest.mark.asyncio
    async def test_analyze_empty_source_ids_list(self, client, fake_db):
        """Empty source_ids list should still work (no filtering)."""
        fake_db.set_execute_result(make_result(scalars=[]))

        resp = await client.post(
            "/api/relations/relations/analyze",
            params={"source_ids": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed_endpoints"] == 0

    @pytest.mark.asyncio
    async def test_array_items_with_id_fields(self, client, fake_db):
        """ID fields inside array items are also discovered."""
        ep = _make_endpoint(
            id=1,
            response_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "integer"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                },
            },
        )
        fake_db.set_execute_result(make_result(scalars=[ep]))

        resp = await client.post("/api/relations/relations/analyze")
        assert resp.status_code == 200
        data = resp.json()
        # "items" (no _id), "items[].product_id" (ends with _id), "items[].label" (no) => 1
        assert data["discovered_relations"] == 1
