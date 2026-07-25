import joblib
import numpy as np
import pandas as pd
import pytest

from backend import model_service
from healthai.features import build_model_pipeline
from healthai.inference import predict_dataframe
from healthai.input_validation import prepare_and_validate_input
from healthai.predict import predict


def test_pima_clinical_zeros_become_imputable_missing_values() -> None:
    result = prepare_and_validate_input(
        pd.DataFrame(
            {
                "glucose_mg_dl": [0.0],
                "bmi_kg_m2": [31.0],
                "age_years": [42],
            }
        ),
        features=["glucose_mg_dl", "bmi_kg_m2", "age_years"],
        numeric_features=["glucose_mg_dl", "bmi_kg_m2", "age_years"],
        filters={
            "invalid_values": {"glucose_mg_dl": [0]},
            "minimum_values": {"age_years": 21},
        },
        input_validation={
            "required_features": ["glucose_mg_dl", "age_years"],
        },
        enforce_required=True,
    )

    assert result.eligibility.iloc[0]
    assert pd.isna(result.dataframe.iloc[0]["glucose_mg_dl"])
    assert result.imputed_features.iloc[0] == ["glucose_mg_dl"]
    assert {warning["code"] for warning in result.warnings.iloc[0]} >= {
        "invalid_value_treated_as_missing"
    }


def test_pregnancies_zero_remains_valid() -> None:
    result = prepare_and_validate_input(
        pd.DataFrame({"pregnancies": [0], "age_years": [30]}),
        features=["pregnancies", "age_years"],
        numeric_features=["pregnancies", "age_years"],
        filters={
            "invalid_values": {"glucose_mg_dl": [0]},
            "minimum_values": {"age_years": 21},
        },
    )

    assert result.eligibility.iloc[0]
    assert result.dataframe.iloc[0]["pregnancies"] == 0


def test_unknown_category_and_hard_limit_block_but_applicability_only_warns() -> None:
    result = prepare_and_validate_input(
        pd.DataFrame(
            {
                "sex": ["unknown", "female", "male"],
                "age": [45, 95, 999],
            }
        ),
        features=["sex", "age"],
        numeric_features=["age"],
        categorical_features=["sex"],
        filters={
            "hard_limits": {"age": {"minimum": 0, "maximum": 130}},
            "applicability_ranges": {"age": {"minimum": 18, "maximum": 80}},
        },
        input_validation={"allowed_categories": {"sex": ["female", "male"]}},
    )

    assert not result.eligibility.iloc[0]
    assert result.errors.iloc[0][0]["code"] == "unknown_category"
    assert result.eligibility.iloc[1]
    assert result.outside_applicability.iloc[1] == ["age"]
    assert not result.eligibility.iloc[2]
    assert result.errors.iloc[2][0]["code"] == "above_hard_limit"


def test_required_and_minimum_completeness_have_distinct_errors() -> None:
    result = prepare_and_validate_input(
        pd.DataFrame({"required": [None], "optional": [None]}),
        features=["required", "optional"],
        numeric_features=["required", "optional"],
        input_validation={
            "required_features": ["required"],
            "minimum_completeness": 0.75,
        },
        enforce_required=True,
    )

    assert not result.eligibility.iloc[0]
    assert {issue["code"] for issue in result.errors.iloc[0]} == {
        "missing_required_value",
        "insufficient_input_completeness",
    }


@pytest.mark.parametrize(
    ("dataframe", "message"),
    [
        (pd.DataFrame(), "vazio"),
        (
            pd.DataFrame([[1, 2]], columns=["age", "age"]),
            "duplicadas",
        ),
    ],
)
def test_structurally_invalid_inputs_are_rejected(
    dataframe: pd.DataFrame,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        prepare_and_validate_input(dataframe, features=["age"])


def test_infinite_numeric_value_is_rejected() -> None:
    result = prepare_and_validate_input(
        pd.DataFrame({"age": [np.inf]}),
        features=["age"],
        numeric_features=["age"],
    )

    assert not result.eligibility.iloc[0]
    assert result.errors.iloc[0][0]["code"] == "non_finite_numeric_value"


def test_api_and_batch_paths_return_identical_probability(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    training = pd.DataFrame({"age": [20.0, 30.0, 50.0, 60.0]})
    pipeline = build_model_pipeline(
        "logistic_regression",
        numeric_features=["age"],
        categorical_features=[],
    ).fit(training, [0, 0, 1, 1])
    artifact = {
        "artifact_schema_version": "2.0",
        "pipeline": pipeline,
        "features": ["age"],
        "numeric_features": ["age"],
        "categorical_features": [],
        "validation_rules": {
            "features": ["age"],
            "numeric_features": ["age"],
            "categorical_features": [],
            "filters": {"minimum_values": {"age": 18}},
            "input_validation": {"required_features": ["age"]},
            "category_mappings": {},
        },
        "model_name": "logistic_regression",
        "experiment_name": "test",
        "model_version": "v-test",
        "training_metadata": {"test_fixture": True},
        "decision_threshold": 0.5,
    }
    monkeypatch.setattr(model_service, "load_artifact", lambda _: artifact)
    api_result = model_service.predict_record("test", {"age": 40})
    repeated_api_result = model_service.predict_record("test", {"age": 40})

    model_path = tmp_path / "model.joblib"
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    joblib.dump(artifact, model_path)
    pd.DataFrame({"age": [40]}).to_csv(input_path, index=False)
    predict(input_path, model_path, output_path)
    batch_result = pd.read_csv(output_path)

    assert api_result["probability"] == pytest.approx(
        batch_result.loc[0, "predicted_probability"],
        abs=1e-12,
    )
    assert repeated_api_result["probability"] == api_result["probability"]
    direct = predict_dataframe(artifact, pd.DataFrame({"age": [40]}))
    assert api_result["probability"] == pytest.approx(
        direct.dataframe.loc[0, "predicted_probability"],
        abs=1e-12,
    )


def test_batch_fail_on_invalid_still_writes_diagnostics(tmp_path) -> None:
    training = pd.DataFrame({"age": [20.0, 30.0, 50.0, 60.0]})
    pipeline = build_model_pipeline(
        "logistic_regression",
        numeric_features=["age"],
        categorical_features=[],
    ).fit(training, [0, 0, 1, 1])
    artifact = {
        "pipeline": pipeline,
        "features": ["age"],
        "filters": {"minimum_values": {"age": 18}},
    }
    model_path = tmp_path / "model.joblib"
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    joblib.dump(artifact, model_path)
    pd.DataFrame({"age": [10]}).to_csv(input_path, index=False)

    with pytest.raises(ValueError, match="inválido"):
        predict(
            input_path,
            model_path,
            output_path,
            fail_on_invalid=True,
        )

    result = pd.read_csv(output_path)
    assert result.loc[0, "prediction_status"] == "invalid"
    assert "outside_target_population" in result.loc[0, "exclusion_reasons"]
