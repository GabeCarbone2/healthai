"""Carregamento dos artefatos e execução de inferência."""

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException

from healthai.artifacts import ArtifactCompatibilityError, validate_artifact
from healthai.inference import local_reference_sensitivity, predict_dataframe

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "model_comparison.json"
MODELS_DIR = PROJECT_ROOT / "models"
LOGGER = logging.getLogger("healthai.ml.inference")

MODEL_LABELS = {
    "logistic_regression": "Regressão Logística",
    "random_forest": "Random Forest",
    "svm": "SVM",
}

INPUT_FIELDS = {
    "pima": [
        {
            "key": "pregnancies",
            "label": "Gestações",
            "type": "number",
            "min": 0,
            "max": 17,
            "step": 1,
            "required": True,
        },
        {
            "key": "glucose_mg_dl",
            "label": "Glicose",
            "unit": "mg/dL",
            "type": "number",
            "min": 44,
            "max": 199,
            "step": 1,
            "required": True,
        },
        {
            "key": "diastolic_bp_mmhg",
            "label": "Pressão diastólica",
            "unit": "mmHg",
            "type": "number",
            "min": 30,
            "max": 122,
            "step": 1,
        },
        {
            "key": "skin_thickness_mm",
            "label": "Espessura da prega cutânea",
            "unit": "mm",
            "type": "number",
            "min": 7,
            "max": 99,
            "step": 1,
        },
        {
            "key": "serum_insulin_muu_ml",
            "label": "Insulina sérica",
            "unit": "µU/mL",
            "type": "number",
            "min": 14,
            "max": 846,
            "step": 1,
        },
        {
            "key": "bmi_kg_m2",
            "label": "IMC",
            "unit": "kg/m²",
            "type": "number",
            "min": 18.2,
            "max": 67.1,
            "step": 0.1,
            "required": True,
        },
        {
            "key": "diabetes_pedigree_function",
            "label": "Função de pedigree",
            "type": "number",
            "min": 0.078,
            "max": 2.42,
            "step": 0.001,
            "required": True,
        },
        {
            "key": "age_years",
            "label": "Idade",
            "unit": "anos",
            "type": "number",
            "min": 21,
            "max": 81,
            "step": 1,
            "required": True,
        },
    ],
    "nhanes": [
        {
            "key": "sex",
            "label": "Sexo",
            "type": "select",
            "required": True,
            "options": [
                {"value": "female", "label": "Feminino"},
                {"value": "male", "label": "Masculino"},
            ],
        },
        {
            "key": "age_years",
            "label": "Idade",
            "unit": "anos",
            "type": "number",
            "min": 18,
            "max": 80,
            "step": 1,
            "required": True,
        },
        {
            "key": "bmi_kg_m2",
            "label": "IMC",
            "unit": "kg/m²",
            "type": "number",
            "min": 14.2,
            "max": 86.2,
            "step": 0.1,
            "required": True,
        },
        {
            "key": "systolic_bp_mmhg",
            "label": "Pressão sistólica",
            "unit": "mmHg",
            "type": "number",
            "min": 73,
            "max": 238,
            "step": 1,
        },
        {
            "key": "diastolic_bp_mmhg",
            "label": "Pressão diastólica",
            "unit": "mmHg",
            "type": "number",
            "min": 31,
            "max": 136,
            "step": 1,
        },
        {
            "key": "hba1c_percent",
            "label": "Hemoglobina glicada",
            "unit": "%",
            "type": "number",
            "min": 3.8,
            "max": 16.2,
            "step": 0.1,
            "required": True,
        },
        {
            "key": "glucose_mg_dl",
            "label": "Glicose em jejum",
            "unit": "mg/dL",
            "type": "number",
            "min": 47,
            "max": 421,
            "step": 1,
        },
    ],
}

EXPERIMENT_LABELS = {
    "pima": "Perfil feminino — base Pima",
    "nhanes": "Perfil geral — base NHANES",
}


@lru_cache(maxsize=4)
def _load_artifact(model_path: str, modified_at: int) -> dict[str, Any]:
    return joblib.load(model_path)


@lru_cache(maxsize=4)
def _artifact_version(model_path: str, modified_at: int) -> str:
    return hashlib.sha256(Path(model_path).read_bytes()).hexdigest()[:16]


