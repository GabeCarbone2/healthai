"""Contrato único de preparação e validação para treino, lote e API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

Issue = dict[str, Any]


@dataclass
class InputValidationResult:
    """Dados preparados e diagnósticos alinhados por índice."""

    dataframe: pd.DataFrame
    eligibility: pd.Series
    errors: pd.Series
    warnings: pd.Series
    missing_features: pd.Series
    imputed_features: pd.Series
    missing_count: pd.Series
    completeness: pd.Series
    outside_applicability: pd.Series
    exclusion_reasons: pd.Series

    def row_diagnostics(self, index: Any) -> dict[str, Any]:
        return {
            "status": "eligible" if bool(self.eligibility.loc[index]) else "invalid",
            "eligible": bool(self.eligibility.loc[index]),
            "errors": self.errors.loc[index],
            "warnings": self.warnings.loc[index],
            "missing_features": self.missing_features.loc[index],
            "imputed_features": self.imputed_features.loc[index],
            "missing_feature_count": int(self.missing_count.loc[index]),
            "input_completeness": float(self.completeness.loc[index]),
            "outside_applicability": self.outside_applicability.loc[index],
            "exclusion_reasons": self.exclusion_reasons.loc[index],
        }


def _list_series(index: pd.Index) -> pd.Series:
    return pd.Series([[] for _ in index], index=index, dtype=object)


def _append_issue(
    issues: pd.Series,
    mask: pd.Series,
    *,
    code: str,
    message: str,
    feature: str | None = None,
    values: pd.Series | None = None,
) -> None:
    for index in mask.index[mask.fillna(False)]:
        issue: Issue = {"code": code, "message": message}
        if feature is not None:
            issue["feature"] = feature
        if values is not None:
            value = values.loc[index]
            issue["value"] = None if pd.isna(value) else value
        issues.loc[index].append(issue)


def _append_feature(values: pd.Series, mask: pd.Series, feature: str) -> None:
    for index in mask.index[mask.fillna(False)]:
        if feature not in values.loc[index]:
            values.loc[index].append(feature)


def _range_values(config: dict[str, Any]) -> tuple[float | None, float | None]:
    return config.get("minimum"), config.get("maximum")


def prepare_and_validate_input(
    dataframe: pd.DataFrame,
    *,
    features: list[str],
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    input_validation: dict[str, Any] | None = None,
    category_mappings: dict[str, dict[Any, Any]] | None = None,
    enforce_required: bool = False,
) -> InputValidationResult:
    """Aplica o contrato de entrada e devolve erros por registro.

    Limites fisicamente impossíveis e critérios explícitos de elegibilidade
    bloqueiam a predição. Faixas de aplicabilidade apenas geram avisos. Valores
    inválidos conhecidos (por exemplo, zeros clínicos no Pima) viram ausentes e
    são deixados para o imputador ajustado exclusivamente no treino.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe deve ser um pandas.DataFrame")
    if dataframe.empty:
        raise ValueError("O conjunto de entrada está vazio.")
    duplicated_columns = dataframe.columns[dataframe.columns.duplicated()].tolist()
    if duplicated_columns:
        raise ValueError(f"Colunas duplicadas na entrada: {duplicated_columns}.")
    if not features:
        raise ValueError("features não pode ser vazio")
    if not dataframe.index.is_unique:
        raise ValueError("O índice dos registros deve ser único.")

    numeric_features = list(numeric_features or [])
    categorical_features = list(categorical_features or [])
    filters = filters or {}
    input_validation = input_validation or {}
    category_mappings = category_mappings or {}

    index = dataframe.index
    prepared = dataframe.copy()
    errors = _list_series(index)
    warnings = _list_series(index)
    missing_features = _list_series(index)
    imputed_features = _list_series(index)
    outside_applicability = _list_series(index)
    exclusion_reasons = _list_series(index)
    required = set(input_validation.get("required_features", []))
    for feature in features:
        if feature not in prepared.columns:
            prepared[feature] = pd.NA
            if enforce_required and feature in required:
                mask = pd.Series(True, index=index)
                _append_issue(
                    errors,
                    mask,
                    code="missing_required_feature",
                    feature=feature,
                    message=f"Variável obrigatória ausente: {feature}.",
                )

    prepared = prepared[features].copy()

    # Artefatos v1 codificavam categorias manualmente antes do pipeline.
    for feature, mapping in category_mappings.items():
        if feature not in prepared:
            continue
        original = prepared[feature].copy()
        mapped = original.map(mapping)
        # O lote também pode já trazer o valor numérico codificado.
        passthrough = original.isin(list(mapping.values()))
        if passthrough.any():
            mapped = mapped.astype(object)
            mapped.loc[passthrough] = original.loc[passthrough]
        unknown = original.notna() & mapped.isna()
        _append_issue(
            errors,
            unknown,
            code="unknown_category",
            feature=feature,
            message=f"Categoria desconhecida para {feature}.",
            values=original,
        )
        prepared[feature] = mapped

    # Tipos numéricos inválidos são erros; valores vazios permanecem imputáveis.
    for feature in numeric_features:
        original = prepared[feature].copy()
        converted = pd.to_numeric(original, errors="coerce")
        invalid_type = original.notna() & converted.isna()
        _append_issue(
            errors,
            invalid_type,
            code="invalid_numeric_value",
            feature=feature,
            message=f"Valor não numérico para {feature}.",
            values=original,
        )
        infinite = converted.notna() & ~np.isfinite(converted.astype(float))
        _append_issue(
            errors,
            infinite,
            code="non_finite_numeric_value",
            feature=feature,
            message=f"Valor infinito não é aceito para {feature}.",
            values=original,
        )
        converted.loc[infinite] = np.nan
        prepared[feature] = converted

    # Categorias são validadas antes de qualquer mapeamento de compatibilidade.
    allowed_categories = {
        key: list(values)
        for key, values in input_validation.get("allowed_categories", {}).items()
    }
    for feature in categorical_features:
        allowed = allowed_categories.get(feature)
        if allowed is None and feature in category_mappings:
            allowed = list(category_mappings[feature])
        if allowed is not None:
            unknown = prepared[feature].notna() & ~prepared[feature].isin(allowed)
            _append_issue(
                errors,
                unknown,
                code="unknown_category",
                feature=feature,
                message=f"Categoria desconhecida para {feature}.",
                values=prepared[feature],
            )

    invalid_values = filters.get("invalid_values", {})
    for feature, values in invalid_values.items():
        if feature not in prepared:
            continue
        invalid = prepared[feature].isin(values)
        if invalid.any():
            _append_feature(imputed_features, invalid, feature)
            _append_issue(
                warnings,
                invalid,
                code="invalid_value_treated_as_missing",
                feature=feature,
                message=(
                    f"Valor inválido conhecido de {feature} convertido em ausente "
                    "para imputação."
                ),
                values=prepared[feature],
            )
            prepared.loc[invalid, feature] = pd.NA

    # Migração do contrato v1: valores abaixo deste piso eram imputados.
    for feature, minimum in filters.get("invalid_below", {}).items():
        if feature not in prepared:
            continue
        invalid = prepared[feature].notna() & prepared[feature].lt(minimum)
        if invalid.any():
            _append_feature(imputed_features, invalid, feature)
            _append_issue(
                warnings,
                invalid,
                code="invalid_value_treated_as_missing",
                feature=feature,
                message=(
                    f"Valor de {feature} abaixo de {minimum} convertido em ausente "
                    "para imputação."
                ),
                values=prepared[feature],
            )
            prepared.loc[invalid, feature] = pd.NA

    if enforce_required:
        for feature in required:
            if feature not in features:
                continue
            missing_required = prepared[feature].isna()
            # Valores inválidos conhecidos são imputáveis; ausência real não é.
            converted_invalid = pd.Series(
                [feature in row for row in imputed_features],
                index=index,
            )
            missing_required &= ~converted_invalid
            _append_issue(
                errors,
                missing_required,
                code="missing_required_value",
                feature=feature,
                message=f"Informe a variável obrigatória {feature}.",
            )

    for feature, limit in filters.get("hard_limits", {}).items():
        if feature not in prepared:
            continue
        minimum, maximum = _range_values(limit)
        if minimum is not None:
            invalid = prepared[feature].notna() & prepared[feature].lt(minimum)
            _append_issue(
                errors,
                invalid,
                code="below_hard_limit",
                feature=feature,
                message=f"{feature} está abaixo do limite físico aceito ({minimum}).",
                values=prepared[feature],
            )
        if maximum is not None:
            invalid = prepared[feature].notna() & prepared[feature].gt(maximum)
            _append_issue(
                errors,
                invalid,
                code="above_hard_limit",
                feature=feature,
                message=f"{feature} está acima do limite físico aceito ({maximum}).",
                values=prepared[feature],
            )

    for feature, minimum in filters.get("minimum_values", {}).items():
        if feature not in prepared:
            continue
        invalid = prepared[feature].isna() | prepared[feature].lt(minimum)
        _append_issue(
            errors,
            invalid,
            code="outside_target_population",
            feature=feature,
            message=f"{feature} deve ser maior ou igual a {minimum}.",
            values=prepared[feature],
        )

    for feature, limit in filters.get("applicability_ranges", {}).items():
        if feature not in prepared:
            continue
        minimum, maximum = _range_values(limit)
        outside = pd.Series(False, index=index)
        if minimum is not None:
            outside |= prepared[feature].notna() & prepared[feature].lt(minimum)
        if maximum is not None:
            outside |= prepared[feature].notna() & prepared[feature].gt(maximum)
        if outside.any():
            _append_feature(outside_applicability, outside, feature)
            _append_issue(
                warnings,
                outside,
                code="outside_model_applicability",
                feature=feature,
                message=(
                    f"{feature} está fora da faixa observada na população de "
                    "desenvolvimento."
                ),
                values=prepared[feature],
            )

    if {"systolic_bp_mmhg", "diastolic_bp_mmhg"}.issubset(prepared.columns):
        invalid_pressure = (
            prepared["systolic_bp_mmhg"].notna()
            & prepared["diastolic_bp_mmhg"].notna()
            & prepared["systolic_bp_mmhg"].le(prepared["diastolic_bp_mmhg"])
        )
        _append_issue(
            errors,
            invalid_pressure,
            code="inconsistent_blood_pressure",
            message="A pressão sistólica deve ser maior que a diastólica.",
        )

    for feature in features:
        missing = prepared[feature].isna()
        _append_feature(missing_features, missing, feature)
        _append_feature(imputed_features, missing, feature)
        optional_missing = missing
        if enforce_required and feature in required:
            optional_missing = pd.Series(False, index=index)
        _append_issue(
            warnings,
            optional_missing,
            code="missing_value_will_be_imputed",
            feature=feature,
            message=f"{feature} ausente; será usado o imputador do pipeline.",
        )

    missing_count = prepared.isna().sum(axis=1).astype(int)
    completeness = (len(features) - missing_count) / len(features)
    minimum_completeness = input_validation.get("minimum_completeness")
    if minimum_completeness is not None:
        incomplete = completeness.lt(float(minimum_completeness))
        _append_issue(
            errors,
            incomplete,
            code="insufficient_input_completeness",
            message=(
                "Completude abaixo do mínimo configurado "
                f"({float(minimum_completeness):.0%})."
            ),
        )

    eligibility = errors.map(len).eq(0)
    for row_index in index:
        exclusion_reasons.loc[row_index].extend(
            issue["code"] for issue in errors.loc[row_index]
        )

    return InputValidationResult(
        dataframe=prepared,
        eligibility=eligibility.astype(bool),
        errors=errors,
        warnings=warnings,
        missing_features=missing_features,
        imputed_features=imputed_features,
        missing_count=missing_count,
        completeness=completeness.astype(float),
        outside_applicability=outside_applicability,
        exclusion_reasons=exclusion_reasons,
    )


def validation_rules_from_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    """Extrai do experimento apenas o contrato necessário em inferência."""
    return {
        "features": [
            *experiment.get("numeric_features", []),
            *experiment.get("categorical_features", []),
        ],
        "numeric_features": experiment.get("numeric_features", []),
        "categorical_features": experiment.get("categorical_features", []),
        "filters": experiment.get("filters", {}),
        "input_validation": experiment.get("input_validation", {}),
        "category_mappings": experiment.get("category_mappings", {}),
    }
