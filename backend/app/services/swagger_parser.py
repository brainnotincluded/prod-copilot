"""Parser for Swagger 2.0 and OpenAPI 3.x specifications."""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedEndpoint:
    """Represents a single parsed API endpoint."""

    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None


class SwaggerParser:
    """Parses Swagger 2.0 and OpenAPI 3.0/3.1 specifications into a
    normalised list of ParsedEndpoint objects."""

    HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

    def parse(self, spec: dict[str, Any]) -> list[ParsedEndpoint]:
        """Detect spec version and dispatch to the appropriate parser."""
        if "swagger" in spec:
            return self._parse_swagger2(spec)
        elif "openapi" in spec:
            return self._parse_openapi3(spec)
        else:
            logger.warning(
                "Could not detect spec version, attempting OpenAPI 3.x parse."
            )
            return self._parse_openapi3(spec)

    # ------------------------------------------------------------------
    # Swagger 2.0
    # ------------------------------------------------------------------

    def _parse_swagger2(self, spec: dict[str, Any]) -> list[ParsedEndpoint]:
        endpoints: list[ParsedEndpoint] = []
        paths: dict[str, Any] = spec.get("paths", {})
        base_path = spec.get("basePath", "")

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters are inherited by every operation
            path_params: list[dict[str, Any]] = path_item.get("parameters", [])

            for method in self.HTTP_METHODS:
                operation = path_item.get(method)
                if operation is None:
                    continue

                # Merge path-level and operation-level parameters
                op_params = operation.get("parameters", [])
                merged_params = self._merge_parameters(path_params, op_params)

                # Separate body parameter (Swagger 2.0 style)
                body_params = [p for p in merged_params if p.get("in") == "body"]
                non_body_params = [p for p in merged_params if p.get("in") != "body"]

                request_body = None
                if body_params:
                    request_body = body_params[0].get("schema", {})

                # Extract success response schema
                response_schema = self._extract_response_swagger2(
                    operation.get("responses", {})
                )

                full_path = f"{base_path}{path}" if base_path else path

                endpoints.append(
                    ParsedEndpoint(
                        method=method.upper(),
                        path=full_path,
                        summary=operation.get("summary"),
                        description=operation.get("description"),
                        parameters=self._normalise_params(non_body_params),
                        request_body=request_body,
                        response_schema=response_schema,
                    )
                )

        logger.info("Parsed %d endpoints from Swagger 2.0 spec.", len(endpoints))
        return endpoints

    @staticmethod
    def _extract_response_swagger2(responses: dict[str, Any]) -> dict[str, Any] | None:
        for code in ("200", "201", "202", "204"):
            resp = responses.get(code)
            if resp and isinstance(resp, dict):
                schema = resp.get("schema")
                if schema:
                    return schema
        # Fallback: try the 'default' response
        default = responses.get("default")
        if default and isinstance(default, dict):
            return default.get("schema")
        return None

    # ------------------------------------------------------------------
    # OpenAPI 3.x
    # ------------------------------------------------------------------

    def _parse_openapi3(self, spec: dict[str, Any]) -> list[ParsedEndpoint]:
        endpoints: list[ParsedEndpoint] = []
        paths: dict[str, Any] = spec.get("paths", {})

        # Determine base path from servers
        servers = spec.get("servers", [])
        base_path = ""
        if servers and isinstance(servers, list):
            first_url = servers[0].get("url", "")
            # Strip protocol+host, keep only the path portion
            if first_url.startswith("/"):
                base_path = first_url.rstrip("/")
            elif "://" in first_url:
                from urllib.parse import urlparse

                parsed = urlparse(first_url)
                base_path = parsed.path.rstrip("/")

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            path_params: list[dict[str, Any]] = path_item.get("parameters", [])

            for method in self.HTTP_METHODS:
                operation = path_item.get(method)
                if operation is None:
                    continue

                op_params = operation.get("parameters", [])
                merged_params = self._merge_parameters(path_params, op_params)

                # Request body (OpenAPI 3.x style)
                request_body = None
                rb = operation.get("requestBody")
                if rb and isinstance(rb, dict):
                    content = rb.get("content", {})
                    # Prefer application/json
                    for media_type in (
                        "application/json",
                        "application/x-www-form-urlencoded",
                        "multipart/form-data",
                    ):
                        if media_type in content:
                            request_body = content[media_type].get("schema")
                            break
                    if request_body is None and content:
                        # Take first available content type
                        first_ct = next(iter(content.values()), {})
                        request_body = first_ct.get("schema")

                # Extract success response schema
                response_schema = self._extract_response_openapi3(
                    operation.get("responses", {})
                )

                full_path = f"{base_path}{path}" if base_path else path

                endpoints.append(
                    ParsedEndpoint(
                        method=method.upper(),
                        path=full_path,
                        summary=operation.get("summary"),
                        description=operation.get("description"),
                        parameters=self._normalise_params(merged_params),
                        request_body=request_body,
                        response_schema=response_schema,
                    )
                )

        logger.info("Parsed %d endpoints from OpenAPI 3.x spec.", len(endpoints))
        return endpoints

    @staticmethod
    def _extract_response_openapi3(
        responses: dict[str, Any],
    ) -> dict[str, Any] | None:
        for code in ("200", "201", "202", "204"):
            resp = responses.get(code)
            if resp and isinstance(resp, dict):
                content = resp.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema")
                if schema:
                    return schema
        default = responses.get("default")
        if default and isinstance(default, dict):
            content = default.get("content", {})
            json_content = content.get("application/json", {})
            return json_content.get("schema")
        return None

    # ------------------------------------------------------------------
    # Base URL extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_base_url(spec: dict[str, Any]) -> str | None:
        """Extract the API base URL from an OpenAPI/Swagger spec.

        Handles both OpenAPI 3.x (servers[].url) and Swagger 2.0
        (host + basePath + schemes).
        """
        # OpenAPI 3.x
        servers = spec.get("servers", [])
        if servers and isinstance(servers, list):
            url = servers[0].get("url", "")
            if url:
                return url.rstrip("/")

        # Swagger 2.0
        host = spec.get("host", "")
        if host:
            schemes = spec.get("schemes", ["https"])
            scheme = schemes[0] if schemes else "https"
            base_path = spec.get("basePath", "").rstrip("/")
            return f"{scheme}://{host}{base_path}"

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_parameters(
        path_params: list[dict[str, Any]],
        op_params: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge path-level and operation-level parameters.
        Operation-level parameters override path-level ones with the same
        name and location."""
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for p in path_params:
            key = (p.get("name", ""), p.get("in", ""))
            merged[key] = p
        for p in op_params:
            key = (p.get("name", ""), p.get("in", ""))
            merged[key] = p
        return list(merged.values())

    @staticmethod
    def _normalise_params(
        params: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return a cleaned list of parameter dicts."""
        normalised = []
        for p in params:
            normalised.append(
                {
                    "name": p.get("name", ""),
                    "in": p.get("in", ""),
                    "required": p.get("required", False),
                    "description": p.get("description", ""),
                    "schema": p.get("schema", p.get("type", "")),
                }
            )
        return normalised
