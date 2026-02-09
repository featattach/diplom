"""Add company_id to inventory_campaigns.

Revision ID: 007
Revises: 006
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не поддерживает ADD CONSTRAINT напрямую — используем batch
    with op.batch_alter_table("inventory_campaigns", schema=None) as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_inventory_campaigns_company_id",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("inventory_campaigns", schema=None) as batch_op:
        batch_op.drop_constraint("fk_inventory_campaigns_company_id", type_="foreignkey")
        batch_op.drop_column("company_id")
