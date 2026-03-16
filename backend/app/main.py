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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/sandbox/files/{session_id}/{filename}")
async def proxy_sandbox_file(session_id: str, filename: str):
    """Proxy sandbox files from MLOps service."""
    import httpx
    from fastapi import HTTPException
    from fastapi.responses import Response
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://mlops:8001/api/sandbox/files/{session_id}/{filename}")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code)
        return Response(
            content=resp.content,
            media_type=resp.headers.get("content-type", "application/octet-stream"),
        )
