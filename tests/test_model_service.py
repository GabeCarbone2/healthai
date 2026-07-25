from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import model_service
from backend.model_service import predict_record


@pytest.mark.parametrize(
    ("experiment", "values"),
    [
        (
            "pima",
            {
                "pregnancies": 2,
                "glucose_mg_dl": 120,
                "diastolic_bp_mmhg": 72,
                "skin_thickness_mm": None,
                "serum_insulin_muu_ml": None,
                "bmi_kg_m2": 28.5,
                "diabetes_pedigree_function": 0.45,
                "age_years": 42,
            },
        ),
        (
            "nhanes",
            {
                "sex": "female",
                "age_years": 48,
                "bmi_kg_m2": 29.1,
                "systolic_bp_mmhg": 128,
                "diastolic_bp_mmhg": 78,
                "hba1c_percent": 5.9,
                "glucose_mg_dl": 105,
            },
        ),
    ],
)
def test_prediction_includes_ephemeral_local_sensitivity(
    experiment: str,
    values: dict[str, object],
) -> None:
    prediction = predict_record(experiment, values)
    explanation = prediction["local_explanation"]

    assert explanation["method"] == "single_feature_reference_replacement"
    assert 1 <= len(explanation["features"]) <= 5
    assert all(
        feature["direction"] in {"increases", "decreases", "neutral"}
        for feature in explanation["features"]
    )
    assert all(
        set(feature) == {"feature", "probability_effect", "direction"}
        for feature in explanation["features"]
    )


def test_unknown_experiment_returns_service_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_service, "MODELS_DIR", tmp_path)

    with pytest.raises(HTTPException) as error:
        model_service.load_artifact("unknown")

    assert error.value.status_code == 503


def test_invalid_model_input_returns_detailed_422() -> None:
    with pytest.raises(HTTPException) as error:
        predict_record(
            "pima",
            {
                "pregnancies": 2,
                "glucose_mg_dl": 120,
                "bmi_kg_m2": 28.5,
                "diabetes_pedigree_function": 0.45,
                "age_years": 10,
            },
        )

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "invalid_model_input"
    assert error.value.detail["errors"]
