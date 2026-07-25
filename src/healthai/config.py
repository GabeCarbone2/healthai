"""Leitura tipada e validação da configuração dos experimentos."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ConfigModel(BaseModel):
    """Base que rejeita chaves desconhecidas para revelar erros de digitação."""

    model_config = ConfigDict(extra="forbid")


class DataConfig(ConfigModel):
    path: str
    target: str
    source_column: str


class SplitConfig(ConfigModel):
    test_size: float = Field(default=0.2, gt=0, lt=1)
    random_state: int = 42


class ThresholdConfig(ConfigModel):
    metric: Literal["fbeta", "f1", "f2"] = "fbeta"
    beta: float = Field(default=2.0, gt=0)
    minimum: float = Field(default=0.1, ge=0, le=1)
    maximum: float = Field(default=0.9, ge=0, le=1)
    step: float = Field(default=0.01, gt=0, le=1)

    @model_validator(mode="after")
    def validate_interval(self) -> "ThresholdConfig":
        if self.minimum >= self.maximum:
            raise ValueError("threshold.minimum deve ser menor que threshold.maximum")
        return self


class NestedCVConfig(ConfigModel):
    enabled: bool = True
    outer_folds: int = Field(default=5, ge=2)
    inner_folds: int = Field(default=4, ge=2)


class SelectionConfig(ConfigModel):
    # ``scoring`` permanece aceito para compatibilidade com configurações v1.
    scoring: str = "average_precision"
    model_metric: str | None = None
    cv_folds: int = Field(default=5, ge=2)
    shuffle: bool = True
    search_iterations: int = Field(default=8, ge=1)
    n_jobs: int | None = -1
    nested_cv: NestedCVConfig = Field(default_factory=NestedCVConfig)
    threshold: ThresholdConfig = Field(default_factory=ThresholdConfig)

    @model_validator(mode="after")
    def align_legacy_fields(self) -> "SelectionConfig":
        if self.model_metric is None:
            self.model_metric = self.scoring
        if "nested_cv" not in self.model_fields_set:
            self.nested_cv.outer_folds = self.cv_folds
            self.nested_cv.inner_folds = self.cv_folds
        return self


class CalibrationCurveConfig(ConfigModel):
    n_bins: int = Field(default=10, ge=2)
    strategy: Literal["quantile", "uniform"] = "quantile"


class ModelCalibrationConfig(ConfigModel):
    enabled: bool = False
    method: Literal["sigmoid", "isotonic"] = "sigmoid"
    cv_folds: int = Field(default=5, ge=2)
    minimum_samples_isotonic: int = Field(default=1000, ge=100)
    reason: str | None = None


class ConfidenceIntervalConfig(ConfigModel):
    enabled: bool = True
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    n_bootstrap: int = Field(default=2000, ge=1)
    random_state: int = 42
    stratified: bool = True


class ExplainabilityConfig(ConfigModel):
    enabled: bool = False
    method: Literal["permutation_importance"] = "permutation_importance"
    dataset: Literal["held_out_test", "validation"] = "held_out_test"
    final_model_only: bool = True
    scoring: str = "roc_auc"
    n_repeats: int = Field(default=10, ge=1)
    random_state: int = 42
    n_jobs: int | None = None
    top_n: int = Field(default=12, ge=1)


class DecisionCurveConfig(ConfigModel):
    enabled: bool = False
    reason: str | None = None


class EvaluationConfig(ConfigModel):
    calibration: CalibrationCurveConfig = Field(default_factory=CalibrationCurveConfig)
    model_calibration: ModelCalibrationConfig = Field(
        default_factory=ModelCalibrationConfig
    )
    confidence_intervals: ConfidenceIntervalConfig = Field(
        default_factory=ConfidenceIntervalConfig
    )
    subgroup_minimum_size: int = Field(default=20, ge=1)
    subgroup_minimum_events: int = Field(default=10, ge=1)
    subgroup_bootstrap: int = Field(default=1000, ge=0)
    explainability: ExplainabilityConfig = Field(default_factory=ExplainabilityConfig)
    decision_curve_analysis: DecisionCurveConfig = Field(
        default_factory=DecisionCurveConfig
    )


class ExternalValidationConfig(ConfigModel):
    status: Literal["not_performed", "performed"] = "not_performed"
    target_dataset: str | None = None
    reason: str | None = None
    recommended_protocol: list[str] | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "ExternalValidationConfig":
        if self.status == "performed" and not self.target_dataset:
            raise ValueError(
                "external_validation.target_dataset é obrigatório quando performed"
            )
        return self


class SubgroupConfig(ConfigModel):
    name: str
    column: str
    label: str | None = None
    bins: list[float] | None = None
    labels: list[str] | None = None
    right: bool = False
    value_labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bins(self) -> "SubgroupConfig":
        if (self.bins is None) != (self.labels is None):
            raise ValueError("subgrupo deve informar bins e labels em conjunto")
        if self.bins and len(self.bins) != len(self.labels or []) + 1:
            raise ValueError("subgrupo requer len(bins) = len(labels) + 1")
        return self


class RangeConfig(ConfigModel):
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "RangeConfig":
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum não pode ser maior que maximum")
        return self


class FilterConfig(ConfigModel):
    minimum_values: dict[str, float] = Field(default_factory=dict)
    # Compatibilidade v1. Novos experimentos devem preferir invalid_values.
    invalid_below: dict[str, float] = Field(default_factory=dict)
    invalid_values: dict[str, list[float | str]] = Field(default_factory=dict)
    hard_limits: dict[str, RangeConfig] = Field(default_factory=dict)
    applicability_ranges: dict[str, RangeConfig] = Field(default_factory=dict)


class InputValidationConfig(ConfigModel):
    required_features: list[str] = Field(default_factory=list)
    allowed_categories: dict[str, list[str | int | float]] = Field(default_factory=dict)
    minimum_completeness: float | None = Field(default=None, gt=0, le=1)


class SurveyWeightingConfig(ConfigModel):
    applied: bool = False
    weight_column: str | None = None
    strata_column: str | None = None
    cluster_column: str | None = None
    reason: str | None = None
    interpretation: str | None = None

    @model_validator(mode="after")
    def validate_weight(self) -> "SurveyWeightingConfig":
        if self.applied and not self.weight_column:
            raise ValueError("weight_column é obrigatório quando applied=true")
        return self


class ModelSettings(ConfigModel):
    enabled: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    search_params: dict[str, list[Any]] = Field(default_factory=dict)


class ExperimentConfig(ConfigModel):
    source_value: str
    target_definition: str | None = None
    intended_use: str | None = None
    external_validation: ExternalValidationConfig = Field(
        default_factory=ExternalValidationConfig
    )
    numeric_features: list[str] = Field(default_factory=list)
    categorical_features: list[str] = Field(default_factory=list)
    category_mappings: dict[str, dict[str, int | float | str]] = Field(
        default_factory=dict
    )
    subgroups: list[SubgroupConfig] = Field(default_factory=list)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    input_validation: InputValidationConfig = Field(
        default_factory=InputValidationConfig
    )
    survey_weighting: SurveyWeightingConfig = Field(
        default_factory=SurveyWeightingConfig
    )
    models: dict[str, ModelSettings]

    @model_validator(mode="after")
    def validate_features(self) -> "ExperimentConfig":
        features = [*self.numeric_features, *self.categorical_features]
        if not features:
            raise ValueError("experimento deve informar ao menos uma feature")
        if len(features) != len(set(features)):
            raise ValueError("features numéricas e categóricas não podem se repetir")
        unknown_required = set(self.input_validation.required_features) - set(features)
        if unknown_required:
            raise ValueError(
                "required_features fora das features do modelo: "
                f"{sorted(unknown_required)}"
            )
        unknown_categories = set(self.input_validation.allowed_categories) - set(
            self.categorical_features
        )
        if unknown_categories:
            raise ValueError(
                "allowed_categories fora das features categóricas: "
                f"{sorted(unknown_categories)}"
            )
        rule_fields = {
            *self.filters.minimum_values,
            *self.filters.invalid_below,
            *self.filters.invalid_values,
            *self.filters.hard_limits,
            *self.filters.applicability_ranges,
            *self.category_mappings,
        }
        unknown_rules = rule_fields - set(features)
        if unknown_rules:
            raise ValueError(
                f"regras de entrada apontam para features ausentes: "
                f"{sorted(unknown_rules)}"
            )
        return self


class OutputConfig(ConfigModel):
    models_dir: str
    metrics_path: str
    figures_dir: str | None = None
    data_quality_path: str | None = None


class PipelineConfig(ConfigModel):
    data: DataConfig
    split: SplitConfig = Field(default_factory=SplitConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    experiments: dict[str, ExperimentConfig]
    outputs: OutputConfig


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega YAML e devolve uma configuração validada e normalizada."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuração não encontrada: {config_path}")

    with config_path.open(encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    if not isinstance(raw_config, dict):
        raise ValueError("A configuração deve ser um mapeamento YAML.")
    try:
        validated = PipelineConfig.model_validate(raw_config)
    except ValidationError as error:
        raise ValueError(f"Configuração inválida em {config_path}:\n{error}") from error
    return validated.model_dump(mode="python")