def load_artifact(experiment: str) -> dict[str, Any]:
    """Carrega o modelo e atualiza o cache quando o artefato muda."""
    model_path = MODELS_DIR / f"{experiment}_selected.joblib"
    if not model_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Modelo {experiment} não encontrado. Execute make train.",
        )
    try:
        raw_artifact = _load_artifact(
            str(model_path), model_path.stat().st_mtime_ns
        ).copy()
        artifact = validate_artifact(raw_artifact)
    except (
        OSError,
        EOFError,
        ValueError,
        TypeError,
        ArtifactCompatibilityError,
    ) as error:
        LOGGER.exception(
            "artifact_load_failed experiment=%s path=%s",
            experiment,
            model_path.name,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_artifact_incompatible_or_corrupted",
                "message": (
                    f"O artefato do modelo {experiment} não pôde ser validado."
                ),
            },
        ) from error
    artifact.setdefault(
        "model_version",
        _artifact_version(str(model_path), model_path.stat().st_mtime_ns),
    )
    return artifact


def get_catalog() -> dict[str, Any]:
    """Retorna metadados dos experimentos e resultados versionados."""
    if not REPORT_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Relatório de modelos não encontrado. Execute make train.",
        )
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    experiments = []
    for experiment, metrics in report.items():
        artifact = load_artifact(experiment)
        experiments.append(
            {
                "id": experiment,
                "label": EXPERIMENT_LABELS.get(experiment, experiment),
                "selected_model": metrics["selected_model"],
                "selected_model_label": MODEL_LABELS.get(
                    metrics["selected_model"], metrics["selected_model"]
                ),
                "model_version": artifact["model_version"],
                "source_dataset": metrics["source_dataset"],
                "n_train": metrics["n_train"],
                "n_test": metrics["n_test"],
                "selection": metrics["selection"],
                "models": metrics["models"],
                "input_fields": INPUT_FIELDS[experiment],
            }
        )
    return {"experiments": experiments, "model_labels": MODEL_LABELS}


def _prepare_model_input(
    artifact: dict[str, Any],
    values: dict[str, Any],
) -> pd.DataFrame:
    batch = predict_dataframe(
        artifact,
        pd.DataFrame([values]),
        enforce_required=True,
    )
    return batch.validation.dataframe


def _local_reference_explanation(
    artifact: dict[str, Any],
    model_input: pd.DataFrame,
    probability: float,
) -> dict[str, Any]:
    return local_reference_sensitivity(artifact, model_input, probability)


def predict_record(experiment: str, values: dict[str, Any]) -> dict[str, Any]:
    """Executa uma previsão sem persistir o registro recebido."""
    artifact = load_artifact(experiment)
    try:
        batch = predict_dataframe(
            artifact,
            pd.DataFrame([values]),
            enforce_required=True,
        )
    except (ValueError, TypeError) as error:
        LOGGER.exception("input_preparation_failed experiment=%s", experiment)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "input_preparation_failed",
                "message": str(error),
            },
        ) from error
    row_index = batch.dataframe.index[0]
    diagnostics = batch.validation.row_diagnostics(row_index)
    if not diagnostics["eligible"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_model_input",
                "message": "A entrada não atende ao contrato do modelo.",
                "errors": diagnostics["errors"],
                "warnings": diagnostics["warnings"],
                "input_completeness": diagnostics["input_completeness"],
                "missing_features": diagnostics["missing_features"],
                "outside_applicability": diagnostics["outside_applicability"],
            },
        )

    probability = float(batch.dataframe.loc[row_index, "predicted_probability"])
    decision_threshold = float(batch.dataframe.loc[row_index, "decision_threshold"])
    predicted_class = int(batch.dataframe.loc[row_index, "predicted_class"])
    model_input = batch.validation.dataframe.loc[[row_index]]
    LOGGER.info(
        "prediction_completed experiment=%s model_version=%s status=predicted "
        "warning_count=%d missing_count=%d",
        experiment,
        artifact["model_version"],
        len(diagnostics["warnings"]),
        diagnostics["missing_feature_count"],
    )
    return {
        "experiment": experiment,
        "model": artifact["model_name"],
        "model_version": artifact["model_version"],
        "predicted_class": predicted_class,
        "probability": probability,
        "decision_threshold": decision_threshold,
        "input_completeness": diagnostics["input_completeness"],
        "missing_feature_count": diagnostics["missing_feature_count"],
        "input_status": "predicted",
        "validation_warnings": diagnostics["warnings"],
        "missing_features": diagnostics["missing_features"],
        "imputed_features": diagnostics["imputed_features"],
        "outside_applicability": diagnostics["outside_applicability"],
        "local_explanation": local_reference_sensitivity(
            artifact,
            model_input,
            probability,
            missing_features=diagnostics["missing_features"],
        ),
    }
