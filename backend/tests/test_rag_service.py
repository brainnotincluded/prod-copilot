"""Tests for RAGService — embedding index and search.

All external calls (MLOps, DB) are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.db.models import ApiEndpoint
from app.services.rag_service import RAGService
from app.services.swagger_parser import ParsedEndpoint
from tests.conftest import FakeAsyncSession, make_result


@pytest.fixture()
def fake_db():
    return FakeAsyncSession()


@pytest.fixture()
def rag(fake_db):
    return RAGService(fake_db)


# -----------------------------------------------------------------------
# index_endpoints
# -----------------------------------------------------------------------

class TestIndexEndpoints:

    @pytest.mark.asyncio
    async def test_indexes_all_endpoints(self, rag, fake_db):
        endpoints = [
            ParsedEndpoint(method="GET", path="/users", summary="List users"),
            ParsedEndpoint(method="POST", path="/users", summary="Create user"),
        ]

        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(return_value=[0.1] * 384)

            count = await rag.index_endpoints(swagger_source_id=1, parsed_endpoints=endpoints)

        assert count == 2
        assert len(fake_db.added) == 2
        assert fake_db.flushed is True

        # Verify stored objects
        for obj in fake_db.added:
            assert isinstance(obj, ApiEndpoint)
            assert obj.swagger_source_id == 1
            assert obj.embedding == [0.1] * 384

    @pytest.mark.asyncio
    async def test_embedding_failure_stores_none(self, rag, fake_db):
        """If embedding fails, the endpoint is still stored with embedding=None."""
        endpoints = [
            ParsedEndpoint(method="GET", path="/fail"),
        ]

        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(side_effect=RuntimeError("MLOps down"))

            count = await rag.index_endpoints(swagger_source_id=1, parsed_endpoints=endpoints)

        assert count == 1
        assert fake_db.added[0].embedding is None

    @pytest.mark.asyncio
    async def test_empty_endpoints_list(self, rag, fake_db):
        count = await rag.index_endpoints(swagger_source_id=1, parsed_endpoints=[])
        assert count == 0
        assert len(fake_db.added) == 0


# -----------------------------------------------------------------------
# search
# -----------------------------------------------------------------------

class TestSearch:

    @pytest.mark.asyncio
    async def test_returns_endpoints_on_success(self, rag, fake_db):
        # Mock the embedding call
        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(return_value=[0.5] * 384)

            # Mock the DB execute to return a row
            mock_row = MagicMock()
            mock_row.id = 1
            mock_row.swagger_source_id = 1
            mock_row.method = "GET"
            mock_row.path = "/users"
            mock_row.summary = "List"
            mock_row.description = None
            mock_row.parameters = None
            mock_row.request_body = None
            mock_row.response_schema = None
            mock_row.embedding = [0.5] * 384
            mock_row.created_at = None

            fake_db.set_execute_result(make_result(rows=[mock_row]))

            results = await rag.search(query="find users", limit=5)

        assert len(results) == 1
        assert results[0].method == "GET"
        assert results[0].path == "/users"

    @pytest.mark.asyncio
    async def test_returns_empty_on_embedding_failure(self, rag):
        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(side_effect=RuntimeError("down"))

            results = await rag.search(query="anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_embedding_is_none(self, rag):
        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(return_value=None)

            results = await rag.search(query="anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_source_filter(self, rag, fake_db):
        with patch.object(rag, "_mlops") as mock_mlops:
            mock_mlops.get_embedding = AsyncMock(return_value=[0.1] * 384)
            fake_db.set_execute_result(make_result(rows=[]))

            results = await rag.search(
                query="test", limit=5, swagger_source_ids=[1, 2]
            )

        assert results == []


# -----------------------------------------------------------------------
# _build_embedding_text
# -----------------------------------------------------------------------

class TestBuildEmbeddingText:

    def test_minimal(self):
        ep = ParsedEndpoint(method="GET", path="/x")
        text = RAGService._build_embedding_text(ep)
        assert text == "GET /x"

    def test_with_summary_and_description(self):
        ep = ParsedEndpoint(
            method="POST", path="/users",
            summary="Create user", description="Creates a new user in the system"
        )
        text = RAGService._build_embedding_text(ep)
        assert "POST /users" in text
        assert "Create user" in text
        assert "Creates a new user" in text

    def test_with_parameters(self):
        ep = ParsedEndpoint(
            method="GET", path="/search",
            parameters=[{"name": "q"}, {"name": "limit"}],
        )
        text = RAGService._build_embedding_text(ep)
        assert "Parameters: q, limit" in text

    def test_parameters_without_names_skipped(self):
        ep = ParsedEndpoint(
            method="GET", path="/x",
            parameters=[{"description": "no name"}],
        )
        text = RAGService._build_embedding_text(ep)
        # Should not contain "Parameters:" if no named params
        assert "Parameters" not in text

    def test_all_parts_joined_with_pipe(self):
        ep = ParsedEndpoint(
            method="GET", path="/x", summary="S", description="D",
            parameters=[{"name": "p"}],
        )
        text = RAGService._build_embedding_text(ep)
        parts = text.split(" | ")
        assert len(parts) == 4
