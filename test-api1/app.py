#!/usr/bin/env python3
"""
Marketing Automation API

A FastAPI-based marketing automation service providing endpoints for managing
audience segments, audiences, campaigns, push notifications, analytics/KPIs,
and user data. Uses SQLite for persistence.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketing.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row: sqlite3.Row) -> dict:
    return dict(row)


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SegmentCreate(BaseModel):
    """Schema for creating a new audience segment."""
    name: str = Field(..., description="Human-readable segment name", examples=["VIP Customers"])
    description: str = Field("", description="Detailed description of the segment", examples=["Users with lifetime value > $500"])
    criteria: dict = Field(..., description="JSON criteria object used to filter users into this segment", examples=[{"avg_check_min": 5000, "status": "active"}])


class AudienceCreate(BaseModel):
    """Schema for creating an audience from an existing segment."""
    segment_id: int = Field(..., description="ID of the segment to build the audience from")
    name: str = Field(..., description="Name for this audience snapshot", examples=["Premium Q2 2026"])
    filters: Optional[dict] = Field(None, description="Optional additional filters to narrow the audience", examples=[{"region": "eu"}])


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign draft."""
    audience_id: int = Field(..., description="ID of the target audience")
    title: str = Field(..., description="Campaign title", examples=["Summer Sale Push"])
    channel: str = Field("push", description="Delivery channel", examples=["push", "email", "sms"])
    message_variants: List[dict] = Field(
        ...,
        description="List of message variant objects for A/B testing",
        examples=[[
            {"variant": "A", "title": "Big Sale!", "body": "Get 20% off today.", "weight": 50},
            {"variant": "B", "title": "Flash Deal!", "body": "Limited time: 25% off.", "weight": 50},
        ]],
    )
    scheduled_at: Optional[str] = Field(None, description="ISO datetime for scheduled send")


class CampaignStatusUpdate(BaseModel):
    """Schema for updating campaign status."""
    status: str = Field(..., description="New campaign status", examples=["draft", "scheduled", "active", "completed"])


class PushGenerateRequest(BaseModel):
    """Schema for generating push notification variants from a prompt/context."""
    prompt: str = Field(..., description="Description or context for generating push notification text", examples=["Spring sale for premium customers, 20% discount"])
    category: Optional[str] = Field(None, description="Optional category hint", examples=["promotion", "retention"])


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Marketing Automation API",
    description=(
        "API for managing marketing campaigns, audience segments, push notifications, "
        "and analytics. Provides endpoints for segment-based audience building, "
        "campaign creation with A/B testing, push notification generation, "
        "and comprehensive KPI analytics."
    ),
    version="1.0.0",
    servers=[{"url": "http://test-api1:9000", "description": "Docker internal"}],
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup: ensure DB exists (run seed if not)
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    if not os.path.exists(DB_PATH):
        import subprocess
        import sys
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "seed.py")], check=True)


# =====================================================================
# SEGMENTS
# =====================================================================

@app.get(
    "/api/segments",
    tags=["Segments"],
    summary="List all audience segments",
    description="Returns every audience segment with its criteria, estimated size, and status. Use this to discover available segments for audience building.",
    response_description="Array of segment objects",
)
def list_segments():
    db = get_db()
    rows = db.execute("SELECT * FROM segments ORDER BY created_at DESC").fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        d["criteria"] = json.loads(d["criteria"]) if d["criteria"] else {}
        result.append(d)
    return result


