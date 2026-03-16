"""RAG service for storing and searching API endpoints using pgvector."""

import logging
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiEndpoint
from app.services.mlops_client import MLOpsClient
from app.services.swagger_parser import ParsedEndpoint

logger = logging.getLogger(__name__)


class RAGService:
    """Manages embedding generation and vector similarity search for
    API endpoints stored in PostgreSQL with pgvector."""

    def __init__(self, db: AsyncSession, mlops_client: MLOpsClient | None = None) -> None:
        self._db = db
        self._mlops = mlops_client or MLOpsClient()

    async def index_endpoints(
        self,
        swagger_source_id: int,
        parsed_endpoints: list[ParsedEndpoint],
    ) -> int:
        """Generate embeddings for each parsed endpoint and store them in the
        database. Returns the number of endpoints successfully indexed."""
        created = 0

        for ep in parsed_endpoints:
            text_for_embedding = self._build_embedding_text(ep)

            try:
                embedding = await self._mlops.get_embedding(text_for_embedding)
            except Exception as exc:
                logger.warning(
                    "Failed to get embedding for %s %s: %s",
                    ep.method,
                    ep.path,
                    exc,
                )
                embedding = None

            db_endpoint = ApiEndpoint(
                swagger_source_id=swagger_source_id,
                method=ep.method,
                path=ep.path,
                summary=ep.summary,
                description=ep.description,
                parameters=ep.parameters if ep.parameters else None,
                request_body=ep.request_body,
                response_schema=ep.response_schema,
                embedding=embedding,
            )
            self._db.add(db_endpoint)
            created += 1

        await self._db.flush()
        logger.info(
            "Indexed %d endpoints for swagger source %d.",
            created,
            swagger_source_id,
        )
        return created

    async def search(
        self,
        query: str,
        limit: int = 10,
        swagger_source_ids: list[int] | None = None,
    ) -> Sequence[ApiEndpoint]:
        """Perform semantic search against indexed API endpoints.

        1. Get an embedding for the query text via the MLOps service.
        2. Run a pgvector cosine similarity query.
        3. Optionally filter by swagger source ids.
        """
        try:
            query_embedding = await self._mlops.get_embedding(query)
        except Exception as exc:
            logger.error("Failed to get query embedding: %s", exc)
            # Fallback: return empty results rather than crashing
            return []

        if query_embedding is None:
            return []

        # Build the query using pgvector's <=> cosine distance operator.
        # The embedding is passed as a bound parameter to avoid SQL injection.
        embedding_literal = f"[{','.join(str(float(v)) for v in query_embedding)}]"

        if swagger_source_ids:
            # Validate that all IDs are integers to prevent injection
            safe_ids = [int(sid) for sid in swagger_source_ids]
            placeholders = ",".join(f":sid_{i}" for i in range(len(safe_ids)))
            bind_params: dict[str, int | str] = {f"sid_{i}": sid for i, sid in enumerate(safe_ids)}
            bind_params["limit"] = limit
            bind_params["embedding"] = embedding_literal
            stmt = text(
                f"""
                SELECT id, swagger_source_id, method, path, summary, description,
                       parameters, request_body, response_schema, embedding, created_at
                FROM api_endpoints
                WHERE swagger_source_id IN ({placeholders})
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :embedding ::vector
                LIMIT :limit
                """
            ).bindparams(**bind_params)
        else:
            stmt = text(
                """
                SELECT id, swagger_source_id, method, path, summary, description,
                       parameters, request_body, response_schema, embedding, created_at
                FROM api_endpoints
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :embedding ::vector
                LIMIT :limit
                """
            ).bindparams(embedding=embedding_literal, limit=limit)

        result = await self._db.execute(stmt)
        rows = result.fetchall()

        # Map raw rows back to ApiEndpoint instances
        endpoints: list[ApiEndpoint] = []
        for row in rows:
            ep = ApiEndpoint(
                id=row.id,
                swagger_source_id=row.swagger_source_id,
                method=row.method,
                path=row.path,
                summary=row.summary,
                description=row.description,
                parameters=row.parameters,
                request_body=row.request_body,
                response_schema=row.response_schema,
                embedding=row.embedding,
                created_at=row.created_at,
            )
            endpoints.append(ep)

        return endpoints

    @staticmethod
    def _build_embedding_text(ep: ParsedEndpoint) -> str:
        """Construct a natural language description of an endpoint to use for
        generating its embedding vector."""
        parts = [f"{ep.method} {ep.path}"]
        if ep.summary:
            parts.append(ep.summary)
        if ep.description:
            parts.append(ep.description)
        if ep.parameters:
            param_names = [p.get("name", "") for p in ep.parameters if p.get("name")]
            if param_names:
                parts.append(f"Parameters: {', '.join(param_names)}")
        return " | ".join(parts)
