"""Tests for app configuration and settings."""



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
        """Verify Settings picks up code defaults or env overrides correctly."""
        from app.config import Settings
        s = Settings()
        # These fields should have sensible values (from env or defaults)
        assert isinstance(s.postgres_user, str) and len(s.postgres_user) > 0
        assert isinstance(s.postgres_password, str) and len(s.postgres_password) > 0
        assert isinstance(s.postgres_db, str) and len(s.postgres_db) > 0
        assert isinstance(s.postgres_host, str) and len(s.postgres_host) > 0
        assert isinstance(s.postgres_port, int) and s.postgres_port > 0
        assert isinstance(s.mock_mode, bool)
        assert isinstance(s.mlops_base_url, str) and s.mlops_base_url.startswith("http")
        # Security fields added in JWT auth migration
        assert isinstance(s.secret_key, str) and len(s.secret_key) > 0
        assert isinstance(s.access_token_expire_days, int) and s.access_token_expire_days > 0

    def test_custom_port(self):
        from app.config import Settings
        s = Settings(postgres_port=9999)
        assert ":9999/" in s.database_url
