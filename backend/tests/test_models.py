"""Tests for SQLAlchemy ORM model definitions.

Verifies table names, columns, relationships, constraints, and defaults
without connecting to a real database.
"""

import pytest

from app.db.models import ApiEndpoint, Base, SwaggerSource


class TestSwaggerSourceModel:

    def test_table_name(self):
        assert SwaggerSource.__tablename__ == "swagger_sources"

    def test_primary_key(self):
        pk_cols = [c for c in SwaggerSource.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"

    def test_required_columns(self):
        """name and raw_json must be NOT NULL."""
        cols = {c.name: c for c in SwaggerSource.__table__.columns}
        assert cols["name"].nullable is False
        assert cols["raw_json"].nullable is False

    def test_nullable_columns(self):
        cols = {c.name: c for c in SwaggerSource.__table__.columns}
        assert cols["url"].nullable is True
        assert cols["base_url"].nullable is True

    def test_relationship_to_endpoints(self):
        rel = SwaggerSource.endpoints
        assert rel is not None

    def test_cascade_delete(self):
        rel = SwaggerSource.__mapper__.relationships["endpoints"]
        assert "delete" in rel.cascade or "all" in rel.cascade


class TestApiEndpointModel:

    def test_table_name(self):
        assert ApiEndpoint.__tablename__ == "api_endpoints"

    def test_primary_key(self):
        pk_cols = [c for c in ApiEndpoint.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"

    def test_foreign_key_to_swagger_source(self):
        fks = list(ApiEndpoint.__table__.columns["swagger_source_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "swagger_sources.id"

    def test_cascade_on_fk(self):
        fks = list(ApiEndpoint.__table__.columns["swagger_source_id"].foreign_keys)
        assert fks[0].ondelete == "CASCADE"

    def test_required_columns(self):
        cols = {c.name: c for c in ApiEndpoint.__table__.columns}
        assert cols["method"].nullable is False
        assert cols["path"].nullable is False
        assert cols["swagger_source_id"].nullable is False

    def test_nullable_columns(self):
        cols = {c.name: c for c in ApiEndpoint.__table__.columns}
        assert cols["summary"].nullable is True
        assert cols["description"].nullable is True
        assert cols["parameters"].nullable is True
        assert cols["request_body"].nullable is True
        assert cols["response_schema"].nullable is True
        assert cols["embedding"].nullable is True

    def test_embedding_column_dimension(self):
        col = ApiEndpoint.__table__.columns["embedding"]
        # pgvector Vector(384) — the type should carry dimension info
        assert col.type.dim == 384

    def test_relationship_back_to_source(self):
        rel = ApiEndpoint.swagger_source
        assert rel is not None


class TestBaseDeclarative:

    def test_base_has_metadata(self):
        assert hasattr(Base, "metadata")

    def test_both_tables_registered(self):
        table_names = set(Base.metadata.tables.keys())
        assert "swagger_sources" in table_names
        assert "api_endpoints" in table_names
