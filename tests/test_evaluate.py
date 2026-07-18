import numpy as np
import pandas as pd
import pytest

from healthai.evaluate import (
    bootstrap_confidence_intervals,
    calibration_summary,
    classification_metrics,
    explainability_summary,
    subgroup_bias_summary,
    subgroup_evaluation,
)
from healthai.features import build_model_pipeline


def test_metrics_include_brier_score_and_calibration_curve() -> None:
    labels = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.2, 0.8, 0.9])
    predictions = (probabilities >= 0.5).astype(int)

    metrics = classification_metrics(labels, predictions, probabilities)
    calibration = calibration_summary(
        labels,
        probabilities,
        n_bins=2,
        strategy="quantile",
    )

    assert metrics["brier_score"] == pytest.approx(0.025)
    assert calibration["effective_bins"] == 2
    assert sum(point["count"] for point in calibration["points"]) == 4
    assert calibration["expected_calibration_error"] == pytest.approx(0.15)


def test_bootstrap_intervals_are_reproducible_and_contain_estimate() -> None:
    labels = np.array([0, 0, 0, 1, 1, 1])
    probabilities = np.array([0.1, 0.2, 0.4, 0.6, 0.8, 0.9])
    predictions = (probabilities >= 0.5).astype(int)

    first = bootstrap_confidence_intervals(
        labels,
        predictions,
        probabilities,
        n_bootstrap=200,
        random_state=7,
    )
    second = bootstrap_confidence_intervals(
        labels,
        predictions,
        probabilities,
        n_bootstrap=200,
        random_state=7,
    )

    assert first == second
    for interval in first["metrics"].values():
        assert interval is not None
        assert interval["lower"] <= interval["estimate"] <= interval["upper"]


def test_subgroups_report_small_samples_instead_of_hiding_them() -> None:
    labels = np.array([0, 1, 0, 1, 1, 0])
    probabilities = np.array([0.2, 0.8, 0.3, 0.7, 0.6, 0.4])
    predictions = (probabilities >= 0.5).astype(int)
    dataframe = pd.DataFrame(
        {"sex": [0, 0, 0, 0, 1, 1]},
    )

    result = subgroup_evaluation(
        labels,
        predictions,
        probabilities,
        dataframe,
        [
            {
                "name": "sex",
                "column": "sex",
                "value_labels": {"0": "Masculino", "1": "Feminino"},
            }
        ],
        minimum_size=3,
        minimum_events=1,
        confidence_settings={"n_bootstrap": 20, "random_state": 42},
    )

    groups = result["sex"]["groups"]
    assert groups[0]["label"] == "Masculino"
    assert groups[0]["status"] == "estimated"
    assert groups[0]["confidence_intervals"] is not None
    assert groups[1]["label"] == "Feminino"
    assert groups[1]["status"] == "insufficient_sample"
    assert groups[1]["metrics"] is None


def test_subgroup_bias_summary_reports_metric_gaps() -> None:
    subgroup_result = {
        "sex": {
            "label": "Sexo",
            "dataset": "test",
            "minimum_size": 2,
            "minimum_events": 1,
            "groups": [
                {
                    "label": "Grupo A",
                    "status": "estimated",
                    "n": 20,
                    "positives": 10,
                    "metrics": {
                        "recall": 0.9,
                        "precision": 0.6,
                        "false_positive_rate": 0.2,
                        "roc_auc": 0.8,
                        "brier_score": 0.1,
                    },
                },
                {
                    "label": "Grupo B",
                    "status": "estimated",
                    "n": 20,
                    "positives": 10,
                    "metrics": {
                        "recall": 0.7,
                        "precision": 0.5,
                        "false_positive_rate": 0.4,
                        "roc_auc": 0.75,
                        "brier_score": 0.2,
                    },
                },
            ],
        }
    }

    summary = subgroup_bias_summary(subgroup_result)

    recall_gap = summary["sex"]["metrics"]["recall"]
    assert recall_gap["status"] == "estimated"
    assert recall_gap["absolute_gap"] == pytest.approx(0.2)
    assert recall_gap["lowest_group"]["label"] == "Grupo B"
    assert recall_gap["highest_group"]["label"] == "Grupo A"


def test_explainability_summary_returns_ranked_features() -> None:
    dataframe = pd.DataFrame(
        {
            "strong": [0, 0, 0, 1, 1, 1],
            "weak": [0, 1, 0, 1, 0, 1],
        }
    )
    labels = np.array([0, 0, 0, 1, 1, 1])
    pipeline = build_model_pipeline(
        "logistic_regression",
        {"max_iter": 200},
        numeric_features=["strong", "weak"],
        categorical_features=[],
    )
    pipeline.fit(dataframe, labels)

    explanation = explainability_summary(
        pipeline,
        dataframe,
        labels,
        scoring="accuracy",
        n_repeats=3,
        random_state=7,
    )

    assert explanation["method"] == "permutation_importance"
    assert [feature["rank"] for feature in explanation["features"]] == [1, 2]
    assert {feature["feature"] for feature in explanation["features"]} == {
        "strong",
        "weak",
    }
