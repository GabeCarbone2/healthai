"""Modelos persistidos de autenticação."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("crm", "crm_uf", name="uq_users_crm_uf"),
        CheckConstraint(
            "crm_status IS NULL OR crm_status IN "
            "('pending', 'approved', 'rejected')",
            name="ck_users_crm_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    crm: Mapped[str | None] = mapped_column(String(10), nullable=True)
    crm_uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    crm_status: Mapped[str | None] = mapped_column(
        String(20), default="pending", nullable=True
    )
    crm_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )
    crm_verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    crm_rejection_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    privacy_notice_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_tokens_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[int]
    created_at: Mapped[int]


class PredictionResult(Base):
    """Resultado de uma avaliação, sem armazenar os dados clínicos de entrada."""

    __tablename__ = "prediction_results"
    __table_args__ = (
        Index("ix_prediction_results_user_created", "user_id", "created_at"),
        Index("ix_prediction_results_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    patient_identifier: Mapped[str] = mapped_column(String(32))
    experiment: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    predicted_class: Mapped[int] = mapped_column(Integer)
    probability: Mapped[float] = mapped_column(Float)
    decision_threshold: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
