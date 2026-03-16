"""Mock LLM client that returns realistic fake responses for development."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.schemas.models import OrchestrationStep

logger = logging.getLogger(__name__)

# Sample mock data for different result types
MOCK_TABLE_DATA = {
    "columns": ["id", "name", "status", "value", "updated_at"],
    "rows": [
        {"id": 1, "name": "Service Alpha", "status": "active", "value": 98.5, "updated_at": "2026-03-15T10:00:00Z"},
        {"id": 2, "name": "Service Beta", "status": "active", "value": 87.2, "updated_at": "2026-03-15T09:45:00Z"},
        {"id": 3, "name": "Service Gamma", "status": "warning", "value": 62.1, "updated_at": "2026-03-15T09:30:00Z"},
        {"id": 4, "name": "Service Delta", "status": "inactive", "value": 0.0, "updated_at": "2026-03-14T23:00:00Z"},
        {"id": 5, "name": "Service Epsilon", "status": "active", "value": 95.8, "updated_at": "2026-03-15T10:05:00Z"},
    ],
}

MOCK_CHART_DATA = {
    "chart_type": "bar",
    "title": "API Response Times (ms)",
    "labels": ["GET /users", "POST /orders", "GET /products", "PUT /settings", "DELETE /cache"],
    "datasets": [
        {
            "label": "Avg Response Time",
            "data": [45, 120, 32, 88, 15],
        },
        {
            "label": "P95 Response Time",
            "data": [89, 340, 67, 210, 28],
        },
    ],
}

MOCK_MAP_DATA = {
    "center": [55.7558, 37.6173],
    "zoom": 10,
    "markers": [
        {"lat": 55.7558, "lng": 37.6173, "title": "Server DC-1", "description": "Primary datacenter, Moscow"},
        {"lat": 55.7300, "lng": 37.5900, "title": "Server DC-2", "description": "Backup datacenter"},
        {"lat": 55.7700, "lng": 37.6500, "title": "CDN Node", "description": "Edge server"},
        {"lat": 55.7400, "lng": 37.6600, "title": "Monitoring", "description": "Monitoring station"},
    ],
}

MOCK_LIST_DATA = {
    "items": [
        "GET /api/v1/users - List all users with pagination support",
        "POST /api/v1/users - Create a new user account",
        "GET /api/v1/users/{id} - Get user details by ID",
        "PUT /api/v1/users/{id} - Update user information",
        "DELETE /api/v1/users/{id} - Delete a user account",
        "GET /api/v1/orders - List orders with filters",
        "POST /api/v1/orders - Create a new order",
        "GET /api/v1/products - Search products catalog",
    ],
}

MOCK_TEXT_DATA = {
    "content": (
        "Based on the analysis of the available API endpoints, here is a summary:\n\n"
        "The API provides a comprehensive RESTful interface with 24 endpoints across 5 resource groups. "
        "Authentication is handled via Bearer tokens. All endpoints support JSON request/response format.\n\n"
        "Key findings:\n"
        "- User management: 5 endpoints (CRUD + search)\n"
        "- Order processing: 6 endpoints (lifecycle management)\n"
        "- Product catalog: 4 endpoints (read + search)\n"
        "- Analytics: 5 endpoints (reports + dashboards)\n"
        "- System: 4 endpoints (health, config, cache, logs)\n\n"
        "Rate limiting is set to 1000 requests/minute per API key."
    ),
}


def _detect_result_type(query: str) -> str:
    """Detect the desired result type from the query text."""
    q = query.lower()
    if any(w in q for w in ("table", "list all", "show all", "display", "data")):
        return "table"
    if any(w in q for w in ("chart", "graph", "plot", "diagram", "metrics", "statistics")):
        return "chart"
    if any(w in q for w in ("map", "location", "coordinates", "geo", "where")):
        return "map"
    if any(w in q for w in ("list", "endpoints", "available", "find")):
        return "list"
    return "text"


def _mock_classify_intent(query: str) -> dict:
    """Mock intent classification matching the real LLM classifier pattern.

    In real mode, the LLM handles this for any language. In mock mode
    we use a simple heuristic that mirrors the classifier contract.
    """
    q = query.lower().strip().rstrip("!?./)")

    # Simulate the classifier returning chat intent for obvious cases
    if q in ("hi", "hello", "hey"):
        return {
            "intent": "chat",
            "response": (
                "Hello! I'm your API Copilot. I can help you query and "
                "explore your APIs. Upload a Swagger spec and ask me "
                "anything about the data."
            ),
        }
    if q in ("thanks", "thank you", "thx"):
        return {
            "intent": "chat",
            "response": "You're welcome! Let me know if you need anything else.",
        }
    if q in ("bye", "goodbye"):
        return {
            "intent": "chat",
            "response": "Goodbye! Feel free to come back anytime.",
        }
    if any(phrase in q for phrase in ("what can you do", "who are you", "help")):
        return {
            "intent": "chat",
            "response": (
                "I help you work with APIs. Here's what I can do:\n\n"
                "1. Upload a Swagger/OpenAPI spec \u2014 I'll index all endpoints\n"
                "2. Ask me in natural language \u2014 I'll find the right endpoints and call them\n"
                "3. I return results as tables, charts, maps, or lists\n\n"
                'Try: "show all users" or "list todos"'
            ),
        }

    # Default: treat as API query
    return {"intent": "api_query"}


class MockKimiClient:
    """Mock LLM client that returns predefined responses.

    Mirrors the real LLMClient interface including the classifier pattern
    used by the planner for intent detection.
    """

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """Mock chat that handles classifier and translate prompts."""
        await asyncio.sleep(0.3)

        # Check if this is a classifier call (system prompt contains 'Classify')
        system_msg = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        user_msg = next(
            (m["content"] for m in messages if m["role"] == "user"), ""
        )

        if "Classify" in system_msg and "intent" in system_msg:
            # Mock intent classification
            result = _mock_classify_intent(user_msg)
            return json.dumps(result)

        if "Translate" in system_msg:
            # Mock translation: return the original text (mock mode)
            return user_msg

        return json.dumps({"response": "Mock LLM response"})

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        response = "This is a mock streaming response from the LLM."
        for word in response.split():
            await asyncio.sleep(0.1)
            yield word + " "

    async def plan_query(
        self, query: str, endpoints: list[dict]
    ) -> list[OrchestrationStep]:
        await asyncio.sleep(0.5)

        result_type = _detect_result_type(query)
        endpoint_desc = endpoints[0].get("path", "/api/resource") if endpoints else "/api/resource"

        steps = [
            OrchestrationStep(
                step=1,
                action="api_call",
                description=f"Fetching data from {endpoint_desc}",
                endpoint=endpoints[0] if endpoints else {"method": "GET", "path": "/api/mock"},
                parameters={"limit": 100},
                status="pending",
            ),
            OrchestrationStep(
                step=2,
                action="data_process",
                description="Processing and filtering the response data",
                parameters={"operations": [{"type": "filter"}, {"type": "sort", "by": "id"}]},
                status="pending",
            ),
            OrchestrationStep(
                step=3,
                action="format_output",
                description=f"Formatting results as {result_type}",
                parameters={"output_type": result_type},
                status="pending",
            ),
        ]
        return steps

    async def execute_step(self, step: OrchestrationStep, context: dict) -> dict:
        await asyncio.sleep(0.3)

        if step.action == "api_call":
            return {
                "method": "GET",
                "url": "https://mock-api.example.com/data",
                "params": {"limit": 100},
            }
        elif step.action == "format_output":
            output_type = "text"
            if step.parameters:
                output_type = step.parameters.get("output_type", "text")
            return {"output_type": output_type, "config": {}}
        else:
            return {"operations": [{"type": "sort", "by": "id"}]}

    async def close(self) -> None:
        pass
