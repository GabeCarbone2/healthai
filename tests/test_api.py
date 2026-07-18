import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.auth import SESSION_IDLE_TIMEOUT_SECONDS
from backend.database import (
    Base,
    _configure_sqlite_connection,
    get_db,
    get_read_db,
)
from backend.models import (
    EmailVerificationToken,
    PasswordResetToken,
    PredictionResult,
    User,
    UserSession,
)
from backend.security import (
    check_rate_limit,
    trusted_origins,
    validate_unsafe_request_origin,
)


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("HEALTHAI_EMAIL_DELIVERY", "console")
    monkeypatch.setenv("HEALTHAI_RATE_LIMIT_ENABLED", "false")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_read_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client: TestClient, *, approve_crm: bool = True) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        user.email_verified_at = datetime.now(timezone.utc)
        if approve_crm:
            user.crm_status = "approved"
        db.commit()
    login_response = client.post(
        "/auth/login",
        json={
            "email": "usuario@example.com",
            "password": "senha-segura",
        },
    )
    assert login_response.status_code == 200


def pima_payload(patient_identifier: str = "PAC-A1B2C3D4") -> dict[str, object]:
    return {
        "patient_identifier": patient_identifier,
        "pregnancies": 1,
        "glucose_mg_dl": 110,
        "bmi_kg_m2": 27.5,
        "diabetes_pedigree_function": 0.45,
        "age_years": 35,
    }


def test_health_endpoint_is_public(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_http_log_omits_query_string_and_patient_search(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="healthai.http")

    client.get("/health", params={"search": "PAC-SENSITIVE"})

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "healthai.http"
    ]
    assert any("path=/health" in message for message in messages)
    assert all("PAC-SENSITIVE" not in message for message in messages)


def test_privacy_policy_is_public_and_reports_retention(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_RESULT_RETENTION_DAYS", "90")
    monkeypatch.setenv(
        "HEALTHAI_PRIVACY_CONTACT",
        "privacidade@example.com",
    )

    response = client.get("/privacy")

    assert response.status_code == 200
    assert response.json() == {
        "notice_version": "2026-07-11.1",
        "result_retention_days": 90,
        "contact": "privacidade@example.com",
    }


def test_terms_metadata_is_public_and_versioned(client: TestClient) -> None:
    response = client.get("/terms")

    assert response.status_code == 200
    assert response.json() == {
        "version": "2026-07-11.1",
        "effective_date": "2026-07-11",
    }


def test_models_require_authentication(client: TestClient) -> None:
    response = client.get("/models")

    assert response.status_code == 401


def test_cross_site_unsafe_requests_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "usuario@example.com", "password": "senha-segura"},
    )

    assert response.status_code == 403


def test_local_origins_are_not_trusted_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_ENV", "production")
    monkeypatch.setenv("HEALTHAI_FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setenv(
        "HEALTHAI_TRUSTED_ORIGINS",
        "http://127.0.0.1:5173,https://app.healthai.net.br",
    )

    origins = trusted_origins()

    assert "https://healthai.net.br" in origins
    assert "https://www.healthai.net.br" in origins
    assert "https://app.healthai.net.br" in origins
    assert "http://localhost:5173" not in origins
    assert "http://127.0.0.1:5173" not in origins


def test_local_origins_remain_trusted_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_ENV", "development")
    monkeypatch.setenv("HEALTHAI_FRONTEND_URL", "")
    monkeypatch.setenv("HEALTHAI_TRUSTED_ORIGINS", "")

    origins = trusted_origins()

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_production_rejects_unsafe_requests_without_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_ENV", "production")
    request = SimpleNamespace(method="POST", headers={})

    with pytest.raises(HTTPException) as error:
        validate_unsafe_request_origin(request)

    assert error.value.status_code == 403


def test_rate_limit_blocks_excess_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEALTHAI_RATE_LIMIT_ENABLED", "true")
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.10"))

    check_rate_limit(
        request,
        scope="unit-test",
        limit=1,
        window_seconds=60,
        identifier="usuario@example.com",
    )
    with pytest.raises(HTTPException) as error:
        check_rate_limit(
            request,
            scope="unit-test",
            limit=1,
            window_seconds=60,
            identifier="usuario@example.com",
        )

    assert error.value.status_code == 429


