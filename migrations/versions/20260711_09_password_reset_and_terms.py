"""Adiciona recuperação de senha e aceite versionado dos termos.

Revision ID: 20260711_09
Revises: 20260711_08
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_09"
down_revision: str | None = "20260711_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    with op.batch_alter_table("users") as batch_op:
        if "terms_accepted_at" not in user_columns:
            batch_op.add_column(
                sa.Column(
                    "terms_accepted_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )
        if "terms_version" not in user_columns:
            batch_op.add_column(
                sa.Column("terms_version", sa.String(length=20), nullable=True)
            )

    inspector = sa.inspect(op.get_bind())
    if "password_reset_tokens" not in inspector.get_table_names():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_password_reset_tokens_token_hash",
            "password_reset_tokens",
            ["token_hash"],
            unique=True,
        )
        op.create_index(
            "ix_password_reset_tokens_expires_at",
            "password_reset_tokens",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "password_reset_tokens" in inspector.get_table_names():
        op.drop_table("password_reset_tokens")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    with op.batch_alter_table("users") as batch_op:
        if "terms_version" in user_columns:
            batch_op.drop_column("terms_version")
        if "terms_accepted_at" in user_columns:
            batch_op.drop_column("terms_accepted_at")
