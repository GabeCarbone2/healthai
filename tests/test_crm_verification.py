from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from asn1crypto import core
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier
from fastapi.testclient import TestClient
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.crm_verification import (
    CRM_NUMBER_OID,
    CRM_STATE_OID,
    _load_trust_roots,
)
from backend.database import Base, _configure_sqlite_connection, get_db
from backend.models import CrmReviewEvent, CrmVerificationChallenge, User


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("HEALTHAI_EMAIL_DELIVERY", "console")
    monkeypatch.setenv("HEALTHAI_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("HEALTHAI_CRM_REVOCATION_MODE", "soft-fail")
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
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _authenticate_pending_doctor(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "Médica Teste",
            "crm": "123456",
            "crm_uf": "SP",
            "email": "medica@example.com",
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
        db.commit()
    login = client.post(
        "/auth/login",
        json={"email": "medica@example.com", "password": "senha-segura"},
    )
    assert login.status_code == 200
    assert login.json()["crm_status"] == "pending"


def _create_test_signer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    crm: str = "123456",
    crm_uf: str = "SP",
) -> signers.SimpleSigner:
    now = datetime.now(timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "HealthAI Test Root")]
    )
    root_certificate = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(root_key, hashes.SHA256())
    )

    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer_certificate = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name(
                [x509.NameAttribute(NameOID.COMMON_NAME, "Médica Teste")]
            )
        )
        .issuer_name(root_name)
        .public_key(signer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.OtherName(
                        ObjectIdentifier(CRM_NUMBER_OID),
                        core.UTF8String(crm).dump(),
                    ),
                    x509.OtherName(
                        ObjectIdentifier(CRM_STATE_OID),
                        core.UTF8String(crm_uf).dump(),
                    ),
                ]
            ),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )

    root_path = tmp_path / "test-root.pem"
    root_path.write_bytes(
        root_certificate.public_bytes(serialization.Encoding.PEM)
    )
    signer_path = tmp_path / "test-signer.p12"
    signer_path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"healthai-test-signer",
            signer_key,
            signer_certificate,
            [root_certificate],
            serialization.BestAvailableEncryption(b"test-passphrase"),
        )
    )
    monkeypatch.setenv(
        "HEALTHAI_ICP_BRASIL_TRUST_ROOTS",
        str(root_path),
    )
    _load_trust_roots.cache_clear()
    signer = signers.SimpleSigner.load_pkcs12(
        str(signer_path),
        passphrase=b"test-passphrase",
    )
    assert signer is not None
    return signer


def _sign_pdf(unsigned_pdf: bytes, signer: signers.SimpleSigner) -> bytes:
    output = BytesIO()
    pdf_signer = signers.PdfSigner(
        signers.PdfSignatureMetadata(field_name="HealthAiCrmSignature"),
        signer=signer,
        new_field_spec=SigFieldSpec("HealthAiCrmSignature"),
    )
    pdf_signer.sign_pdf(
        IncrementalPdfFileWriter(BytesIO(unsigned_pdf)),
        output=output,
    )
    return output.getvalue()


def test_signed_pdf_approves_crm_without_administrator(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authenticate_pending_doctor(client)
    signer = _create_test_signer(tmp_path, monkeypatch)

    initial_status = client.get("/auth/crm-verification")
    assert initial_status.status_code == 200
    assert initial_status.json()["active_challenge"] is None

    created = client.post("/auth/crm-verification/challenge")
    assert created.status_code == 201
    challenge_id = created.json()["id"]
    assert created.json()["download_url"].endswith(
        f"/{challenge_id}/document"
    )

    download = client.get(created.json()["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["cache-control"] == "no-store"
    signed_pdf = _sign_pdf(download.content, signer)

    approved = client.post(
        "/auth/crm-verification/submit",
        data={"challenge_id": str(challenge_id)},
        files={
            "signed_pdf": (
                "healthai-verificacao-crm-assinado.pdf",
                signed_pdf,
                "application/pdf",
            )
        },
    )
    assert approved.status_code == 200
    assert approved.json()["crm_status"] == "approved"
    assert approved.json()["crm_verified_at"] is not None
    assert approved.json()["crm_verified_by"] is None
    assert client.get("/models").status_code == 200

    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        challenge = db.get(CrmVerificationChallenge, challenge_id)
        event_record = db.scalar(select(CrmReviewEvent))
        assert challenge is not None
        assert challenge.used_at is not None
        assert len(challenge.signer_certificate_sha256 or "") == 64
        assert len(challenge.signed_document_sha256 or "") == 64
        assert event_record is not None
        assert event_record.source == "signed_pdf"
        assert (
            event_record.evidence_fingerprint
            == challenge.signed_document_sha256
        )

    assert client.get(created.json()["download_url"]).status_code == 409
    assert (
        client.post(
            "/auth/crm-verification/submit",
            data={"challenge_id": str(challenge_id)},
            files={"signed_pdf": ("signed.pdf", signed_pdf, "application/pdf")},
        ).status_code
        == 409
    )


def test_certificate_must_match_declared_crm(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authenticate_pending_doctor(client)
    signer = _create_test_signer(
        tmp_path,
        monkeypatch,
        crm="654321",
    )
    created = client.post("/auth/crm-verification/challenge")
    challenge_id = created.json()["id"]
    unsigned_pdf = client.get(created.json()["download_url"]).content

    rejected = client.post(
        "/auth/crm-verification/submit",
        data={"challenge_id": str(challenge_id)},
        files={
            "signed_pdf": (
                "signed.pdf",
                _sign_pdf(unsigned_pdf, signer),
                "application/pdf",
            )
        },
    )

    assert rejected.status_code == 422
    assert "CRM informado" in rejected.json()["detail"]
    assert client.get("/auth/me").json()["crm_status"] == "pending"
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        challenge = db.get(CrmVerificationChallenge, challenge_id)
        assert challenge is not None
        assert challenge.used_at is None


def test_pdf_changed_after_signature_is_rejected(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authenticate_pending_doctor(client)
    signer = _create_test_signer(tmp_path, monkeypatch)
    created = client.post("/auth/crm-verification/challenge")
    unsigned_pdf = client.get(created.json()["download_url"]).content
    altered_pdf = _sign_pdf(unsigned_pdf, signer) + b"\n% changed after signing\n"

    rejected = client.post(
        "/auth/crm-verification/submit",
        data={"challenge_id": str(created.json()["id"])},
        files={"signed_pdf": ("altered.pdf", altered_pdf, "application/pdf")},
    )

    assert rejected.status_code == 422
    assert "alterado" in rejected.json()["detail"]


def test_expired_challenge_cannot_be_downloaded_or_submitted(
    client: TestClient,
) -> None:
    _authenticate_pending_doctor(client)
    created = client.post("/auth/crm-verification/challenge")
    challenge_id = created.json()["id"]
    db_override = app.dependency_overrides[get_db]
    with next(db_override()) as db:
        challenge = db.get(CrmVerificationChallenge, challenge_id)
        assert challenge is not None
        challenge.expires_at = 0
        db.commit()

    expired_download = client.get(created.json()["download_url"])
    expired_submit = client.post(
        "/auth/crm-verification/submit",
        data={"challenge_id": str(challenge_id)},
        files={"signed_pdf": ("signed.pdf", b"%PDF-invalid", "application/pdf")},
    )

    assert expired_download.status_code == 410
    assert expired_submit.status_code == 410
    assert (
        client.get("/auth/crm-verification").json()["active_challenge"]
        is None
    )
