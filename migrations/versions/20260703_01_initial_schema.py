"""Esquema inicial da aplicação.

Compatível com bancos criados anteriormente por SQLAlchemy ``create_all``.

Revision ID: 20260703_01
Revises:
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260703_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_users_email" not in _index_names("users"):
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "user_sessions" not in tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    session_indexes = _index_names("user_sessions")
    if "ix_user_sessions_token_hash" not in session_indexes:
        op.create_index(
            "ix_user_sessions_token_hash",
            "user_sessions",
            ["token_hash"],
            unique=True,
        )
    if "ix_user_sessions_expires_at" not in session_indexes:
        op.create_index(
            "ix_user_sessions_expires_at",
            "user_sessions",
            ["expires_at"],
            unique=False,
        )

    if "prediction_results" not in tables:
        op.create_table(
            "prediction_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("patient_name", sa.String(length=120), nullable=False),
            sa.Column("experiment", sa.String(length=60), nullable=False),
            sa.Column("model", sa.String(length=80), nullable=False),
            sa.Column("predicted_class", sa.Integer(), nullable=False),
            sa.Column("probability", sa.Float(), nullable=False),
            sa.Column("decision_threshold", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if (
        "ix_prediction_results_user_created"
        not in _index_names("prediction_results")
    ):
        op.create_index(
            "ix_prediction_results_user_created",
            "prediction_results",
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_results_user_created",
        table_name="prediction_results",
    )
    op.drop_table("prediction_results")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
