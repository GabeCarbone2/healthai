"""Cadastro e autenticação baseada em sessões opacas."""

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pwdlib import PasswordHash
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.crm_verification import (
    ChallengeDocument,
    CrmVerificationError,
    CrmVerificationUnavailable,
    challenge_duration_seconds,
    generate_challenge_pdf,
    max_signed_pdf_bytes,
    validate_signed_challenge,
)
from backend.database import get_db
from backend.email_service import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from backend.models import (
    CrmReviewEvent,
    CrmVerificationChallenge,
    EmailVerificationToken,
    PasswordResetToken,
    PredictionResult,
    User,
    UserSession,
)
from backend.privacy import PRIVACY_NOTICE_VERSION
from backend.schemas import (
    CrmCredentialsInput,
    CrmVerificationChallengeResponse,
    CrmVerificationStatusResponse,
    DeleteAccountInput,
    ForgotPasswordInput,
    LoginInput,
    PrivacyConsentInput,
    RegisterInput,
    RegistrationResponse,
    ResendEmailVerificationInput,
    ResetPasswordInput,
    TermsConsentInput,
    UserResponse,
    VerifyEmailInput,
)
from backend.security import check_rate_limit, secure_cookie_enabled
from backend.settings import setting
from backend.terms import TERMS_VERSION

SESSION_COOKIE = "healthai_session"
SESSION_IDLE_TIMEOUT_SECONDS = 60 * 30
EMAIL_VERIFICATION_DURATION_SECONDS = 60 * 60 * 24
EMAIL_RESEND_INTERVAL_SECONDS = 60
PASSWORD_RESET_DURATION_SECONDS = 60 * 60
PASSWORD_RESET_RESEND_INTERVAL_SECONDS = 60
password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash("healthai-dummy-password")
router = APIRouter(prefix="/auth", tags=["Autenticação"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=secure_cookie_enabled(),
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
            expires_at=now + SESSION_IDLE_TIMEOUT_SECONDS,
        )
    )
    db.commit()
    _set_session_cookie(response, token)


def _is_legacy_long_session(user_session: UserSession, now: int) -> bool:
    """Derruba sessões criadas antes do timeout de inatividade de 30 minutos."""
    if user_session.expires_at <= now + SESSION_IDLE_TIMEOUT_SECONDS:
        return False

    created_at = user_session.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at <= datetime.now(timezone.utc) - timedelta(
        seconds=SESSION_IDLE_TIMEOUT_SECONDS
    )


def _verification_url(token: str) -> str:
    frontend_url = setting("HEALTHAI_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    return f"{frontend_url}/verify-email?{urlencode({'token': token})}"


def _password_reset_url(token: str) -> str:
    frontend_url = setting("HEALTHAI_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    return f"{frontend_url}/reset-password?{urlencode({'token': token})}"


def _issue_verification_token(db: Session, user: User) -> None:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    token_hash = _token_digest(token)
    db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
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


def _issue_password_reset_token(db: Session, user: User) -> None:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    token_hash = _token_digest(token)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.add(
        PasswordResetToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=now + PASSWORD_RESET_DURATION_SECONDS,
            created_at=now,
        )
    )
    db.commit()
    try:
        send_password_reset_email(
            recipient=user.email,
            recipient_name=user.name,
            reset_url=_password_reset_url(token),
        )
    except EmailDeliveryError:
        db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
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
    now = int(time.time())
    if _is_legacy_long_session(user_session, now):
        db.execute(delete(UserSession).where(UserSession.id == user_session.id))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )
    user_session.expires_at = now + SESSION_IDLE_TIMEOUT_SECONDS
    db.commit()
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
    if not user.terms_accepted_at or user.terms_version != TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceite os Termos de Uso vigentes para continuar.",
        )
    if user.crm_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu cadastro profissional ainda não foi aprovado.",
        )
    return user


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register(
    data: RegisterInput,
    db: DatabaseSession,
    request: Request,
) -> RegistrationResponse:
    email = str(data.email).strip().lower()
    check_rate_limit(
        request,
        scope="register",
        limit=30,
        window_seconds=60 * 60,
        identifier=email,
    )
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
        role="user",
        password_hash=password_hash.hash(data.password),
        privacy_accepted_at=datetime.now(timezone.utc),
        privacy_notice_version=PRIVACY_NOTICE_VERSION,
        terms_accepted_at=datetime.now(timezone.utc),
        terms_version=TERMS_VERSION,
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
    request: Request,
) -> User:
    check_rate_limit(
        request,
        scope="verify-email",
        limit=30,
        window_seconds=10 * 60,
        identifier=data.token[:16],
    )
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
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    db.commit()
    db.refresh(user)
    _create_session(db, user, response)
    return user


