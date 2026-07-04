"""Adiciona controles de privacidade e pseudonimiza resultados existentes.

Revision ID: 20260704_02
Revises: 20260703_01
Create Date: 2026-07-04
"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_02"
down_revision: str | None = "20260703_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    if (
        "privacy_accepted_at" not in user_columns
        or "privacy_notice_version" not in user_columns
    ):
        with op.batch_alter_table("users") as batch_op:
            if "privacy_accepted_at" not in user_columns:
                batch_op.add_column(
                    sa.Column(
                        "privacy_accepted_at",
                        sa.DateTime(),
                        nullable=True,
                    )
                )
            if "privacy_notice_version" not in user_columns:
                batch_op.add_column(
                    sa.Column(
                        "privacy_notice_version",
                        sa.String(length=20),
                        nullable=True,
                    )
                )

    result_columns = {
        column["name"]
        for column in inspector.get_columns("prediction_results")
    }
    if "patient_identifier" not in result_columns:
        with op.batch_alter_table("prediction_results") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "patient_identifier",
                    sa.String(length=32),
                    nullable=True,
                )
            )

    if "patient_name" in result_columns:
        connection = op.get_bind()
        rows = connection.execute(
            sa.text("SELECT id, user_id FROM prediction_results")
        )
        for row in rows:
            digest = hashlib.sha256(
                f"{row.user_id}:{row.id}".encode()
            ).hexdigest()[:12].upper()
            connection.execute(
                sa.text(
                    "UPDATE prediction_results "
                    "SET patient_identifier = :identifier WHERE id = :id"
                ),
                {"identifier": f"PAC-{digest}", "id": row.id},
            )

        with op.batch_alter_table("prediction_results") as batch_op:
            batch_op.alter_column(
                "patient_identifier",
                existing_type=sa.String(length=32),
                nullable=False,
            )
            batch_op.drop_column("patient_name")


def downgrade() -> None:
    with op.batch_alter_table("prediction_results") as batch_op:
        batch_op.add_column(
            sa.Column("patient_name", sa.String(length=120), nullable=True)
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE prediction_results "
            "SET patient_name = patient_identifier"
        )
    )

    with op.batch_alter_table("prediction_results") as batch_op:
        batch_op.alter_column(
            "patient_name",
            existing_type=sa.String(length=120),
            nullable=False,
        )
        batch_op.drop_column("patient_identifier")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("privacy_notice_version")
        batch_op.drop_column("privacy_accepted_at")
