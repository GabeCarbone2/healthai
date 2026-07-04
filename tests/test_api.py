from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.database import Base, get_db
from backend.models import (
    EmailVerificationToken,
    PredictionResult,
    User,
    UserSession,
)


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("HEALTHAI_EMAIL_DELIVERY", "console")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
        },
    )
    assert response.status_code == 201
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


def test_health_endpoint_is_public(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
        "notice_version": "2026-07-04.2",
        "result_retention_days": 90,
        "contact": "privacidade@example.com",
    }


def test_models_require_authentication(client: TestClient) -> None:
    response = client.get("/models")

    assert response.status_code == 401


def test_registration_requires_explicit_privacy_consent(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Usuário Teste",
            "email": "usuario@example.com",
            "password": "senha-segura",
            "privacy_accepted": False,
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
            "email": "USUARIO@example.com",
            "password": "senha-segura",
            "privacy_accepted": True,
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
        assert user.email_verified_at is None
        verification = db.scalar(select(EmailVerificationToken))
        assert verification is not None
        raw_token = parse_qs(
            urlparse(sent_message["verification_url"]).query
        )["token"][0]
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
    assert "HttpOnly" in verification_response.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 200
    with next(db_override()) as db:
        assert db.scalar(select(EmailVerificationToken)) is None


def test_invalid_email_verification_token_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/verify-email",
        json={"token": "x" * 32},
    )

    assert response.status_code == 400


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/register",
        json={
            "name": "Outro Nome",
            "email": "usuario@example.com",
            "password": "outra-senha",
            "privacy_accepted": True,
        },
    )

    assert response.status_code == 409


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
    assert consent.json()["privacy_notice_version"] == "2026-07-04.2"
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
        json={
            "patient_identifier": "PAC-A1B2C3D4",
            "pregnancies": 1,
            "age_years": 35,
        },
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
            "patient_identifier": "PAC-A1B2C3D4",
            "pregnancies": 2,
            "age_years": 42,
        },
    )

    assert prediction.status_code == 200
    results = client.get("/results")
    assert results.status_code == 200
    assert results.json()["total"] == 1
    assert prediction.json() == results.json()["items"][0]
    assert results.json()["items"][0] == {
        "id": 1,
        "patient_identifier": "PAC-A1B2C3D4",
        "created_at": results.json()["items"][0]["created_at"],
        "experiment": "Pima",
        "model": "Random Forest",
        "predicted_class": 1,
        "probability": 0.81,
        "decision_threshold": 0.35,
    }

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
            json={
                "patient_identifier": patient_identifier,
                "pregnancies": 1,
                "age_years": 35,
            },
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
    assert (
        results.json()["items"][0]["patient_identifier"]
        == "PAC-NEW12345"
    )
