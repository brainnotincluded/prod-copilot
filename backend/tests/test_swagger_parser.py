"""Pure unit tests for SwaggerParser — no DB, no network, no mocking."""

import pytest

from app.services.swagger_parser import ParsedEndpoint, SwaggerParser

from tests.conftest import PETSTORE_OPENAPI3, PETSTORE_SWAGGER2


class TestParseOpenAPI3:
    """Parsing of an OpenAPI 3.x spec."""

    def setup_method(self):
        self.parser = SwaggerParser()
        self.endpoints = self.parser.parse(PETSTORE_OPENAPI3)

    def test_returns_list(self):
        assert isinstance(self.endpoints, list)

    def test_correct_endpoint_count(self):
        # GET /pets, POST /pets, GET /pets/{petId}, DELETE /pets/{petId}
        assert len(self.endpoints) == 4

    def test_all_are_parsed_endpoint(self):
        for ep in self.endpoints:
            assert isinstance(ep, ParsedEndpoint)

    def test_methods_uppercased(self):
        methods = {ep.method for ep in self.endpoints}
        assert methods == {"GET", "POST", "DELETE"}

    def test_paths_include_base(self):
        paths = {ep.path for ep in self.endpoints}
        assert "/v1/pets" in paths
        assert "/v1/pets/{petId}" in paths

    def test_summary_extracted(self):
        get_pets = next(ep for ep in self.endpoints if ep.method == "GET" and ep.path == "/v1/pets")
        assert get_pets.summary == "List all pets"

    def test_description_extracted(self):
        get_pets = next(ep for ep in self.endpoints if ep.method == "GET" and ep.path == "/v1/pets")
        assert get_pets.description == "Returns all pets from the store"

    def test_parameters_parsed(self):
        get_pets = next(ep for ep in self.endpoints if ep.method == "GET" and ep.path == "/v1/pets")
        assert len(get_pets.parameters) >= 1
        names = [p["name"] for p in get_pets.parameters]
        assert "limit" in names

    def test_path_level_parameters_inherited(self):
        """Path-level params (petId) must appear on GET /pets/{petId}."""
        get_pet = next(
            ep for ep in self.endpoints
            if ep.method == "GET" and "{petId}" in ep.path
        )
        names = [p["name"] for p in get_pet.parameters]
        assert "petId" in names

    def test_request_body_for_post(self):
        post_pets = next(ep for ep in self.endpoints if ep.method == "POST")
        assert post_pets.request_body is not None

    def test_response_schema_for_get(self):
        get_pets = next(ep for ep in self.endpoints if ep.method == "GET" and ep.path == "/v1/pets")
        assert get_pets.response_schema is not None
        assert get_pets.response_schema["type"] == "array"

    def test_delete_has_no_request_body(self):
        delete_ep = next(ep for ep in self.endpoints if ep.method == "DELETE")
        assert delete_ep.request_body is None


class TestParseSwagger2:
    """Parsing of a Swagger 2.0 spec."""

    def setup_method(self):
        self.parser = SwaggerParser()
        self.endpoints = self.parser.parse(PETSTORE_SWAGGER2)

    def test_correct_count(self):
        # GET /v2/pets, POST /v2/pets
        assert len(self.endpoints) == 2

    def test_base_path_prepended(self):
        paths = {ep.path for ep in self.endpoints}
        assert all(p.startswith("/v2") for p in paths)

    def test_body_param_becomes_request_body(self):
        post_ep = next(ep for ep in self.endpoints if ep.method == "POST")
        assert post_ep.request_body is not None
        # Body param must NOT appear in the parameters list
        param_names = [p["name"] for p in post_ep.parameters]
        assert "body" not in param_names

    def test_query_param_in_parameters(self):
        get_ep = next(ep for ep in self.endpoints if ep.method == "GET")
        names = [p["name"] for p in get_ep.parameters]
        assert "status" in names

    def test_response_schema_extracted(self):
        get_ep = next(ep for ep in self.endpoints if ep.method == "GET")
        assert get_ep.response_schema is not None


class TestExtractBaseUrl:
    """SwaggerParser.extract_base_url static method."""

    def test_openapi3_servers(self):
        url = SwaggerParser.extract_base_url(PETSTORE_OPENAPI3)
        assert url == "https://petstore.example.com/v1"

    def test_swagger2_host(self):
        url = SwaggerParser.extract_base_url(PETSTORE_SWAGGER2)
        assert url == "https://api.petstore.io/v2"

    def test_swagger2_no_scheme_defaults_https(self):
        spec = {"host": "example.com", "basePath": "/api"}
        url = SwaggerParser.extract_base_url(spec)
        assert url == "https://example.com/api"

    def test_no_host_no_servers_returns_none(self):
        url = SwaggerParser.extract_base_url({"openapi": "3.0.0"})
        assert url is None

    def test_trailing_slash_stripped(self):
        spec = {"servers": [{"url": "https://api.example.com/"}]}
        url = SwaggerParser.extract_base_url(spec)
        assert not url.endswith("/")


class TestParseEmptySpec:
    """Edge case: spec with no paths should return an empty list."""

    def test_no_endpoints(self):
        parser = SwaggerParser()
        result = parser.parse({"openapi": "3.0.0", "info": {"title": "x", "version": "1"}, "paths": {}})
        assert result == []


class TestParseUnknownVersion:
    """If neither 'swagger' nor 'openapi' key exists, fallback to OpenAPI 3."""

    def test_fallback_still_parses(self):
        spec = {
            "info": {"title": "mystery"},
            "paths": {
                "/foo": {
                    "get": {"summary": "bar", "responses": {"200": {"description": "ok"}}}
                }
            },
        }
        parser = SwaggerParser()
        endpoints = parser.parse(spec)
        assert len(endpoints) == 1
        assert endpoints[0].method == "GET"


class TestMergeParameters:
    """_merge_parameters: operation-level overrides path-level."""

    def test_override(self):
        path_p = [{"name": "id", "in": "path", "description": "old"}]
        op_p = [{"name": "id", "in": "path", "description": "new"}]
        merged = SwaggerParser._merge_parameters(path_p, op_p)
        assert len(merged) == 1
        assert merged[0]["description"] == "new"

    def test_combine_different(self):
        path_p = [{"name": "id", "in": "path"}]
        op_p = [{"name": "limit", "in": "query"}]
        merged = SwaggerParser._merge_parameters(path_p, op_p)
        assert len(merged) == 2


class TestNormaliseParams:
    """_normalise_params returns a cleaned structure."""

    def test_normalised_keys(self):
        raw = [{"name": "q", "in": "query", "extra_field": "ignored"}]
        result = SwaggerParser._normalise_params(raw)
        assert len(result) == 1
        assert set(result[0].keys()) == {"name", "in", "required", "description", "schema"}

    def test_defaults_applied(self):
        raw = [{"name": "x"}]
        result = SwaggerParser._normalise_params(raw)
        assert result[0]["required"] is False
        assert result[0]["in"] == ""
        assert result[0]["description"] == ""
