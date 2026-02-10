"""Add changes_json to asset_events for was/became display.

Revision ID: 009
Revises: 008
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("asset_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("changes_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("asset_events", schema=None) as batch_op:
        batch_op.drop_column("changes_json")
