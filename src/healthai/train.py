"""Treinamento do modelo baseline."""

import argparse
import json
from pathlib import Path

import joblib
from sklearn.model_selection import train_test_split

from healthai.config import load_config
from healthai.data import load_dataset
from healthai.evaluate import classification_metrics
from healthai.features import build_baseline_pipeline


def train(config_path: str | Path) -> dict[str, object]:
    """Treina e salva o pipeline conforme um arquivo de configuração."""
    config = load_config(config_path)
    data_config = config["data"]
    split_config = config["split"]
    model_config = config["model"]
    output_config = config["outputs"]

    features = data_config["features"]
    target = data_config["target"]
    dataframe = load_dataset(data_config["path"], features, target)

    x_train, x_test, y_train, y_test = train_test_split(
        dataframe[features],
        dataframe[target],
        test_size=split_config["test_size"],
        random_state=split_config["random_state"],
        stratify=dataframe[target],
    )

    pipeline = build_baseline_pipeline(
        max_iter=model_config["max_iter"],
        class_weight=model_config["class_weight"],
    )
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    probabilities = pipeline.predict_proba(x_test)[:, 1]
    metrics = classification_metrics(y_test, predictions, probabilities)

    model_path = Path(output_config["model_path"])
    metrics_path = Path(output_config["metrics_path"])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {"pipeline": pipeline, "features": features, "target": target}
    joblib.dump(artifact, model_path)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina o baseline do HealthAI.")
    parser.add_argument(
        "--config", default="configs/baseline.yaml", help="Arquivo YAML do experimento."
    )
    args = parser.parse_args()
    metrics = train(args.config)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

