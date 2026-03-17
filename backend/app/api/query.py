import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiEndpoint, SwaggerSource
from app.db.session import get_db, async_session_factory
from app.schemas.models import (
    OrchestrationStep,
    QueryRequest,
    ResultResponse,
)
from app.services.mlops_client import MLOpsClient

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=ResultResponse)
async def query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> ResultResponse:
    """Send a natural language query. The backend lists all available endpoints
    for the selected sources and forwards them along with the query to the MLOps
    orchestrator. The LLM decides which endpoints are relevant."""
    mlops_client = MLOpsClient()

    # List all endpoints for selected sources (no RAG search, no embedding).
    # The LLM is smart enough to pick the right endpoints from the full list.
    stmt = sa_select(ApiEndpoint).join(
        SwaggerSource, ApiEndpoint.swagger_source_id == SwaggerSource.id
    ).where(SwaggerSource.base_url.isnot(None))
    if request.swagger_source_ids:
        stmt = stmt.where(ApiEndpoint.swagger_source_id.in_(request.swagger_source_ids))
    result = await db.execute(stmt.order_by(ApiEndpoint.id))
    relevant_endpoints = list(result.scalars().all())

    # Find base_url: pick the first swagger source that has one
    base_url: str | None = None
    source_cache: dict[int, SwaggerSource | None] = {}
    for ep in relevant_endpoints:
        sid = ep.swagger_source_id
        if sid not in source_cache:
            source_cache[sid] = await db.get(SwaggerSource, sid)
        src = source_cache[sid]
        if src and src.base_url:
            base_url = src.base_url
            break

    endpoints_payload = [
        {
            "id": ep.id,
            "method": ep.method,
            "path": ep.path,
            "summary": ep.summary,
            "description": ep.description,
            "parameters": ep.parameters,
            "request_body": ep.request_body,
            "response_schema": ep.response_schema,
            "base_url": src.base_url if (src := source_cache.get(ep.swagger_source_id)) else None,
        }
        for ep in relevant_endpoints
    ]

    # Short-circuit: no endpoints found
    if not endpoints_payload:
        return ResultResponse(
            type="text",
            data={"content": "No relevant API endpoints found for your query. Please upload a Swagger spec with the right API."},
            metadata={"status": "completed"},
        )

    # Forward to MLOps orchestrator (pass the ORIGINAL query so LLM sees user's language)
    try:
        result = await mlops_client.orchestrate(
            query=request.query,
            endpoints=endpoints_payload,
            base_url=base_url,
        )
    except Exception as exc:
        logger.error("Orchestration failed: %s", exc)
        return ResultResponse(
            type="text",
            data={"content": f"Orchestration error: {str(exc)}"},
            metadata={"status": "error"},
        )

    result_data = result.get("data", {})
    result_type = result.get("type", "text")

    # Handle empty result data gracefully
    if not result_data or result_data == {}:
        result_type = "text"
        result_data = {"content": "The query completed but returned no data."}

    return ResultResponse(
        type=result_type,
        data=result_data,
        metadata=result.get("metadata"),
    )


