from pathlib import Path

import joblib
import pandas as pd

from healthai.features import build_model_pipeline
from healthai.predict import predict


def test_predict_applies_artifact_mappings_and_filters(tmp_path: Path) -> None:
    train_data = pd.DataFrame(
        {
            "sex": [0, 1, 0, 1],
            "age": [20, 30, 50, 60],
        }
    )
    pipeline = build_model_pipeline(
        "logistic_regression",
        numeric_features=["sex", "age"],
        categorical_features=[],
    )
    pipeline.fit(train_data, [0, 0, 1, 1])

    artifact_path = tmp_path / "model.joblib"
    joblib.dump(
        {
            "pipeline": pipeline,
            "features": ["sex", "age"],
            "category_mappings": {"sex": {"male": 0, "female": 1}},
            "filters": {"minimum_values": {"age": 18}},
            "decision_threshold": 0.9,
        },
        artifact_path,
    )
    input_path = tmp_path / "input.csv"
    pd.DataFrame(
        {
            "sex": ["female", "male"],
            "age": [10, 40],
        }
    ).to_csv(input_path, index=False)
    output_path = tmp_path / "predictions.csv"

    predict(input_path, artifact_path, output_path)

    result = pd.read_csv(output_path)
    assert pd.isna(result.loc[0, "predicted_class"])
    assert result.loc[1, "predicted_class"] == int(
        result.loc[1, "predicted_probability"] >= 0.9
    )
    assert result.loc[1, "decision_threshold"] == 0.9
    assert isinstance(result.loc[1, "model_version"], str)
    assert len(result.loc[1, "model_version"]) == 16
