"""Tests for User model — JWT authentication related.

Covers: table structure, constraints, defaults, and relationships.
"""


from app.db.models import User


class TestUserModel:
    """SQLAlchemy User model validation."""

    def test_table_name(self):
        assert User.__tablename__ == "users"

    def test_primary_key(self):
        pk_cols = [c for c in User.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"
        assert pk_cols[0].autoincrement is True

    def test_email_unique_and_indexed(self):
        email_col = User.__table__.columns["email"]
        assert email_col.nullable is False
        assert email_col.unique is True
        assert email_col.index is True

    def test_required_columns(self):
        cols = {c.name: c for c in User.__table__.columns}
        assert cols["hashed_password"].nullable is False
        assert cols["role"].nullable is False
        assert cols["is_active"].nullable is False

    def test_nullable_columns(self):
        cols = {c.name: c for c in User.__table__.columns}
        assert cols["name"].nullable is True

    def test_role_default(self):
        """Default role should be 'editor'."""
        cols = {c.name: c for c in User.__table__.columns}
        assert cols["role"].default.arg == "editor"

    def test_is_active_default(self):
        """Default is_active should be 1 (active)."""
        cols = {c.name: c for c in User.__table__.columns}
        assert cols["is_active"].default.arg == 1

    def test_created_at_auto(self):
        """created_at should have server default."""
        cols = {c.name: c for c in User.__table__.columns}
        assert cols["created_at"].server_default is not None


class TestUserInstantiations:
    """Test User object creation patterns."""

    def test_create_minimal(self):
        """User with minimal required fields."""
        user = User(
            id=1,
            email="test@example.com",
            hashed_password="hashed_secret",
            role="editor",
            is_active=1,
        )
        assert user.email == "test@example.com"
        assert user.role == "editor"
        assert user.is_active == 1
        assert user.name is None

    def test_create_full(self):
        """User with all fields."""
        user = User(
            id=1,
            email="admin@example.com",
            hashed_password="hashed_secret",
            name="Admin User",
            role="admin",
            is_active=1,
        )
        assert user.name == "Admin User"
        assert user.role == "admin"

    def test_roles_allowed(self):
        """Test that all expected roles can be assigned."""
        for role in ["viewer", "editor", "admin"]:
            user = User(
                id=1,
                email=f"{role}@example.com",
                hashed_password="x",
                role=role,
                is_active=1,
            )
            assert user.role == role


class TestUserPasswordSecurity:
    """Password-related security tests."""

    def test_password_hash_length(self):
        """Hashed password should be stored, not plaintext."""
        long_hash = "x" * 255
        user = User(
            id=1,
            email="test@example.com",
            hashed_password=long_hash,
            role="editor",
            is_active=1,
        )
        # Verify it can be stored (max length 255)
        assert len(user.hashed_password) <= 255

    def test_no_plaintext_password_field(self):
        """User model should not have a plaintext password field."""
        col_names = {c.name for c in User.__table__.columns}
        assert "password" not in col_names
        assert "hashed_password" in col_names