@router.websocket("/ws/query")
async def ws_query(websocket: WebSocket, token: str | None = None) -> None:
    """WebSocket endpoint for streaming orchestration.

    Authentication: pass JWT token as ?token= query parameter.

    Protocol:
    - Client sends JSON: {"query": "...", "swagger_source_ids": [1, 2] | null}
    - Server streams JSON messages back:
      - OrchestrationStep messages during processing
      - Final ResultResponse message
    """
    # Validate token before accepting
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    from app.api.auth import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt as jose_jwt
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            raise ValueError("Invalid token payload")
    except (JWTError, ValueError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    mlops_client = MLOpsClient()

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"error": "Invalid JSON message."}
                )
                continue

            query_text = message.get("query")
            if not query_text:
                await websocket.send_json(
                    {"error": "Missing 'query' field."}
                )
                continue

            # Guard against excessively long or spammy prompts
            MAX_QUERY_LENGTH = 2000
            if len(query_text) > MAX_QUERY_LENGTH:
                query_text = query_text[:MAX_QUERY_LENGTH]
                logger.warning("Query truncated from %d to %d chars", len(message.get("query", "")), MAX_QUERY_LENGTH)

            swagger_source_ids = message.get("swagger_source_ids")
            chat_history = message.get("history", [])
            # Limit chat history to avoid bloating LLM context
            if len(chat_history) > 10:
                chat_history = chat_history[-10:]

            # Resolve base_url and swagger_source_ids from DB
            # (endpoints are NOT loaded here — mlops will use RAG to find relevant ones)
            base_url: str | None = None
            all_source_ids: list[int] = []

            async with async_session_factory() as db:
                stmt = sa_select(SwaggerSource).where(SwaggerSource.base_url.isnot(None))
                if swagger_source_ids:
                    stmt = stmt.where(SwaggerSource.id.in_(swagger_source_ids))
                result = await db.execute(stmt.order_by(SwaggerSource.id))
                sources = list(result.scalars().all())
                for src in sources:
                    all_source_ids.append(src.id)
                    if src.base_url and not base_url:
                        base_url = src.base_url

            # Stream from MLOps orchestrator
            # mlops handles: classification -> RAG search -> planning -> execution
            # Track step_number -> action_name so we can populate it
            # in step_complete/step_error events (which may lack it)
            step_counter = 1
            step_action_map: dict[int, str] = {}
            step_description_map: dict[int, str] = {}

            try:
                async for chunk in mlops_client.orchestrate_stream(
                    query=query_text,
                    endpoints=[],
                    base_url=base_url,
                    history=chat_history,
                    swagger_source_ids=all_source_ids or None,
                ):
                    event_type = chunk.pop("event_type", "")

                    if event_type == "chat_token":
                        await websocket.send_json({
                            "type": "chat_token",
                            "data": {"token": chunk.get("token", "")}
                        })

                    elif event_type == "reasoning":
                        await websocket.send_json({
                            "type": "reasoning",
                            "data": {"content": chunk.get("content", "")}
                        })

                    elif event_type == "confirmation_required":
                        await websocket.send_json({
                            "type": "confirmation_required",
                            "data": {
                                "step": chunk.get("step"),
                                "confirmation_id": chunk.get("confirmation_id"),
                                "action": chunk.get("action", ""),
                                "endpoint_method": chunk.get("endpoint_method", ""),
                                "endpoint_path": chunk.get("endpoint_path", ""),
                                "payload_summary": chunk.get("payload_summary", ""),
                            }
                        })

                    elif event_type in ("step_start", "step_complete", "step_error"):
                        step_num = chunk.get("step", step_counter)
                        action_name = chunk.get("action", "")
                        description = chunk.get("description", "")

                        if event_type == "step_start":
                            status = "running"
                            step_action_map[step_num] = action_name
                            step_description_map[step_num] = description
                        elif event_type == "step_complete":
                            status = "completed"
                            action_name = action_name or step_action_map.get(step_num, "processing")
                            description = description or step_description_map.get(step_num, "")
                        else:
                            status = "error"
                            action_name = action_name or step_action_map.get(step_num, "processing")
                            description = description or step_description_map.get(step_num, "")

                        orchestration_step = OrchestrationStep(
                            step=step_num,
                            action=action_name,
                            description=description,
                            status=status,
                            result=chunk.get("result"),
                        )
                        await websocket.send_json(
                            {"type": "step", "data": orchestration_step.model_dump()}
                        )

                    elif event_type == "result":
                        result_data = chunk.get("data", {})
                        result_type = chunk.get("type", "text")

                        # Handle empty result data gracefully
                        if not result_data or result_data == {}:
                            result_type = "text"
                            result_data = {"content": "The query completed but returned no data."}

                        result = ResultResponse(
                            type=result_type,
                            data=result_data,
                            metadata=chunk.get("metadata"),
                        )
                        await websocket.send_json(
                            {"type": "result", "data": result.model_dump()}
                        )

            except Exception as stream_exc:
                logger.error("Streaming orchestration failed: %s", stream_exc)
                await websocket.send_json(
                    {"type": "error", "data": {"message": f"Orchestration stream failed: {stream_exc}"}}
                )

            # Send done signal
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
