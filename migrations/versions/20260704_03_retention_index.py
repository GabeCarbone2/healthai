"""Adiciona índice para a rotina global de retenção.

Revision ID: 20260704_03
Revises: 20260704_02
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_03"
down_revision: str | None = "20260704_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(
            "prediction_results"
        )
    }
    if "ix_prediction_results_created_at" not in indexes:
        op.create_index(
            "ix_prediction_results_created_at",
            "prediction_results",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_results_created_at",
        table_name="prediction_results",
    )
