"""Política técnica de privacidade e retenção do HealthAI."""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.models import (
    EmailVerificationToken,
    PasswordResetToken,
    PredictionResult,
    UserSession,
)
from backend.settings import setting

PRIVACY_NOTICE_VERSION = "2026-07-11.1"
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


def cleanup_interval_seconds() -> int:
    raw_value = setting("HEALTHAI_CLEANUP_INTERVAL_SECONDS", "3600")
    try:
        seconds = int(raw_value)
    except ValueError as error:
        raise RuntimeError(
            "HEALTHAI_CLEANUP_INTERVAL_SECONDS deve ser um número inteiro."
        ) from error
    if seconds < 60:
        raise RuntimeError(
            "HEALTHAI_CLEANUP_INTERVAL_SECONDS deve ser maior ou igual a 60."
        )
    return seconds


def result_retention_cutoff() -> datetime:
    """Retorna o limite que também deve ser aplicado às consultas de leitura."""
    return datetime.now(timezone.utc) - timedelta(days=result_retention_days())


def purge_expired_results(db: Session, user_id: int | None = None) -> int:
    """Remove resultados cujo prazo de retenção terminou."""
    cutoff = result_retention_cutoff()
    statement = delete(PredictionResult).where(PredictionResult.created_at < cutoff)
    if user_id is not None:
        statement = statement.where(PredictionResult.user_id == user_id)
    result = db.execute(statement)
    return result.rowcount or 0


def purge_expired_auth_records(db: Session) -> int:
    """Remove sessões e links de verificação cujo prazo terminou."""
    now = int(time.time())
    sessions = db.execute(delete(UserSession).where(UserSession.expires_at <= now))
    verifications = db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.expires_at <= now)
    )
    password_resets = db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.expires_at <= now)
    )
    return (
        (sessions.rowcount or 0)
        + (verifications.rowcount or 0)
        + (password_resets.rowcount or 0)
    )
