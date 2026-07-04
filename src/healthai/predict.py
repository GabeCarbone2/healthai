"""Predições em lote com um pipeline previamente treinado."""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from healthai.data import load_dataset


def predict(
    input_path: str | Path,
    model_path: str | Path,
    output_path: str | Path,
) -> None:
    """Acrescenta classe e probabilidade preditas a um CSV."""
    artifact = joblib.load(model_path)
    features = artifact["features"]
    pipeline = artifact["pipeline"]
    dataframe = load_dataset(input_path, features)
    model_input = dataframe[features].copy()
    for column, mapping in artifact.get("category_mappings", {}).items():
        model_input[column] = model_input[column].map(mapping)

    eligible = pd.Series(True, index=dataframe.index)
    filters = artifact.get("filters", {})
    for column, minimum in filters.get("minimum_values", {}).items():
        eligible &= model_input[column].ge(minimum)
    for column, minimum in filters.get("invalid_below", {}).items():
        model_input.loc[model_input[column].lt(minimum), column] = pd.NA

    result = dataframe.copy()
    result["predicted_class"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["predicted_probability"] = np.nan
    result["decision_threshold"] = np.nan
    if eligible.any():
        eligible_input = model_input.loc[eligible]
        probabilities = pipeline.predict_proba(eligible_input)[:, 1]
        decision_threshold = artifact.get("decision_threshold", 0.5)
        result.loc[eligible, "predicted_class"] = (
            probabilities >= decision_threshold
        ).astype(int)
        result.loc[eligible, "predicted_probability"] = probabilities
        result.loc[eligible, "decision_threshold"] = decision_threshold

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa predições em um CSV.")
    parser.add_argument("--input", required=True, help="CSV contendo as variáveis.")
    parser.add_argument(
        "--model", required=True, help="Modelo selecionado para a base dos dados."
    )
    parser.add_argument("--output", required=True, help="Destino do CSV de resultados.")
    args = parser.parse_args()
    predict(args.input, args.model, args.output)


if __name__ == "__main__":
    main()