@router.post("/resend-verification", status_code=204)
def resend_verification(
    data: ResendEmailVerificationInput,
    db: DatabaseSession,
    request: Request,
) -> None:
    email = str(data.email).strip().lower()
    check_rate_limit(
        request,
        scope="resend-verification",
        limit=10,
        window_seconds=60 * 60,
        identifier=email,
    )
    user = db.scalar(select(User).where(User.email == email))
    if not user or user.email_verified_at or not user.is_active:
        return

    now = int(time.time())
    latest_token = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
    )
    if latest_token and latest_token.created_at > now - EMAIL_RESEND_INTERVAL_SECONDS:
        return
    try:
        _issue_verification_token(db, user)
    except EmailDeliveryError:
        # A resposta permanece genérica para não revelar contas cadastradas.
        return


@router.post("/forgot-password", status_code=204)
def forgot_password(
    data: ForgotPasswordInput,
    db: DatabaseSession,
    request: Request,
) -> None:
    """Solicita recuperação sem revelar se o e-mail está cadastrado."""
    email = str(data.email).strip().lower()
    check_rate_limit(
        request,
        scope="forgot-password",
        limit=10,
        window_seconds=60 * 60,
        identifier=email,
    )
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not user.email_verified_at:
        return

    now = int(time.time())
    latest_token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
    )
    if (
        latest_token
        and latest_token.created_at
        > now - PASSWORD_RESET_RESEND_INTERVAL_SECONDS
    ):
        return
    try:
        _issue_password_reset_token(db, user)
    except EmailDeliveryError:
        # Resposta genérica evita enumeração e não expõe falhas internas do SMTP.
        return


@router.post("/reset-password", status_code=204)
def reset_password(
    data: ResetPasswordInput,
    db: DatabaseSession,
    request: Request,
) -> None:
    check_rate_limit(
        request,
        scope="reset-password",
        limit=20,
        window_seconds=60 * 60,
        identifier=data.token[:16],
    )
    reset = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _token_digest(data.token),
            PasswordResetToken.expires_at > int(time.time()),
        )
    )
    user = db.get(User, reset.user_id) if reset else None
    if not reset or not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de recuperação inválido ou expirado.",
        )

    user.password_hash = password_hash.hash(data.password)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()


@router.post("/login", response_model=UserResponse)
def login(
    data: LoginInput,
    response: Response,
    db: DatabaseSession,
    request: Request,
) -> User:
    email = str(data.email).strip().lower()
    check_rate_limit(
        request,
        scope="login",
        limit=20,
        window_seconds=5 * 60,
        identifier=email,
    )
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
    locked_user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida.",
        )
    user = locked_user
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
    db.execute(
        delete(CrmVerificationChallenge).where(
            CrmVerificationChallenge.user_id == user.id,
            CrmVerificationChallenge.used_at.is_(None),
        )
    )
    db.commit()
    db.refresh(user)
    return user


def _challenge_response(
    challenge: CrmVerificationChallenge,
) -> CrmVerificationChallengeResponse:
    return CrmVerificationChallengeResponse(
        id=challenge.id,
        created_at=datetime.fromtimestamp(challenge.created_at, timezone.utc),
        expires_at=datetime.fromtimestamp(challenge.expires_at, timezone.utc),
        download_url=(
            f"/auth/crm-verification/challenge/{challenge.id}/document"
        ),
    )


