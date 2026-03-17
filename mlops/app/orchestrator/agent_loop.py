"""Agent loop: LLM-driven tool-calling orchestration."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from app.config import get_settings
from app.llm.kimi_client import get_llm_client
from app.mcp.api_executor import execute_api_call
from app.mcp.data_processor import process_data
from app.schemas.models import ResultResponse, OrchestrationStreamEvent

logger = logging.getLogger(__name__)

ORCHESTRATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "call_api",
            "description": "Execute an HTTP request to an API endpoint. Use the base_url + endpoint path to form the full URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                    "url": {"type": "string", "description": "Full URL to call"},
                    "params": {"type": "object", "description": "Query parameters"},
                    "headers": {"type": "object", "description": "HTTP headers"},
                    "body": {"type": "object", "description": "Request body for POST/PUT/PATCH"},
                },
                "required": ["method", "url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_data",
            "description": "Process data using pandas operations like filter, sort, group_by, aggregate",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "The data to process (from a previous API call)"},
                    "operations": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of operations: filter, sort, group_by, aggregate, select_columns, limit",
                    },
                },
                "required": ["data", "operations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python code in a sandboxed environment. Has pandas, numpy, matplotlib, plotly available. Code can generate files (charts, CSVs, etc.) that will be served via URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {"type": "integer", "description": "Execution timeout in seconds (max 60)", "default": 30},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "format_result",
            "description": "Format the final result for display. Call this when you have the data ready to present.",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_type": {"type": "string", "enum": ["text", "list", "table", "chart", "image", "map", "dashboard"]},
                    "data": {"type": "object", "description": "The formatted data"},
                    "summary": {"type": "string", "description": "Brief summary of the results"},
                },
                "required": ["output_type", "data"],
            },
        },
    },
]

AGENT_SYSTEM_PROMPT = """You are an API orchestration agent. The user wants to extract information from APIs.

You have access to these tools:
- call_api: Make HTTP requests to API endpoints
- process_data: Transform data with pandas operations (filter, sort, group_by, etc.)
- execute_code: Run Python code in a sandbox (pandas, numpy, matplotlib, plotly available). Use for data analysis, calculations, and generating charts/images.
- format_result: Format the final output for the user (MUST be called to complete the task)

Available API endpoints:
{endpoints}

Target API base URL: {base_url}

Instructions:
1. Analyze the user's query
2. Decide which API endpoints to call
3. Call them using call_api with the full URL (base_url + path)
4. Optionally process the returned data with process_data
5. For complex analysis, calculations, or chart generation, use execute_code
6. ALWAYS call format_result as the last step with the appropriate output_type:
   - "table" for structured records (provide columns and rows)
   - "chart" for statistics/trends (provide chart_type, labels, datasets)
   - "image" for generated images/charts from execute_code (provide url or images array)
   - "map" for geographic data (provide center, zoom, markers)
   - "list" for simple items (provide items array)
   - "text" for summaries (provide content string)
