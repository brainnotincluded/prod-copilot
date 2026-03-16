"""MCP API Executor: executes HTTP requests to external API endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Reusable async HTTP client
_client: httpx.AsyncClient | None = None

_DEFAULT_TIMEOUT = 30.0
_MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_client() -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=10.0),
            follow_redirects=True,
            verify=False,  # Skip SSL verification for external API calls from Docker
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )
    return _client


def _validate_url(url: str, allowed_base_urls: list[str] | None = None) -> bool:
    """Validate URL against optional allowed base URLs for security."""
    if not allowed_base_urls:
        return True
    return any(url.startswith(base) for base in allowed_base_urls)


async def execute_api_call(
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float | None = None,
    allowed_base_urls: list[str] | None = None,
) -> dict:
    """Execute an HTTP request to an external API endpoint.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH).
        url: Full URL of the API endpoint.
        params: Optional query parameters.
        headers: Optional HTTP headers (including auth).
        body: Optional JSON request body.
        timeout: Optional timeout override in seconds.
        allowed_base_urls: Optional list of allowed URL prefixes for security.
            If provided, the URL must start with one of these prefixes.

    Returns:
        Dict with keys:
            - status_code: HTTP status code
            - headers: Response headers
            - body: Parsed response body (JSON if possible, else text)
            - elapsed_ms: Request duration in milliseconds
            - success: Whether the request was successful (2xx)

    Raises:
        ValueError: If method or URL is invalid.
    """
    method = method.upper().strip()
    if method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}:
        raise ValueError(f"Unsupported HTTP method: {method}")

    if not url or not url.strip():
        raise ValueError("URL must not be empty")

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://: {url}")

    if not _validate_url(url, allowed_base_urls):
        raise ValueError(
            f"URL {url!r} is not under any of the allowed base URLs: {allowed_base_urls}"
        )

    client = _get_client()
    request_kwargs: dict[str, Any] = {
        "method": method,
        "url": url,
    }

    if params:
        # Filter out None values
        request_kwargs["params"] = {k: v for k, v in params.items() if v is not None}

    if headers:
        request_kwargs["headers"] = headers

    if body and method in {"POST", "PUT", "PATCH"}:
        request_kwargs["json"] = body

    if timeout:
        request_kwargs["timeout"] = timeout

    start_time = time.monotonic()

    try:
        response = await client.request(**request_kwargs)
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        # Parse response body
        content_type = response.headers.get("content-type", "")
        response_body: Any

        if "application/json" in content_type:
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text
        elif "text/" in content_type or "xml" in content_type:
            response_body = response.text
        else:
            # Try JSON first, fall back to text
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

        # Truncate very large text responses
        if isinstance(response_body, str) and len(response_body) > _MAX_RESPONSE_SIZE:
            response_body = response_body[:_MAX_RESPONSE_SIZE] + "... [truncated]"

        result = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
            "elapsed_ms": elapsed_ms,
            "success": 200 <= response.status_code < 300,
        }

        logger.info(
            "%s %s -> %d (%0.1fms)",
            method, url[:100], response.status_code, elapsed_ms,
        )

        return result

    except httpx.TimeoutException as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.error("Request timeout: %s %s (%0.1fms)", method, url[:100], elapsed_ms)
        return {
            "status_code": 0,
            "headers": {},
            "body": None,
            "elapsed_ms": elapsed_ms,
            "success": False,
            "error": f"Request timed out: {str(e)}",
        }

    except httpx.ConnectError as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.error("Connection error: %s %s: %s", method, url[:100], str(e))
        return {
            "status_code": 0,
            "headers": {},
            "body": None,
            "elapsed_ms": elapsed_ms,
            "success": False,
            "error": f"Connection error: {str(e)}",
        }

    except httpx.HTTPError as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.error("HTTP error: %s %s: %s", method, url[:100], str(e))
        return {
            "status_code": 0,
            "headers": {},
            "body": None,
            "elapsed_ms": elapsed_ms,
            "success": False,
            "error": f"HTTP error: {str(e)}",
        }

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.error("Unexpected error: %s %s: %s", method, url[:100], str(e))
        return {
            "status_code": 0,
            "headers": {},
            "body": None,
            "elapsed_ms": elapsed_ms,
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


async def close_client() -> None:
    """Close the HTTP client on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
