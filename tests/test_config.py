from pathlib import Path

import pytest
import yaml

from healthai.config import load_config


def _minimal_config(tmp_path: Path) -> dict:
    return {
        "data": {"path": "data.csv", "target": "target", "source_column": "source"},
        "experiments": {
            "demo": {
                "source_value": "demo",
                "numeric_features": ["age"],
                "models": {"logistic_regression": {"enabled": True}},
            }
        },
        "outputs": {
            "models_dir": "models",
            "metrics_path": "reports/metrics.json",
        },
    }


def test_config_rejects_unknown_keys_with_path(tmp_path: Path) -> None:
    config = _minimal_config(tmp_path)
    config["selection"] = {"scorring": "roc_auc"}
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="scorring"):
        load_config(path)


def test_config_rejects_rules_for_unknown_features(tmp_path: Path) -> None:
    config = _minimal_config(tmp_path)
    config["experiments"]["demo"]["filters"] = {
        "hard_limits": {"glucose": {"minimum": 0, "maximum": 1000}}
    }
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="glucose"):
        load_config(path)
