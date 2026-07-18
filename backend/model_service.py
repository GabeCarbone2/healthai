"""Carregamento dos artefatos e execução de inferência."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "model_comparison.json"
MODELS_DIR = PROJECT_ROOT / "models"

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
    artifact = _load_artifact(str(model_path), model_path.stat().st_mtime_ns).copy()
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
    model_input = pd.DataFrame([values], columns=artifact["features"])
    for column, mapping in artifact.get("category_mappings", {}).items():
        model_input[column] = model_input[column].map(mapping)
    for column, minimum in artifact.get("filters", {}).get("invalid_below", {}).items():
        model_input.loc[model_input[column].lt(minimum), column] = pd.NA
    return model_input


def _local_reference_explanation(
    artifact: dict[str, Any],
    model_input: pd.DataFrame,
    probability: float,
) -> dict[str, Any]:
    """Mede sensibilidade local substituindo uma variável pela referência imputada.

    A explicação é calculada em memória e não é aditiva: cada efeito compara a
    predição original com uma nova execução em que somente aquela variável é
    omitida e substituída pelo valor de referência aprendido pelo pipeline.
    """
    pipeline = artifact["pipeline"]
    effects = []
    for feature in artifact["features"]:
        if pd.isna(model_input.at[0, feature]):
            continue
        reference_input = model_input.copy()
        reference_input.at[0, feature] = pd.NA
        reference_probability = float(pipeline.predict_proba(reference_input)[0, 1])
        effect = probability - reference_probability
        direction = (
            "increases"
            if effect > 1e-6
            else "decreases"
            if effect < -1e-6
            else "neutral"
        )
        effects.append(
            {
                "feature": feature,
                "probability_effect": effect,
                "direction": direction,
            }
        )
    effects.sort(key=lambda item: abs(item["probability_effect"]), reverse=True)
    return {
        "method": "single_feature_reference_replacement",
        "interpretation": (
            "Sensibilidade desta predição: cada efeito compara o resultado atual "
            "com uma nova execução em que apenas aquela variável é substituída "
            "pela referência estatística aprendida no treino. Os efeitos não são "
            "causais nem aditivos."
        ),
        "features": effects[:5],
    }


def predict_record(experiment: str, values: dict[str, Any]) -> dict[str, Any]:
    """Executa uma previsão sem persistir o registro recebido."""
    artifact = load_artifact(experiment)
    missing_feature_count = sum(
        values.get(feature) is None for feature in artifact["features"]
    )
    input_completeness = (len(artifact["features"]) - missing_feature_count) / len(
        artifact["features"]
    )
    model_input = _prepare_model_input(artifact, values)

    pipeline = artifact["pipeline"]
    probability = float(pipeline.predict_proba(model_input)[0, 1])
    decision_threshold = float(artifact.get("decision_threshold", 0.5))
    predicted_class = int(probability >= decision_threshold)
    return {
        "experiment": experiment,
        "model": artifact["model_name"],
        "model_version": artifact["model_version"],
        "predicted_class": predicted_class,
        "probability": probability,
        "decision_threshold": decision_threshold,
        "input_completeness": input_completeness,
        "missing_feature_count": missing_feature_count,
        "local_explanation": _local_reference_explanation(
            artifact,
            model_input,
            probability,
        ),
    }