def test_registration_requires_explicit_privacy_consent(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": False,
            "terms_accepted": True,
        },
    )

    assert response.status_code == 422


def test_registration_requires_explicit_terms_acceptance(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
            "terms_accepted": False,
        },
    )

    assert response.status_code == 422


def test_registration_requires_email_verification_before_creating_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_message: dict[str, str] = {}

    def capture_email(**message: str) -> None:
        sent_message.update(message)

    monkeypatch.setattr("backend.auth.send_verification_email", capture_email)
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "123456",
            "crm_uf": "sp",
            "email": "USUARIO@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "usuario@example.com"
    assert response.json()["verification_required"] is True
    assert response.json()["email_sent"] is True
    assert "set-cookie" not in response.headers
    assert client.get("/auth/me").status_code == 401

    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        assert user.password_hash != "senha-segura"
        assert user.crm == "123456"
        assert user.crm_uf == "SP"
        assert user.crm_status == "pending"
        assert user.email_verified_at is None
        verification = db.scalar(select(EmailVerificationToken))
        assert verification is not None
        raw_token = parse_qs(urlparse(sent_message["verification_url"]).query)["token"][
            0
        ]
        assert verification.token_hash != raw_token

    blocked_login = client.post(
        "/auth/login",
        json={
            "email": "usuario@example.com",
            "password": "senha-segura",
        },
    )
    assert blocked_login.status_code == 403

    token = parse_qs(urlparse(sent_message["verification_url"]).query)["token"][0]
    verification_response = client.post(
        "/auth/verify-email",
        json={"token": token},
    )
    assert verification_response.status_code == 200
    assert verification_response.json()["email_verified_at"] is not None
    assert verification_response.json()["crm"] == "123456"
    assert verification_response.json()["crm_uf"] == "SP"
    assert verification_response.json()["crm_status"] == "pending"
    verification_cookie = verification_response.headers["set-cookie"]
    assert "HttpOnly" in verification_cookie
    assert "Max-Age" not in verification_cookie
    assert "expires=" not in verification_cookie.lower()
    assert client.get("/auth/me").status_code == 200
    with next(db_override()) as db:
        assert db.scalar(select(EmailVerificationToken)) is None


def test_login_cookie_expires_with_browser_session(
    client: TestClient,
) -> None:
    registration = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )
    assert registration.status_code == 201

    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        user.email_verified_at = datetime.now(timezone.utc)
        db.commit()

    login_response = client.post(
        "/auth/login",
        json={
            "email": "usuario@example.com",
            "password": "senha-segura",
        },
    )

    assert login_response.status_code == 200
    login_cookie = login_response.headers["set-cookie"]
    assert "healthai_session=" in login_cookie
    assert "HttpOnly" in login_cookie
    assert "Max-Age" not in login_cookie
    assert "expires=" not in login_cookie.lower()
    assert client.get("/auth/me").status_code == 200


def test_session_expires_after_idle_timeout_and_refreshes_on_activity(
    client: TestClient,
) -> None:
    register(client)
    db_override = app.dependency_overrides[get_db]

    with next(db_override()) as db:
        session = db.scalar(select(UserSession))
        assert session is not None
        session.expires_at = int(time.time()) + 5
        original_expiration = session.expires_at
        db.commit()

    assert client.get("/auth/me").status_code == 200

    with next(db_override()) as db:
        refreshed_session = db.scalar(select(UserSession))
        assert refreshed_session is not None
        assert refreshed_session.expires_at > original_expiration
        assert (
            refreshed_session.expires_at
            <= int(time.time()) + SESSION_IDLE_TIMEOUT_SECONDS + 2
        )

        refreshed_session.expires_at = int(time.time()) - 1
        db.commit()

    assert client.get("/auth/me").status_code == 401


