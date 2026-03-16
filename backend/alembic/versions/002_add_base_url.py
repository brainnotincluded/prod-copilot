"""Add base_url column to swagger_sources table

Revision ID: 002_add_base_url
Revises: 001_initial
Create Date: 2026-03-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_base_url"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swagger_sources",
        sa.Column("base_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swagger_sources", "base_url")
