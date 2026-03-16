"""Tests for the 3 remaining architectural improvements:
1. $ref resolution in swagger parser
2. RAG pre-filtering in orchestration
3. Deduplication on upload
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import ApiEndpoint, SwaggerSource
from app.services.swagger_parser import SwaggerParser
from tests.conftest import FakeAsyncSession, make_result


# -----------------------------------------------------------------------
# 1. $ref resolution
# -----------------------------------------------------------------------

class TestRefResolution:
    """SwaggerParser must resolve $ref pointers to actual schemas."""

    def test_simple_ref_resolved(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {
                "/pets": {
                    "get": {
                        "summary": "List pets",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Pet"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    }
                }
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        assert len(endpoints) == 1
        # The response_schema should be the resolved Pet, not {"$ref": "..."}
        rs = endpoints[0].response_schema
        assert rs is not None
        assert "$ref" not in str(rs)
        assert rs["type"] == "object"
        assert "id" in rs["properties"]

    def test_nested_ref_resolved(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {
                "/orders": {
                    "post": {
                        "summary": "Create order",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Order"}
                                }
                            }
                        },
                        "responses": {"201": {"description": "Created"}},
                    }
                }
            },
            "components": {
                "schemas": {
                    "Order": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "item": {"$ref": "#/components/schemas/Item"},
                        },
                    },
                    "Item": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                }
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        rb = endpoints[0].request_body
        assert rb is not None
        assert "$ref" not in json.dumps(rb)
        # Nested Item should be resolved
        assert rb["properties"]["item"]["type"] == "object"
        assert "name" in rb["properties"]["item"]["properties"]

    def test_circular_ref_handled(self):
        """Circular $ref should not cause infinite recursion."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {
                "/nodes": {
                    "get": {
                        "summary": "Tree",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Node"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "children": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Node"},
                            },
                        },
                    }
                }
            },
        }
        parser = SwaggerParser()
        # Must not raise RecursionError
        endpoints = parser.parse(spec)
        assert len(endpoints) == 1

    def test_unresolvable_ref_left_asis(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {
                "/x": {
                    "get": {
                        "summary": "X",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/NonExistent"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        # Should not crash
        assert len(endpoints) == 1

    def test_swagger2_definitions_resolved(self):
        spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1"},
            "host": "api.test.com",
            "paths": {
                "/items": {
                    "get": {
                        "summary": "List",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "schema": {"$ref": "#/definitions/Item"},
                            }
                        },
                    }
                }
            },
            "definitions": {
                "Item": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                },
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        rs = endpoints[0].response_schema
        assert rs is not None
        assert rs["type"] == "object"
        assert "$ref" not in str(rs)

    def test_ref_in_parameters_resolved(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {
                "/items": {
                    "get": {
                        "summary": "List",
                        "parameters": [{"$ref": "#/components/parameters/LimitParam"}],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
            "components": {
                "parameters": {
                    "LimitParam": {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    }
                }
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        assert len(endpoints) == 1
        names = [p["name"] for p in endpoints[0].parameters]
        assert "limit" in names


# -----------------------------------------------------------------------
# 2. RAG pre-filtering in orchestration
# -----------------------------------------------------------------------

class TestRagPreFiltering:
    """When endpoints exceed threshold, orchestration should use RAG."""

    @pytest.mark.asyncio
    async def test_rag_used_when_above_threshold(self):
        from app.services.orchestration import OrchestrationService, OrchestrationContext

        fake_db = FakeAsyncSession()
        now = datetime.now(timezone.utc)

        # Create 60 endpoints (above default threshold of 50)
        many_eps = [
            ApiEndpoint(
                id=i, swagger_source_id=1, method="GET", path=f"/ep{i}",
                summary=f"Endpoint {i}", description=None,
                parameters=None, request_body=None, response_schema=None,
                created_at=now,
            )
            for i in range(1, 61)
        ]
        src = SwaggerSource(
            id=1, name="BigAPI", raw_json="{}", base_url="https://big.api",
            created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=many_eps))
        fake_db.register_get(SwaggerSource, 1, src)

        # RAG should return only 5 relevant endpoints
        rag_results = [many_eps[0], many_eps[10], many_eps[20], many_eps[30], many_eps[40]]

        mock_mlops = MagicMock()
        mock_mlops.get_embedding = AsyncMock(return_value=[0.1] * 384)

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)

        with patch("app.services.orchestration.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.search = AsyncMock(return_value=rag_results)

            ctx = OrchestrationContext(query="find users")
            payload, _ = await service._fetch_endpoints(ctx)

        # Should have filtered down from 60 to 5
        assert len(payload) == 5

    @pytest.mark.asyncio
    async def test_no_rag_when_below_threshold(self):
        from app.services.orchestration import OrchestrationService, OrchestrationContext

        fake_db = FakeAsyncSession()
        now = datetime.now(timezone.utc)

        # 10 endpoints — below threshold
        few_eps = [
            ApiEndpoint(
                id=i, swagger_source_id=1, method="GET", path=f"/ep{i}",
                summary=f"Endpoint {i}", description=None,
                parameters=None, request_body=None, response_schema=None,
                created_at=now,
            )
            for i in range(1, 11)
        ]
        src = SwaggerSource(
            id=1, name="SmallAPI", raw_json="{}", base_url="https://small.api",
            created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=few_eps))
        fake_db.register_get(SwaggerSource, 1, src)

        service = OrchestrationService(fake_db)

        with patch("app.services.orchestration.RAGService") as MockRAG:
            ctx = OrchestrationContext(query="test")
            payload, _ = await service._fetch_endpoints(ctx)

            # RAG should NOT be called
            MockRAG.assert_not_called()

        assert len(payload) == 10

    @pytest.mark.asyncio
    async def test_rag_failure_falls_back_to_all(self):
        from app.services.orchestration import OrchestrationService, OrchestrationContext

        fake_db = FakeAsyncSession()
        now = datetime.now(timezone.utc)

        many_eps = [
            ApiEndpoint(
                id=i, swagger_source_id=1, method="GET", path=f"/ep{i}",
                summary=f"Endpoint {i}", description=None,
                parameters=None, request_body=None, response_schema=None,
                created_at=now,
            )
            for i in range(1, 61)
        ]
        src = SwaggerSource(
            id=1, name="BigAPI", raw_json="{}", base_url="https://big.api",
            created_at=now,
        )
        fake_db.set_execute_result(make_result(scalars=many_eps))
        fake_db.register_get(SwaggerSource, 1, src)

        mock_mlops = MagicMock()

        service = OrchestrationService(fake_db, mlops_client=mock_mlops)

        with patch("app.services.orchestration.RAGService") as MockRAG:
            instance = MockRAG.return_value
            # RAG returns empty — should fallback to all endpoints
            instance.search = AsyncMock(return_value=[])

            ctx = OrchestrationContext(query="test")
            payload, _ = await service._fetch_endpoints(ctx)

        assert len(payload) == 60


# -----------------------------------------------------------------------
# 3. Deduplication on upload
# -----------------------------------------------------------------------

class TestDeduplication:
    """Uploading the same spec twice should be rejected."""

    @pytest.mark.asyncio
    async def test_duplicate_upload_409(self, client, fake_db):
        from tests.conftest import PETSTORE_OPENAPI3

        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        # First upload — simulate existing source found
        now = datetime.now(timezone.utc)
        existing = SwaggerSource(
            id=1, name="Petstore", raw_json="{}", base_url="https://petstore.example.com/v1",
            created_at=now,
        )

        with patch("app.api.swagger.RAGService"):
            # Mock the dedup query to return existing
            fake_db.set_execute_result(make_result(scalars=[existing]))

            resp = await client.post(
                "/api/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )

        assert resp.status_code == 409
        assert "already uploaded" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_non_duplicate_upload_succeeds(self, client, fake_db):
        from tests.conftest import PETSTORE_OPENAPI3

        spec_bytes = json.dumps(PETSTORE_OPENAPI3).encode()

        with patch("app.api.swagger.RAGService") as MockRAG:
            instance = MockRAG.return_value
            instance.index_endpoints = AsyncMock(return_value=4)

            # No existing source — dedup query returns empty
            fake_db.set_execute_result(make_result(scalars=[]))

            resp = await client.post(
                "/api/swagger/upload",
                files={"file": ("petstore.json", io.BytesIO(spec_bytes), "application/json")},
            )

        assert resp.status_code == 200
        assert resp.json()["endpoints_count"] == 4