def test_legacy_long_session_is_rejected_after_idle_timeout(
    client: TestClient,
) -> None:
    register(client)
    db_override = app.dependency_overrides[get_db]

    with next(db_override()) as db:
        session = db.scalar(select(UserSession))
        assert session is not None
        session.expires_at = int(time.time()) + 60 * 60 * 24 * 7
        session.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()

    assert client.get("/auth/me").status_code == 401

    with next(db_override()) as db:
        assert db.scalar(select(UserSession)) is None


def test_invalid_email_verification_token_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/verify-email",
        json={"token": "x" * 32},
    )

    assert response.status_code == 400


def test_password_reset_is_generic_single_use_and_revokes_sessions(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    sent_message: dict[str, str] = {}

    def capture_email(**message: str) -> None:
        sent_message.update(message)

    monkeypatch.setattr("backend.auth.send_password_reset_email", capture_email)

    assert client.post(
        "/auth/forgot-password",
        json={"email": "usuario@example.com"},
    ).status_code == 204
    assert client.post(
        "/auth/forgot-password",
        json={"email": "nao-cadastrado@example.com"},
    ).status_code == 204

    raw_token = parse_qs(urlparse(sent_message["reset_url"]).query)["token"][0]
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        stored = db.scalar(select(PasswordResetToken))
        assert stored is not None
        assert stored.token_hash != raw_token

    assert client.post(
        "/auth/reset-password",
        json={"token": "x" * 32, "password": "nova-senha-segura"},
    ).status_code == 400
    assert client.post(
        "/auth/reset-password",
        json={"token": raw_token, "password": "nova-senha-segura"},
    ).status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "usuario@example.com", "password": "senha-segura"},
    ).status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "usuario@example.com", "password": "nova-senha-segura"},
    ).status_code == 200
    assert client.post(
        "/auth/reset-password",
        json={"token": raw_token, "password": "outra-senha-segura"},
    ).status_code == 400


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/register",
        json={
            "name": "Outro Nome",
            "crm": "654321",
            "crm_uf": "RJ",
            "email": "usuario@example.com",
            "password": "outra-senha",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )

    assert response.status_code == 409


def test_duplicate_crm_in_same_state_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/register",
        json={
            "name": "Outra Médica",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "outra@example.com",
            "password": "outra-senha",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )

    assert response.status_code == 409
    assert "CRM 123456/SP" in response.json()["detail"]


def test_registration_rejects_invalid_crm_and_state(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "crm": "CRM-12",
            "crm_uf": "XX",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )

    assert response.status_code == 422


def test_pending_crm_blocks_clinical_access(client: TestClient) -> None:
    register(client, approve_crm=False)

    response = client.get("/models")

    assert response.status_code == 403
    assert "ainda não foi aprovado" in response.json()["detail"]
    assert client.get("/auth/me").json()["crm_status"] == "pending"
    assert client.get("/auth/admin/crm-reviews").status_code == 403