"""


async def _execute_tool_call(name: str, arguments: dict, context: dict) -> dict:
    """Execute a tool call and return the result."""
    if name == "call_api":
        base_url = context.get("base_url", "")
        allowed = [base_url] if base_url else None

        # Check if this is a mutating action that needs confirmation
        # (skip if already handled by streaming path)
        pre_approved = context.get("_confirmation_approved_steps", set())
        current_step = context.get("_agent_step_counter", 1)
        method = arguments.get("method", "GET").upper()
        if method in ("POST", "PUT", "PATCH", "DELETE") and current_step not in pre_approved:
            from app.orchestrator.executor import _request_confirmation
            from app.schemas.models import OrchestrationStep

            # Build a minimal OrchestrationStep for the confirmation API
            confirm_step = OrchestrationStep(
                step=current_step,
                action="api_call",
                description=f"{method} {arguments.get('url', '')}",
                status="running",
                endpoint={
                    "method": method,
                    "path": arguments.get("url", ""),
                },
            )
            confirmation = await _request_confirmation(confirm_step, context)
            if confirmation == "rejected":
                return {"error": "Action rejected by user", "confirmation": "rejected", "success": False}
            # On error/timeout, proceed (matches existing plan-execute behavior)

        try:
            result = await execute_api_call(
                method=arguments.get("method", "GET"),
                url=arguments.get("url", ""),
                params=arguments.get("params"),
                headers=arguments.get("headers"),
                body=arguments.get("body"),
                allowed_base_urls=allowed,
            )
            return result
        except Exception as e:
            return {"error": str(e), "success": False}

    elif name == "process_data":
        try:
            data = arguments.get("data", {})
            operations = arguments.get("operations", [])
            result = process_data(data, operations)
            return result
        except Exception as e:
            return {"error": str(e)}

    elif name == "execute_code":
        import json as _json
        from app.mcp.code_sandbox import execute_code
        try:
            code = arguments.get("code", "")
            timeout = arguments.get("timeout", 30)

            # Inject context data so code can use `data` variable
            ctx_data = context.get("_last_api_result")
            if ctx_data is not None:
                data_json = _json.dumps(ctx_data, default=str, ensure_ascii=False)
                code = f"import json as _json\ndata = _json.loads({repr(data_json)})\n" + code

            result = await execute_code(code, timeout=timeout)

            # Store API result for future code steps
            if result.get("success"):
                stdout = result.get("stdout", "").strip()
                files = result.get("files", [])
                images = [f for f in files if f.get("filename", "").endswith(('.png', '.jpg', '.jpeg', '.svg'))]
                if images:
                    return {"files": files, "stdout": stdout, "success": True}
                if stdout:
                    try:
                        return _json.loads(stdout)
                    except _json.JSONDecodeError:
                        return {"content": stdout, "success": True}
                return {"content": "Code executed (no output)", "success": True}
            return {"error": result.get("error", "Code failed"), "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    elif name == "format_result":
        return arguments  # Pass through to be used as the final result

    return {"error": f"Unknown tool: {name}"}


async def run_agent_loop(
    query: str,
    endpoints: list[dict],
    context: dict | None = None,
) -> ResultResponse:
    """Run the agent loop with tool calling."""
    settings = get_settings()
    max_iterations = settings.orchestration_max_iterations or 100  # 0 = unlimited (capped at 100 safety)
    client = get_llm_client()

    base_url = (context or {}).get("base_url", "")
    endpoints_json = json.dumps(endpoints, indent=2, ensure_ascii=False)

    system_prompt = AGENT_SYSTEM_PROMPT.format(
        endpoints=endpoints_json[:10000],
        base_url=base_url or "Not specified",
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    final_result: dict | None = None
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info("Agent loop iteration %d", iteration)

        response = await client._client.chat.completions.create(
            model=client._model,
            messages=messages,
            tools=ORCHESTRATION_TOOLS,
            tool_choice="auto" if not final_result else "none",
            temperature=0.2,
            max_tokens=4096,
        )

        choice = response.choices[0]

        # If the model gives a text response without tool calls, we're done
        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            if choice.message.content:
                # Model gave a text answer - wrap as text result
                final_result = {
                    "output_type": "text",
                    "data": {"content": choice.message.content},
                    "summary": "",
                }
            break

        # Process tool calls
        messages.append(choice.message.model_dump())

        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logger.info("Agent calling tool: %s", fn_name)
            ctx = context or {}
            result = await _execute_tool_call(fn_name, fn_args, ctx)

            # Store API result in context so execute_code can access it
            if fn_name == "call_api" and isinstance(result, dict) and result.get("success"):
                ctx["_last_api_result"] = result.get("body", result)

            # Check if this is format_result (final step)
            if fn_name == "format_result":
                final_result = result

            # Truncate large results before adding to messages
            result_str = json.dumps(result, default=str, ensure_ascii=False)
            if len(result_str) > 10000:
                result_str = result_str[:10000] + "...[truncated]"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

        if final_result:
            break

    if not final_result:
        return ResultResponse(
            type="text",
            data={"content": "The agent could not complete the task within the iteration limit."},
            metadata={"status": "incomplete", "iterations": max_iterations},
        )

    return ResultResponse(
        type=final_result.get("output_type", "text"),
        data=final_result.get("data", {}),
        metadata={
            "status": "completed",
            "mode": "agent",
            "summary": final_result.get("summary", ""),
        },
    )


async def run_agent_loop_stream(
    query: str,
    endpoints: list[dict],
    context: dict | None = None,
) -> AsyncGenerator[OrchestrationStreamEvent, None]:
    """Streaming version of the agent loop - yields events as tool calls happen."""
    settings = get_settings()
    max_iterations = settings.orchestration_max_iterations or 100
    client = get_llm_client()

    base_url = (context or {}).get("base_url", "")
    endpoints_json = json.dumps(endpoints, indent=2, ensure_ascii=False)

    system_prompt = AGENT_SYSTEM_PROMPT.format(
        endpoints=endpoints_json[:10000],
        base_url=base_url or "Not specified",
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    # Emit plan event
    yield OrchestrationStreamEvent(
        event="plan",
        data={"steps": [], "total": 0, "mode": "agent"},
    )

    final_result: dict | None = None
    step_counter = 1
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = await client._client.chat.completions.create(
            model=client._model,
            messages=messages,
            tools=ORCHESTRATION_TOOLS,
            tool_choice="auto" if not final_result else "none",
            temperature=0.2,
            max_tokens=4096,
        )

        choice = response.choices[0]

        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            if choice.message.content and not final_result:
                final_result = {
                    "output_type": "text",
                    "data": {"content": choice.message.content},
                }
            break

        messages.append(choice.message.model_dump())

        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            # Emit step_start
            yield OrchestrationStreamEvent(
                event="step_start",
                data={"step": step_counter, "action": fn_name, "description": f"Calling {fn_name}"},
            )

            # For mutating API calls, emit confirmation_required before executing
            exec_context = context or {}
            if fn_name == "call_api":
                call_method = fn_args.get("method", "GET").upper()
                if call_method in ("POST", "PUT", "PATCH", "DELETE"):
                    from app.orchestrator.executor import _create_confirmation, _poll_confirmation
                    from app.schemas.models import OrchestrationStep as _Step

                    _confirm_step = _Step(
                        step=step_counter,
                        action="api_call",
                        description=f"{call_method} {fn_args.get('url', '')}",
                        status="running",
                        endpoint={"method": call_method, "path": fn_args.get("url", "")},
                    )
                    _conf_data = await _create_confirmation(_confirm_step, exec_context)
                    if _conf_data:
                        yield OrchestrationStreamEvent(
                            event="confirmation_required",
                            data={
                                "step": step_counter,
                                "confirmation_id": _conf_data["id"],
                                "action": _conf_data.get("action", ""),
                                "endpoint_method": _conf_data.get("endpoint_method", ""),
                                "endpoint_path": _conf_data.get("endpoint_path", ""),
                                "payload_summary": _conf_data.get("payload_summary", ""),
                            },
                        )
                        _resolution = await _poll_confirmation(_conf_data["id"])
                        if _resolution == "rejected":
                            result_str = json.dumps({"error": "Action rejected by user", "confirmation": "rejected"})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result_str,
                            })
                            yield OrchestrationStreamEvent(
                                event="step_error",
                                data={"step": step_counter, "error": "Action rejected by user"},
                            )
                            step_counter += 1
                            continue
                        # Approved or timeout-fallthrough — mark step as pre-approved
                        exec_context["_confirmation_approved_steps"] = exec_context.get("_confirmation_approved_steps", set())
                        exec_context["_confirmation_approved_steps"].add(step_counter)

            exec_context["_agent_step_counter"] = step_counter
            result = await _execute_tool_call(fn_name, fn_args, exec_context)

            if fn_name == "format_result":
                final_result = result

            result_str = json.dumps(result, default=str, ensure_ascii=False)
            if len(result_str) > 10000:
                result_str = result_str[:10000] + "...[truncated]"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

            # Emit step_complete
            yield OrchestrationStreamEvent(
                event="step_complete",
                data={"step": step_counter, "result": result if len(json.dumps(result, default=str)) < 5000 else {"truncated": True}},
            )
            step_counter += 1

        if final_result:
            break

    # Emit final result
    if not final_result:
        final_result = {
            "output_type": "text",
            "data": {"content": "Agent could not complete the task."},
        }

    yield OrchestrationStreamEvent(
        event="result",
        data={
            "type": final_result.get("output_type", "text"),
            "data": final_result.get("data", {}),
            "metadata": {"status": "completed", "mode": "agent"},
        },
    )
