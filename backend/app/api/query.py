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
async def ws_query(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming orchestration.

    Protocol:
    - Client sends JSON: {"query": "...", "swagger_source_ids": [1, 2] | null}
    - Server streams JSON messages back:
      - OrchestrationStep messages during processing
      - Final ResultResponse message
    """
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

            swagger_source_ids = message.get("swagger_source_ids")
            chat_history = message.get("history", [])

            # List all endpoints for selected sources (no RAG, no embedding).
            # The LLM decides which endpoints are relevant.
            base_url: str | None = None

            async with async_session_factory() as db:
                stmt = sa_select(ApiEndpoint).join(
                    SwaggerSource, ApiEndpoint.swagger_source_id == SwaggerSource.id
                ).where(SwaggerSource.base_url.isnot(None))
                if swagger_source_ids:
                    stmt = stmt.where(ApiEndpoint.swagger_source_id.in_(swagger_source_ids))
                result = await db.execute(stmt.order_by(ApiEndpoint.id))
                relevant_endpoints = list(result.scalars().all())

                # Find base_url: pick the first source that has one
                source_cache: dict[int, SwaggerSource | None] = {}
                for ep in relevant_endpoints:
                    sid = ep.swagger_source_id
                    if sid not in source_cache:
                        source_cache[sid] = await db.get(SwaggerSource, sid)
                    src = source_cache[sid]
                    if src and src.base_url and not base_url:
                        base_url = src.base_url

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
                    }
                    for ep in relevant_endpoints
                ]

            # Send initial step with informative description
            if endpoints_payload:
                endpoint_names = [
                    f"{ep['method']} {ep['path']}"
                    for ep in endpoints_payload[:3]
                ]
                names_str = ", ".join(endpoint_names)
                if len(endpoints_payload) > 3:
                    names_str += f" and {len(endpoints_payload) - 3} more"
                search_description = f"{len(endpoints_payload)} endpoints available from selected APIs: {names_str}"
            else:
                search_description = "No endpoints available."

            search_step = OrchestrationStep(
                step=1,
                action="search",
                description=search_description,
                status="completed",
                result={"count": len(endpoints_payload)},
            )
            await websocket.send_json(
                {"type": "step", "data": search_step.model_dump()}
            )

            # Short-circuit: no endpoints available
            if not endpoints_payload:
                result = ResultResponse(
                    type="text",
                    data={"content": "No API endpoints available. Please upload a Swagger spec with a base URL configured."},
                    metadata={"status": "completed"},
                )
                await websocket.send_json(
                    {"type": "result", "data": result.model_dump()}
                )
                await websocket.send_json({"type": "done", "data": {}})
                continue

            # Stream from MLOps orchestrator (pass ORIGINAL query so LLM sees user's language)
            # Track step_number -> action_name so we can populate it
            # in step_complete/step_error events (which may lack it)
            step_counter = 2
            step_action_map: dict[int, str] = {}
            step_description_map: dict[int, str] = {}

            try:
                async for chunk in mlops_client.orchestrate_stream(
                    query=query_text,
                    endpoints=endpoints_payload,
                    base_url=base_url,
                    history=chat_history,
                ):
                    event_type = chunk.pop("event_type", "")

                    if event_type in ("step_start", "step_complete", "step_error"):
                        step_num = chunk.get("step", step_counter)

                        if event_type == "step_start":
                            status = "running"
                            # Store action and description from step_start
                            action_name = chunk.get("action", "processing")
                            description = chunk.get("description", "")
                            step_action_map[step_num] = action_name
                            step_description_map[step_num] = description
                        elif event_type == "step_complete":
                            status = "completed"
                            # Use stored action/description, fall back to chunk values
                            action_name = chunk.get("action") or step_action_map.get(step_num, "processing")
                            description = chunk.get("description") or step_description_map.get(step_num, "")
                        else:  # step_error
                            status = "error"
                            action_name = chunk.get("action") or step_action_map.get(step_num, "processing")
                            description = chunk.get("description") or step_description_map.get(step_num, "")

                        orchestration_step = OrchestrationStep(
                            step=step_counter,
                            action=action_name,
                            description=description,
                            status=status,
                            result=chunk.get("result"),
                        )
                        await websocket.send_json(
                            {"type": "step", "data": orchestration_step.model_dump()}
                        )
                        if event_type in ("step_complete", "step_error"):
                            step_counter += 1

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