def test_admin_can_approve_pending_crm(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_ADMIN_EMAILS", "admin@example.com")
    register(client, approve_crm=False)
    assert client.post("/auth/logout").status_code == 204

    admin_registration = client.post(
        "/auth/register",
        json={
            "name": "Administradora",
            "crm": "999999",
            "crm_uf": "DF",
            "email": "admin@example.com",
            "password": "senha-admin",
            "privacy_accepted": True,
            "terms_accepted": True,
        },
    )
    assert admin_registration.status_code == 201

    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert admin is not None
        assert admin.role == "admin"
        admin.email_verified_at = datetime.now(timezone.utc)
        db.commit()

    login = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "senha-admin"},
    )
    assert login.status_code == 200

    pending = client.get(
        "/auth/admin/crm-reviews",
        params={"status": "pending"},
    )
    assert pending.status_code == 200
    doctor = next(
        item for item in pending.json() if item["email"] == "usuario@example.com"
    )

    rejected_without_reason = client.post(
        f"/auth/admin/crm-reviews/{doctor['id']}",
        json={"status": "rejected"},
    )
    assert rejected_without_reason.status_code == 422

    approval = client.post(
        f"/auth/admin/crm-reviews/{doctor['id']}",
        json={"status": "approved"},
    )
    assert approval.status_code == 200
    assert approval.json()["crm_status"] == "approved"
    assert approval.json()["crm_verified_by"] == login.json()["id"]
    assert approval.json()["crm_verified_at"] is not None

    history = client.get(f"/auth/admin/crm-reviews/{doctor['id']}/history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "approved"
    assert history.json()[0]["reviewer_id"] == login.json()["id"]

    assert client.post("/auth/logout").status_code == 204
    doctor_login = client.post(
        "/auth/login",
        json={
            "email": "usuario@example.com",
            "password": "senha-segura",
        },
    )
    assert doctor_login.status_code == 200
    assert client.get("/models").status_code == 200


def test_logout_invalidates_session(client: TestClient) -> None:
    register(client)

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_existing_user_must_accept_current_privacy_notice(
    client: TestClient,
) -> None:
    register(client)
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        user.privacy_accepted_at = None
        user.privacy_notice_version = None
        db.commit()

    blocked = client.get("/results")
    assert blocked.status_code == 403

    consent = client.post(
        "/auth/privacy-consent",
        json={"accepted": True},
    )
    assert consent.status_code == 200
    assert consent.json()["privacy_accepted_at"] is not None
    assert consent.json()["privacy_notice_version"] == "2026-07-11.1"
    assert client.get("/results").status_code == 200


def test_existing_user_must_accept_current_terms(client: TestClient) -> None:
    register(client)
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        user.terms_accepted_at = None
        user.terms_version = None
        db.commit()

    assert client.get("/results").status_code == 403
    consent = client.post("/auth/terms-consent", json={"accepted": True})
    assert consent.status_code == 200
    assert consent.json()["terms_accepted_at"] is not None
    assert consent.json()["terms_version"] == "2026-07-11.1"
    assert client.get("/results").status_code == 200


def test_account_deletion_requires_password_and_removes_all_user_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    monkeypatch.setattr(
        "backend.app.predict_record",
        lambda experiment, values: {
            "experiment": experiment,
            "model": "random_forest",
            "predicted_class": 0,
            "probability": 0.2,
            "decision_threshold": 0.35,
        },
    )
    client.post(
        "/predict/pima",
        json=pima_payload(),
    )

    wrong_password = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "senha-errada", "confirmation": "EXCLUIR"},
    )
    assert wrong_password.status_code == 401

    deleted = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "senha-segura", "confirmation": "EXCLUIR"},
    )
    assert deleted.status_code == 204
    assert client.get("/auth/me").status_code == 401

    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(UserSession)) is None
        assert db.scalar(select(PredictionResult)) is None


def test_nhanes_rejects_participant_under_18(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/predict/nhanes",
        json={"sex": "female", "age_years": 17},
    )

    assert response.status_code == 422


def test_prediction_requires_core_clinical_measurements(
    client: TestClient,
) -> None:
    register(client)

    incomplete = client.post(
        "/predict/pima",
        json={
            "patient_identifier": "PAC-A1B2C3D4",
            "pregnancies": 1,
            "age_years": 35,
        },
    )
    invalid_pressure = client.post(
        "/predict/nhanes",
        json={
            "patient_identifier": "PAC-A1B2C3D4",
            "sex": "female",
            "age_years": 45,
            "bmi_kg_m2": 27.5,
            "hba1c_percent": 5.8,
            "systolic_bp_mmhg": 90,
            "diastolic_bp_mmhg": 100,
        },
    )

    assert incomplete.status_code == 422
    assert invalid_pressure.status_code == 422


def test_new_prediction_returns_local_explanation_without_persisting_it(
    client: TestClient,
) -> None:
    register(client)

    response = client.post("/predict/pima", json=pima_payload())

    assert response.status_code == 200
    explanation = response.json()["local_explanation"]
    assert explanation["method"] == "single_feature_reference_replacement"
    assert explanation["features"]
    history_item = client.get("/results").json()["items"][0]
    assert "local_explanation" not in history_item


