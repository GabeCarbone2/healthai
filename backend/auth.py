"""Cadastro e autenticação baseada em sessões opacas."""

import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.email_service import EmailDeliveryError, send_verification_email
from backend.models import (
    EmailVerificationToken,
    PredictionResult,
    User,
    UserSession,
)
from backend.privacy import PRIVACY_NOTICE_VERSION
from backend.schemas import (
    AdminCrmReviewResponse,
    CrmCredentialsInput,
    CrmReviewInput,
    CrmStatus,
    DeleteAccountInput,
    LoginInput,
    PrivacyConsentInput,
    RegisterInput,
    RegistrationResponse,
    ResendEmailVerificationInput,
    UserResponse,
    VerifyEmailInput,
)
from backend.settings import setting

SESSION_COOKIE = "healthai_session"
SESSION_DURATION_SECONDS = 60 * 60 * 24 * 7
EMAIL_VERIFICATION_DURATION_SECONDS = 60 * 60 * 24
EMAIL_RESEND_INTERVAL_SECONDS = 60
password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash("healthai-dummy-password")
router = APIRouter(prefix="/auth", tags=["Autenticação"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def configured_admin_emails() -> set[str]:
    """Retorna os e-mails autorizados a receber a função administrativa."""
    return {
        email.strip().lower()
        for email in setting("HEALTHAI_ADMIN_EMAILS").split(",")
        if email.strip()
    }


def promote_configured_admins(db: Session) -> int:
    """Promove contas existentes explicitamente listadas na configuração."""
    emails = configured_admin_emails()
    if not emails:
        return 0
    users = db.scalars(select(User).where(User.email.in_(emails))).all()
    promoted = 0
    for user in users:
        if user.role != "admin":
            user.role = "admin"
            promoted += 1
    return promoted


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=setting("HEALTHAI_SECURE_COOKIE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )


def _create_session(db: Session, user: User, response: Response) -> None:
    now = int(time.time())
    db.execute(delete(UserSession).where(UserSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            token_hash=_token_digest(token),
            user_id=user.id,
            expires_at=now + SESSION_DURATION_SECONDS,
        )
    )
    db.commit()
    _set_session_cookie(response, token)


def _verification_url(token: str) -> str:
    frontend_url = setting(
        "HEALTHAI_FRONTEND_URL", "http://127.0.0.1:5173"
    ).rstrip("/")
    return f"{frontend_url}/verify-email?{urlencode({'token': token})}"


def _issue_verification_token(db: Session, user: User) -> None:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    token_hash = _token_digest(token)
    db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    )
    db.add(
        EmailVerificationToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=now + EMAIL_VERIFICATION_DURATION_SECONDS,
            created_at=now,
        )
    )
    db.commit()
    try:
        send_verification_email(
            recipient=user.email,
            recipient_name=user.name,
            verification_url=_verification_url(token),
        )
    except EmailDeliveryError:
        db.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash
            )
        )
        db.commit()
        raise


def get_current_user(
    db: DatabaseSession,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """Valida a sessão e retorna o usuário autenticado."""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
        )

    user_session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == _token_digest(session_token),
            UserSession.expires_at > int(time.time()),
        )
    )
    user = db.get(User, user_session.user_id) if user_session else None
    if not user or not user.is_active or not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )
    return user


