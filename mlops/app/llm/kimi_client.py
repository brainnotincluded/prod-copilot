"""LLM client using OpenAI-compatible API (Kimi/Moonshot, OpenRouter, Ollama, etc.)."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings
from app.llm.prompts import PLANNER_PROMPT, EXECUTOR_PROMPT
from app.schemas.models import OrchestrationStep

logger = logging.getLogger(__name__)


def _merge_json_fragments(text: str) -> list | None:
    """Merge multiple JSON arrays/objects separated by whitespace into a single list.

    Handles a common granite4 issue where the LLM outputs:
        [{step1}]
        [{step2}]
    instead of:
        [{step1}, {step2}]

    Returns a merged list, or None if merging fails.
    """
    # Find all top-level JSON arrays and objects using a simple bracket-matching approach
    fragments: list = []
    i = 0
    while i < len(text):
        if text[i] in ('{', '['):
            # Find the matching closing bracket
            open_char = text[i]
            close_char = '}' if open_char == '{' else ']'
            depth = 0
            in_string = False
            escape = False
            j = i
            while j < len(text):
                c = text[j]
                if escape:
                    escape = False
                elif c == '\\' and in_string:
                    escape = True
                elif c == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if c == open_char:
                        depth += 1
                    elif c == close_char:
                        depth -= 1
                        if depth == 0:
                            break
                j += 1

            if depth == 0:
                fragment_str = text[i:j + 1]
                try:
                    parsed = json.loads(fragment_str)
                    if isinstance(parsed, list):
                        fragments.extend(parsed)
                    else:
                        fragments.append(parsed)
                    i = j + 1
                    continue
                except json.JSONDecodeError:
                    pass
        i += 1

    if fragments:
        return fragments
    return None


def _build_retry_decorator(max_retries: int, retry_delay: float):
    """Build a tenacity retry decorator from settings."""
    return retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        stop=stop_after_attempt(min(max_retries, 2)),
        wait=wait_exponential(multiplier=retry_delay, min=1, max=10),
        reraise=True,
    )


class LLMClient:
    """Client for OpenAI-compatible LLM APIs (Kimi/Moonshot, OpenRouter, Ollama, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self._model = model
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat completion request and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool/function definitions.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            The assistant's response text.

        Raises:
            Exception: On API errors (after retries are exhausted).
        """
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Disable Qwen3 thinking mode for faster responses
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            },
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        retry_decorator = _build_retry_decorator(self._max_retries, self._retry_delay)

        @retry_decorator
        async def _do_chat():
            return await self._client.chat.completions.create(**kwargs)

        try:
            response = await _do_chat()
            choice = response.choices[0]

            if choice.message.content:
                return choice.message.content

            # Handle thinking/reasoning models (kimi-k2.5, deepseek, etc.)
            # These put the answer in a "reasoning" field and leave content empty.
            # The reasoning contains chain-of-thought noise; we must extract
            # the actual answer (JSON object/array, quoted string, or last line).
            msg_dict = choice.message.model_dump() if hasattr(choice.message, 'model_dump') else {}
            reasoning = msg_dict.get("reasoning", "")
            if reasoning and not choice.message.content:
                logger.info("Extracting answer from reasoning (thinking model)")

                # Try to find a JSON array (plan) — must contain "step" or "intent"
                array_match = re.search(r'(\[[\s\S]*?"(?:step|action)"[\s\S]*?\])', reasoning)
                if array_match:
                    try:
                        json.loads(array_match.group())
                        return array_match.group()
                    except json.JSONDecodeError:
                        pass

                # Try to find a JSON object with quoted keys (not path params like {id})
                obj_match = re.search(r'(\{"[^{}]+\})', reasoning)
                if obj_match:
                    try:
                        json.loads(obj_match.group())
                        return obj_match.group()
                    except json.JSONDecodeError:
                        pass

                # Try last quoted string (for translate calls)
                quotes = re.findall(r'"([^"]{3,100})"', reasoning)
                # Filter out common noise words
                useful_quotes = [q for q in quotes if not any(
                    w in q.lower() for w in ("the user", "let me", "i need", "i should", "i'll", "i will")
                )]
                if useful_quotes:
                    return useful_quotes[-1]

                # Take last short non-empty line
                lines = [line.strip() for line in reasoning.split('\n') if line.strip() and 5 < len(line.strip()) < 150]
                if lines:
                    return lines[-1]
                return reasoning[:500]

            # Handle tool calls if present
            if choice.message.tool_calls:
                tool_results = []
                for tc in choice.message.tool_calls:
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "function_name": tc.function.name,
                        "arguments": tc.function.arguments,
                    })
                return json.dumps(tool_results)

            return ""

        except (RateLimitError, APIConnectionError, APITimeoutError):
            # Re-raised by tenacity after max retries
            raise

        except Exception as e:
            logger.error("LLM API chat error: %s", str(e))
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request and yield response chunks.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool/function definitions.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Yields:
            Response text chunks as they arrive.
        """
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            },
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        retry_decorator = _build_retry_decorator(self._max_retries, self._retry_delay)

        @retry_decorator
        async def _create_stream():
            return await self._client.chat.completions.create(**kwargs)

        try:
            stream = await _create_stream()
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except (RateLimitError, APIConnectionError, APITimeoutError):
            raise

        except Exception as e:
            logger.error("LLM API stream error: %s", str(e))
            raise

    def _clean_json_text(self, text: str) -> str:
        """Strip markdown fences and whitespace from LLM JSON output."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return cleaned

    def _parse_json_robust(self, text: str) -> dict | list:
        """Parse JSON from LLM output, handling common formatting issues.

        Tries in order:
        1. Direct json.loads
        2. Merge multiple JSON fragments
        3. Wrap in array brackets

        Raises json.JSONDecodeError if all fail.
        """
        cleaned = self._clean_json_text(text)

        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try merging fragments: [{a}]\n[{b}] → [{a},{b}]
        merged = _merge_json_fragments(cleaned)
        if merged is not None:
            return merged

        # Try wrapping in array: {a},{b} → [{a},{b}]
        return json.loads("[" + cleaned + "]")

    async def _chat_for_json(
        self,
        messages: list[dict],
        max_retries: int = 3,
        temperature: float = 0.2,
    ) -> dict | list:
        """Call LLM and retry until valid JSON is returned.

        On each failed parse, appends the error as a user message
        and asks the LLM to fix its output. Retries up to max_retries times.
        """
        for attempt in range(max_retries):
            # Thinking models need more tokens for reasoning + answer
            response_text = await self.chat(messages, temperature=temperature, max_tokens=2048)

            try:
                return self._parse_json_robust(response_text)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "JSON parse failed (attempt %d/%d): %s | Response: %s",
                    attempt + 1, max_retries, str(e), response_text[:200],
                )
                # Do NOT include the failed response (may contain huge reasoning
                # text from thinking models). Just append a short error message.
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "Invalid JSON. Return ONLY valid JSON.",
                    },
                ]

        # Final attempt failed — raise
        raise ValueError(
            f"LLM failed to produce valid JSON after {max_retries} attempts"
        )

    async def plan_query(
        self, query: str, endpoints: list[dict], history: list[dict] | None = None
    ) -> list[OrchestrationStep]:
        """Use the LLM to create an execution plan. Retries on invalid JSON."""
        endpoints_summary = json.dumps(endpoints, indent=2, ensure_ascii=False)

        messages: list[dict] = [
            {"role": "system", "content": PLANNER_PROMPT},
        ]

        # Include chat history for context (so LLM understands references like "those posts")
        if history:
            for msg in history[-6:]:  # last 6 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": (
                f"User query: {query}\n\n"
                f"Available endpoints:\n{endpoints_summary}"
            ),
        })

        try:
            steps_data = await self._chat_for_json(messages)
        except (ValueError, Exception) as e:
            logger.error("Plan query failed after retries: %s", str(e))
            return [
                OrchestrationStep(
                    step=1,
                    action="error",
                    description=f"Failed to create plan: {str(e)}",
                    status="error",
                    error=str(e),
                )
            ]

        # Handle chat response: {"type": "chat", "message": "..."}
        if isinstance(steps_data, dict) and steps_data.get("type") == "chat":
            chat_message = steps_data.get("message", "")
            return [
                OrchestrationStep(
                    step=1,
                    action="chat_response",
                    description=chat_message,
                    status="completed",
                    result={"content": chat_message},
                )
            ]

        if not isinstance(steps_data, list):
            steps_data = [steps_data]

        steps = []
        for sd in steps_data:
            if not isinstance(sd, dict):
                continue
            step = OrchestrationStep(
                step=sd.get("step", len(steps) + 1),
                action=sd.get("action", "unknown"),
                description=sd.get("description", ""),
                endpoint=sd.get("endpoint"),
                parameters=sd.get("parameters"),
                status="pending",
            )
            steps.append(step)

        return steps if steps else [
            OrchestrationStep(
                step=1, action="error",
                description="LLM returned an empty plan",
                status="error", error="Empty plan",
            )
        ]

    async def execute_step(
        self, step: OrchestrationStep, context: dict
    ) -> dict:
        """Use the LLM to determine how to execute a step. Retries on invalid JSON."""
        context_summary = json.dumps(context, indent=2, default=str, ensure_ascii=False)

        messages = [
            {"role": "system", "content": EXECUTOR_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Step: {step.model_dump_json()}\n\n"
                    f"Context from previous steps:\n{context_summary}"
                ),
            },
        ]

        try:
            result = await self._chat_for_json(messages, temperature=0.1)
            if isinstance(result, dict):
                return result
            # If LLM returned a list, take the first dict
            if isinstance(result, list) and result and isinstance(result[0], dict):
                return result[0]
            return {"error": f"Unexpected response type: {type(result).__name__}"}
        except (ValueError, Exception) as e:
            logger.error("Execute step failed after retries: %s", str(e))
            return {
                "error": f"Failed to get execution instructions: {str(e)}",
            }

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# Backward-compatible alias
KimiClient = LLMClient


@lru_cache()
def get_llm_client() -> LLMClient:
    """Return a cached LLMClient singleton. Uses MockKimiClient when MOCK_MODE=true."""
    settings = get_settings()

    if settings.mock_mode:
        from app.llm.mock_client import MockKimiClient
        logger.info("Using MockKimiClient (MOCK_MODE=true)")
        return MockKimiClient()  # type: ignore[return-value]

    llm_config = settings.get_llm_config()

    return LLMClient(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        model=llm_config.model,
        timeout=llm_config.timeout,
        max_retries=llm_config.max_retries,
        retry_delay=llm_config.retry_delay,
    )


# Backward-compatible alias
get_kimi_client = get_llm_client
