"""Carregamento dos artefatos e execução de inferência."""

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
            "max": 20,
            "step": 1,
            "required": True,
        },
        {
            "key": "glucose_mg_dl",
            "label": "Glicose",
            "unit": "mg/dL",
            "type": "number",
            "min": 20,
            "max": 600,
            "step": 1,
        },
        {
            "key": "diastolic_bp_mmhg",
            "label": "Pressão diastólica",
            "unit": "mmHg",
            "type": "number",
            "min": 30,
            "max": 180,
            "step": 1,
        },
        {
            "key": "skin_thickness_mm",
            "label": "Espessura da prega cutânea",
            "unit": "mm",
            "type": "number",
            "min": 1,
            "max": 100,
            "step": 1,
        },
        {
            "key": "serum_insulin_muu_ml",
            "label": "Insulina sérica",
            "unit": "µU/mL",
            "type": "number",
            "min": 1,
            "max": 1000,
            "step": 1,
        },
        {
            "key": "bmi_kg_m2",
            "label": "IMC",
            "unit": "kg/m²",
            "type": "number",
            "min": 10,
            "max": 80,
            "step": 0.1,
        },
        {
            "key": "diabetes_pedigree_function",
            "label": "Função de pedigree",
            "type": "number",
            "min": 0,
            "max": 3,
            "step": 0.001,
        },
        {
            "key": "age_years",
            "label": "Idade",
            "unit": "anos",
            "type": "number",
            "min": 21,
            "max": 100,
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
            "max": 100,
            "step": 1,
            "required": True,
        },
        {
            "key": "bmi_kg_m2",
            "label": "IMC",
            "unit": "kg/m²",
            "type": "number",
            "min": 10,
            "max": 90,
            "step": 0.1,
        },
        {
            "key": "systolic_bp_mmhg",
            "label": "Pressão sistólica",
            "unit": "mmHg",
            "type": "number",
            "min": 60,
            "max": 260,
            "step": 1,
        },
        {
            "key": "diastolic_bp_mmhg",
            "label": "Pressão diastólica",
            "unit": "mmHg",
            "type": "number",
            "min": 30,
            "max": 180,
            "step": 1,
        },
        {
            "key": "hba1c_percent",
            "label": "Hemoglobina glicada",
            "unit": "%",
            "type": "number",
            "min": 2,
            "max": 20,
            "step": 0.1,
        },
        {
            "key": "glucose_mg_dl",
            "label": "Glicose em jejum",
            "unit": "mg/dL",
            "type": "number",
            "min": 20,
            "max": 600,
            "step": 1,
        },
    ],
}

EXPERIMENT_LABELS = {
    "pima": "Perfil feminino",
    "nhanes": "Perfil geral",
}


@lru_cache(maxsize=4)
def _load_artifact(model_path: str, modified_at: int) -> dict[str, Any]:
    return joblib.load(model_path)


def load_artifact(experiment: str) -> dict[str, Any]:
    """Carrega o modelo e atualiza o cache quando o artefato muda."""
    model_path = MODELS_DIR / f"{experiment}_selected.joblib"
    if not model_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Modelo {experiment} não encontrado. Execute make train.",
        )
    return _load_artifact(str(model_path), model_path.stat().st_mtime_ns)


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
        experiments.append(
            {
                "id": experiment,
                "label": EXPERIMENT_LABELS.get(experiment, experiment),
                "selected_model": metrics["selected_model"],
                "selected_model_label": MODEL_LABELS.get(
                    metrics["selected_model"], metrics["selected_model"]
                ),
                "source_dataset": metrics["source_dataset"],
                "n_train": metrics["n_train"],
                "n_test": metrics["n_test"],
                "selection": metrics["selection"],
                "models": metrics["models"],
                "input_fields": INPUT_FIELDS[experiment],
            }
        )
    return {"experiments": experiments, "model_labels": MODEL_LABELS}


def predict_record(experiment: str, values: dict[str, Any]) -> dict[str, Any]:
    """Executa uma previsão sem persistir o registro recebido."""
    artifact = load_artifact(experiment)
    model_input = pd.DataFrame([values], columns=artifact["features"])
    for column, mapping in artifact.get("category_mappings", {}).items():
        model_input[column] = model_input[column].map(mapping)
    for column, minimum in artifact.get("filters", {}).get("invalid_below", {}).items():
        model_input.loc[model_input[column].lt(minimum), column] = pd.NA

    pipeline = artifact["pipeline"]
    probability = float(pipeline.predict_proba(model_input)[0, 1])
    decision_threshold = float(artifact.get("decision_threshold", 0.5))
    predicted_class = int(probability >= decision_threshold)
    return {
        "experiment": experiment,
        "model": artifact["model_name"],
        "predicted_class": predicted_class,
        "probability": probability,
        "decision_threshold": decision_threshold,
    }
