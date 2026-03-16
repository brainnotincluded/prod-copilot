import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.mcp.api_executor import execute_api_call, _validate_url


class TestValidateUrl:
    def test_no_restrictions(self):
        """None allowed_base_urls means no restrictions."""
        assert _validate_url("https://anything.com/path") is True

    def test_allowed_url(self):
        assert _validate_url("https://api.example.com/v1/users", ["https://api.example.com"]) is True

    def test_blocked_url(self):
        assert _validate_url("https://evil.com/steal", ["https://api.example.com"]) is False

    def test_empty_allowed_list(self):
        """Empty list is falsy in Python, so `not []` is True, meaning no restrictions."""
        assert _validate_url("https://anything.com/path", []) is True


class TestExecuteApiCall:
    @pytest.mark.asyncio
    async def test_invalid_method(self):
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await execute_api_call(method="INVALID", url="https://example.com")

    @pytest.mark.asyncio
    async def test_empty_url(self):
        with pytest.raises(ValueError, match="URL must not be empty"):
            await execute_api_call(method="GET", url="")

    @pytest.mark.asyncio
    async def test_whitespace_only_url(self):
        with pytest.raises(ValueError, match="URL must not be empty"):
            await execute_api_call(method="GET", url="   ")

    @pytest.mark.asyncio
    async def test_invalid_url_scheme(self):
        with pytest.raises(ValueError, match="must start with http"):
            await execute_api_call(method="GET", url="ftp://example.com")

    @pytest.mark.asyncio
    async def test_url_validation_blocked(self):
        with pytest.raises(ValueError, match="not under any of the allowed base URLs"):
            await execute_api_call(
                method="GET",
                url="https://evil.com/data",
                allowed_base_urls=["https://api.example.com"],
            )

    @pytest.mark.asyncio
    async def test_valid_methods_accepted(self):
        """All valid methods should pass the method check (but may fail on network)."""
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            # These will fail on network connect, but should NOT raise ValueError
            result = await execute_api_call(method=method, url="https://192.0.2.1/test", timeout=0.1)
            # Should return a dict with error info, not raise ValueError
            assert isinstance(result, dict)
            assert result["success"] is False
