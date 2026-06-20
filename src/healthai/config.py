"""Leitura e validação da configuração dos experimentos."""

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega um arquivo YAML de configuração."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuração não encontrada: {config_path}")

    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("A configuração deve ser um mapeamento YAML.")
    return config

