from pathlib import Path

import joblib
import pandas as pd
import pytest
import yaml

from healthai.train import (
    _model_version,
    _optimize_threshold,
    _prepare_experiment,
    train,
)


def test_optimize_threshold_uses_out_of_fold_probabilities() -> None:
    result = _optimize_threshold(
        pd.Series([0, 0, 1, 1]),
        probabilities=pd.Series([0.1, 0.2, 0.35, 0.4]).to_numpy(),
        settings={"beta": 2, "minimum": 0.2, "maximum": 0.5, "step": 0.05},
    )

    assert result["value"] == 0.35
    assert result["f_beta"] == 1.0


def test_train_saves_selected_model_per_experiment(tmp_path: Path) -> None:
    rows = []
    for source in ("source_a", "source_b"):
        for index in range(20):
            rows.append(
                {
                    "source": source,
                    "feature": float(index),
                    "target": int(index >= 10),
                }
            )
    data_path = tmp_path / "data.csv"
    pd.DataFrame(rows).to_csv(data_path, index=False)

    config = {
        "data": {
            "path": str(data_path),
            "target": "target",
            "source_column": "source",
        },
        "split": {"test_size": 0.2, "random_state": 42},
        "selection": {"scoring": "f1", "cv_folds": 2, "shuffle": True},
        "evaluation": {
            "calibration": {"n_bins": 2, "strategy": "quantile"},
            "confidence_intervals": {
                "enabled": True,
                "confidence_level": 0.95,
                "n_bootstrap": 20,
                "random_state": 42,
            },
        },
        "experiments": {
            "first": {
                "source_value": "source_a",
                "numeric_features": ["feature"],
                "categorical_features": [],
                "models": {
                    "logistic_regression": {
                        "enabled": True,
                        "params": {"max_iter": 100},
                    }
                },
            },
            "second": {
                "source_value": "source_b",
                "numeric_features": ["feature"],
                "categorical_features": [],
                "models": {
                    "random_forest": {
                        "enabled": True,
                        "params": {"n_estimators": 5},
                    }
                },
            },
        },
        "outputs": {
            "models_dir": str(tmp_path / "models"),
            "metrics_path": str(tmp_path / "reports" / "metrics.json"),
            "figures_dir": str(tmp_path / "reports" / "figures"),
        },
    }
    config_path = tmp_path / "models.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    results = train(config_path)

    assert results["first"]["selected_model"] == "logistic_regression"
    assert results["second"]["selected_model"] == "random_forest"
    for experiment in ("first", "second"):
        model_name = results[experiment]["selected_model"]
        validation = results[experiment]["models"][model_name]["cross_validation"]
        assert len(validation["fold_scores"]) == 2
        assert validation["method"] == "nested_stratified_cross_validation"
        assert len(validation["oof_probabilities"]) == 16
        assert validation["hyperparameter_search_scope"] == (
            "inner_training_folds_only"
        )
        assert "threshold" in results[experiment]["models"][model_name]
        assert "brier_score" in results[experiment]["models"][model_name]
        assert "calibration" in results[experiment]["models"][model_name]
        assert "bias_summary" in results[experiment]["models"][model_name]
        assert "external_validation" in results[experiment]
        assert (
            results[experiment]["models"][model_name]["confidence_intervals"][
                "n_bootstrap"
            ]
            == 20
        )
        assert (
            tmp_path / "reports" / "figures" / f"{experiment}_calibration.png"
        ).exists()
        artifact = joblib.load(tmp_path / "models" / f"{experiment}_selected.joblib")
        assert artifact["selected"] is True
        assert len(artifact["model_version"]) == 16
        assert results[experiment]["model_version"] == artifact["model_version"]
        assert artifact["cross_validation"] == validation
        assert artifact["artifact_schema_version"] == "2.0"
        assert (
            artifact["training_metadata"]["split_integrity"]["shared_index_count"] == 0
        )
        assert artifact["threshold_metrics"]["dataset"] == "training_out_of_fold"
        assert 0.1 <= artifact["decision_threshold"] <= 0.9


def test_non_binary_target_is_rejected() -> None:
    dataframe = pd.DataFrame(
        {"source": ["demo", "demo"], "feature": [1, 2], "target": [0, 2]}
    )
    experiment = {
        "source_value": "demo",
        "numeric_features": ["feature"],
        "categorical_features": [],
    }

    with pytest.raises(ValueError, match="não binário"):
        _prepare_experiment(
            dataframe,
            experiment,
            source_column="source",
            target="target",
        )


def test_model_version_changes_with_data_and_config(tmp_path: Path) -> None:
    data_a = tmp_path / "data-a.csv"
    data_b = tmp_path / "data-b.csv"
    config_a = tmp_path / "config-a.yaml"
    config_b = tmp_path / "config-b.yaml"
    data_a.write_text("x\n1\n", encoding="utf-8")
    data_b.write_text("x\n2\n", encoding="utf-8")
    config_a.write_text("seed: 1\n", encoding="utf-8")
    config_b.write_text("seed: 2\n", encoding="utf-8")
    common = {
        "experiment_name": "demo",
        "model_name": "logistic_regression",
        "threshold": {"value": 0.5},
        "validation": {"best_params": {}},
    }

    version = _model_version(data_path=data_a, config_path=config_a, **common)

    assert version != _model_version(
        data_path=data_b,
        config_path=config_a,
        **common,
    )
    assert version != _model_version(
        data_path=data_a,
        config_path=config_b,
        **common,
    )
