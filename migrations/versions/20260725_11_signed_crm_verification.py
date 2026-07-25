"""Substitui a revisão manual por desafio PDF assinado.

Revision ID: 20260725_11
Revises: 20260713_10
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_11"
down_revision: str | None = "20260713_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "crm_verification_challenges" not in inspector.get_table_names():
        op.create_table(
            "crm_verification_challenges",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("challenge_code", sa.String(length=64), nullable=False),
            sa.Column("crm", sa.String(length=10), nullable=False),
            sa.Column("crm_uf", sa.String(length=2), nullable=False),
            sa.Column("expires_at", sa.Integer(), nullable=False),
            sa.Column("used_at", sa.Integer(), nullable=True),
            sa.Column(
                "signer_certificate_sha256",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "signed_document_sha256",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_crm_verification_challenges_challenge_code",
            "crm_verification_challenges",
            ["challenge_code"],
            unique=True,
        )
        op.create_index(
            "ix_crm_verification_challenges_expires_at",
            "crm_verification_challenges",
            ["expires_at"],
            unique=False,
        )
        op.create_index(
            "ix_crm_verification_challenges_user_created",
            "crm_verification_challenges",
            ["user_id", "created_at"],
            unique=False,
        )

    inspector = sa.inspect(op.get_bind())
    event_columns = {
        column["name"]
        for column in inspector.get_columns("crm_review_events")
    }
    with op.batch_alter_table("crm_review_events") as batch_op:
        if "source" not in event_columns:
            batch_op.add_column(
                sa.Column(
                    "source",
                    sa.String(length=40),
                    nullable=False,
                    server_default="legacy_manual",
                )
            )
        if "evidence_fingerprint" not in event_columns:
            batch_op.add_column(
                sa.Column(
                    "evidence_fingerprint",
                    sa.String(length=64),
                    nullable=True,
                )
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    event_columns = {
        column["name"]
        for column in inspector.get_columns("crm_review_events")
    }
    with op.batch_alter_table("crm_review_events") as batch_op:
        if "evidence_fingerprint" in event_columns:
            batch_op.drop_column("evidence_fingerprint")
        if "source" in event_columns:
            batch_op.drop_column("source")

    inspector = sa.inspect(op.get_bind())
    if "crm_verification_challenges" in inspector.get_table_names():
        op.drop_table("crm_verification_challenges")
