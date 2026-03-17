"""Plan execution: runs orchestration steps sequentially, calling APIs and processing data."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.config import get_settings
from app.llm.kimi_client import get_kimi_client
from app.mcp.api_executor import execute_api_call
from app.mcp.data_processor import process_data
from app.schemas.models import OrchestrationStep, ResultResponse, OrchestrationStreamEvent

logger = logging.getLogger(__name__)

# Per-step execution timeout in seconds
_STEP_TIMEOUT = 120.0

# Confirmation polling settings
_CONFIRM_POLL_INTERVAL = 2.0  # seconds between polls
_CONFIRM_TIMEOUT = 300.0  # max wait time for confirmation (5 min)
_BACKEND_URL = "http://backend:8000"


async def _request_confirmation(step: OrchestrationStep, context: dict) -> str:
    """Request confirmation for a mutating API action.

    Creates a confirmation record in the backend and polls until
    approved or rejected. Returns 'approved', 'rejected', or 'error'.
    """
    import httpx

    method = step.endpoint.get("method", "POST") if step.endpoint else "POST"
    path = step.endpoint.get("path", "/unknown") if step.endpoint else "/unknown"
    correlation_id = context.get("correlation_id", "unknown")
    payload_summary = step.description[:200] if step.description else ""

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Create confirmation request
            resp = await client.post(
                f"{_BACKEND_URL}/api/v1/confirmations",
                json={
                    "correlation_id": correlation_id,
                    "action": step.description or step.action,
                    "endpoint_method": method,
                    "endpoint_path": path,
                    "payload_summary": payload_summary,
                },
            )
            if resp.status_code != 201:
                logger.warning("Failed to create confirmation: %s", resp.text)
                return "error"

            confirmation_id = resp.json().get("id")
            logger.info("Confirmation %d created for %s %s, polling...", confirmation_id, method, path)

            # Poll for resolution
            elapsed = 0.0
            while elapsed < _CONFIRM_TIMEOUT:
                await asyncio.sleep(_CONFIRM_POLL_INTERVAL)
                elapsed += _CONFIRM_POLL_INTERVAL

                check = await client.get(f"{_BACKEND_URL}/api/v1/confirmations?status=pending")
                if check.status_code != 200:
                    continue

                pending = check.json()
                # If our confirmation is no longer pending, it was resolved
                still_pending = any(c["id"] == confirmation_id for c in pending)
                if not still_pending:
                    # Check if it was approved or rejected
                    for status in ("approved", "rejected"):
                        resolved = await client.get(f"{_BACKEND_URL}/api/v1/confirmations?status={status}")
                        if resolved.status_code == 200:
                            for c in resolved.json():
                                if c["id"] == confirmation_id:
                                    logger.info("Confirmation %d resolved: %s", confirmation_id, status)
                                    return status
                    # If we can't find it in either, assume approved
                    return "approved"

            logger.warning("Confirmation %d timed out after %.0fs", confirmation_id, _CONFIRM_TIMEOUT)
            return "error"

    except Exception as exc:
        logger.warning("Confirmation request failed: %s", exc)
        return "error"


def _truncate_for_llm(context: dict, max_chars: int = 50000) -> dict:
    """Truncate step results to fit LLM context window."""
    truncated: dict = {"step_results": {}}
    # Preserve non-step_results keys (e.g. base_url)
    for key, value in context.items():
        if key != "step_results":
            truncated[key] = value

    step_results = context.get("step_results", {})
    if not step_results:
        return truncated
    per_step_limit = max(max_chars // len(step_results), 5000)
    for key, value in step_results.items():
        serialized = json.dumps(value, default=str)
        if len(serialized) > per_step_limit:
            if isinstance(value, dict) and "body" in value:
                value = {**value, "body": str(value["body"])[:per_step_limit] + "...[truncated]"}
            elif isinstance(value, list) and len(value) > 20:
                value = value[:20]  # Keep first 20 items
        truncated["step_results"][key] = value
    return truncated


def _get_mock_result_data(step: OrchestrationStep, context: dict) -> dict:
    """Return mock data for a step based on the format_output type."""
    from app.llm.mock_client import (
        MOCK_TABLE_DATA, MOCK_CHART_DATA, MOCK_MAP_DATA,
        MOCK_LIST_DATA, MOCK_TEXT_DATA,
    )
    output_type = "text"
    if step.parameters:
        output_type = step.parameters.get("output_type", "text")

    data_map = {
        "table": MOCK_TABLE_DATA,
        "chart": MOCK_CHART_DATA,
        "map": MOCK_MAP_DATA,
        "list": MOCK_LIST_DATA,
        "text": MOCK_TEXT_DATA,
    }
    return data_map.get(output_type, MOCK_TEXT_DATA)


def _reshape_output_data(output_type: str, data: dict | list | None, config: dict | None = None) -> dict:
    """Reshape data to match frontend expectations for a given output_type.

    Args:
        output_type: One of "table", "chart", "map", "list", "text".
        data: The raw data from previous steps.
        config: Optional config from the LLM format instructions.

    Returns:
        Dict shaped to match frontend expectations.
    """
    if data is None:
        if output_type == "text":
            return {"content": "The operation completed but returned no data."}
        return {}

    if isinstance(data, list):
        # Wrap list data in a dict
        data = {"items": data}

    if output_type == "table":
        # Ensure {"columns": [...], "rows": [...]}
        if "columns" in data and "rows" in data:
            return data
        # If we have a list of records under "data" or "items"
        records = data.get("data", data.get("items", data.get("body", [])))
        if isinstance(records, list) and records and isinstance(records[0], dict):
            columns = list(records[0].keys())
            return {"columns": columns, "rows": records}
        # Fallback: return as-is
        return data

    elif output_type == "chart":
        # Ensure {"chart_type": "...", "labels": [...], "datasets": [...]}
        if "labels" in data and "datasets" in data:
            return data
        chart_type = (config or {}).get("chart_type", data.get("chart_type", "bar"))
        # Try to infer from data
        if "data" in data and isinstance(data["data"], list):
            records = data["data"]
            if records and isinstance(records[0], dict):
                keys = list(records[0].keys())
                if len(keys) >= 2:
                    labels = [str(r.get(keys[0], "")) for r in records]
                    datasets = [{"label": keys[1], "data": [r.get(keys[1], 0) for r in records]}]
                    return {"chart_type": chart_type, "labels": labels, "datasets": datasets}
        return {**data, "chart_type": chart_type}

    elif output_type == "map":
        # Ensure {"center": [...], "zoom": N, "markers": [...]}
        if "markers" in data and "center" in data:
            return data
        # Try to extract from points
        markers = data.get("markers", data.get("points", []))
        if markers:
            avg_lat = sum(m.get("lat", 0) for m in markers) / len(markers)
            avg_lng = sum(m.get("lng", 0) for m in markers) / len(markers)
            return {
                "center": [avg_lat, avg_lng],
                "zoom": data.get("zoom", 10),
                "markers": markers,
            }
        return data

    elif output_type == "list":
        # Ensure {"items": [...]}
        if "items" in data:
            return data
        items = data.get("data", [])
        if isinstance(items, list):
            return {"items": items}
        return {"items": [str(data)]}

    elif output_type == "text":
        # Ensure {"content": "..."}
        if "content" in data and isinstance(data["content"], str):
            if data["content"] in ("{}", "null", "[]", ""):
                return {"content": "The operation completed but returned no data."}
            return data
        if "error" in data:
            return {"content": f"API error: {data['error']}"}
        # Aggregate results: {"aggregate": "mean", "column": "avg_check", "value": 7500}
        if "value" in data and ("aggregate" in data or "column" in data):
            col = data.get("column", "")
            func = data.get("aggregate", data.get("function", ""))
            val = data["value"]
            if isinstance(val, float):
                val = round(val, 2)
            return {"content": f"**{func}({col})** = {val}"}
        # Single key-value pairs — format nicely
        content = data.get("content", data.get("message", ""))
        if not content:
            lines = []
            for k, v in data.items():
                if isinstance(v, float):
                    v = round(v, 2)
                elif isinstance(v, list):
                    # Summarize lists instead of dumping raw
                    if v and isinstance(v[0], dict):
                        items = []
                        for item in v[:10]:
                            label = item.get("name", item.get("segment", item.get("status", item.get("tier", ""))))
                            count = item.get("count", item.get("value", ""))
                            items.append(f"  - {label}: {count}")
                        v = "\n" + "\n".join(items)
                    else:
                        v = ", ".join(str(x) for x in v[:10])
                lines.append(f"**{k}**: {v}")
            content = "\n".join(lines) if lines else json.dumps(data, default=str, ensure_ascii=False)
            if content in ("{}", "null", "[]"):
                return {"content": "The operation completed but returned no data."}
        return {"content": str(content)}

    elif output_type == "image":
        if isinstance(data, dict) and "files" in data:
            images = [f for f in data["files"] if f.get("filename", "").endswith(('.png', '.jpg', '.jpeg', '.svg'))]
            if len(images) == 1:
                return {"url": images[0]["url"], "title": images[0].get("filename", "")}
            if images:
                return {"images": [{"url": f["url"], "title": f.get("filename", "")} for f in images]}
        if isinstance(data, dict) and "url" in data:
            return data
        return {"content": "No images generated"}

    # dashboard or unknown: return as-is
    return data


async def _execute_single_step(
    step: OrchestrationStep,
    context: dict,
) -> OrchestrationStep:
    """Execute a single orchestration step and update its status and result.

    Args:
        step: The step to execute.
        context: Accumulated context from previous steps.

    Returns:
        The step with updated status and result.
    """
    step.status = "running"
    client = get_kimi_client()
    settings = get_settings()

    try:
        if settings.mock_mode:
            # Mock mode: simulate step execution with delays
            await asyncio.sleep(0.5)
            if step.action == "api_call":
                step.result = {"status_code": 200, "success": True, "body": {"data": "mock response"}, "elapsed_ms": 45.2}
            elif step.action == "format_output":
                step.result = _get_mock_result_data(step, context)
            else:
                step.result = {"processed": True, "rows": 5}
            step.status = "completed"
            return step

        if step.action == "api_call":
            # Use the endpoint's own base_url (from its swagger source) instead of
            # a single global base_url so that multi-source queries hit the correct server.
            if step.endpoint:
                ep_base_url = step.endpoint.get("base_url", "") or context.get("base_url", "")
            else:
                ep_base_url = context.get("base_url", "")
            base_url = ep_base_url

            # No base_url means the swagger source didn't have a server URL — can't call APIs
            if not base_url:
                step.status = "error"
                step.error = "No API base URL configured. The uploaded Swagger spec is missing a server URL."
                step.result = {"error": step.error}
                return step

            # Check if this is a mutating action that needs confirmation
            method = "GET"
            if step.endpoint:
                method = step.endpoint.get("method", "GET").upper()
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                confirmation = await _request_confirmation(step, context)
                if confirmation == "rejected":
                    step.status = "error"
                    step.error = "Action rejected by system owner"
                    step.result = {"error": step.error, "confirmation": "rejected"}
                    return step
                elif confirmation == "error":
                    logger.warning("Confirmation check failed, proceeding anyway for hackathon demo")

            # Use truncated context for LLM call
            execution_instructions = await asyncio.wait_for(
                client.execute_step(step, _truncate_for_llm(context)),
                timeout=_STEP_TIMEOUT,
            )

            if "error" in execution_instructions:
                step.status = "error"
                step.error = execution_instructions["error"]
                step.result = execution_instructions
                return step

            # Construct full URL by combining base_url with endpoint path if needed
            url = execution_instructions.get("url", "")
            if url and not url.startswith(("http://", "https://")):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")
            elif not url and step.endpoint:
                path = step.endpoint.get("path", "")
                if path:
                    url = base_url.rstrip("/") + "/" + path.lstrip("/")

            # Set allowed base URLs for security — block LLM-hallucinated URLs
            allowed_base_urls = [base_url]

            api_result = await asyncio.wait_for(
                execute_api_call(
                    method=execution_instructions.get("method", "GET"),
                    url=url,
                    params=execution_instructions.get("params"),
                    headers=execution_instructions.get("headers"),
                    body=execution_instructions.get("body"),
                    allowed_base_urls=allowed_base_urls,
                ),
                timeout=_STEP_TIMEOUT,
            )

            step.result = api_result
            if api_result.get("success"):
                step.status = "completed"
            else:
                step.status = "error"
                step.error = api_result.get("error", f"API returned status {api_result.get('status_code')}")

        elif step.action == "data_process":
            # Get processing instructions from step parameters or ask the LLM
            operations = []
            if step.parameters and "operations" in step.parameters:
                operations = step.parameters["operations"]
            else:
                execution_instructions = await asyncio.wait_for(
                    client.execute_step(step, _truncate_for_llm(context)),
                    timeout=_STEP_TIMEOUT,
                )
                operations = execution_instructions.get("operations", [])

            # Validate operations - ensure it's a list
            if not isinstance(operations, list):
                logger.warning("Invalid operations type: %s, using empty list", type(operations).__name__)
                operations = []

            # Filter out operations without a valid type
            valid_operations = []
            for op in operations:
                if isinstance(op, dict) and op.get("type"):
                    valid_operations.append(op)
                else:
                    logger.warning("Skipping invalid operation: %s", op)

            if not valid_operations:
                # Use sensible defaults: just pass data through
                logger.info("No valid operations, using default passthrough")
                valid_operations = [{"type": "limit", "n": 100}]

            # Extract body/items from step results for merge operations
            extracted_results = {}
            for k, v in context.get("step_results", {}).items():
                if isinstance(v, dict):
                    extracted_results[k] = v.get("body", v.get("items", v.get("data", v)))
                else:
                    extracted_results[k] = v

            # Smart input selection: when a merge operation references certain
            # steps as the right side, the *left* side (input) should be a
            # different step.  _get_latest_data always picks the highest-numbered
            # step, which may be the merge source itself.
            input_data = _get_latest_data(context)

            # Collect step keys referenced as merge sources
            merge_sources: set[str] = set()
            for op in valid_operations:
                if op.get("type") == "merge":
                    src = str(op.get("source", ""))
                    if src:
                        merge_sources.add(src)

            if merge_sources:
                step_results_dict = context.get("step_results", {})
                latest_key = str(max(int(k) for k in step_results_dict.keys()))
                if latest_key in merge_sources and len(step_results_dict) > 1:
                    # The latest step is a merge source — use a different step as input
                    # Pick the highest-numbered step that is NOT a merge source
                    candidate_keys = sorted(
                        (int(k) for k in step_results_dict if k not in merge_sources),
                        reverse=True,
                    )
                    if candidate_keys:
                        alt_key = str(candidate_keys[0])
                        alt_result = step_results_dict[alt_key]
                        if isinstance(alt_result, dict):
                            if "status_code" in alt_result and "success" in alt_result:
                                input_data = alt_result.get("body") if alt_result.get("success") else input_data
                            else:
                                input_data = alt_result.get("data", alt_result.get("body", alt_result))
                        else:
                            input_data = alt_result
                        logger.info(
                            "data_process: switched input from step %s (merge source) to step %s",
                            latest_key, alt_key,
                        )

            if input_data is None:
                step.status = "error"
                step.error = "No data available from previous steps"
                step.result = {"error": step.error}
                return step

            process_result = process_data(input_data, valid_operations, step_results=extracted_results)
            step.result = process_result
            step.status = "completed"

        elif step.action == "aggregate":
            # Combine results from multiple previous steps
            execution_instructions = await asyncio.wait_for(
                client.execute_step(step, _truncate_for_llm(context)),
                timeout=_STEP_TIMEOUT,
            )
            step.result = _aggregate_context_data(context, execution_instructions)
            step.status = "completed"

        elif step.action == "format_output":
            # Get data for formatting
            step_results = context.get("step_results", {})
            if step_results:
                latest_data = _get_latest_data(context)
            else:
                # No API calls were made — use available_endpoints if present
                available_eps = context.get("available_endpoints")
                if available_eps:
                    latest_data = [
                        {"method": ep.get("method", ""), "path": ep.get("path", ""),
                         "summary": ep.get("summary", ""), "description": ep.get("description", "")}
                        for ep in available_eps
                    ]
                else:
                    latest_data = None

            # Use step parameters hint if available
            output_type = (step.parameters or {}).get("output_type", "")

            # Auto-detect from data structure if no hint
            if not output_type:
                if isinstance(latest_data, list):
                    if latest_data and isinstance(latest_data[0], dict):
                        output_type = "table"
                    else:
                        output_type = "list"
                elif isinstance(latest_data, dict):
                    if "error" in latest_data and len(latest_data) == 1:
                        output_type = "text"
                    elif any(k in latest_data for k in ("markers", "center", "coordinates")):
                        output_type = "map"
                    elif any(k in latest_data for k in ("labels", "datasets", "chart_type")):
                        output_type = "chart"
                    elif any(k in latest_data for k in ("columns", "rows")):
                        output_type = "table"
                    elif "value" in latest_data and ("aggregate" in latest_data or "column" in latest_data):
                        output_type = "text"  # aggregate result
                    elif len(latest_data) <= 5 and not any(isinstance(v, (list, dict)) for v in latest_data.values()):
                        output_type = "text"  # small dict with scalar values
                    elif "items" in latest_data and isinstance(latest_data.get("items"), list):
                        items = latest_data["items"]
                        output_type = "table" if items and isinstance(items[0], dict) else "list"
                    else:
                        # Single object with data fields — show as single-row table
                        # unless it only has metadata-like keys (content, message, error)
                        non_meta_keys = [
                            k for k in latest_data.keys()
                            if k not in ("content", "message", "error", "status")
                        ]
                        if non_meta_keys and len(latest_data) >= 2:
                            output_type = "table"
                        else:
                            output_type = "text"
                elif latest_data is None:
                    output_type = "text"
                else:
                    output_type = "text"

            # For single dicts being shown as table, wrap in a list ONLY if
            # it's truly a single record (no "items", "data", or "body" keys that
            # _reshape_output_data knows how to extract from)
            if output_type == "table" and isinstance(latest_data, dict):
                if ("columns" not in latest_data and "rows" not in latest_data
                        and "items" not in latest_data and "data" not in latest_data
                        and "body" not in latest_data):
                    latest_data = [latest_data]

            # For text output, ask LLM to formulate a human answer
            if output_type == "text" and latest_data is not None:
                try:
                    user_query = context.get("original_query", step.description)
                    data_summary = json.dumps(latest_data, default=str, ensure_ascii=False)[:2000]
                    answer = await asyncio.wait_for(
                        client.chat(
                            [
                                {"role": "system", "content": "You are an API assistant. Answer the user's question based on the data. Be concise. Answer in the user's language."},
                                {"role": "user", "content": f"Question: {user_query}\n\nData from API:\n{data_summary}\n\nAnswer the question directly."},
                            ],
                            temperature=0.2,
                            max_tokens=512,
                        ),
                        timeout=30,
                    )
                    shaped_data = {"content": answer.strip()}
                except Exception as e:
                    logger.warning("LLM format failed, falling back to raw: %s", e)
                    shaped_data = _reshape_output_data(output_type, latest_data, {})
            else:
                shaped_data = _reshape_output_data(output_type, latest_data, {})

            # Final guard: never store empty/meaningless data
            if shaped_data is None or shaped_data == {}:
                output_type = "text"
                shaped_data = {"content": "The operation completed but returned no data."}

            step.result = {
                "output_type": output_type,
                "data": shaped_data,
                "config": {},
            }
            step.status = "completed"

        elif step.action == "execute_code":
            from app.mcp.code_sandbox import execute_code
            # Get code from step parameters (planner should include it)
            code = ""
            if step.parameters and step.parameters.get("code"):
                code = step.parameters["code"]

            if not code:
                logger.warning("No code in execute_code step, passing data through")
                prev_data = _get_latest_data(context)
                if prev_data is None:
                    prev_data = {}
                if isinstance(prev_data, list):
                    step.result = {"data": prev_data}
                elif isinstance(prev_data, dict):
                    step.result = prev_data
                else:
                    step.result = {"data": prev_data}
                step.status = "completed"
                return step

            if not code:
                step.status = "error"
                step.error = "No code provided"
                step.result = {"error": step.error}
                return step

            # Inject ALL previous step results so code can access any step's data
            step_results = context.get("step_results", {})
            data_preamble = "import json as _json\n"

            # `data` = latest step result (most common use case)
            prev_data = _get_latest_data(context)
            if prev_data is not None:
                data_json = json.dumps(prev_data, default=str, ensure_ascii=False)
                data_preamble += f"data = _json.loads({repr(data_json)})\n"

            # `step_results` dict = all step results keyed by step number
            # So code can do: posts = step_results["1"], users = step_results["2"]
            all_results = {}
            for k, v in step_results.items():
                # Extract body/items from API call results
                if isinstance(v, dict):
                    if v.get("body") is not None:
                        all_results[k] = v["body"]
                    elif v.get("items") is not None:
                        all_results[k] = v["items"]
                    elif v.get("data") is not None:
                        all_results[k] = v["data"]
                    else:
                        all_results[k] = v
                else:
                    all_results[k] = v

            results_json = json.dumps(all_results, default=str, ensure_ascii=False)
            data_preamble += f"step_results = _json.loads({repr(results_json)})\n"

            code = data_preamble + code

            sandbox_result = await execute_code(code, timeout=30)

            # Extract meaningful output: stdout is the user-visible result
            if sandbox_result["success"]:
                stdout = sandbox_result.get("stdout", "").strip()
                files = sandbox_result.get("files", [])
                image_files = [f for f in files if f.get("filename", "").endswith(('.png', '.jpg', '.jpeg', '.svg'))]

                if image_files:
                    # Code generated images
                    step.result = {"files": files, "stdout": stdout}
                elif stdout:
                    # Code printed a result — try to parse as JSON for structured data
                    try:
                        parsed = json.loads(stdout)
                        if isinstance(parsed, list):
                            # List of records → wrap for table display
                            step.result = {"items": parsed}
                        elif isinstance(parsed, dict):
                            step.result = parsed
                        else:
                            step.result = {"content": str(parsed)}
                    except json.JSONDecodeError:
                        step.result = {"content": stdout}
                else:
                    step.result = {"content": "Code executed successfully (no output)"}
                step.status = "completed"
            else:
                step.status = "error"
                step.error = sandbox_result.get("error", "Code execution failed")
                step.result = {"error": step.error}

        elif step.action == "error":
            # Error steps from planning phase — store useful error info
            step.status = "error"
            if step.result is None:
                step.result = {"error": step.error or step.description}

        else:
            # Unknown action: ask LLM to handle it
            execution_instructions = await asyncio.wait_for(
                client.execute_step(step, _truncate_for_llm(context)),
                timeout=_STEP_TIMEOUT,
            )
            step.result = execution_instructions
            step.status = "completed"

    except asyncio.TimeoutError:
        logger.warning("Step %d timed out after %.1fs", step.step, _STEP_TIMEOUT)
        # For format_output, fallback to auto-detection instead of failing
        if step.action == "format_output":
            logger.info("format_output timed out, using auto-detection fallback")
            latest_data = _get_latest_data(context)
            auto_type = _determine_output_type(context)
            shaped = _reshape_output_data(auto_type, latest_data, {})
            step.result = {"output_type": auto_type, "data": shaped, "config": {}}
            step.status = "completed"
        else:
            step.status = "error"
            step.error = f"Step timed out after {_STEP_TIMEOUT}s"
            step.result = {"error": step.error}

    except Exception as e:
        logger.error("Error executing step %d: %s", step.step, str(e))
        step.status = "error"
        step.error = str(e)
        step.result = {"error": str(e)}

    return step


def _merge_all_step_results(context: dict) -> list[dict] | None:
    """Merge results from all steps into a flat list of summary records.

    Each API call result becomes one row with a 'source' label.
    If a result is a list, each item gets its own row.
    """
    step_results = context.get("step_results", {})
    merged: list[dict] = []

    for step_num in sorted(step_results.keys(), key=int):
        result = step_results[step_num]
        if not isinstance(result, dict):
            continue

        # Extract body from api_call results
        body = result
        if "status_code" in result and "success" in result:
            if not result.get("success"):
                continue
            body = result.get("body")
            if not body:
                continue

        if isinstance(body, dict) and "data" in body:
            body = body["data"]
        if isinstance(body, dict) and "body" in body:
            body = body["body"]

        if isinstance(body, list):
            merged.extend(
                row if isinstance(row, dict) else {"value": row}
                for row in body
            )
        elif isinstance(body, dict):
            merged.append(body)

    return merged if merged else None


def _get_latest_data(context: dict) -> dict | list | None:
    """Extract the most recent data from the context.

    Looks for results from the highest numbered step.
    For api_call results, extracts the response body and skips
    unsuccessful responses.
    """
    step_results = context.get("step_results", {})
    if not step_results:
        return None

    # Get the highest step number
    max_step = max(int(k) for k in step_results.keys())
    result = step_results[str(max_step)]

    # Try to extract meaningful data
    if isinstance(result, dict):
        # If this looks like an api_call result (has status_code/success),
        # extract the body and check if the call actually succeeded
        if "status_code" in result and "success" in result:
            if not result.get("success"):
                error_msg = result.get("error", f"API returned status {result.get('status_code')}")
                return {"error": error_msg}
            body = result.get("body")
            if body is None or body == {} or body == "":
                return None
            # Unwrap paginated responses: {"body": [...], "meta": {...}}
            if isinstance(body, dict):
                if "body" in body and isinstance(body["body"], list):
                    return body["body"]
                if "data" in body and isinstance(body["data"], list):
                    return body["data"]
                if "items" in body and isinstance(body["items"], list):
                    return body["items"]
            return body

        if "data" in result:
            return result["data"]
        if "body" in result:
            return result["body"]
        return result

    return result


def _aggregate_context_data(context: dict, instructions: dict) -> dict:
    """Aggregate data from multiple steps in the context.

    Args:
        context: Full execution context.
        instructions: Aggregation instructions from the LLM.

    Returns:
        Aggregated data dict.
    """
    step_results = context.get("step_results", {})
    strategy = instructions.get("strategy", "merge")
    keys = instructions.get("keys", [])

    if strategy == "merge":
        merged = {}
        for step_num, result in step_results.items():
            if isinstance(result, dict):
                merged[f"step_{step_num}"] = result
        return {"merged": merged}

    elif strategy == "concat":
        items: list = []
        for step_num, result in step_results.items():
            if isinstance(result, list):
                items.extend(result)
            elif isinstance(result, dict):
                data = result.get("data", result.get("body", result))
                if isinstance(data, list):
                    items.extend(data)
                else:
                    items.append(data)
        return {"items": items, "count": len(items)}

    elif strategy == "join":
        # Simple join on keys
        return {"joined": step_results, "keys": keys}

    return {"raw": step_results}


def _determine_output_type(context: dict) -> str:
    """Determine the best output type based on the context data."""
    step_results = context.get("step_results", {})
    if not step_results:
        return "text"

    latest = _get_latest_data(context)

    if latest is None:
        return "text"

    # Check for image files in the latest result
    if isinstance(latest, dict) and "files" in latest:
        image_files = [f for f in latest["files"] if f.get("filename", "").endswith(('.png', '.jpg', '.jpeg', '.svg'))]
        if image_files:
            return "image"

    if isinstance(latest, dict):
        # Check for specific patterns
        if "output_type" in latest:
            return latest["output_type"]
        if any(k in latest for k in ("lat", "lng", "latitude", "longitude", "coordinates", "markers", "center")):
            return "map"
        if any(k in latest for k in ("columns", "rows", "headers")):
            return "table"
        if any(k in latest for k in ("labels", "datasets", "series", "chart_type")):
            return "chart"
        if "items" in latest and isinstance(latest["items"], list):
            # List of dicts = table, list of scalars = list
            items = latest["items"]
            if items and isinstance(items[0], dict):
                return "table"
            return "list"
        if "content" in latest and isinstance(latest["content"], str):
            return "text"
        return "text"

    if isinstance(latest, list):
        if len(latest) > 0:
            if isinstance(latest[0], dict):
                return "table"
            return "list"

    return "text"


async def execute_plan(
    plan: list[OrchestrationStep],
    context: dict | None = None,
) -> ResultResponse:
    """Execute an orchestration plan sequentially and return the final result.

    Args:
        plan: Ordered list of steps to execute.
        context: Optional initial context.

    Returns:
        ResultResponse with the final aggregated result.
    """
    if context is None:
        context = {}

    if "step_results" not in context:
        context["step_results"] = {}

    # Fast path: chat_response — return text immediately without orchestration
    if len(plan) == 1 and plan[0].action == "chat_response":
        content = plan[0].result.get("content", plan[0].description) if plan[0].result else plan[0].description
        return ResultResponse(
            type="text",
            data={"content": content},
            metadata={"status": "completed", "mode": "chat"},
        )

    for step in plan:
        logger.info("Executing step %d: %s (%s)", step.step, step.description, step.action)

        step = await _execute_single_step(step, context)

        # Store step result in context for subsequent steps
        context["step_results"][str(step.step)] = step.result

        if step.status == "error":
            logger.warning("Step %d failed: %s", step.step, step.error)
            # Continue execution unless it's a critical step
            # (api_call failures for the first step are critical)
            if step.step == 1 and step.action == "api_call":
                return ResultResponse(
                    type="text",
                    data={
                        "error": step.error or "Unknown error",
                        "message": f"Plan execution failed at step {step.step}: {step.description}",
                    },
                    metadata={
                        "steps_total": len(plan),
                        "steps_completed": step.step - 1,
                        "status": "error",
                    },
                )

    # Collect errors from failed steps
    errored_steps = [s for s in plan if s.status == "error"]

    # Determine output type from the last step or context
    output_type = _determine_output_type(context)
    final_data = _get_latest_data(context)

    # Auto-reshape: if data is a list of dicts, convert to table format
    if isinstance(final_data, list):
        if final_data and isinstance(final_data[0], dict):
            output_type = "table"
            final_data = _reshape_output_data("table", final_data)
        elif final_data:
            final_data = {"items": final_data}
        else:
            final_data = None
    elif isinstance(final_data, dict):
        # Try to reshape if output_type is known
        final_data = _reshape_output_data(output_type, final_data)

    # Check if final_data is effectively empty
    is_empty = (
        final_data is None
        or final_data == {}
        or (isinstance(final_data, dict) and final_data.get("content") in ("{}", "null", "[]", ""))
    )

    if is_empty and errored_steps:
        error_msgs = [f"Step {s.step} ({s.action}): {s.error}" for s in errored_steps]
        output_type = "text"
        final_data = {
            "content": "Some steps failed during execution:\n" + "\n".join(error_msgs),
        }
    elif is_empty:
        output_type = "text"
        final_data = {"content": "The operation completed but returned no data."}

    return ResultResponse(
        type=output_type,
        data=final_data,
        metadata={
            "steps_total": len(plan),
            "steps_completed": sum(1 for s in plan if s.status == "completed"),
            "steps_errored": sum(1 for s in plan if s.status == "error"),
            "status": "completed" if not errored_steps else "partial",
        },
    )


async def execute_plan_stream(
    plan: list[OrchestrationStep],
    context: dict | None = None,
) -> AsyncGenerator[OrchestrationStreamEvent, None]:
    """Execute a plan and yield events as each step completes.

    Yields OrchestrationStreamEvent objects for SSE streaming.

    Args:
        plan: Ordered list of steps to execute.
        context: Optional initial context.

    Yields:
        OrchestrationStreamEvent for each step start, completion, error, and final result.
    """
    if context is None:
        context = {}

    if "step_results" not in context:
        context["step_results"] = {}

    # Fast path: chat_response — emit result immediately
    if len(plan) == 1 and plan[0].action == "chat_response":
        content = plan[0].result.get("content", plan[0].description) if plan[0].result else plan[0].description
        yield OrchestrationStreamEvent(
            event="result",
            data={
                "type": "text",
                "data": {"content": content},
                "metadata": {"status": "completed", "mode": "chat"},
            },
        )
        return

    # Emit reasoning if available (CoT visibility)
    reasoning = getattr(plan[0], '_reasoning', '') if plan else ''
    if reasoning:
        yield OrchestrationStreamEvent(
            event="reasoning",
            data={"content": reasoning},
        )

    # Emit the plan
    yield OrchestrationStreamEvent(
        event="plan",
        data={
            "steps": [s.model_dump() for s in plan],
            "total": len(plan),
        },
    )

    for step in plan:
        # Emit step start
        yield OrchestrationStreamEvent(
            event="step_start",
            data={"step": step.step, "action": step.action, "description": step.description},
        )

        step = await _execute_single_step(step, context)
        context["step_results"][str(step.step)] = step.result

        if step.status == "error":
            yield OrchestrationStreamEvent(
                event="step_error",
                data={
                    "step": step.step,
                    "action": step.action,
                    "description": step.description,
                    "error": step.error or "Unknown error",
                    "result": step.result,
                },
            )
        else:
            yield OrchestrationStreamEvent(
                event="step_complete",
                data={
                    "step": step.step,
                    "action": step.action,
                    "description": step.description,
                    "result": step.result,
                },
            )

    # Emit final result
    errored_steps = [s for s in plan if s.status == "error"]

    # Collect all format_output results for multi-panel display
    format_steps = [s for s in plan if s.action == "format_output" and s.status == "completed"]

    if len(format_steps) > 1:
        # Multiple format_output steps → combine into dashboard
        output_type = "dashboard"
        panels = []
        for fs in format_steps:
            if fs.result and isinstance(fs.result, dict):
                panel_type = fs.result.get("output_type", "text")
                panel_data = fs.result.get("data", {})
                panels.append({
                    "type": panel_type,
                    "data": panel_data,
                    "title": fs.description,
                })
        final_data = {"panels": panels}
        summary = "; ".join(fs.description for fs in format_steps)
    else:
        output_type = _determine_output_type(context)
        final_data = _get_latest_data(context)

        # Auto-reshape: if data is a list of dicts, convert to table format
        if isinstance(final_data, list):
            if final_data and isinstance(final_data[0], dict):
                output_type = "table"
                final_data = _reshape_output_data("table", final_data)
            elif final_data:
                final_data = {"items": final_data}
            else:
                final_data = None
        elif isinstance(final_data, dict):
            final_data = _reshape_output_data(output_type, final_data)

        summary = format_steps[-1].description if format_steps else ""

    # Check if final_data is effectively empty
    is_empty = (
        final_data is None
        or final_data == {}
        or (isinstance(final_data, dict) and final_data.get("content") in ("{}", "null", "[]", ""))
    )

    if is_empty and errored_steps:
        error_msgs = [f"Step {s.step} ({s.action}): {s.error}" for s in errored_steps]
        output_type = "text"
        final_data = {
            "content": "Some steps failed during execution:\n" + "\n".join(error_msgs),
        }
    elif is_empty:
        output_type = "text"
        final_data = {"content": "The operation completed but returned no data."}

    yield OrchestrationStreamEvent(
        event="result",
        data={
            "type": output_type,
            "data": final_data,
            "metadata": {
                "steps_total": len(plan),
                "steps_completed": sum(1 for s in plan if s.status == "completed"),
                "steps_errored": sum(1 for s in plan if s.status == "error"),
                "status": "completed" if not errored_steps else "partial",
                "summary": summary,
            },
        },
    )
