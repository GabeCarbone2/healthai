"""Substitui nomes técnicos por perfis de avaliação.

Revision ID: 20260705_07
Revises: 20260705_06
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260705_07"
down_revision: str | None = "20260705_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE prediction_results
            SET experiment = CASE experiment
                WHEN 'Pima' THEN 'Perfil feminino'
                WHEN 'NHANES' THEN 'Perfil geral'
                ELSE experiment
            END
            WHERE experiment IN ('Pima', 'NHANES')
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE prediction_results
            SET experiment = CASE experiment
                WHEN 'Perfil feminino' THEN 'Pima'
                WHEN 'Perfil geral' THEN 'NHANES'
                ELSE experiment
            END
            WHERE experiment IN ('Perfil feminino', 'Perfil geral')
            """
        )
    )
