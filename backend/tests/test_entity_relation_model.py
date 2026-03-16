"""Tests for EntityRelation model.

Covers: table structure, relationships, constraints.
"""


from app.db.models import EntityRelation


class TestEntityRelationModel:
    """SQLAlchemy EntityRelation model validation."""

    def test_table_name(self):
        assert EntityRelation.__tablename__ == "entity_relations"

    def test_primary_key(self):
        pk_cols = [c for c in EntityRelation.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"

    def test_foreign_keys(self):
        """Should have FKs to api_endpoints."""
        source_fks = list(EntityRelation.__table__.columns["source_endpoint_id"].foreign_keys)
        target_fks = list(EntityRelation.__table__.columns["target_endpoint_id"].foreign_keys)
        assert len(source_fks) == 1
        assert len(target_fks) == 1
        assert "api_endpoints.id" in str(source_fks[0].target_fullname)
        assert "api_endpoints.id" in str(target_fks[0].target_fullname)

    def test_cascade_delete_on_fks(self):
        """FKs should have CASCADE on delete."""
        source_fks = list(EntityRelation.__table__.columns["source_endpoint_id"].foreign_keys)
        target_fks = list(EntityRelation.__table__.columns["target_endpoint_id"].foreign_keys)
        assert source_fks[0].ondelete == "CASCADE"
        assert target_fks[0].ondelete == "CASCADE"

    def test_relation_type_default(self):
        cols = {c.name: c for c in EntityRelation.__table__.columns}
        assert cols["relation_type"].default.arg == "one_to_many"

    def test_field_mapping_json(self):
        """field_mapping should be JSON type."""
        col = EntityRelation.__table__.columns["field_mapping"]
        assert str(col.type) == "JSON"
        assert col.nullable is False  # Required field

    def test_confidence_default(self):
        cols = {c.name: c for c in EntityRelation.__table__.columns}
        assert cols["confidence"].default.arg == "0.8"

    def test_confidence_is_string(self):
        """confidence is stored as string (VARCHAR(10))."""
        col = EntityRelation.__table__.columns["confidence"]
        assert "VARCHAR" in str(col.type)
        assert col.type.length == 10


class TestEntityRelationCreation:
    """EntityRelation object creation patterns."""

    def test_create_minimal(self):
        relation = EntityRelation(
            id=1,
            source_endpoint_id=10,
            target_endpoint_id=20,
            relation_type="one_to_many",
            field_mapping={"source_field": "user_id", "target_field": "id"},
            confidence="0.8",  # Must be provided explicitly in test
        )
        assert relation.source_endpoint_id == 10
        assert relation.target_endpoint_id == 20
        assert relation.relation_type == "one_to_many"
        assert relation.confidence == "0.8"

    def test_create_with_confidence(self):
        relation = EntityRelation(
            id=1,
            source_endpoint_id=10,
            target_endpoint_id=20,
            relation_type="many_to_many",
            field_mapping={"a": "b"},
            confidence="0.95",
        )
        assert relation.relation_type == "many_to_many"
        assert relation.confidence == "0.95"

    def test_relation_types_allowed(self):
        """Test various relation types."""
        for rel_type in ["one_to_many", "many_to_one", "many_to_many", "one_to_one"]:
            relation = EntityRelation(
                id=1,
                source_endpoint_id=10,
                target_endpoint_id=20,
                relation_type=rel_type,
                field_mapping={},
            )
            assert relation.relation_type == rel_type
