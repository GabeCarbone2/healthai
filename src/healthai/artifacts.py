"""Contrato, compatibilidade e persistência atômica dos artefatos."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib

ARTIFACT_SCHEMA_VERSION = "2.0"
SUPPORTED_ARTIFACT_MAJOR_VERSIONS = {1, 2}


class ArtifactCompatibilityError(ValueError):
    """O artefato não pode ser usado com segurança por esta versão."""


def migrate_legacy_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta metadados seguros sem alterar a predição de artefatos v1."""
    migrated = artifact.copy()
    migrated.setdefault("artifact_schema_version", "1.0")
    migrated.setdefault("numeric_features", list(migrated.get("features", [])))
    migrated.setdefault("categorical_features", [])
    migrated.setdefault("category_mappings", {})
    migrated.setdefault("filters", {})
    migrated.setdefault("input_validation", {"required_features": []})
    migrated.setdefault("decision_threshold", 0.5)
    migrated.setdefault(
        "validation_rules",
        {
            "features": migrated.get("features", []),
            "numeric_features": migrated.get("numeric_features", []),
            "categorical_features": migrated.get("categorical_features", []),
            "filters": migrated.get("filters", {}),
            "input_validation": migrated.get("input_validation", {}),
            "category_mappings": migrated.get("category_mappings", {}),
        },
    )
    migrated["legacy_artifact"] = True
    return migrated


def validate_artifact(artifact: Any) -> dict[str, Any]:
    """Valida versão e campos indispensáveis antes de qualquer predição."""
    if not isinstance(artifact, dict):
        raise ArtifactCompatibilityError("Artefato deve ser um dicionário.")
    artifact = migrate_legacy_artifact(artifact)
    version = str(artifact.get("artifact_schema_version", "1.0"))
    try:
        major = int(version.split(".", maxsplit=1)[0])
    except (TypeError, ValueError) as error:
        raise ArtifactCompatibilityError(
            f"Versão de schema inválida: {version!r}."
        ) from error
    if major not in SUPPORTED_ARTIFACT_MAJOR_VERSIONS:
        raise ArtifactCompatibilityError(
            f"Schema de artefato incompatível: {version}. "
            "Versões principais suportadas: "
            f"{sorted(SUPPORTED_ARTIFACT_MAJOR_VERSIONS)}."
        )

    required = {"pipeline", "features"}
    missing = sorted(required - set(artifact))
    if missing:
        raise ArtifactCompatibilityError(
            f"Artefato incompleto; campos ausentes: {missing}."
        )
    if not hasattr(artifact["pipeline"], "predict_proba"):
        raise ArtifactCompatibilityError(
            "O pipeline do artefato não implementa predict_proba."
        )
    if not isinstance(artifact["features"], list) or not artifact["features"]:
        raise ArtifactCompatibilityError(
            "artifact.features deve ser uma lista não vazia."
        )
    threshold = artifact.get("decision_threshold")
    if (
        not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0 <= float(threshold) <= 1
    ):
        raise ArtifactCompatibilityError(
            "artifact.decision_threshold deve estar entre zero e um."
        )
    if major >= 2:
        required_v2 = {
            "artifact_schema_version",
            "validation_rules",
            "model_name",
            "model_version",
            "training_metadata",
        }
        missing_v2 = sorted(required_v2 - set(artifact))
        if missing_v2:
            raise ArtifactCompatibilityError(
                f"Artefato schema 2 incompleto; campos ausentes: {missing_v2}."
            )
        if artifact["validation_rules"].get("features") != artifact["features"]:
            raise ArtifactCompatibilityError(
                "Features do contrato de validação divergem do pipeline."
            )
    return artifact


def load_artifact_file(path: str | Path) -> dict[str, Any]:
    return validate_artifact(joblib.load(path))


def _temporary_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(name)
    permissions = destination.stat().st_mode & 0o777 if destination.exists() else 0o644
    temporary.chmod(permissions)
    return temporary


def atomic_joblib_dump(value: Any, path: str | Path) -> None:
    """Escreve joblib no mesmo filesystem e troca o destino atomicamente."""
    destination = Path(path)
    temporary = _temporary_path(destination)
    try:
        joblib.dump(value, temporary)
        with temporary.open("rb") as source:
            os.fsync(source.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(value: Any, path: str | Path) -> None:
    destination = Path(path)
    temporary = _temporary_path(destination)
    try:
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_csv(dataframe: Any, path: str | Path) -> None:
    destination = Path(path)
    temporary = _temporary_path(destination)
    try:
        dataframe.to_csv(temporary, index=False)
        with temporary.open("rb") as source:
            os.fsync(source.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
