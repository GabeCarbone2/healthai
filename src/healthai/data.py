"""Carregamento e validação dos dados tabulares."""

from pathlib import Path
from typing import Iterable

import pandas as pd


def validate_columns(dataframe: pd.DataFrame, required: Iterable[str]) -> None:
    """Garante que todas as colunas necessárias estejam presentes."""
    missing = sorted(set(required) - set(dataframe.columns))
    if missing:
        raise ValueError(f"Colunas ausentes no conjunto de dados: {missing}")


def load_dataset(
    path: str | Path,
    features: list[str],
    target: str | None = None,
) -> pd.DataFrame:
    """Lê um CSV e valida suas colunas de entrada e, se informado, o alvo."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dados não encontrados: {dataset_path}. "
            "Consulte data/README.md para preparar o CSV."
        )

    dataframe = pd.read_csv(dataset_path)
    required = [*features, *([target] if target else [])]
    validate_columns(dataframe, required)
    return dataframe

