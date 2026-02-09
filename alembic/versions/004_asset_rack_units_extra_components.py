"""Add rack_units (U) and extra_components to assets.

Revision ID: 004
Revises: 003
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("rack_units", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("extra_components", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "extra_components")
    op.drop_column("assets", "rack_units")
