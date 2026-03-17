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

            # Campaigns
            camps = await _fetch(client, f"{base}/api/campaigns")
            if isinstance(camps, list):
                dashboard["campaigns"] = camps

            # User stats (by segment, by status)
            stats = await _fetch(client, f"{base}/api/users/stats")
            if stats:
                dashboard["user_stats"] = stats

            # Campaign performance for first campaign
            if isinstance(camps, list) and camps:
                perf = await _fetch(client, f"{base}/api/analytics/campaign/{camps[0]['id']}/performance")
                if perf:
                    dashboard["campaign_performance"] = perf.get("daily_metrics", [])

    return dashboard
