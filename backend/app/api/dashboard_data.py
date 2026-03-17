"""Proxy endpoint that fetches live data from connected APIs for dashboard rendering.

Aggregates data from multiple API sources so the frontend dashboard
can show KPIs, charts, tables and cards with real business data.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SwaggerSource
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

TIMEOUT = 8.0  # seconds per upstream call


async def _fetch(client: httpx.AsyncClient, url: str) -> Any:
    """Fetch JSON from upstream, return None on failure."""
    try:
        r = await client.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        logger.warning("Dashboard fetch %s failed: %s", url, exc)
    return None


@router.get("/dashboard/live")
async def live_dashboard(
    db: AsyncSession = Depends(get_db),
    source_id: int | None = Query(None, description="Filter by swagger source"),
) -> dict[str, Any]:
    """Fetch live business data from connected APIs for dashboard.

    Discovers base_urls from SwaggerSource records and calls known
    analytics/business endpoints. Returns aggregated data ready for
    KPI cards, charts, tables and entity cards.
    """
    # Find connected API base URLs
    stmt = select(SwaggerSource)
    if source_id:
        stmt = stmt.where(SwaggerSource.id == source_id)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    base_urls: list[str] = []
    for s in sources:
        url = s.base_url
        if url:
            base_urls.append(url.rstrip("/"))

    if not base_urls:
        return {"status": "no_sources", "kpi": {}, "segments": [], "audiences": [], "campaigns": [], "charts": {}}

    dashboard: dict[str, Any] = {
        "status": "ok",
        "kpi": {},
        "segments": [],
        "audiences": [],
        "campaigns": [],
        "user_stats": {},
        "charts": {},
        "campaign_performance": [],
    }

    async with httpx.AsyncClient(verify=False) as client:
        for base in base_urls:
            # KPIs
            kpi = await _fetch(client, f"{base}/api/analytics/kpi")
            if kpi:
                dashboard["kpi"] = kpi

            # Segments
            segs = await _fetch(client, f"{base}/api/segments")
            if isinstance(segs, list):
                dashboard["segments"] = segs

            # Audiences
            auds = await _fetch(client, f"{base}/api/audiences")
            if isinstance(auds, list):
                dashboard["audiences"] = auds

            # Campaigns (list + enrich with KPIs from detail endpoint)
            camps = await _fetch(client, f"{base}/api/campaigns")
            if isinstance(camps, list):
                for camp in camps:
                    detail = await _fetch(client, f"{base}/api/campaigns/{camp['id']}")
                    if detail and "kpis" in detail:
                        camp["kpis"] = detail["kpis"]
                dashboard["campaigns"] = camps

            # User stats (by segment, by status)
            stats = await _fetch(client, f"{base}/api/users/stats")
            if stats:
                dashboard["user_stats"] = stats

            # Campaign performance for each campaign
            if isinstance(camps, list):
                all_perf = []
                for camp in camps:
                    perf = await _fetch(client, f"{base}/api/analytics/campaign/{camp['id']}/performance")
                    if perf:
                        all_perf.append({
                            "campaign_id": camp["id"],
                            "title": camp.get("title", ""),
                            "daily_metrics": perf.get("daily_metrics", []),
                        })
                dashboard["campaign_performance"] = all_perf[0].get("daily_metrics", []) if all_perf else []
                dashboard["all_campaign_performance"] = all_perf

    return dashboard


# ── Individual proxy endpoints ──
# These provide direct access to specific data types from connected APIs.


async def _get_first_base_url(db: AsyncSession) -> str | None:
    """Return the first available base_url from SwaggerSource records."""
    result = await db.execute(select(SwaggerSource))
    for s in result.scalars().all():
        if s.base_url:
            return s.base_url.rstrip("/")
    return None


@router.get("/dashboard/kpi")
async def dashboard_kpi(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Proxy KPI data from connected API (test-api1)."""
    base = await _get_first_base_url(db)
    if not base:
        return {"status": "no_sources", "data": None}
    async with httpx.AsyncClient(verify=False) as client:
        data = await _fetch(client, f"{base}/api/analytics/kpi")
    return {"status": "ok", "data": data} if data else {"status": "empty", "data": None}


@router.get("/dashboard/segments")
async def dashboard_segments(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Proxy segments list from connected API."""
    base = await _get_first_base_url(db)
    if not base:
        return {"status": "no_sources", "data": []}
    async with httpx.AsyncClient(verify=False) as client:
        data = await _fetch(client, f"{base}/api/segments")
    return {"status": "ok", "data": data if isinstance(data, list) else []}


@router.get("/dashboard/campaigns")
async def dashboard_campaigns(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Proxy campaigns list from connected API."""
    base = await _get_first_base_url(db)
    if not base:
        return {"status": "no_sources", "data": []}
    async with httpx.AsyncClient(verify=False) as client:
        data = await _fetch(client, f"{base}/api/campaigns")
    return {"status": "ok", "data": data if isinstance(data, list) else []}


@router.get("/dashboard/user-stats")
async def dashboard_user_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Proxy user stats from connected API."""
    base = await _get_first_base_url(db)
    if not base:
        return {"status": "no_sources", "data": None}
    async with httpx.AsyncClient(verify=False) as client:
        data = await _fetch(client, f"{base}/api/users/stats")
    return {"status": "ok", "data": data} if data else {"status": "empty", "data": None}
