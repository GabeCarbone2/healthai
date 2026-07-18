"""Otimiza índices para consultas e chaves estrangeiras mais usadas.

Revision ID: 20260713_10
Revises: 20260711_09
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_10"
down_revision: str | None = "20260711_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(table_name: str) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }


def _create_index_if_missing(
    name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=False)


def upgrade() -> None:
    _create_index_if_missing("ix_users_created_at", "users", ["created_at"])
    _create_index_if_missing(
        "ix_users_crm_status_created",
        "users",
        ["crm_status", "created_at"],
    )
    _create_index_if_missing(
        "ix_users_crm_verified_by",
        "users",
        ["crm_verified_by"],
    )
    _create_index_if_missing(
        "ix_user_sessions_user_id",
        "user_sessions",
        ["user_id"],
    )
    _create_index_if_missing(
        "ix_email_verification_tokens_user_created",
        "email_verification_tokens",
        ["user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_password_reset_tokens_user_created",
        "password_reset_tokens",
        ["user_id", "created_at"],
    )

    result_indexes = _index_names("prediction_results")
    if "ix_prediction_results_user_created" in result_indexes:
        op.drop_index(
            "ix_prediction_results_user_created",
            table_name="prediction_results",
        )
    _create_index_if_missing(
        "ix_prediction_results_user_created_id",
        "prediction_results",
        ["user_id", "created_at", "id"],
    )

    review_indexes = _index_names("crm_review_events")
    if "ix_crm_review_events_user_created" in review_indexes:
        op.drop_index(
            "ix_crm_review_events_user_created",
            table_name="crm_review_events",
        )
    _create_index_if_missing(
        "ix_crm_review_events_user_created_id",
        "crm_review_events",
        ["user_id", "created_at", "id"],
    )
    _create_index_if_missing(
        "ix_crm_review_events_reviewer_id",
        "crm_review_events",
        ["reviewer_id"],
    )


def downgrade() -> None:
    indexes = {
        "crm_review_events": _index_names("crm_review_events"),
        "prediction_results": _index_names("prediction_results"),
        "password_reset_tokens": _index_names("password_reset_tokens"),
        "email_verification_tokens": _index_names("email_verification_tokens"),
        "user_sessions": _index_names("user_sessions"),
        "users": _index_names("users"),
    }
    for name, table_name in (
        ("ix_crm_review_events_reviewer_id", "crm_review_events"),
        ("ix_crm_review_events_user_created_id", "crm_review_events"),
        ("ix_prediction_results_user_created_id", "prediction_results"),
        ("ix_password_reset_tokens_user_created", "password_reset_tokens"),
        ("ix_email_verification_tokens_user_created", "email_verification_tokens"),
        ("ix_user_sessions_user_id", "user_sessions"),
        ("ix_users_crm_verified_by", "users"),
        ("ix_users_crm_status_created", "users"),
        ("ix_users_created_at", "users"),
    ):
        if name in indexes[table_name]:
            op.drop_index(name, table_name=table_name)

    _create_index_if_missing(
        "ix_prediction_results_user_created",
        "prediction_results",
        ["user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_crm_review_events_user_created",
        "crm_review_events",
        ["user_id", "created_at"],
    )
