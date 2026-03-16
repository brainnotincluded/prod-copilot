"""API for entity relations and block map — shows how APIs and entities are connected.

This powers the "map of blocks and connections" visual layer.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiEndpoint, EntityRelation, SwaggerSource
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/map")
async def get_entity_map(
    source_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the visual map of entities and their connections.

    Returns nodes (APIs, endpoints, entities) and edges (relations)
    for graph visualization.
    """
    # Build nodes
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Query sources
    source_stmt = select(SwaggerSource)
    if source_id:
        source_stmt = source_stmt.where(SwaggerSource.id == source_id)
    source_result = await db.execute(source_stmt)
    sources = source_result.scalars().all()

    # Add API sources as nodes
    for source in sources:
        nodes.append({
            "id": f"source_{source.id}",
            "type": "api",
            "label": source.name,
            "base_url": source.base_url,
            "data": {"id": source.id, "name": source.name},
        })

    # Query endpoints
    endpoint_stmt = select(ApiEndpoint)
    if source_id:
        endpoint_stmt = endpoint_stmt.where(ApiEndpoint.swagger_source_id == source_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoints = endpoint_result.scalars().all()

    # Add endpoints as nodes
    for ep in endpoints:
        node_id = f"endpoint_{ep.id}"
        nodes.append({
            "id": node_id,
            "type": "endpoint",
            "label": f"{ep.method} {ep.path}",
            "parent": f"source_{ep.swagger_source_id}",
            "data": {
                "id": ep.id,
                "method": ep.method,
                "path": ep.path,
                "summary": ep.summary,
                "has_request_body": ep.request_body is not None,
                "has_response": ep.response_schema is not None,
            },
        })
        # Edge from source to endpoint
        edges.append({
            "id": f"source_{ep.swagger_source_id}_to_{node_id}",
            "from": f"source_{ep.swagger_source_id}",
            "to": node_id,
            "type": "contains",
        })

    # Query discovered relations
    relation_stmt = select(EntityRelation)
    if source_id:
        # Filter relations where at least one endpoint belongs to this source
        relation_stmt = relation_stmt.where(
            (EntityRelation.source_endpoint_id.in_(
                select(ApiEndpoint.id).where(ApiEndpoint.swagger_source_id == source_id)
            )) | (EntityRelation.target_endpoint_id.in_(
                select(ApiEndpoint.id).where(ApiEndpoint.swagger_source_id == source_id)
            ))
        )
    relation_result = await db.execute(relation_stmt)
    relations = relation_result.scalars().all()

    # Add relation edges
    for rel in relations:
        edges.append({
            "id": f"rel_{rel.id}",
            "from": f"endpoint_{rel.source_endpoint_id}",
            "to": f"endpoint_{rel.target_endpoint_id}",
            "type": "relation",
            "relation_type": rel.relation_type,
            "label": _format_field_mapping(rel.field_mapping),
            "confidence": float(rel.confidence),
            "data": {
                "field_mapping": rel.field_mapping,
                "confidence": float(rel.confidence),
            },
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_apis": len([n for n in nodes if n["type"] == "api"]),
            "total_endpoints": len([n for n in nodes if n["type"] == "endpoint"]),
            "total_relations": len(relations),
        },
    }


@router.get("/relations/{endpoint_id}/suggestions")
async def get_connection_suggestions(
    endpoint_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get suggestions for combining this endpoint with others.

    Returns a list of suggested next steps based on:
    - Direct entity relations
    - Common usage patterns
    - Response schema compatibility
    """
    # Get the endpoint
    endpoint = await db.get(ApiEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    suggestions: list[dict[str, Any]] = []

    # Find direct relations where this endpoint is the source
    stmt = select(EntityRelation).where(
        EntityRelation.source_endpoint_id == endpoint_id
    )
    result = await db.execute(stmt)
    relations = result.scalars().all()

    for rel in relations:
        target = await db.get(ApiEndpoint, rel.target_endpoint_id)
        if target:
            suggestions.append({
                "type": "direct_relation",
                "endpoint_id": target.id,
                "endpoint": f"{target.method} {target.path}",
                "reason": f"Uses {rel.field_mapping.get('target_field', 'related')} from this endpoint",
                "field_mapping": rel.field_mapping,
                "confidence": float(rel.confidence),
            })

    # Find reverse relations (where this endpoint is the target)
    reverse_stmt = select(EntityRelation).where(
        EntityRelation.target_endpoint_id == endpoint_id
    )
    reverse_result = await db.execute(reverse_stmt)
    reverse_relations = reverse_result.scalars().all()

    for rel in reverse_relations:
        source = await db.get(ApiEndpoint, rel.source_endpoint_id)
        if source:
            suggestions.append({
                "type": "prerequisite",
                "endpoint_id": source.id,
                "endpoint": f"{source.method} {source.path}",
                "reason": f"Provides {rel.field_mapping.get('source_field', 'data')} needed here",
                "field_mapping": rel.field_mapping,
                "confidence": float(rel.confidence),
            })

    # Sort by confidence
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    return suggestions


@router.post("/relations/analyze")
async def analyze_relations(
    source_ids: list[int] | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger analysis of entity relations across APIs.

    This scans response schemas and request bodies to find potential
    foreign key relationships and data dependencies.
    """
    # Query endpoints to analyze
    stmt = select(ApiEndpoint)
    if source_ids:
        stmt = stmt.where(ApiEndpoint.swagger_source_id.in_(source_ids))
    result = await db.execute(stmt)
    endpoints = result.scalars().all()

    # Simple heuristic: look for common field patterns
    discovered = 0
    for ep in endpoints:
        if not ep.response_schema:
            continue
        # Extract fields from response schema
        fields = _extract_schema_fields(ep.response_schema)
        # Look for ID fields that might be foreign keys elsewhere
        for field in fields:
            if field.endswith("_id") or field == "id":
                # Potential relation found
                # In real implementation, this would use LLM to analyze semantics
                discovered += 1

    return {
        "message": f"Analyzed {len(endpoints)} endpoints, found {discovered} potential relations",
        "discovered_relations": discovered,
        "analyzed_endpoints": len(endpoints),
    }


def _format_field_mapping(mapping: dict[str, str] | None) -> str:
    """Format field mapping for display."""
    if not mapping:
        return "→"
    src = mapping.get("source_field", "?")
    tgt = mapping.get("target_field", "?")
    return f"{src} → {tgt}"


def _extract_schema_fields(schema: Any, prefix: str = "") -> list[str]:
    """Recursively extract field names from JSON schema."""
    fields: list[str] = []
    if not isinstance(schema, dict):
        return fields

    properties = schema.get("properties", {})
    for key, value in properties.items():
        full_key = f"{prefix}.{key}" if prefix else key
        fields.append(full_key)
        # Recurse into nested objects
        if isinstance(value, dict) and value.get("type") == "object":
            fields.extend(_extract_schema_fields(value, full_key))
        # Handle array items
        elif isinstance(value, dict) and value.get("type") == "array":
            items = value.get("items", {})
            if items.get("type") == "object":
                fields.extend(_extract_schema_fields(items, f"{full_key}[]"))

    return fields
