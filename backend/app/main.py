import logging
import time as _time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.db.session import engine
from app.db.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Ensure new columns exist on tables that were created before this migration
        try:
            await conn.execute(
                text("ALTER TABLE swagger_sources ADD COLUMN IF NOT EXISTS base_url VARCHAR(2048)")
            )
        except Exception:
            pass  # Column already exists or DB does not support IF NOT EXISTS
    logger.info("Database tables initialized")
    yield
    await engine.dispose()


app = FastAPI(
    title="Prod Copilot",
    description="Universal API endpoint discovery and orchestration tool",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request, call_next):
    # Generate or propagate trace ID
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())[:8]
    request.state.trace_id = trace_id

    start = _time.monotonic()
    response = await call_next(request)
    duration_ms = (_time.monotonic() - start) * 1000

    # Add trace ID to response
    response.headers["X-Trace-Id"] = trace_id

    path = request.url.path
    if path not in ("/health", "/metrics"):
        logger.info(
            "[%s] %s %s → %d (%.1fms)",
            trace_id, request.method, path, response.status_code, duration_ms,
            extra={"trace_id": trace_id, "method": request.method, "path": path, "status": response.status_code, "duration_ms": round(duration_ms, 1)},
        )

    return response

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Check health of the service and its dependencies (DB, MLOps)."""
    import httpx
    from starlette.responses import JSONResponse
    from app.config import settings
    from app.db.session import async_session_factory

    db_status = "error"
    mlops_status = "error"

    # Check DB
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.warning("Health check: DB unreachable: %s", exc)

    # Check MLOps
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.mlops_base_url}/health")
            if resp.status_code == 200:
                mlops_status = "ok"
    except Exception as exc:
        logger.warning("Health check: MLOps unreachable: %s", exc)

    if db_status == "ok" and mlops_status == "ok":
        overall = "ok"
    elif db_status == "error" and mlops_status == "error":
        overall = "error"
    else:
        overall = "degraded"

    status_code = 503 if overall == "error" else 200

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "db": db_status,
            "mlops": mlops_status,
            "version": "1.0.0",
        },
    )


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    from starlette.responses import Response
    from app.db.session import async_session_factory
    from sqlalchemy import select, func
    from app.db.models import ScenarioRun, ApiEndpoint, SwaggerSource, ActionConfirmation

    lines = []

    try:
        async with async_session_factory() as session:
            # Count scenarios by status
            for status in ["running", "completed", "error", "cancelled"]:
                result = await session.execute(
                    select(func.count()).select_from(ScenarioRun).where(ScenarioRun.status == status)
                )
                count = result.scalar() or 0
                lines.append(f'scenarios_total{{status="{status}"}} {count}')

            # Count endpoints
            result = await session.execute(select(func.count()).select_from(ApiEndpoint))
            lines.append(f'api_endpoints_total {result.scalar() or 0}')

            # Count swagger sources
            result = await session.execute(select(func.count()).select_from(SwaggerSource))
            lines.append(f'swagger_sources_total {result.scalar() or 0}')

            # Count confirmations by status
            for status in ["pending", "approved", "rejected"]:
                result = await session.execute(
                    select(func.count()).select_from(ActionConfirmation).where(ActionConfirmation.status == status)
                )
                count = result.scalar() or 0
                lines.append(f'confirmations_total{{status="{status}"}} {count}')
    except Exception as e:
        lines.append(f'# Error collecting metrics: {e}')

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/sandbox/files/{session_id}/{filename}")
async def proxy_sandbox_file(session_id: str, filename: str):
    """Proxy sandbox files from MLOps service."""
    import re
    import httpx
    from fastapi import HTTPException
    from fastapi.responses import Response

    # Prevent path traversal: only allow safe characters in both params
    safe_pattern = re.compile(r"^[a-zA-Z0-9._-]+$")
    if not safe_pattern.match(session_id) or not safe_pattern.match(filename):
        raise HTTPException(status_code=400, detail="Invalid session_id or filename.")

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://mlops:8001/api/sandbox/files/{session_id}/{filename}")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code)
        return Response(
            content=resp.content,
            media_type=resp.headers.get("content-type", "application/octet-stream"),
        )
