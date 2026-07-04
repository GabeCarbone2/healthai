"""Leitura de configuração sem alterar globalmente o ambiente do processo."""

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_VALUES = dotenv_values(PROJECT_ROOT / ".env")


def setting(name: str, default: str = "") -> str:
    """Prioriza o ambiente real e usa `.env` apenas como fallback local."""
    value = os.getenv(name)
    if value is None:
        value = DOTENV_VALUES.get(name)
    return value if isinstance(value, str) else default
