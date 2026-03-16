"""Tests for app configuration and settings."""

import pytest
from unittest.mock import patch


class TestSettings:

    def test_database_url_format(self):
        from app.config import Settings
        s = Settings(
            postgres_user="u", postgres_password="p",
            postgres_db="db", postgres_host="h", postgres_port=5432,
        )
        assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"

    def test_database_url_sync_format(self):
        from app.config import Settings
        s = Settings(
            postgres_user="u", postgres_password="p",
            postgres_db="db", postgres_host="h", postgres_port=5432,
        )
        assert s.database_url_sync == "postgresql://u:p@h:5432/db"

    def test_defaults(self):
        from app.config import Settings
        s = Settings()
        assert s.postgres_user == "postgres"
        assert s.postgres_password == "postgres"
        assert s.postgres_db == "prod_copilot"
        assert s.postgres_host == "localhost"
        assert s.postgres_port == 5432
        assert s.mock_mode is False
        assert s.mlops_base_url == "http://mlops:8001"

    def test_custom_port(self):
        from app.config import Settings
        s = Settings(postgres_port=9999)
        assert ":9999/" in s.database_url