@app.get(
    "/api/segments/{segment_id}",
    tags=["Segments"],
    summary="Get segment details",
    description="Returns full details of a specific segment including its criteria and an up-to-date member count derived from the users table.",
)
def get_segment(segment_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Segment not found")
    d = dict(row)
    d["criteria"] = json.loads(d["criteria"]) if d["criteria"] else {}

    # Count actual matching users
    member_count = _count_segment_users(db, d["criteria"])
    d["member_count"] = member_count
    db.close()
    return d


@app.post(
    "/api/segments",
    tags=["Segments"],
    summary="Create a new audience segment",
    description="Creates a new segment with the given name, description, and filter criteria. The segment can then be used to build audiences.",
    status_code=201,
)
def create_segment(body: SegmentCreate):
    db = get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    estimated = _count_segment_users(db, body.criteria)
    cur = db.execute(
        "INSERT INTO segments (name, description, criteria, estimated_size, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
        (body.name, body.description, json.dumps(body.criteria), estimated, now),
    )
    db.commit()
    seg_id = cur.lastrowid
    db.close()
    return {"id": seg_id, "name": body.name, "estimated_size": estimated, "status": "active", "created_at": now}


@app.get(
    "/api/segments/{segment_id}/audience",
    tags=["Segments"],
    summary="Get audience size estimate for a segment",
    description="Returns an estimated audience size for a segment with a breakdown by each criterion showing how many users match.",
)
def segment_audience_estimate(segment_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Segment not found")
    criteria = json.loads(row["criteria"]) if row["criteria"] else {}
    total = _count_segment_users(db, criteria)

    breakdown = {}
    for key, value in criteria.items():
        single_criteria = {key: value}
        breakdown[key] = _count_segment_users(db, single_criteria)

    db.close()
    return {
        "segment_id": segment_id,
        "segment_name": row["name"],
        "total_estimated": total,
        "criteria_breakdown": breakdown,
    }


@app.get(
    "/api/segments/search",
    tags=["Segments"],
    summary="Search segments by name or description",
    description="Full-text search across segment names and descriptions. Useful for finding segments by keyword.",
)
def search_segments(q: str = Query(..., description="Search query string")):
    db = get_db()
    pattern = f"%{q}%"
    rows = db.execute(
        "SELECT * FROM segments WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC",
        (pattern, pattern),
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        d["criteria"] = json.loads(d["criteria"]) if d["criteria"] else {}
        result.append(d)
    return result


# =====================================================================
# AUDIENCES
# =====================================================================

@app.get(
    "/api/audiences",
    tags=["Audiences"],
    summary="List all audiences",
    description="Returns all created audiences with their size, linked segment, and current status.",
)
def list_audiences():
    db = get_db()
    rows = db.execute(
        "SELECT a.*, s.name as segment_name FROM audiences a LEFT JOIN segments s ON a.segment_id = s.id ORDER BY a.created_at DESC"
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        d["filters"] = json.loads(d["filters"]) if d["filters"] else {}
        result.append(d)
    return result


@app.post(
    "/api/audiences",
    tags=["Audiences"],
    summary="Create an audience from a segment",
    description="Builds a concrete audience snapshot from a segment's criteria. Optionally applies additional filters. Members are materialized into the audience_members table.",
    status_code=201,
)
def create_audience(body: AudienceCreate):
    db = get_db()
    seg = db.execute("SELECT * FROM segments WHERE id = ?", (body.segment_id,)).fetchone()
    if not seg:
        db.close()
        raise HTTPException(404, "Segment not found")

    criteria = json.loads(seg["criteria"]) if seg["criteria"] else {}
    matching_users = _get_segment_user_ids(db, criteria)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    cur = db.execute(
        "INSERT INTO audiences (segment_id, name, size, status, created_at, filters) VALUES (?, ?, ?, 'ready', ?, ?)",
        (body.segment_id, body.name, len(matching_users), now, json.dumps(body.filters or {})),
    )
    db.commit()
    audience_id = cur.lastrowid

    for uid in matching_users[:500]:
        db.execute("INSERT INTO audience_members (audience_id, user_id) VALUES (?, ?)", (audience_id, uid))
    db.commit()
    db.close()

    return {"id": audience_id, "name": body.name, "size": len(matching_users), "status": "ready", "created_at": now}


@app.get(
    "/api/audiences/{audience_id}",
    tags=["Audiences"],
    summary="Get audience details with paginated member list",
    description="Returns audience metadata and a paginated list of audience member user records.",
)
def get_audience(
    audience_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of members per page"),
):
    db = get_db()
    aud = db.execute("SELECT * FROM audiences WHERE id = ?", (audience_id,)).fetchone()
    if not aud:
        db.close()
        raise HTTPException(404, "Audience not found")

    d = dict(aud)
    d["filters"] = json.loads(d["filters"]) if d["filters"] else {}

    offset = (page - 1) * page_size
    members = db.execute(
        """SELECT u.* FROM audience_members am
           JOIN users u ON am.user_id = u.id
           WHERE am.audience_id = ?
           ORDER BY u.id LIMIT ? OFFSET ?""",
        (audience_id, page_size, offset),
    ).fetchall()

    total_members = db.execute(
        "SELECT COUNT(*) as cnt FROM audience_members WHERE audience_id = ?", (audience_id,)
    ).fetchone()["cnt"]

    db.close()

    d["members"] = rows_to_list(members)
    d["pagination"] = {
        "page": page,
        "page_size": page_size,
        "total": total_members,
        "pages": (total_members + page_size - 1) // page_size,
    }
    return d


@app.get(
    "/api/audiences/{audience_id}/overlap",
    tags=["Audiences"],
    summary="Calculate overlap between two audiences",
    description="Computes the number and percentage of users shared between two audiences. Useful for deduplication and campaign planning.",
)
def audience_overlap(
    audience_id: int,
    other_audience_id: int = Query(..., description="ID of the second audience to compare"),
):
    db = get_db()
    # Verify both exist
    a1 = db.execute("SELECT * FROM audiences WHERE id = ?", (audience_id,)).fetchone()
    a2 = db.execute("SELECT * FROM audiences WHERE id = ?", (other_audience_id,)).fetchone()
    if not a1 or not a2:
        db.close()
        raise HTTPException(404, "One or both audiences not found")

    overlap = db.execute(
        """SELECT COUNT(*) as cnt FROM audience_members am1
           JOIN audience_members am2 ON am1.user_id = am2.user_id
           WHERE am1.audience_id = ? AND am2.audience_id = ?""",
        (audience_id, other_audience_id),
    ).fetchone()["cnt"]

    db.close()
    size1 = a1["size"]
    size2 = a2["size"]
    pct1 = round(overlap / size1 * 100, 2) if size1 > 0 else 0
    pct2 = round(overlap / size2 * 100, 2) if size2 > 0 else 0

    return {
        "audience_a": {"id": audience_id, "name": a1["name"], "size": size1},
        "audience_b": {"id": other_audience_id, "name": a2["name"], "size": size2},
        "overlap_count": overlap,
        "overlap_pct_of_a": pct1,
        "overlap_pct_of_b": pct2,
    }


# =====================================================================
# CAMPAIGNS
# =====================================================================

@app.get(
    "/api/campaigns",
    tags=["Campaigns"],
    summary="List all campaigns",
    description="Returns all campaigns with their status, linked audience, delivery channel, and message variant count.",
)
def list_campaigns():
    db = get_db()
    rows = db.execute(
        """SELECT c.*, a.name as audience_name, a.size as audience_size
           FROM campaigns c LEFT JOIN audiences a ON c.audience_id = a.id
           ORDER BY c.created_at DESC"""
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        variants = json.loads(d["message_variants"]) if d["message_variants"] else []
        d["message_variants"] = variants
        d["variant_count"] = len(variants)
        result.append(d)
    return result


@app.post(
    "/api/campaigns",
    tags=["Campaigns"],
    summary="Create a new campaign draft",
    description="Creates a campaign in draft status targeting a specific audience. Includes message variants for A/B testing.",
    status_code=201,
)
def create_campaign(body: CampaignCreate):
    db = get_db()
    aud = db.execute("SELECT id FROM audiences WHERE id = ?", (body.audience_id,)).fetchone()
    if not aud:
        db.close()
        raise HTTPException(404, "Audience not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    cur = db.execute(
        "INSERT INTO campaigns (audience_id, title, channel, status, message_variants, created_at, scheduled_at) VALUES (?, ?, ?, 'draft', ?, ?, ?)",
        (body.audience_id, body.title, body.channel, json.dumps(body.message_variants), now, body.scheduled_at),
    )
    db.commit()
    campaign_id = cur.lastrowid
    db.close()
    return {"id": campaign_id, "title": body.title, "status": "draft", "created_at": now}


@app.get(
    "/api/campaigns/{campaign_id}",
    tags=["Campaigns"],
    summary="Get campaign details with KPIs",
    description="Returns full campaign details including message variants and aggregated performance KPIs (impressions, clicks, conversions, CTR, conversion rate).",
)
def get_campaign(campaign_id: int):
    db = get_db()
    row = db.execute(
        """SELECT c.*, a.name as audience_name, a.size as audience_size
           FROM campaigns c LEFT JOIN audiences a ON c.audience_id = a.id
           WHERE c.id = ?""",
        (campaign_id,),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Campaign not found")

    d = dict(row)
    d["message_variants"] = json.loads(d["message_variants"]) if d["message_variants"] else []

    # Aggregate metrics
    metrics = db.execute(
        "SELECT SUM(impressions) as total_impressions, SUM(clicks) as total_clicks, SUM(conversions) as total_conversions FROM campaign_metrics WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    db.close()

    total_imp = metrics["total_impressions"] or 0
    total_clk = metrics["total_clicks"] or 0
    total_conv = metrics["total_conversions"] or 0

    d["kpis"] = {
        "total_impressions": total_imp,
        "total_clicks": total_clk,
        "total_conversions": total_conv,
        "ctr": round(total_clk / total_imp * 100, 2) if total_imp > 0 else 0,
        "conversion_rate": round(total_conv / total_clk * 100, 2) if total_clk > 0 else 0,
    }
    return d


@app.patch(
    "/api/campaigns/{campaign_id}",
    tags=["Campaigns"],
    summary="Update campaign status",
    description="Transitions a campaign between statuses: draft, scheduled, active, completed. Validates that the status is one of the allowed values.",
)
def update_campaign_status(campaign_id: int, body: CampaignStatusUpdate):
    allowed = {"draft", "scheduled", "active", "completed"}
    if body.status not in allowed:
        raise HTTPException(400, f"Status must be one of: {', '.join(sorted(allowed))}")
    db = get_db()
    row = db.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Campaign not found")
    db.execute("UPDATE campaigns SET status = ? WHERE id = ?", (body.status, campaign_id))
    db.commit()
    db.close()
    return {"id": campaign_id, "status": body.status}


@app.get(
    "/api/campaigns/{campaign_id}/variants",
    tags=["Campaigns"],
    summary="Get message variants with A/B test results",
    description="Returns the message variants for a campaign. For completed campaigns, includes simulated A/B test performance metrics per variant.",
)
def campaign_variants(campaign_id: int):
    db = get_db()
    row = db.execute("SELECT message_variants, status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Campaign not found")

    variants = json.loads(row["message_variants"]) if row["message_variants"] else []

    if row["status"] == "completed":
        # Simulate A/B results
        import random
        for v in variants:
            sends = random.randint(800, 2000)
            opens = random.randint(int(sends * 0.15), int(sends * 0.45))
            clicks = random.randint(int(opens * 0.10), int(opens * 0.35))
            v["metrics"] = {
                "sends": sends,
                "opens": opens,
                "clicks": clicks,
                "open_rate": round(opens / sends * 100, 2),
                "click_rate": round(clicks / opens * 100, 2) if opens > 0 else 0,
            }

    db.close()
    return {"campaign_id": campaign_id, "status": row["status"], "variants": variants}


# =====================================================================
# PUSH NOTIFICATIONS
# =====================================================================

@app.post(
    "/api/push/generate",
    tags=["Push Notifications"],
    summary="Generate push notification variants from a prompt",
    description="Accepts a text prompt/context and returns 2-3 push notification variants suitable for A/B testing. Each variant has a title and body optimized for mobile push delivery.",
)
def generate_push(body: PushGenerateRequest):
    # Return hardcoded but contextual variants (no LLM needed)
    prompt_lower = body.prompt.lower()

    if "sale" in prompt_lower or "discount" in prompt_lower or "off" in prompt_lower:
        variants = [
            {"variant": "A", "title": "Flash Sale Alert!", "body": f"Don't miss out! {body.prompt}. Shop now before it's gone.", "estimated_ctr": 8.5},
            {"variant": "B", "title": "Your Exclusive Deal", "body": f"Just for you: {body.prompt}. Tap to claim your offer.", "estimated_ctr": 7.2},
            {"variant": "C", "title": "Limited Time Offer", "body": f"Hurry! {body.prompt}. This deal won't last long.", "estimated_ctr": 6.8},
        ]
    elif "back" in prompt_lower or "miss" in prompt_lower or "return" in prompt_lower:
        variants = [
            {"variant": "A", "title": "We Miss You!", "body": f"It's been a while. {body.prompt}. Come see what's new!", "estimated_ctr": 5.4},
            {"variant": "B", "title": "Welcome Back Gift", "body": f"We saved something special for you. {body.prompt}.", "estimated_ctr": 6.1},
        ]
    else:
        variants = [
            {"variant": "A", "title": "Check This Out!", "body": f"{body.prompt}. Tap to learn more.", "estimated_ctr": 4.5},
            {"variant": "B", "title": "Something New for You", "body": f"Hey! {body.prompt}. Don't miss it.", "estimated_ctr": 5.0},
            {"variant": "C", "title": "Just for You", "body": f"We thought you'd like this: {body.prompt}.", "estimated_ctr": 4.8},
        ]

    return {"prompt": body.prompt, "category": body.category, "variants": variants}


@app.get(
    "/api/push/templates",
    tags=["Push Notifications"],
    summary="List push notification templates",
    description="Returns all available push notification templates with their title/body templates and category. Templates use placeholders like {name}, {discount}, {code}.",
)
def list_push_templates():
    db = get_db()
    rows = db.execute("SELECT * FROM push_templates ORDER BY id").fetchall()
    db.close()
    return rows_to_list(rows)


# =====================================================================
# ANALYTICS / KPI
# =====================================================================

@app.get(
    "/api/analytics/kpi",
    tags=["Analytics"],
    summary="Get overall marketing KPIs",
    description="Returns high-level marketing KPIs: total users, active users, average check amount, conversion rate, and retention rate. Computed from current user data.",
)
def overall_kpis():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
    active = db.execute("SELECT COUNT(*) as cnt FROM users WHERE status = 'active'").fetchone()["cnt"]
    avg_check = db.execute("SELECT AVG(avg_check) as val FROM users WHERE status = 'active'").fetchone()["val"] or 0
    # Retention: active users who made a purchase in last 30 days
    thirty_days_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)).strftime("%Y-%m-%d")
    retained = db.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE status = 'active' AND last_active >= ?", (thirty_days_ago,)
    ).fetchone()["cnt"]
    db.close()

    retention = round(retained / active * 100, 2) if active > 0 else 0
    conversion = round(retained / total * 100, 2) if total > 0 else 0

    return {
        "total_users": total,
        "active_users": active,
        "avg_check": round(avg_check, 2),
        "conversion_rate": conversion,
        "retention_rate": retention,
        "period": "last_30_days",
    }


@app.get(
    "/api/analytics/segments/{segment_id}/kpi",
    tags=["Analytics"],
    summary="Get segment-specific KPIs",
    description="Returns KPIs calculated specifically for users matching a given segment's criteria: user count, average check, activity rate, and average purchases.",
)
def segment_kpis(segment_id: int):
    db = get_db()
    seg = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if not seg:
        db.close()
        raise HTTPException(404, "Segment not found")
    criteria = json.loads(seg["criteria"]) if seg["criteria"] else {}

    conditions, params = _build_user_conditions(criteria)
    where = " AND ".join(conditions) if conditions else "1=1"

    stats = db.execute(
        f"""SELECT
            COUNT(*) as user_count,
            AVG(avg_check) as avg_check,
            AVG(total_purchases) as avg_purchases,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count
        FROM users WHERE {where}""",
        params,
    ).fetchone()
    db.close()

    user_count = stats["user_count"] or 0
    return {
        "segment_id": segment_id,
        "segment_name": seg["name"],
        "user_count": user_count,
        "avg_check": round(stats["avg_check"] or 0, 2),
        "avg_purchases": round(stats["avg_purchases"] or 0, 1),
        "active_count": stats["active_count"] or 0,
        "activity_rate": round((stats["active_count"] or 0) / user_count * 100, 2) if user_count > 0 else 0,
    }


@app.get(
    "/api/analytics/audience-forecast",
    tags=["Analytics"],
    summary="Forecast audience size for segment combinations",
    description="Calculates the estimated audience size when combining multiple segments using intersection (AND) or union (OR) logic. Useful for planning campaigns across multiple segments.",
)
def audience_forecast(
    segment_ids: str = Query(..., description="Comma-separated segment IDs", examples=["1,2,3"]),
    logic: str = Query("union", description="Combination logic: 'union' (OR) or 'intersection' (AND)", examples=["union", "intersection"]),
):
    ids = [int(x.strip()) for x in segment_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(400, "Provide at least one segment_id")

    db = get_db()
    sets_of_user_ids = []
    segment_info = []

    for sid in ids:
        seg = db.execute("SELECT * FROM segments WHERE id = ?", (sid,)).fetchone()
        if not seg:
            db.close()
            raise HTTPException(404, f"Segment {sid} not found")
        criteria = json.loads(seg["criteria"]) if seg["criteria"] else {}
        user_ids = set(_get_segment_user_ids(db, criteria))
        sets_of_user_ids.append(user_ids)
        segment_info.append({"id": sid, "name": seg["name"], "size": len(user_ids)})

    db.close()

    if logic == "intersection":
        combined = sets_of_user_ids[0]
        for s in sets_of_user_ids[1:]:
            combined = combined & s
    else:  # union
        combined = set()
        for s in sets_of_user_ids:
            combined = combined | s

    return {
        "logic": logic,
        "segments": segment_info,
        "forecasted_size": len(combined),
    }


@app.get(
    "/api/analytics/campaign/{campaign_id}/performance",
    tags=["Analytics"],
    summary="Get campaign performance metrics over time",
    description="Returns daily performance metrics (impressions, clicks, conversions) for a campaign, along with computed CTR and conversion rates per day.",
)
def campaign_performance(campaign_id: int):
    db = get_db()
    camp = db.execute("SELECT id, title, status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not camp:
        db.close()
        raise HTTPException(404, "Campaign not found")

    rows = db.execute(
        "SELECT * FROM campaign_metrics WHERE campaign_id = ? ORDER BY date",
        (campaign_id,),
    ).fetchall()
    db.close()

    daily = []
    for r in rows:
        d = dict(r)
        d["ctr"] = round(d["clicks"] / d["impressions"] * 100, 2) if d["impressions"] > 0 else 0
        d["conversion_rate"] = round(d["conversions"] / d["clicks"] * 100, 2) if d["clicks"] > 0 else 0
        daily.append(d)

    total_imp = sum(d["impressions"] for d in daily)
    total_clk = sum(d["clicks"] for d in daily)
    total_conv = sum(d["conversions"] for d in daily)

    return {
        "campaign_id": campaign_id,
        "title": camp["title"],
        "status": camp["status"],
        "daily_metrics": daily,
        "totals": {
            "impressions": total_imp,
            "clicks": total_clk,
            "conversions": total_conv,
            "ctr": round(total_clk / total_imp * 100, 2) if total_imp > 0 else 0,
            "conversion_rate": round(total_conv / total_clk * 100, 2) if total_clk > 0 else 0,
        },
    }


# =====================================================================
# USERS
# =====================================================================

@app.get(
    "/api/users",
    tags=["Users"],
    summary="List users with filtering and pagination",
    description="Returns a paginated list of users. Supports filtering by segment name, user status, minimum average check, and last active within N days.",
)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    segment: Optional[str] = Query(None, description="Filter by segment name"),
    status: Optional[str] = Query(None, description="Filter by user status (active/inactive)"),
    min_check: Optional[float] = Query(None, description="Minimum average check amount"),
    last_active_days: Optional[int] = Query(None, description="Only users active within this many days"),
):
    db = get_db()
    conditions = []
    params = []

    if segment:
        conditions.append("segment = ?")
        params.append(segment)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if min_check is not None:
        conditions.append("avg_check >= ?")
        params.append(min_check)
    if last_active_days is not None:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=last_active_days)).strftime("%Y-%m-%d")
        conditions.append("last_active >= ?")
        params.append(cutoff)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    total = db.execute(f"SELECT COUNT(*) as cnt FROM users {where}", params).fetchone()["cnt"]

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM users {where} ORDER BY id LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    db.close()

    return {
        "users": rows_to_list(rows),
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@app.get(
    "/api/users/stats",
    tags=["Users"],
    summary="Get user statistics breakdown",
    description="Returns aggregate user statistics: counts by segment, counts by activity status, and distribution by average check tier (low/medium/high/premium).",
)
def user_stats():
    db = get_db()

    by_segment = db.execute(
        "SELECT segment, COUNT(*) as count, AVG(avg_check) as avg_check FROM users GROUP BY segment ORDER BY count DESC"
    ).fetchall()

    by_status = db.execute(
        "SELECT status, COUNT(*) as count FROM users GROUP BY status"
    ).fetchall()

    tiers = db.execute("""
        SELECT
            CASE
                WHEN avg_check < 1000 THEN 'low'
                WHEN avg_check < 3000 THEN 'medium'
                WHEN avg_check < 7000 THEN 'high'
                ELSE 'premium'
            END as tier,
            COUNT(*) as count,
            AVG(avg_check) as avg_check
        FROM users GROUP BY tier ORDER BY avg_check
    """).fetchall()

    db.close()

    return {
        "by_segment": [{"segment": r["segment"], "count": r["count"], "avg_check": round(r["avg_check"], 2)} for r in by_segment],
        "by_status": [{"status": r["status"], "count": r["count"]} for r in by_status],
        "by_avg_check_tier": [{"tier": r["tier"], "count": r["count"], "avg_check": round(r["avg_check"], 2)} for r in tiers],
    }


@app.get(
    "/api/users/{user_id}",
    tags=["Users"],
    summary="Get user profile with purchase history summary",
    description="Returns a user's full profile including their segment, activity status, and a summary of their purchase behavior.",
)
def get_user(user_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "User not found")
    d = dict(row)

    # Add purchase history summary
    d["purchase_summary"] = {
        "total_purchases": d["total_purchases"],
        "avg_check": d["avg_check"],
        "estimated_ltv": round(d["total_purchases"] * d["avg_check"], 2),
        "last_active": d["last_active"],
    }

    # Find which audiences this user belongs to
    audiences = db.execute(
        """SELECT a.id, a.name FROM audience_members am
           JOIN audiences a ON am.audience_id = a.id
           WHERE am.user_id = ?""",
        (user_id,),
    ).fetchall()
    db.close()

    d["audiences"] = rows_to_list(audiences)
    return d


# =====================================================================
# Internal helpers
# =====================================================================

def _build_user_conditions(criteria: dict) -> tuple:
    """Build SQL WHERE conditions from segment criteria."""
    conditions = []
    params = []

    if "avg_check_min" in criteria:
        conditions.append("avg_check >= ?")
        params.append(criteria["avg_check_min"])
    if "avg_check_max" in criteria:
        conditions.append("avg_check <= ?")
        params.append(criteria["avg_check_max"])
    if "status" in criteria:
        conditions.append("status = ?")
        params.append(criteria["status"])
    if "total_purchases_min" in criteria:
        conditions.append("total_purchases >= ?")
        params.append(criteria["total_purchases_min"])
    if "last_active_days_min" in criteria:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=criteria["last_active_days_min"])).strftime("%Y-%m-%d")
        conditions.append("last_active <= ?")
        params.append(cutoff)
    if "last_active_days_max" in criteria:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=criteria["last_active_days_max"])).strftime("%Y-%m-%d")
        conditions.append("last_active >= ?")
        params.append(cutoff)
    if "registered_days_max" in criteria:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=criteria["registered_days_max"])).strftime("%Y-%m-%d")
        conditions.append("last_active >= ?")
        params.append(cutoff)

    return conditions, params


def _count_segment_users(db: sqlite3.Connection, criteria: dict) -> int:
    conditions, params = _build_user_conditions(criteria)
    where = " AND ".join(conditions) if conditions else "1=1"
    return db.execute(f"SELECT COUNT(*) as cnt FROM users WHERE {where}", params).fetchone()["cnt"]


def _get_segment_user_ids(db: sqlite3.Connection, criteria: dict) -> list:
    conditions, params = _build_user_conditions(criteria)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = db.execute(f"SELECT id FROM users WHERE {where}", params).fetchall()
    return [r["id"] for r in rows]
