"""Add manufacture_date to assets for traffic-light report.

Revision ID: 010
Revises: 009
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("manufacture_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("manufacture_date")
