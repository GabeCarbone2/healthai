import numpy as np
import pandas as pd
import pytest

from healthai.evaluate import (
    bootstrap_confidence_intervals,
    calibration_summary,
    classification_metrics,
    subgroup_evaluation,
)


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
