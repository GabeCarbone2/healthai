import pytest

from backend.settings import validate_production_settings

PRODUCTION_SETTINGS = {
    "HEALTHAI_ENV": "production",
    "HEALTHAI_PRIVACY_CONTACT": "privacidade@example.com",
    "HEALTHAI_FRONTEND_URL": "https://healthai.example",
    "HEALTHAI_EMAIL_DELIVERY": "smtp",
    "HEALTHAI_CRM_REVOCATION_MODE": "hard-fail",
    "HEALTHAI_SMTP_HOST": "smtp.example.com",
    "HEALTHAI_SMTP_USERNAME": "mailer@example.com",
    "HEALTHAI_SMTP_PASSWORD": "secret",
    "HEALTHAI_EMAIL_FROM": "HealthAI <mailer@example.com>",
}


def configure_production(monkeypatch) -> None:
    for name, value in PRODUCTION_SETTINGS.items():
        monkeypatch.setenv(name, value)


def test_production_configuration_accepts_complete_https_setup(
    monkeypatch,
) -> None:
    configure_production(monkeypatch)

    validate_production_settings()


def test_production_configuration_rejects_missing_or_insecure_values(
    monkeypatch,
) -> None:
    configure_production(monkeypatch)
    monkeypatch.setenv("HEALTHAI_SMTP_PASSWORD", "")

    with pytest.raises(RuntimeError, match="HEALTHAI_SMTP_PASSWORD"):
        validate_production_settings()

    monkeypatch.setenv("HEALTHAI_SMTP_PASSWORD", "secret")
    monkeypatch.setenv("HEALTHAI_FRONTEND_URL", "http://healthai.example")
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_production_settings()

    monkeypatch.setenv("HEALTHAI_FRONTEND_URL", "https://healthai.example")
    monkeypatch.setenv("HEALTHAI_SMTP_PASSWORD", "SUBSTITUA_POR_UM_SEGREDO")
    with pytest.raises(RuntimeError, match="senha SMTP"):
        validate_production_settings()


def test_production_requires_hard_fail_certificate_revocation(
    monkeypatch,
) -> None:
    configure_production(monkeypatch)
    monkeypatch.setenv("HEALTHAI_CRM_REVOCATION_MODE", "soft-fail")

    with pytest.raises(RuntimeError, match="hard-fail"):
        validate_production_settings()