def get_consented_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Exige aceite da versão atual do aviso para acessar dados da aplicação."""
    if (
        not user.privacy_accepted_at
        or user.privacy_notice_version != PRIVACY_NOTICE_VERSION
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceite o aviso de privacidade para continuar.",
        )
    if user.crm_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu cadastro profissional ainda não foi aprovado.",
        )
    return user


def get_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso administrativo necessário.",
        )
    return user


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register(
    data: RegisterInput,
    db: DatabaseSession,
) -> RegistrationResponse:
    email = str(data.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    if db.scalar(
        select(User).where(
            User.crm == data.crm,
            User.crm_uf == data.crm_uf,
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=f"O CRM {data.crm}/{data.crm_uf} já está cadastrado.",
        )

    user = User(
        email=email,
        name=data.name.strip(),
        crm=data.crm,
        crm_uf=data.crm_uf,
        crm_status="pending",
        role="admin" if email in configured_admin_emails() else "user",
        password_hash=password_hash.hash(data.password),
        privacy_accepted_at=datetime.now(timezone.utc),
        privacy_notice_version=PRIVACY_NOTICE_VERSION,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Este e-mail ou CRM já está cadastrado.",
        ) from error
    db.refresh(user)
    email_sent = True
    try:
        _issue_verification_token(db, user)
    except EmailDeliveryError:
        email_sent = False
    return RegistrationResponse(
        email=user.email,
        expires_in_seconds=EMAIL_VERIFICATION_DURATION_SECONDS,
        email_sent=email_sent,
    )


@router.post("/verify-email", response_model=UserResponse)
def verify_email(
    data: VerifyEmailInput,
    response: Response,
    db: DatabaseSession,
) -> User:
    now = int(time.time())
    verification = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == _token_digest(data.token),
            EmailVerificationToken.expires_at > now,
        )
    )
    user = db.get(User, verification.user_id) if verification else None
    if not verification or not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de verificação inválido ou expirado.",
        )

    user.email_verified_at = datetime.now(timezone.utc)
    db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    )
    db.commit()
    db.refresh(user)
    _create_session(db, user, response)
    return user


@router.post("/resend-verification", status_code=204)
def resend_verification(
    data: ResendEmailVerificationInput,
    db: DatabaseSession,
) -> None:
    email = str(data.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or user.email_verified_at or not user.is_active:
        return

    now = int(time.time())
    latest_token = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
    )
    if (
        latest_token
        and latest_token.created_at > now - EMAIL_RESEND_INTERVAL_SECONDS
    ):
        return
    try:
        _issue_verification_token(db, user)
    except EmailDeliveryError:
        # A resposta permanece genérica para não revelar contas cadastradas.
        return


@router.post("/login", response_model=UserResponse)
def login(
    data: LoginInput,
    response: Response,
    db: DatabaseSession,
) -> User:
    email = str(data.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user else dummy_password_hash
    valid_password = password_hash.verify(data.password, stored_hash)
    if not user or not valid_password or not user.is_active:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    if not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirme seu e-mail antes de entrar.",
        )

    _create_session(db, user, response)
    return user


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/crm", response_model=UserResponse)
def submit_crm(
    data: CrmCredentialsInput,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.crm_status == "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O CRM desta conta já foi aprovado.",
        )
    duplicate = db.scalar(
        select(User).where(
            User.crm == data.crm,
            User.crm_uf == data.crm_uf,
            User.id != user.id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O CRM {data.crm}/{data.crm_uf} já está cadastrado.",
        )
    user.crm = data.crm
    user.crm_uf = data.crm_uf
    user.crm_status = "pending"
    user.crm_verified_at = None
    user.crm_verified_by = None
    user.crm_rejection_reason = None
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/admin/crm-reviews",
    response_model=list[AdminCrmReviewResponse],
)
def list_crm_reviews(
    db: DatabaseSession,
    _: Annotated[User, Depends(get_admin_user)],
    review_status: Annotated[CrmStatus | None, Query(alias="status")] = None,
) -> list[User]:
    statement = (
        select(User)
        .where(User.crm.is_not(None), User.crm_uf.is_not(None))
        .order_by(User.created_at.asc())
    )
    if review_status:
        statement = statement.where(User.crm_status == review_status)
    return list(db.scalars(statement))


@router.post(
    "/admin/crm-reviews/{user_id}",
    response_model=UserResponse,
)
def review_crm(
    user_id: int,
    data: CrmReviewInput,
    db: DatabaseSession,
    admin: Annotated[User, Depends(get_admin_user)],
) -> User:
    target = db.get(User, user_id)
    if not target or not target.crm or not target.crm_uf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cadastro profissional não encontrado.",
        )
    target.crm_status = data.status
    target.crm_verified_at = datetime.now(timezone.utc)
    target.crm_verified_by = admin.id
    target.crm_rejection_reason = (
        data.rejection_reason if data.status == "rejected" else None
    )
    db.commit()
    db.refresh(target)
    return target


@router.post("/privacy-consent", response_model=UserResponse)
def accept_privacy_notice(
    _: PrivacyConsentInput,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    user.privacy_accepted_at = datetime.now(timezone.utc)
    user.privacy_notice_version = PRIVACY_NOTICE_VERSION
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DatabaseSession,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    if session_token:
        db.execute(
            delete(UserSession).where(
                UserSession.token_hash == _token_digest(session_token)
            )
        )
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.delete("/account", status_code=204)
def delete_account(
    data: DeleteAccountInput,
    response: Response,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if not password_hash.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Senha incorreta.")

    db.execute(
        delete(PredictionResult).where(PredictionResult.user_id == user.id)
    )
    db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    )
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
