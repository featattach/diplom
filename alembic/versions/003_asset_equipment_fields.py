"""Add equipment kind, model and tech fields to assets.

Revision ID: 003
Revises: 002
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("equipment_kind", sa.String(32), nullable=True))
    op.add_column("assets", sa.Column("model", sa.String(256), nullable=True))
    op.add_column("assets", sa.Column("cpu", sa.String(128), nullable=True))
    op.add_column("assets", sa.Column("ram", sa.String(64), nullable=True))
    op.add_column("assets", sa.Column("disk1_type", sa.String(32), nullable=True))
    op.add_column("assets", sa.Column("disk1_capacity", sa.String(64), nullable=True))
    op.add_column("assets", sa.Column("network_card", sa.String(128), nullable=True))
    op.add_column("assets", sa.Column("motherboard", sa.String(128), nullable=True))
    op.add_column("assets", sa.Column("screen_diagonal", sa.String(32), nullable=True))
    op.add_column("assets", sa.Column("screen_resolution", sa.String(64), nullable=True))
    op.add_column("assets", sa.Column("power_supply", sa.String(128), nullable=True))
    op.add_column("assets", sa.Column("monitor_diagonal", sa.String(32), nullable=True))


def downgrade() -> None:
    for col in ("monitor_diagonal", "power_supply", "screen_resolution", "screen_diagonal",
                "motherboard", "network_card", "disk1_capacity", "disk1_type", "ram", "cpu",
                "model", "equipment_kind"):
        op.drop_column("assets", col)
