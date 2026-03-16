import json
import logging
from typing import Optional

import httpx
import yaml
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.params import Form
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, Role, require_role
from app.db.models import ApiEndpoint, SwaggerSource
from app.db.session import get_db
from app.schemas.models import EndpointSearchResult, SwaggerSourceResponse, SwaggerUploadResponse
from app.services.rag_service import RAGService
from app.services.swagger_parser import SwaggerParser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=SwaggerUploadResponse)
async def upload_swagger(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role(Role.EDITOR)),
) -> SwaggerUploadResponse:
    """Upload a Swagger/OpenAPI spec from a file (JSON/YAML) or a URL."""
    if file is None and url is None:
        raise HTTPException(
            status_code=400,
            detail="Either a file or a URL must be provided.",
        )

    raw_content: str = ""
    spec_dict: dict = {}

    if file is not None:
        content_bytes = await file.read()
        raw_content = content_bytes.decode("utf-8")
        file_name = file.filename or "unknown"

        try:
            spec_dict = json.loads(raw_content)
        except json.JSONDecodeError:
            try:
                spec_dict = yaml.safe_load(raw_content)
            except yaml.YAMLError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse file as JSON or YAML: {exc}",
                )

        if not isinstance(spec_dict, dict):
            raise HTTPException(
                status_code=400,
                detail="Spec must be a JSON/YAML object (dictionary), not a scalar or array.",
            )

        if name is None:
            name = spec_dict.get("info", {}).get("title", file_name)

    elif url is not None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                raw_content = response.text
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch spec from URL: {exc}",
            )

        try:
            spec_dict = json.loads(raw_content)
        except json.JSONDecodeError:
            try:
                spec_dict = yaml.safe_load(raw_content)
            except yaml.YAMLError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse response as JSON or YAML: {exc}",
                )

        if not isinstance(spec_dict, dict):
            raise HTTPException(
                status_code=400,
                detail="Spec must be a JSON/YAML object (dictionary), not a scalar or array.",
            )

        if name is None:
            name = spec_dict.get("info", {}).get("title", url)

    # Parse the spec into endpoints
    parser = SwaggerParser()
    parsed_endpoints = parser.parse(spec_dict)

    if not parsed_endpoints:
        raise HTTPException(
            status_code=400,
            detail="No endpoints found in the provided spec.",
        )

    # Extract API base URL from the spec
    base_url = SwaggerParser.extract_base_url(spec_dict)

    # Deduplication: check if a source with the same name + base_url already exists
    raw_json_str = json.dumps(spec_dict, ensure_ascii=False, sort_keys=True)

    existing = await db.execute(
        select(SwaggerSource).where(
            SwaggerSource.name == name,
            SwaggerSource.base_url == base_url,
        )
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"API '{name}' with base URL '{base_url}' is already uploaded (id={duplicate.id}). Delete it first to re-upload.",
        )

    # Store the swagger source
    swagger_source = SwaggerSource(
        name=name,
        url=url,
        raw_json=raw_json_str,
        base_url=base_url,
    )
    db.add(swagger_source)
    await db.flush()

    # Index endpoints via RAG service
    rag_service = RAGService(db)
    endpoints_created = await rag_service.index_endpoints(
        swagger_source_id=swagger_source.id,
        parsed_endpoints=parsed_endpoints,
    )

    return SwaggerUploadResponse(
        id=swagger_source.id,
        name=swagger_source.name,
        base_url=swagger_source.base_url,
        endpoints_count=endpoints_created,
        message=f"Successfully parsed and indexed {endpoints_created} endpoints.",
    )


@router.get("/list", response_model=list[SwaggerSourceResponse])
async def list_swagger_sources(
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> list[SwaggerSourceResponse]:
    """List all uploaded Swagger/OpenAPI sources."""
    result = await db.execute(
        select(SwaggerSource).order_by(SwaggerSource.created_at.desc()).offset(offset).limit(limit)
    )
    sources = result.scalars().all()
    return [
        SwaggerSourceResponse(
            id=s.id,
            name=s.name,
            url=s.url,
            base_url=s.base_url,
            created_at=s.created_at,
        )
        for s in sources
    ]


@router.get("/{source_id}/endpoints", response_model=list[EndpointSearchResult])
async def get_source_endpoints(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[EndpointSearchResult]:
    """Get all endpoints for a specific swagger source."""
    source = await db.get(SwaggerSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Swagger source not found.")

    result = await db.execute(
        select(ApiEndpoint)
        .where(ApiEndpoint.swagger_source_id == source_id)
        .order_by(ApiEndpoint.path)
    )
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


@router.get("/{source_id}/stats")
async def get_source_stats(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get statistics for a specific swagger source."""
    source = await db.get(SwaggerSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Swagger source not found.")

    result = await db.execute(
        select(ApiEndpoint.method, func.count(ApiEndpoint.id))
        .where(ApiEndpoint.swagger_source_id == source_id)
        .group_by(ApiEndpoint.method)
    )
    methods = list(result)

    return {
        "id": source.id,
        "name": source.name,
        "base_url": source.base_url,
        "total_endpoints": sum(r[1] for r in methods),
        "by_method": {r[0]: r[1] for r in methods},
    }


@router.delete("/{source_id}")
async def delete_swagger_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Delete a Swagger source and all its endpoints."""
    result = await db.execute(
        select(SwaggerSource).where(SwaggerSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail="Swagger source not found.")

    await db.delete(source)

    return {"message": f"Swagger source '{source.name}' and its endpoints deleted."}
