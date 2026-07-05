"""Política técnica de privacidade e retenção do HealthAI."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.models import PredictionResult
from backend.settings import setting

PRIVACY_NOTICE_VERSION = "2026-07-04.3"
DEFAULT_RESULT_RETENTION_DAYS = 180


def result_retention_days() -> int:
    """Retorna o prazo configurado para retenção dos resultados."""
    raw_value = setting(
        "HEALTHAI_RESULT_RETENTION_DAYS",
        str(DEFAULT_RESULT_RETENTION_DAYS),
    )
    try:
        days = int(raw_value)
    except ValueError as error:
        raise RuntimeError(
            "HEALTHAI_RESULT_RETENTION_DAYS deve ser um número inteiro."
        ) from error
    if days < 1:
        raise RuntimeError(
            "HEALTHAI_RESULT_RETENTION_DAYS deve ser maior ou igual a 1."
        )
    return days


def privacy_contact() -> str:
    return setting("HEALTHAI_PRIVACY_CONTACT", "Não configurado")


def purge_expired_results(db: Session, user_id: int | None = None) -> int:
    """Remove resultados cujo prazo de retenção terminou."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=result_retention_days()
    )
    statement = delete(PredictionResult).where(
        PredictionResult.created_at < cutoff
    )
    if user_id is not None:
        statement = statement.where(PredictionResult.user_id == user_id)
    result = db.execute(statement)
    return result.rowcount or 0
