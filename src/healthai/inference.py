"""Inferência compartilhada pela API e pelo processamento em lote."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from healthai.artifacts import validate_artifact
from healthai.input_validation import (
    InputValidationResult,
    prepare_and_validate_input,
)


@dataclass
class BatchPrediction:
    dataframe: pd.DataFrame
    validation: InputValidationResult


def predict_dataframe(
    artifact: dict[str, Any],
    dataframe: pd.DataFrame,
    *,
    enforce_required: bool = True,
) -> BatchPrediction:
    """Valida e prediz registros com o mesmo caminho usado em produção."""
    artifact = validate_artifact(artifact)
    rules = artifact["validation_rules"]
    validation = prepare_and_validate_input(
        dataframe,
        features=rules["features"],
        numeric_features=rules.get("numeric_features", []),
        categorical_features=rules.get("categorical_features", []),
        filters=rules.get("filters", {}),
        input_validation=rules.get("input_validation", {}),
        category_mappings=rules.get("category_mappings", {}),
        enforce_required=enforce_required,
    )

    result = dataframe.copy()
    result["prediction_status"] = np.where(
        validation.eligibility,
        "predicted",
        "invalid",
    )
    result["predicted_class"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["predicted_probability"] = np.nan
    result["decision_threshold"] = np.nan
    result["model_version"] = artifact.get("model_version", "unversioned")

    for name, values in (
        ("validation_errors", validation.errors),
        ("validation_warnings", validation.warnings),
        ("missing_features", validation.missing_features),
        ("imputed_features", validation.imputed_features),
        ("outside_applicability", validation.outside_applicability),
        ("exclusion_reasons", validation.exclusion_reasons),
    ):
        result[name] = values
    result["missing_feature_count"] = validation.missing_count
    result["input_completeness"] = validation.completeness

    if validation.eligibility.any():
        eligible_input = validation.dataframe.loc[validation.eligibility]
        probabilities = artifact["pipeline"].predict_proba(eligible_input)[:, 1]
        decision_threshold = float(artifact.get("decision_threshold", 0.5))
        result.loc[validation.eligibility, "predicted_class"] = (
            probabilities >= decision_threshold
        ).astype(int)
        result.loc[validation.eligibility, "predicted_probability"] = probabilities
        result.loc[validation.eligibility, "decision_threshold"] = decision_threshold
    return BatchPrediction(dataframe=result, validation=validation)


def local_reference_sensitivity(
    artifact: dict[str, Any],
    prepared_input: pd.DataFrame,
    probability: float,
    *,
    missing_features: list[str] | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Compara a predição com a referência aprendida para uma feature por vez."""
    artifact = validate_artifact(artifact)
    pipeline = artifact["pipeline"]
    missing = set(missing_features or [])
    effects: list[dict[str, Any]] = []
    expanded: list[dict[str, Any]] = []
    for feature in artifact["features"]:
        if feature in missing or pd.isna(prepared_input.iloc[0][feature]):
            continue
        reference_input = prepared_input.copy()
        original_value = reference_input.iloc[0][feature]
        # ``np.nan`` é aceito tanto pelos imputadores numéricos quanto pelo
        # categórico; ``pd.NA`` torna a comparação de objetos ambígua.
        reference_input.loc[reference_input.index[0], feature] = np.nan
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
        expanded.append(
            {
                "feature": feature,
                "original_value": (
                    original_value.item()
                    if hasattr(original_value, "item")
                    else original_value
                ),
                "baseline_probability": probability,
                "reference_probability": reference_probability,
                "probability_effect": effect,
                "absolute_effect": abs(effect),
                "direction": direction,
                "reference": "pipeline_training_imputation",
            }
        )
    effects.sort(key=lambda item: abs(item["probability_effect"]), reverse=True)
    expanded.sort(key=lambda item: item["absolute_effect"], reverse=True)
    return {
        # Nome legado preservado para clientes existentes.
        "method": "single_feature_reference_replacement",
        "concept": "local_sensitivity_to_training_reference",
        "interpretation": (
            "Sensibilidade local, não explicação causal: cada efeito compara a "
            "predição atual com uma nova execução em que uma variável é substituída "
            "pela referência aprendida no treino. Os efeitos não são aditivos."
        ),
        "features": effects[:top_n],
        "reference_effects": expanded[:top_n],
    }
