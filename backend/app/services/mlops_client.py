"""HTTP client for communication with the MLOps service."""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MLOpsClient:
    """Async HTTP client for the MLOps orchestration service."""

    def __init__(self) -> None:
        self._base_url = settings.mlops_base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout=120.0, connect=10.0)

    async def translate(self, query: str) -> str:
        """Translate a query to English for RAG search.

        Returns the original query unchanged if it is already English
        or if translation fails.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/translate",
                    json={"query": query},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("translated", query)
        except Exception as exc:
            logger.warning("Translation request failed, using original: %s", exc)
            return query

    async def get_embedding(self, text: str) -> list[float] | None:
        """Request an embedding vector for the given text."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/embeddings",
                json={"texts": [text]},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if embeddings and isinstance(embeddings, list) and len(embeddings) > 0:
                return embeddings[0]
            logger.warning("MLOps returned unexpected embedding format: %s", data)
            return None

    async def orchestrate(
        self,
        query: str,
        endpoints: list[dict[str, Any]],
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Send a query and relevant endpoints to the MLOps orchestrator."""
        payload: dict[str, Any] = {
            "query": query,
            "endpoints": endpoints,
        }
        if base_url:
            payload["context"] = {"base_url": base_url}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/orchestrate",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def orchestrate_stream(
        self,
        query: str,
        endpoints: list[dict[str, Any]],
        base_url: str | None = None,
        history: list[dict] | None = None,
        swagger_source_ids: list[int] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream orchestration events from the MLOps service via SSE.

        Parses SSE format (event: + data:) and yields dicts with
        'event_type' key added for the consumer to dispatch on.
        """
        payload: dict[str, Any] = {
            "query": query,
            "endpoints": endpoints,
        }
        if swagger_source_ids is not None:
            payload["swagger_source_ids"] = swagger_source_ids
        ctx: dict[str, Any] = {}
        if base_url:
            ctx["base_url"] = base_url
        if history:
            ctx["history"] = history
        if ctx:
            payload["context"] = ctx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/orchestrate/stream",
                json=payload,
            ) as response:
                response.raise_for_status()
                current_event = "message"
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            try:
                                parsed = json.loads(data_str)
                                parsed["event_type"] = current_event
                                yield parsed
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse SSE data: %s", data_str[:200])
                            current_event = "message"
