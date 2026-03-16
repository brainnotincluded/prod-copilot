"""Shared fixtures for the entire test suite.

All tests run **without** a real PostgreSQL / pgvector / MLOps service.
We override FastAPI dependencies and mock external calls so every test is
fast, deterministic and independent.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Prevent the real engine / session from connecting to Postgres on import.
# We patch *before* importing the app so the module‑level ``engine`` object
# is never used.
# ---------------------------------------------------------------------------

_fake_engine = MagicMock()
_fake_engine.dispose = AsyncMock()
_fake_engine.begin = MagicMock()
_fake_session_factory = MagicMock()


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# A lightweight mock DB session that records add/delete/flush/execute calls.
# ---------------------------------------------------------------------------

class FakeAsyncSession:
    """Mimics ``AsyncSession`` well enough for handler‑level tests."""

    def __init__(self) -> None:
        self.added: list = []
        self.deleted: list = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self._execute_results: list = []
        self._get_store: dict[tuple, object] = {}
        self._scalar_result = None
        self._id_counter = 1

    def add(self, obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = self._id_counter
            self._id_counter += 1
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushed = True
        # Assign IDs to any objects without them
        for obj in self.added:
            if hasattr(obj, "id") and obj.id is None:
                obj.id = self._id_counter
                self._id_counter += 1

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def execute(self, stmt, *args, **kwargs):
        if self._execute_results:
            return self._execute_results.pop(0)
        return _empty_result()

    async def scalar(self, stmt):
        return self._scalar_result

    async def get(self, model_cls, pk):
        return self._get_store.get((model_cls, pk))

    def set_execute_result(self, result):
        self._execute_results.append(result)

    def register_get(self, model_cls, pk, obj):
        self._get_store[(model_cls, pk)] = obj


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    """Wraps a list to behave like SQLAlchemy Result."""

    def __init__(self, rows=None, scalars=None):
        self._rows = rows or []
        self._scalars = scalars or []

    def scalars(self):
        return _FakeScalarResult(self._scalars)

    def scalar_one_or_none(self):
        return self._scalars[0] if self._scalars else None

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


def _empty_result():
    return _FakeResult()


def make_result(*, rows=None, scalars=None):
    """Helper to build a fake SQLAlchemy result."""
    return _FakeResult(rows=rows, scalars=scalars)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture()
def app(fake_db):
    """Create a fresh FastAPI app with the DB dependency overridden."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    from app.db.session import get_db
    from app.main import app as real_app

    # Replace lifespan so it never touches real Postgres
    real_app.router.lifespan_context = _noop_lifespan

    async def _override_get_db() -> AsyncGenerator:
        yield fake_db

    real_app.dependency_overrides[get_db] = _override_get_db
    yield real_app
    real_app.dependency_overrides.clear()


@pytest.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async client wired directly to the ASGI app (no network).

    Default role is admin so all endpoints are accessible in tests.
    Individual test classes override via X-User-Role header.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-User-Role": "admin"},
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

PETSTORE_OPENAPI3 = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "summary": "List all pets",
                "description": "Returns all pets from the store",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Pet"},
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Pet"}
                        }
                    }
                },
                "responses": {"201": {"description": "Pet created"}},
            },
        },
        "/pets/{petId}": {
            "parameters": [
                {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "get": {
                "summary": "Get pet by ID",
                "responses": {
                    "200": {
                        "description": "A pet",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        },
                    }
                },
            },
            "delete": {
                "summary": "Delete a pet",
                "responses": {"204": {"description": "Pet deleted"}},
            },
        },
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

PETSTORE_SWAGGER2 = {
    "swagger": "2.0",
    "info": {"title": "Petstore Swagger2", "version": "1.0"},
    "host": "api.petstore.io",
    "basePath": "/v2",
    "schemes": ["https"],
    "paths": {
        "/pets": {
            "get": {
                "summary": "List pets",
                "parameters": [
                    {"name": "status", "in": "query", "type": "string"}
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {"type": "array", "items": {"type": "object"}},
                    }
                },
            },
            "post": {
                "summary": "Add pet",
                "parameters": [
                    {
                        "name": "body",
                        "in": "body",
                        "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                    }
                ],
                "responses": {"201": {"description": "Created"}},
            },
        }
    },
}

MINIMAL_SPEC_NO_PATHS = {
    "openapi": "3.0.0",
    "info": {"title": "Empty", "version": "0.0.1"},
    "paths": {},
}
