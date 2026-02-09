"""Add companies table and asset.company_id.

Revision ID: 006
Revises: 005
Create Date: 2025-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # Таблица могла быть создана ранее через Base.metadata.create_all,
    # поэтому аккуратно проверяем наличие перед созданием.
    if not insp.has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(256), nullable=False),
            sa.Column("short_info", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # SQLite не поддерживает ADD CONSTRAINT — добавляем столбец и FK через batch.
    columns = [c["name"] for c in insp.get_columns("assets")]
    if "company_id" not in columns:
        with op.batch_alter_table("assets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_assets_company_id",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_constraint("fk_assets_company_id", type_="foreignkey")
        batch_op.drop_column("company_id")
    op.drop_table("companies")
