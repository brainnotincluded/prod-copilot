import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_settings():
    """Settings with mock_mode=True for unit tests."""
    with patch("app.config.get_settings") as mock:
        settings = MagicMock()
        settings.mock_mode = True
        settings.rag_embedding_model = "test-model"
        settings.rag_embedding_dimension = 384
        settings.llm_provider = "kimi"
        settings.get_llm_config.return_value = MagicMock(
            api_key="test-key",
            base_url="https://test.api/v1",
            model="test-model",
            timeout=30.0,
            max_retries=1,
            retry_delay=0.1,
        )
        mock.return_value = settings
        yield settings


@pytest.fixture
def sample_endpoints():
    """Sample API endpoints for testing."""
    return [
        {"method": "GET", "path": "/api/v1/users", "summary": "List users", "description": "Returns list of users", "parameters": [{"name": "limit", "in": "query"}]},
        {"method": "POST", "path": "/api/v1/users", "summary": "Create user", "description": "Create a new user"},
        {"method": "GET", "path": "/api/v1/orders", "summary": "List orders", "description": "Returns list of orders"},
        {"method": "GET", "path": "/api/v1/analytics/revenue", "summary": "Revenue stats", "description": "Revenue analytics data"},
    ]


@pytest.fixture
def sample_context():
    """Sample execution context."""
    return {
        "base_url": "https://api.example.com",
        "step_results": {
            "1": {"status_code": 200, "body": [{"id": 1, "name": "Test", "status": "active"}], "success": True},
        },
    }
