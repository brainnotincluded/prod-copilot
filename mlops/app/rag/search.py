"""Semantic search over API endpoints using pgvector."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.rag.embeddings import build_endpoint_text, get_embedding, get_embeddings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def _get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ensure_table() -> None:
    """Create the endpoint_embeddings table and pgvector extension if they don't exist."""
    settings = get_settings()
    dim = settings.rag_embedding_dimension

    async with get_session() as session:
        await session.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.execute(
            sa_text(f"""
                CREATE TABLE IF NOT EXISTS endpoint_embeddings (
                    id SERIAL PRIMARY KEY,
                    swagger_source_id INTEGER NOT NULL,
                    endpoint_data JSONB NOT NULL,
                    endpoint_text TEXT NOT NULL,
                    embedding vector({dim}) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
        )
        # Create an index for cosine similarity search (HNSW works on empty tables)
        await session.execute(
            sa_text("""
                CREATE INDEX IF NOT EXISTS idx_endpoint_embeddings_cosine
                ON endpoint_embeddings
                USING hnsw (embedding vector_cosine_ops)
            """)
        )
        # Index on swagger_source_id for filtering
        await session.execute(
            sa_text("""
                CREATE INDEX IF NOT EXISTS idx_endpoint_embeddings_source_id
                ON endpoint_embeddings (swagger_source_id)
            """)
        )


async def index_endpoints(swagger_source_id: int, endpoints: list[dict]) -> int:
    """Generate embeddings for endpoint descriptions and store them in pgvector.

    Args:
        swagger_source_id: The ID of the swagger source these endpoints belong to.
        endpoints: List of endpoint definition dicts.

    Returns:
        The number of endpoints successfully indexed.

    Raises:
        ValueError: If endpoints list is empty.
    """
    if not endpoints:
        raise ValueError("Endpoints list must not be empty")

    await ensure_table()

    # Build text representations
    texts: list[str] = []
    valid_endpoints: list[dict] = []
    for ep in endpoints:
        ep_text = build_endpoint_text(ep)
        if ep_text:
            texts.append(ep_text)
            valid_endpoints.append(ep)
        else:
            logger.warning("Skipping endpoint with empty text representation: %s", ep)

    if not texts:
        raise ValueError("No valid endpoints to index after text extraction")

    # Generate embeddings in batch
    embeddings = get_embeddings(texts)

    # Delete existing embeddings for this swagger source (upsert behavior)
    async with get_session() as session:
        await session.execute(
            sa_text(
                "DELETE FROM endpoint_embeddings WHERE swagger_source_id = :source_id"
            ),
            {"source_id": swagger_source_id},
        )

        # Insert new embeddings
        for ep, ep_text, emb in zip(valid_endpoints, texts, embeddings):
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            await session.execute(
                sa_text("""
                    INSERT INTO endpoint_embeddings
                        (swagger_source_id, endpoint_data, endpoint_text, embedding)
                    VALUES
                        (:source_id, :endpoint_data, :endpoint_text, :embedding::vector)
                """),
                {
                    "source_id": swagger_source_id,
                    "endpoint_data": json.dumps(ep),
                    "endpoint_text": ep_text,
                    "embedding": emb_str,
                },
            )

    logger.info(
        "Indexed %d endpoints for swagger source %d",
        len(valid_endpoints),
        swagger_source_id,
    )
    return len(valid_endpoints)


async def search_endpoints(
    query: str,
    swagger_source_ids: list[int] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Perform semantic search to find endpoints similar to the query.

    Args:
        query: Natural language search query.
        swagger_source_ids: Optional list of swagger source IDs to filter by.
        limit: Maximum number of results to return.

    Returns:
        List of dicts with 'endpoint' and 'score' keys, sorted by similarity.

    Raises:
        ValueError: If query is empty.
    """
    if not query or not query.strip():
        raise ValueError("Search query must not be empty")

    await ensure_table()

    # Embed the query
    query_embedding = get_embedding(query.strip())
    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Build the SQL query
    if swagger_source_ids:
        placeholders = ", ".join(str(sid) for sid in swagger_source_ids)
        filter_clause = f"WHERE swagger_source_id IN ({placeholders})"
    else:
        filter_clause = ""

    sql = f"""
        SELECT
            endpoint_data,
            1 - (embedding <=> '{emb_str}'::vector) AS similarity
        FROM endpoint_embeddings
        {filter_clause}
        ORDER BY embedding <=> '{emb_str}'::vector
        LIMIT :limit
    """

    async with get_session() as session:
        result = await session.execute(
            sa_text(sql),
            {"limit": limit},
        )
        rows = result.fetchall()

    results = []
    for row in rows:
        endpoint_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        score = float(row[1])
        results.append({
            "endpoint": endpoint_data,
            "score": round(score, 6),
        })

    logger.info("Search for '%s' returned %d results", query[:80], len(results))
    return results


async def shutdown() -> None:
    """Dispose of the database engine on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
