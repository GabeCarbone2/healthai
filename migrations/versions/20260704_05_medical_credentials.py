"""Adiciona CRM e UF às contas médicas.

Revision ID: 20260704_05
Revises: 20260704_04
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_05"
down_revision: str | None = "20260704_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    if "crm" not in user_columns:
        op.add_column(
            "users",
            sa.Column("crm", sa.String(length=10), nullable=True),
        )
    if "crm_uf" not in user_columns:
        op.add_column(
            "users",
            sa.Column("crm_uf", sa.String(length=2), nullable=True),
        )

    inspector = sa.inspect(op.get_bind())
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("users")
    }
    if "uq_users_crm_uf" not in constraints:
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_unique_constraint(
                "uq_users_crm_uf",
                ["crm", "crm_uf"],
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "uq_users_crm_uf" in constraints:
            batch_op.drop_constraint("uq_users_crm_uf", type_="unique")
        columns = {
            column["name"] for column in inspector.get_columns("users")
        }
        if "crm_uf" in columns:
            batch_op.drop_column("crm_uf")
        if "crm" in columns:
            batch_op.drop_column("crm")
