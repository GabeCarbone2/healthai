"""Adiciona o fluxo de revisão manual do CRM.

Revision ID: 20260705_06
Revises: 20260704_05
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260705_06"
down_revision: str | None = "20260704_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "crm_status" not in columns:
            batch_op.add_column(
                sa.Column("crm_status", sa.String(length=20), nullable=True)
            )
        if "crm_verified_at" not in columns:
            batch_op.add_column(
                sa.Column("crm_verified_at", sa.DateTime(), nullable=True)
            )
        if "crm_verified_by" not in columns:
            batch_op.add_column(
                sa.Column("crm_verified_by", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_users_crm_verified_by_users",
                "users",
                ["crm_verified_by"],
                ["id"],
                ondelete="SET NULL",
            )
        if "crm_rejection_reason" not in columns:
            batch_op.add_column(
                sa.Column(
                    "crm_rejection_reason",
                    sa.String(length=500),
                    nullable=True,
                )
            )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET crm_status = 'pending'
            WHERE crm IS NOT NULL AND crm_uf IS NOT NULL
              AND crm_status IS NULL
            """
        )
    )

    inspector = sa.inspect(op.get_bind())
    checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("users")
    }
    if "ck_users_crm_status" not in checks:
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_check_constraint(
                "ck_users_crm_status",
                "crm_status IS NULL OR crm_status IN "
                "('pending', 'approved', 'rejected')",
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("users")
    }
    foreign_keys = {
        constraint["name"]
        for constraint in inspector.get_foreign_keys("users")
    }
    columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    with op.batch_alter_table("users") as batch_op:
        if "ck_users_crm_status" in checks:
            batch_op.drop_constraint(
                "ck_users_crm_status", type_="check"
            )
        if "fk_users_crm_verified_by_users" in foreign_keys:
            batch_op.drop_constraint(
                "fk_users_crm_verified_by_users",
                type_="foreignkey",
            )
        for column in (
            "crm_rejection_reason",
            "crm_verified_by",
            "crm_verified_at",
            "crm_status",
        ):
            if column in columns:
                batch_op.drop_column(column)
