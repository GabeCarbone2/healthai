import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from healthai.features import build_model_pipeline


@pytest.mark.parametrize(
    ("model_name", "classifier_type"),
    [
        ("logistic_regression", LogisticRegression),
        ("random_forest", RandomForestClassifier),
        ("svm", CalibratedClassifierCV),
        ("gradient_boosting", GradientBoostingClassifier),
    ],
)
def test_model_pipeline_handles_missing_values(
    model_name: str, classifier_type: type
) -> None:
    x = np.array([[80.0, 20.0], [120.0, np.nan], [160.0, 35.0], [190.0, 40.0]])
    y = np.array([0, 0, 1, 1])
    params = {
        "random_forest": {"n_estimators": 5},
        "gradient_boosting": {"n_estimators": 5},
        "svm": {"calibration_cv": 2},
    }.get(model_name, {})
    pipeline = build_model_pipeline(model_name, params)

    pipeline.fit(x, y)

    assert pipeline.predict([[130.0, np.nan]]).shape == (1,)
    assert pipeline.predict_proba([[130.0, np.nan]]).shape == (1, 2)
    assert isinstance(pipeline.named_steps["classifier"], classifier_type)


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="Modelo desconhecido"):
        build_model_pipeline("neural_network")


def test_pipeline_handles_numeric_and_categorical_features() -> None:
    dataframe = pd.DataFrame(
        {
            "age": [25.0, 35.0, 55.0, np.nan],
            "sex": ["female", "male", "female", "male"],
        }
    )
    target = np.array([0, 0, 1, 1])
    pipeline = build_model_pipeline(
        "logistic_regression",
        numeric_features=["age"],
        categorical_features=["sex"],
    )

    pipeline.fit(dataframe, target)
    prediction = pipeline.predict(pd.DataFrame({"age": [45.0], "sex": ["other"]}))

    assert prediction.shape == (1,)