def test_prediction_result_survives_new_request_and_can_be_cleared(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    monkeypatch.setattr(
        "backend.app.predict_record",
        lambda experiment, values: {
            "experiment": experiment,
            "model": "random_forest",
            "predicted_class": 1,
            "probability": 0.81,
            "decision_threshold": 0.35,
        },
    )

    prediction = client.post(
        "/predict/pima",
        json={
            **pima_payload(),
            "pregnancies": 2,
            "age_years": 42,
        },
    )

    assert prediction.status_code == 200
    results = client.get("/results")
    assert results.status_code == 200
    assert results.json()["total"] == 1
    assert prediction.json()["local_explanation"]["features"] == []
    assert "local_explanation" not in results.json()["items"][0]
    persisted_prediction = {
        key: value
        for key, value in prediction.json().items()
        if key != "local_explanation"
    }
    assert persisted_prediction == results.json()["items"][0]
    assert results.json()["items"][0] == {
        "id": 1,
        "patient_identifier": "PAC-A1B2C3D4",
        "created_at": results.json()["items"][0]["created_at"],
        "experiment": "Perfil feminino — base Pima",
        "model": "Random Forest",
        "model_version": "unversioned",
        "predicted_class": 1,
        "probability": 0.81,
        "decision_threshold": 0.35,
        "input_completeness": 1.0,
        "missing_feature_count": 0,
    }
    assert results.json()["items"][0]["created_at"].endswith("Z")

    assert client.delete("/results").status_code == 204
    empty_page = client.get("/results").json()
    assert empty_page["items"] == []
    assert empty_page["total"] == 0


def test_results_support_search_dates_pagination_and_individual_deletion(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    monkeypatch.setattr(
        "backend.app.predict_record",
        lambda experiment, values: {
            "experiment": experiment,
            "model": "random_forest",
            "predicted_class": 0,
            "probability": 0.2,
            "decision_threshold": 0.35,
        },
    )
    for patient_identifier in (
        "PAC-A1B2C3D4",
        "PAC-B1C2D3E4",
        "PAC-C1D2E3F4",
    ):
        response = client.post(
            "/predict/pima",
            json=pima_payload(patient_identifier),
        )
        assert response.status_code == 200

    first_page = client.get(
        "/results",
        params={"page": 1, "page_size": 2},
    ).json()
    assert first_page["total"] == 3
    assert first_page["pages"] == 2
    assert [item["patient_identifier"] for item in first_page["items"]] == [
        "PAC-C1D2E3F4",
        "PAC-B1C2D3E4",
    ]

    second_page = client.get(
        "/results",
        params={"page": 2, "page_size": 2},
    ).json()
    assert [item["patient_identifier"] for item in second_page["items"]] == [
        "PAC-A1B2C3D4"
    ]

    search = client.get("/results", params={"search": "A1B2"}).json()
    assert search["total"] == 1
    assert search["items"][0]["patient_identifier"] == "PAC-A1B2C3D4"

    creation_date = search["items"][0]["created_at"][:10]
    by_date = client.get(
        "/results",
        params={"date_from": creation_date, "date_to": creation_date},
    ).json()
    assert by_date["total"] == 3

    result_id = search["items"][0]["id"]
    assert client.delete(f"/results/{result_id}").status_code == 204
    assert client.get("/results", params={"search": "A1B2"}).json()["total"] == 0
    assert client.delete(f"/results/{result_id}").status_code == 404


def test_expired_results_are_removed_by_retention_policy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTHAI_RESULT_RETENTION_DAYS", "30")
    register(client)
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        user = db.scalar(select(User))
        assert user is not None
        db.add_all(
            [
                PredictionResult(
                    user_id=user.id,
                    patient_identifier="PAC-OLD12345",
                    experiment="Pima",
                    model="Random Forest",
                    predicted_class=0,
                    probability=0.2,
                    decision_threshold=0.35,
                    created_at=datetime.now(timezone.utc) - timedelta(days=31),
                ),
                PredictionResult(
                    user_id=user.id,
                    patient_identifier="PAC-NEW12345",
                    experiment="Pima",
                    model="Random Forest",
                    predicted_class=1,
                    probability=0.8,
                    decision_threshold=0.35,
                ),
            ]
        )
        db.commit()

    results = client.get("/results")

    assert results.status_code == 200
    assert results.json()["total"] == 1
    assert results.json()["items"][0]["patient_identifier"] == "PAC-NEW12345"
