"""Adiciona versão do modelo, completude e auditoria imutável de CRM.

Revision ID: 20260711_08
Revises: 20260705_07
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_08"
down_revision: str | None = "20260705_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    result_columns = {
        column["name"] for column in inspector.get_columns("prediction_results")
    }
    with op.batch_alter_table("prediction_results") as batch_op:
        if "model_version" not in result_columns:
            batch_op.add_column(
                sa.Column(
                    "model_version",
                    sa.String(length=64),
                    nullable=False,
                    server_default="legacy",
                )
            )
        if "input_completeness" not in result_columns:
            batch_op.add_column(
                sa.Column(
                    "input_completeness",
                    sa.Float(),
                    nullable=False,
                    server_default="1.0",
                )
            )
        if "missing_feature_count" not in result_columns:
            batch_op.add_column(
                sa.Column(
                    "missing_feature_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )

    inspector = sa.inspect(op.get_bind())
    if "crm_review_events" not in inspector.get_table_names():
        op.create_table(
            "crm_review_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("rejection_reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('approved', 'rejected')",
                name="ck_crm_review_events_status",
            ),
        )
        op.create_index(
            "ix_crm_review_events_user_created",
            "crm_review_events",
            ["user_id", "created_at"],
            unique=False,
        )
        op.execute(
            sa.text(
                """
                INSERT INTO crm_review_events
                    (user_id, reviewer_id, status, rejection_reason, created_at)
                SELECT id, crm_verified_by, crm_status, crm_rejection_reason,
                       crm_verified_at
                FROM users
                WHERE crm_status IN ('approved', 'rejected')
                  AND crm_verified_at IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "crm_review_events" in inspector.get_table_names():
        op.drop_table("crm_review_events")

    result_columns = {
        column["name"] for column in inspector.get_columns("prediction_results")
    }
    with op.batch_alter_table("prediction_results") as batch_op:
        for column in (
            "missing_feature_count",
            "input_completeness",
            "model_version",
        ):
            if column in result_columns:
                batch_op.drop_column(column)
