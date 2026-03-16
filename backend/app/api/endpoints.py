import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiEndpoint, SwaggerSource
from app.db.session import get_db
from app.schemas.models import EndpointSearchResult
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list", response_model=list[EndpointSearchResult])
async def list_endpoints(
    swagger_source_id: Optional[int] = Query(None, description="Filter by swagger source"),
    method: Optional[str] = Query(None, description="Filter by HTTP method (GET, POST, etc.)"),
    path_contains: Optional[str] = Query(None, description="Filter by path substring"),
    search: Optional[str] = Query(None, description="Text search in summary and description"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    has_parameters: Optional[bool] = Query(None, description="Filter endpoints that accept parameters"),
    has_request_body: Optional[bool] = Query(None, description="Filter endpoints with request body"),
    db: AsyncSession = Depends(get_db),
) -> list[EndpointSearchResult]:
    """List ALL indexed endpoints with optional filters.

    Supports filtering by source, method, path substring, text search,
    parameters presence, and request body presence.
    """
    stmt = select(ApiEndpoint).join(
        SwaggerSource, ApiEndpoint.swagger_source_id == SwaggerSource.id
    ).where(SwaggerSource.base_url.isnot(None))

    if swagger_source_id:
        stmt = stmt.where(ApiEndpoint.swagger_source_id == swagger_source_id)
    if method:
        stmt = stmt.where(ApiEndpoint.method == method.upper())
    if path_contains:
        stmt = stmt.where(ApiEndpoint.path.ilike(f"%{path_contains}%"))
    if search:
        stmt = stmt.where(
            ApiEndpoint.summary.ilike(f"%{search}%")
            | ApiEndpoint.description.ilike(f"%{search}%")
        )
    if has_parameters is True:
        stmt = stmt.where(ApiEndpoint.parameters.isnot(None))
    if has_request_body is True:
        stmt = stmt.where(ApiEndpoint.request_body.isnot(None))

    stmt = stmt.order_by(ApiEndpoint.swagger_source_id, ApiEndpoint.id)
    result = await db.execute(stmt)
    endpoints = result.scalars().all()

    return [
        EndpointSearchResult(
            id=ep.id,
            swagger_source_id=ep.swagger_source_id,
            method=ep.method,
            path=ep.path,
            summary=ep.summary,
            description=ep.description,
            parameters=ep.parameters,
            request_body=ep.request_body,
            response_schema=ep.response_schema,
        )
        for ep in endpoints
    ]


@router.get("/stats")
async def endpoint_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get statistics: count by method, count by source, total count."""
    total = await db.scalar(select(func.count(ApiEndpoint.id)))

    method_result = await db.execute(
        select(ApiEndpoint.method, func.count(ApiEndpoint.id))
        .group_by(ApiEndpoint.method)
    )
    by_method = {r[0]: r[1] for r in method_result}

    source_result = await db.execute(
        select(SwaggerSource.name, func.count(ApiEndpoint.id))
        .join(SwaggerSource, ApiEndpoint.swagger_source_id == SwaggerSource.id)
        .group_by(SwaggerSource.name)
    )
    by_source = {r[0]: r[1] for r in source_result}

    return {
        "total": total or 0,
        "by_method": by_method,
        "by_source": by_source,
    }


@router.get("/methods")
async def list_methods(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """List unique HTTP methods across all indexed endpoints."""
    result = await db.execute(select(ApiEndpoint.method).distinct())
    return [r[0] for r in result]


@router.get("/paths")
async def list_paths(
    swagger_source_id: Optional[int] = Query(None, description="Filter by swagger source"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all unique paths with their method and summary."""
    stmt = select(ApiEndpoint.method, ApiEndpoint.path, ApiEndpoint.summary)
    if swagger_source_id:
        stmt = stmt.where(ApiEndpoint.swagger_source_id == swagger_source_id)
    result = await db.execute(stmt.order_by(ApiEndpoint.path))
    return [{"method": r[0], "path": r[1], "summary": r[2]} for r in result]


@router.get("/search", response_model=list[EndpointSearchResult])
async def search_endpoints(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db),
) -> list[EndpointSearchResult]:
    """Semantic search over indexed API endpoints."""
    rag_service = RAGService(db)
    results = await rag_service.search(query=q, limit=limit)

    return [
        EndpointSearchResult(
            id=ep.id,
            swagger_source_id=ep.swagger_source_id,
            method=ep.method,
            path=ep.path,
            summary=ep.summary,
            description=ep.description,
            parameters=ep.parameters,
            request_body=ep.request_body,
            response_schema=ep.response_schema,
        )
        for ep in results
    ]


@router.get("/{endpoint_id}", response_model=EndpointSearchResult)
async def get_endpoint(
    endpoint_id: int,
    db: AsyncSession = Depends(get_db),
) -> EndpointSearchResult:
    """Get a single endpoint by ID."""
    ep = await db.get(ApiEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found.")
    return EndpointSearchResult(
        id=ep.id,
        swagger_source_id=ep.swagger_source_id,
        method=ep.method,
        path=ep.path,
        summary=ep.summary,
        description=ep.description,
        parameters=ep.parameters,
        request_body=ep.request_body,
        response_schema=ep.response_schema,
    )
