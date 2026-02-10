"""Add os, network_interfaces, current_user to assets.

Revision ID: 008
Revises: 007
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("os", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("network_interfaces", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("current_user", sa.String(256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("current_user")
        batch_op.drop_column("network_interfaces")
        batch_op.drop_column("os")