@router.post(
    "/crm-verification/challenge",
    response_model=CrmVerificationChallengeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crm_verification_challenge(
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> CrmVerificationChallengeResponse:
    check_rate_limit(
        request,
        scope="crm-verification-challenge",
        limit=10,
        window_seconds=60 * 60,
        identifier=str(user.id),
    )
    if user.crm_status == "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O CRM desta conta já foi aprovado.",
        )
    if not user.crm or not user.crm_uf:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Informe CRM e UF antes de gerar o desafio.",
        )

    now = int(time.time())
    db.execute(
        delete(CrmVerificationChallenge).where(
            CrmVerificationChallenge.user_id == user.id,
            CrmVerificationChallenge.used_at.is_(None),
        )
    )
    challenge = CrmVerificationChallenge(
        user_id=user.id,
        challenge_code=secrets.token_urlsafe(32),
        crm=user.crm,
        crm_uf=user.crm_uf,
        created_at=now,
        expires_at=now + challenge_duration_seconds(),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return _challenge_response(challenge)


@router.get(
    "/crm-verification",
    response_model=CrmVerificationStatusResponse,
)
def crm_verification_status(
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> CrmVerificationStatusResponse:
    active_challenge = db.scalar(
        select(CrmVerificationChallenge)
        .where(
            CrmVerificationChallenge.user_id == user.id,
            CrmVerificationChallenge.used_at.is_(None),
            CrmVerificationChallenge.expires_at > int(time.time()),
        )
        .order_by(CrmVerificationChallenge.created_at.desc())
    )
    return CrmVerificationStatusResponse(
        crm_status=user.crm_status,
        active_challenge=(
            _challenge_response(active_challenge)
            if active_challenge
            else None
        ),
    )


@router.get("/crm-verification/challenge/{challenge_id}/document")
def download_crm_verification_challenge(
    challenge_id: int,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    challenge = db.scalar(
        select(CrmVerificationChallenge).where(
            CrmVerificationChallenge.id == challenge_id,
            CrmVerificationChallenge.user_id == user.id,
        )
    )
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Desafio de verificação não encontrado.",
        )
    if challenge.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este desafio já foi utilizado.",
        )
    if challenge.expires_at <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este desafio expirou. Gere um novo documento.",
        )
    if user.crm != challenge.crm or user.crm_uf != challenge.crm_uf:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Os dados do CRM mudaram. Gere um novo desafio.",
        )

    pdf_bytes = generate_challenge_pdf(
        ChallengeDocument(
            challenge_id=challenge.id,
            challenge_code=challenge.challenge_code,
            user_id=user.id,
            account_name=user.name,
            crm=challenge.crm,
            crm_uf=challenge.crm_uf,
            created_at=challenge.created_at,
            expires_at=challenge.expires_at,
        )
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="healthai-verificacao-crm.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/crm-verification/submit",
    response_model=UserResponse,
)
async def submit_signed_crm_verification(
    request: Request,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
    challenge_id: Annotated[int, Form(gt=0)],
    signed_pdf: Annotated[UploadFile, File()],
) -> User:
    check_rate_limit(
        request,
        scope="crm-verification-submit",
        limit=10,
        window_seconds=60 * 60,
        identifier=str(user.id),
    )
    if user.crm_status == "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O CRM desta conta já foi aprovado.",
        )
    challenge = db.scalar(
        select(CrmVerificationChallenge).where(
            CrmVerificationChallenge.id == challenge_id,
            CrmVerificationChallenge.user_id == user.id,
        )
    )
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Desafio de verificação não encontrado.",
        )
    if challenge.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este desafio já foi utilizado.",
        )
    if challenge.expires_at <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este desafio expirou. Gere um novo documento.",
        )
    if user.crm != challenge.crm or user.crm_uf != challenge.crm_uf:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Os dados do CRM mudaram. Gere um novo desafio.",
        )

    maximum_size = max_signed_pdf_bytes()
    pdf_bytes = await signed_pdf.read(maximum_size + 1)
    await signed_pdf.close()
    if len(pdf_bytes) > maximum_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="O PDF assinado excede o tamanho permitido.",
        )
    try:
        evidence = await run_in_threadpool(
            validate_signed_challenge,
            pdf_bytes,
            challenge_code=challenge.challenge_code,
            expected_crm=challenge.crm,
            expected_crm_uf=challenge.crm_uf,
        )
    except CrmVerificationUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except CrmVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    validated_at = int(time.time())
    locked_user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        locked_user is None
        or locked_user.crm != challenge.crm
        or locked_user.crm_uf != challenge.crm_uf
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Os dados do CRM mudaram durante a verificação.",
        )
    if locked_user.crm_status == "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O CRM desta conta já foi aprovado.",
        )
    user = locked_user
    consumed = db.execute(
        update(CrmVerificationChallenge)
        .where(
            CrmVerificationChallenge.id == challenge.id,
            CrmVerificationChallenge.used_at.is_(None),
            CrmVerificationChallenge.expires_at > validated_at,
        )
        .values(
            used_at=validated_at,
            signer_certificate_sha256=evidence.certificate_sha256,
            signed_document_sha256=evidence.signed_document_sha256,
        )
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O desafio expirou ou já foi utilizado.",
        )

    verified_at = datetime.now(timezone.utc)
    user.crm_status = "approved"
    user.crm_verified_at = verified_at
    user.crm_verified_by = None
    user.crm_rejection_reason = None
    db.add(
        CrmReviewEvent(
            user_id=user.id,
            reviewer_id=None,
            status="approved",
            rejection_reason=None,
            source="signed_pdf",
            evidence_fingerprint=evidence.signed_document_sha256,
            created_at=verified_at,
        )
    )
    db.commit()
    db.refresh(user)
    return user


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


@router.post("/terms-consent", response_model=UserResponse)
def accept_terms(
    _: TermsConsentInput,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    user.terms_accepted_at = datetime.now(timezone.utc)
    user.terms_version = TERMS_VERSION
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

    db.execute(delete(PredictionResult).where(PredictionResult.user_id == user.id))
    db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
