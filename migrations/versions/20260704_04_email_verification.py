"""Adiciona verificação de e-mail às contas.

Revision ID: 20260704_04
Revises: 20260704_03
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_04"
down_revision: str | None = "20260704_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    if "email_verified_at" not in user_columns:
        op.add_column(
            "users",
            sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        )

    # Contas anteriores à funcionalidade continuam com acesso.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET email_verified_at = created_at
            WHERE email_verified_at IS NULL
            """
        )
    )

    if "email_verification_tokens" not in inspector.get_table_names():
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_email_verification_tokens_token_hash",
            "email_verification_tokens",
            ["token_hash"],
            unique=True,
        )
        op.create_index(
            "ix_email_verification_tokens_expires_at",
            "email_verification_tokens",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "email_verification_tokens" in inspector.get_table_names():
        op.drop_table("email_verification_tokens")
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    if "email_verified_at" in user_columns:
        op.drop_column("users", "email_verified_at")
