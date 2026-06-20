"""Predições em lote com um pipeline previamente treinado."""

import argparse
from pathlib import Path

import joblib

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

    result = dataframe.copy()
    result["predicted_class"] = pipeline.predict(dataframe[features])
    result["predicted_probability"] = pipeline.predict_proba(dataframe[features])[:, 1]

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa predições em um CSV.")
    parser.add_argument("--input", required=True, help="CSV contendo as variáveis.")
    parser.add_argument(
        "--model", default="models/diabetes_pipeline.joblib", help="Modelo treinado."
    )
    parser.add_argument("--output", required=True, help="Destino do CSV de resultados.")
    args = parser.parse_args()
    predict(args.input, args.model, args.output)


if __name__ == "__main__":
    main()
