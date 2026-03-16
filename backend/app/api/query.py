"""Thin controllers for query orchestration.

All business logic lives in OrchestrationService.
These handlers only handle HTTP/WebSocket protocol concerns.
"""

import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, Role, require_role
from app.db.session import get_db, async_session_factory
from app.schemas.models import QueryRequest, ResultResponse
from app.services.orchestration import OrchestrationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=ResultResponse)
async def query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role(Role.EDITOR)),
) -> ResultResponse:
    """Send a natural language query. The orchestration service manages
    endpoint discovery and LLM-driven API calls."""
    service = OrchestrationService(db)
    return await service.execute(
        query=request.query,
        swagger_source_ids=request.swagger_source_ids,

    )


@router.websocket("/ws/query")
async def ws_query(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming orchestration.

    Protocol:
    - Client sends JSON: {"query": "...", "swagger_source_ids": [1,2] | null, "history": [...], "api_key": "..."}
    - Server streams back: step → result → done
    """
    await websocket.accept()

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON message."})
                continue

            query_text = message.get("query")
            if not query_text:
                await websocket.send_json({"error": "Missing 'query' field."})
                continue

            swagger_source_ids = message.get("swagger_source_ids")
            chat_history = message.get("history", [])

            async with async_session_factory() as db:
                service = OrchestrationService(db)
                async for event in service.execute_stream(
                    query=query_text,
                    swagger_source_ids=swagger_source_ids,
                    history=chat_history,
                ):
                    await websocket.send_json(event)

            await websocket.send_json({"type": "done", "data": {}})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        try:
            await websocket.send_json(
                {"type": "error", "data": {"message": str(exc)}}
            )
        except Exception:
            pass
