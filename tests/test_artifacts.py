from pathlib import Path

import joblib
import pytest

from healthai.artifacts import (
    ArtifactCompatibilityError,
    atomic_joblib_dump,
    migrate_legacy_artifact,
    validate_artifact,
)


class ProbabilityPipeline:
    def predict_proba(self, values):
        return [[0.5, 0.5] for _ in range(len(values))]


def test_legacy_artifact_gets_safe_validation_contract() -> None:
    migrated = migrate_legacy_artifact(
        {"pipeline": ProbabilityPipeline(), "features": ["age"]}
    )

    assert migrated["artifact_schema_version"] == "1.0"
    assert migrated["legacy_artifact"] is True
    assert migrated["validation_rules"]["features"] == ["age"]
    assert validate_artifact(migrated)["features"] == ["age"]


def test_incompatible_artifact_version_is_rejected() -> None:
    with pytest.raises(ArtifactCompatibilityError, match="incompatível"):
        validate_artifact(
            {
                "artifact_schema_version": "99.0",
                "pipeline": ProbabilityPipeline(),
                "features": ["age"],
            }
        )


def test_schema_two_requires_metadata_and_valid_threshold() -> None:
    with pytest.raises(ArtifactCompatibilityError, match="campos ausentes"):
        validate_artifact(
            {
                "artifact_schema_version": "2.0",
                "pipeline": ProbabilityPipeline(),
                "features": ["age"],
                "decision_threshold": 0.5,
            }
        )
    with pytest.raises(ArtifactCompatibilityError, match="entre zero e um"):
        validate_artifact(
            {
                "pipeline": ProbabilityPipeline(),
                "features": ["age"],
                "decision_threshold": 2,
            }
        )


def test_atomic_joblib_preserves_previous_file_on_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "artifact.joblib"
    joblib.dump({"version": "old"}, destination)

    def interrupted_dump(value, path):
        Path(path).write_bytes(b"partial")
        raise RuntimeError("interrupted")

    monkeypatch.setattr("healthai.artifacts.joblib.dump", interrupted_dump)
    with pytest.raises(RuntimeError, match="interrupted"):
        atomic_joblib_dump({"version": "new"}, destination)

    assert joblib.load(destination) == {"version": "old"}
    assert list(tmp_path.glob(".*.tmp")) == []
