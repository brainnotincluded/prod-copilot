"""Query planning: uses the Kimi LLM to create execution plans."""

from __future__ import annotations

import json
import logging

from app.llm.kimi_client import get_kimi_client
from app.llm.prompts import CLASSIFIER_PROMPT
from app.schemas.models import OrchestrationStep

logger = logging.getLogger(__name__)

# Tiny instant-response set: avoids an LLM call for the most trivial greetings.
# Everything else goes through the LLM classifier (works for any language).
_INSTANT_GREETINGS = {"hi", "hello", "hey"}

_INSTANT_GREETING_RESPONSE = (
    "Hello! I'm your API Copilot. Upload a Swagger spec and ask me "
    "anything about your data \u2014 I'll fetch it from the API for you."
)


async def _classify_intent(query: str, history: list[dict] | None = None) -> dict:
    """Use the LLM to classify a query as 'chat' or 'api_query'.

    Returns a dict like:
        {"intent": "chat", "response": "..."} or {"intent": "api_query"}
    """
    client = get_kimi_client()

    messages = [
        {"role": "system", "content": CLASSIFIER_PROMPT},
    ]
    # Include recent chat history for conversational context
    if history:
        for msg in history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": query})

    try:
        raw = await client.chat(messages, temperature=0.1, max_tokens=1024)
        cleaned = raw.strip()

        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Thinking models: reasoning may contain chain-of-thought.
        # Try to extract JSON object from anywhere in the text.
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Search for JSON object pattern in the text
            import re
            json_match = re.search(r'\{[^{}]*"intent"\s*:\s*"[^"]+?"[^{}]*\}', cleaned)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Heuristic: check if text mentions "chat" or "api"
                lower = cleaned.lower()
                if any(w in lower for w in ("greeting", "smalltalk", "chat", "привет", "hello")):
                    result = {"intent": "chat", "response": cleaned[:200]}
                else:
                    result = {"intent": "api_query"}

        if isinstance(result, dict) and "intent" in result:
            return result
    except Exception as exc:
        logger.warning("Intent classification failed, defaulting to api_query: %s", exc)

    # Default: treat as API query so we never block real requests
    return {"intent": "api_query"}


async def create_plan(
    query: str,
    endpoints: list[dict],
    context: dict | None = None,
) -> list[OrchestrationStep]:
    """Create an orchestration plan for a user query.

    Uses the Kimi LLM to analyze the query against available endpoints
    and produces a sequence of steps to answer the query.

    Args:
        query: Natural language user query.
        endpoints: List of available API endpoint definitions.
        context: Optional context dict (may contain base_url, etc.).

    Returns:
        Ordered list of OrchestrationStep objects.

    Raises:
        ValueError: If query or endpoints are empty.
    """
    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    stripped = query.strip()

    # Fast-path: instant response for trivial greetings (no LLM call needed)
    normalized = stripped.lower().rstrip("!?./)")
    if normalized in _INSTANT_GREETINGS:
        return [
            OrchestrationStep(
                step=1,
                action="chat_response",
                description=_INSTANT_GREETING_RESPONSE,
                status="completed",
                result={"content": _INSTANT_GREETING_RESPONSE},
            )
        ]

    # LLM-based intent classification (works for any language)
    classification = await _classify_intent(stripped)

    if classification.get("intent") == "chat":
        chat_response = classification.get(
            "response",
            "Hello! How can I help you with your APIs today?",
        )

        # The classifier already generates contextual responses in the user's
        # language.  No need for an extra LLM call to "enrich" with endpoint
        # listings -- that was causing simple greetings like "привет" to return
        # a wall of endpoint descriptions.
        return [
            OrchestrationStep(
                step=1,
                action="chat_response",
                description=chat_response,
                status="completed",
                result={"content": chat_response},
            )
        ]

    # Intent is api_query: proceed with plan creation
    client = get_kimi_client()

    # Extract chat history from context for conversational continuity
    history = context.get("history") if context else None

    # Limit endpoints sent to LLM to avoid overflowing context window.
    # Send only compact representations (method, path, summary) for planning.
    compact_endpoints = [
        {"method": ep.get("method", ""), "path": ep.get("path", ""),
         "summary": ep.get("summary", "")}
        for ep in endpoints[:15]  # max 15 endpoints in planner prompt
    ]

    logger.info("Creating plan for query: '%s' with %d endpoints", stripped[:80], len(compact_endpoints))
    steps = await client.plan_query(stripped, compact_endpoints, history=history)

    # Validate step numbers are sequential
    for i, step in enumerate(steps):
        if step.step != i + 1:
            step.step = i + 1

    # Don't modify chat_response plans -- they're complete as-is
    if len(steps) == 1 and steps[0].action == "chat_response":
        return steps

    # Ensure last step is format_output if not present
    if steps and steps[-1].action != "format_output":
        steps.append(OrchestrationStep(
            step=len(steps) + 1,
            action="format_output",
            description="Format the results for display",
            parameters={"output_type": "text"},
            status="pending",
        ))

    logger.info("Plan created with %d steps", len(steps))
    return steps
