"""Leitura de configuração sem alterar globalmente o ambiente do processo."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_VALUES = dotenv_values(PROJECT_ROOT / ".env")


def setting(name: str, default: str = "") -> str:
    """Prioriza o ambiente real e usa `.env` apenas como fallback local."""
    value = os.getenv(name)
    if value is None:
        value = DOTENV_VALUES.get(name)
    return value if isinstance(value, str) else default


def is_production_environment() -> bool:
    return setting("HEALTHAI_ENV", "development").strip().lower() in {
        "prod",
        "production",
    }


def validate_production_settings() -> None:
    """Interrompe a inicialização quando a produção está insegura/incompleta."""
    if not is_production_environment():
        return

    required = {
        "HEALTHAI_PRIVACY_CONTACT": setting("HEALTHAI_PRIVACY_CONTACT"),
        "HEALTHAI_FRONTEND_URL": setting("HEALTHAI_FRONTEND_URL"),
        "HEALTHAI_SMTP_HOST": setting("HEALTHAI_SMTP_HOST"),
        "HEALTHAI_SMTP_USERNAME": setting("HEALTHAI_SMTP_USERNAME"),
        "HEALTHAI_SMTP_PASSWORD": setting("HEALTHAI_SMTP_PASSWORD"),
        "HEALTHAI_EMAIL_FROM": setting("HEALTHAI_EMAIL_FROM"),
    }
    missing = sorted(name for name, value in required.items() if not value.strip())
    if missing:
        raise RuntimeError("Configuração de produção incompleta: " + ", ".join(missing))

    if "SUBSTITUA" in required["HEALTHAI_SMTP_PASSWORD"].upper():
        raise RuntimeError("Substitua a senha SMTP de exemplo antes do deploy.")

    if setting("HEALTHAI_EMAIL_DELIVERY", "console").strip().lower() != "smtp":
        raise RuntimeError("Produção exige HEALTHAI_EMAIL_DELIVERY=smtp.")

    if setting(
        "HEALTHAI_CRM_REVOCATION_MODE", "hard-fail"
    ).strip().lower() != "hard-fail":
        raise RuntimeError(
            "Produção exige HEALTHAI_CRM_REVOCATION_MODE=hard-fail."
        )

    trust_roots = setting("HEALTHAI_ICP_BRASIL_TRUST_ROOTS").strip()
    if trust_roots and not Path(trust_roots).expanduser().is_file():
        raise RuntimeError(
            "HEALTHAI_ICP_BRASIL_TRUST_ROOTS deve apontar para um arquivo."
        )

    frontend = urlparse(required["HEALTHAI_FRONTEND_URL"].strip())
    if frontend.scheme != "https" or not frontend.hostname:
        raise RuntimeError("HEALTHAI_FRONTEND_URL deve usar HTTPS em produção.")

    if required["HEALTHAI_PRIVACY_CONTACT"].strip().lower() in {
        "não configurado",
        "nao configurado",
    }:
        raise RuntimeError("Configure um canal de privacidade válido em produção.")
