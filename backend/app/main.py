import logging
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

app.include_router(api_router, prefix="/api")


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
