"""Predições em lote com o mesmo contrato de inferência usado pela API."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from healthai.artifacts import atomic_write_csv, load_artifact_file
from healthai.inference import predict_dataframe


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def predict(
    input_path: str | Path,
    model_path: str | Path,
    output_path: str | Path,
    *,
    fail_on_invalid: bool = False,
) -> dict[str, int]:
    """Valida, prediz e grava status detalhado para cada linha do CSV."""
    model_path = Path(model_path)
    artifact = load_artifact_file(model_path)
    artifact["model_version"] = artifact.get(
        "model_version",
        hashlib.sha256(model_path.read_bytes()).hexdigest()[:16],
    )
    dataframe = pd.read_csv(input_path)
    batch = predict_dataframe(artifact, dataframe, enforce_required=True)
    result = batch.dataframe.copy()
    structured_columns = (
        "validation_errors",
        "validation_warnings",
        "missing_features",
        "imputed_features",
        "outside_applicability",
        "exclusion_reasons",
    )
    for column in structured_columns:
        result[column] = result[column].map(_json_cell)

    atomic_write_csv(result, output_path)
    invalid_count = int((result["prediction_status"] == "invalid").sum())
    summary = {
        "total": int(len(result)),
        "predicted": int((result["prediction_status"] == "predicted").sum()),
        "invalid": invalid_count,
    }
    if fail_on_invalid and invalid_count:
        raise ValueError(
            f"{invalid_count} registro(s) inválido(s); consulte {output_path}."
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa predições em um CSV.")
    parser.add_argument("--input", required=True, help="CSV contendo as variáveis.")
    parser.add_argument(
        "--model", required=True, help="Modelo selecionado para a base dos dados."
    )
    parser.add_argument("--output", required=True, help="Destino do CSV de resultados.")
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Retorna erro após gravar o relatório se houver linha inválida.",
    )
    args = parser.parse_args()
    summary = predict(
        args.input,
        args.model,
        args.output,
        fail_on_invalid=args.fail_on_invalid,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
