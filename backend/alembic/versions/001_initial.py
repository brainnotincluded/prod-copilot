"""Initial migration - create tables and enable pgvector

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create swagger_sources table
    op.create_table(
        "swagger_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Create api_endpoints table
    op.create_table(
        "api_endpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "swagger_source_id",
            sa.Integer(),
            sa.ForeignKey("swagger_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("response_schema", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Create index for vector similarity search (HNSW works on empty tables)
    op.create_index(
        "ix_api_endpoints_embedding",
        "api_endpoints",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # Create index on swagger_source_id for faster lookups
    op.create_index(
        "ix_api_endpoints_swagger_source_id",
        "api_endpoints",
        ["swagger_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_endpoints_swagger_source_id", table_name="api_endpoints")
    op.drop_index("ix_api_endpoints_embedding", table_name="api_endpoints")
    op.drop_table("api_endpoints")
    op.drop_table("swagger_sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
