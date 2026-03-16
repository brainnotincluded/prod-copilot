"""MLOps Service: LLM orchestration, RAG embeddings, and MCP server management."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.llm.kimi_client import get_llm_client
from app.llm.prompts import TRANSLATE_PROMPT
from app.rag.embeddings import get_embedding, get_embeddings
from app.rag.search import (
    index_endpoints as rag_index_endpoints,
    search_endpoints as rag_search_endpoints,
    shutdown as rag_shutdown,
)
from app.mcp.api_executor import close_client as close_api_client
from app.orchestrator.planner import create_plan
from app.orchestrator.executor import execute_plan, execute_plan_stream
from app.schemas.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    IndexRequest,
    SearchRequest,
    SearchResponse,
    SearchResult,
    OrchestrationRequest,
    OrchestrationStep,
    ResultResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown handlers."""
    settings = get_settings()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Kimi base URL: %s", settings.kimi_base_url)
    logger.info("Embedding model: %s", settings.rag_embedding_model)

    if not settings.mock_mode:
        logger.info("Preloading embedding model...")
        from app.rag.embeddings import _get_model
        _get_model()  # Trigger lazy load at startup
        logger.info("Embedding model ready")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_api_client()
    await rag_shutdown()
    logger.info("Shutdown complete")


app = FastAPI(
    title="MLOps Service",
    description="LLM orchestration, RAG embeddings, and MCP server management for the universal API copilot.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "mlops"}


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

@app.post("/api/embeddings", response_model=EmbeddingResponse)
async def generate_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """Generate embedding vectors for a list of texts.

    Uses sentence-transformers to produce dense vector representations.
    """
    try:
        embeddings = get_embeddings(request.texts)
        return EmbeddingResponse(embeddings=embeddings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Embedding generation failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")


# ---------------------------------------------------------------------------
# RAG: Index and Search
# ---------------------------------------------------------------------------

@app.post("/api/rag/index")
async def index_endpoint_data(request: IndexRequest) -> dict:
    """Index API endpoint definitions by generating embeddings and storing them in pgvector.

    This replaces any existing embeddings for the given swagger_source_id.
    """
    try:
        count = await rag_index_endpoints(
            swagger_source_id=request.swagger_source_id,
            endpoints=request.endpoints,
        )
        return {
            "status": "ok",
            "indexed": count,
            "swagger_source_id": request.swagger_source_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Indexing failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/api/rag/search", response_model=SearchResponse)
async def search_endpoint_data(request: SearchRequest) -> SearchResponse:
    """Semantic search over indexed API endpoints.

    Embeds the query and performs cosine similarity search against stored endpoint embeddings.
    """
    try:
        results = await rag_search_endpoints(
            query=request.query,
            swagger_source_ids=request.swagger_source_ids,
            limit=request.limit,
        )
        return SearchResponse(
            results=[
                SearchResult(endpoint=r["endpoint"], score=r["score"])
                for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Search failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ---------------------------------------------------------------------------
# Translation (for cross-language RAG search)
# ---------------------------------------------------------------------------

@app.post("/api/translate")
async def translate_query(request: dict) -> dict:
    """Translate a user query to English for RAG embedding search.

    If the query is already ASCII (likely English), returns it unchanged.
    Otherwise uses the LLM to produce a concise English translation.
    """
    query = request.get("query", "")
    if not query or not query.strip():
        return {"translated": query}

    # Skip translation if text is already ASCII (likely English)
    if all(ord(c) < 128 for c in query.replace(" ", "")):
        return {"translated": query}

    try:
        client = get_llm_client()
        messages = [
            {"role": "system", "content": TRANSLATE_PROMPT},
            {"role": "user", "content": query},
        ]
        translated = await client.chat(messages, temperature=0.1, max_tokens=2048)
        result = translated.strip()

        # If LLM returned empty, fall back to original
        if not result or len(result) < 2:
            logger.warning("Translation returned empty, using original query")
            return {"translated": query}

        # Thinking models return chain-of-thought instead of just the answer.
        # If result is too long (>200 chars), extract the last short line as the answer.
        if len(result) > 200:
            logger.info("Translation looks like chain-of-thought, extracting answer")
            # Try to find a short quoted string
            import re
            quotes = re.findall(r'"([^"]{3,80})"', result)
            if quotes:
                # Use the last quoted phrase as the likely answer
                result = quotes[-1]
            else:
                # Take the last non-empty line that's short enough
                lines = [l.strip() for l in result.split("\n") if l.strip() and len(l.strip()) < 100]
                result = lines[-1] if lines else query

        # Final sanity checks
        if len(result) > 150:
            result = result[:150]
        # If result is a single word or too short, likely not a real translation
        if len(result.split()) <= 1 and len(query.split()) > 1:
            logger.warning("Translation too short ('%s'), using original", result)
            return {"translated": query}

        logger.info("Translated '%s' -> '%s'", query[:50], result[:50])
        return {"translated": result}
    except Exception as exc:
        logger.warning("Translation failed, using original query: %s", exc)
        return {"translated": query}


# ---------------------------------------------------------------------------
# Sandbox: serve generated files
# ---------------------------------------------------------------------------

@app.get("/api/sandbox/files/{session_id}/{filename}")
async def serve_sandbox_file(session_id: str, filename: str):
    """Serve a file generated by the code sandbox."""
    import re
    # Validate session_id is UUID
    if not re.match(r'^[0-9a-f-]{36}$', session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")
    # Prevent path traversal
    if '..' in filename or '/' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = f"/tmp/sandbox_output/{session_id}/{filename}"
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@app.post("/api/orchestrate", response_model=ResultResponse)
async def orchestrate(request: OrchestrationRequest) -> ResultResponse:
    """Main orchestration endpoint.

    Takes a natural language query and available API endpoints,
    uses the LLM to plan and execute a multi-step workflow,
    then returns the aggregated result.

    Supports two orchestration modes (set via ORCHESTRATION_MODE env var):
    - "plan": Traditional plan-then-execute flow (default)
    - "agent": LLM-driven tool-calling agent loop
    """
    settings = get_settings()

    try:
        if settings.orchestration_mode == "agent":
            from app.orchestrator.agent_loop import run_agent_loop
            result = await run_agent_loop(
                query=request.query,
                endpoints=request.endpoints,
                context=request.context,
            )
            return result

        # Default: plan-execute flow
        # 1. Create execution plan
        plan = await create_plan(
            query=request.query,
            endpoints=request.endpoints,
            context=request.context,
        )

        # Check if plan contains only error steps
        if all(s.status == "error" for s in plan):
            return ResultResponse(
                type="text",
                data={
                    "message": "Failed to create execution plan",
                    "errors": [s.error or s.description for s in plan],
                },
                metadata={"status": "error"},
            )

        # 2. Execute the plan
        result = await execute_plan(
            plan=plan,
            context=request.context or {},
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Orchestration failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@app.post("/api/orchestrate/stream")
async def orchestrate_stream(request: OrchestrationRequest):
    """Streaming orchestration endpoint (Server-Sent Events).

    Same as /api/orchestrate but streams step-by-step progress events.
    Events:
        - plan: The execution plan
        - step_start: A step is starting
        - step_complete: A step completed
        - step_error: A step failed
        - result: The final result

    Supports both "plan" and "agent" orchestration modes.
    """
    settings = get_settings()

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            if settings.orchestration_mode == "agent":
                from app.orchestrator.agent_loop import run_agent_loop_stream
                async for event in run_agent_loop_stream(
                    query=request.query,
                    endpoints=request.endpoints,
                    context=request.context,
                ):
                    yield {
                        "event": event.event,
                        "data": json.dumps(event.data, default=str, ensure_ascii=False),
                    }
                return

            # Default: plan-execute flow
            # Create plan
            plan = await create_plan(
                query=request.query,
                endpoints=request.endpoints,
                context=request.context,
            )

            # Stream execution events
            async for event in execute_plan_stream(
                plan=plan,
                context=request.context or {},
            ):
                yield {
                    "event": event.event,
                    "data": json.dumps(event.data, default=str, ensure_ascii=False),
                }

        except ValueError as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
        except Exception as e:
            logger.error("Streaming orchestration failed: %s", str(e))
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Orchestration failed: {str(e)}"}),
            }

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler."""
    logger.error("Unhandled exception: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
        },
    )
