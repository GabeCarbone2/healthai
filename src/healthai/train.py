"""Treinamento auditável dos modelos do HealthAI por conjunto de dados."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import subprocess
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
    train_test_split,
)

from healthai.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    atomic_joblib_dump,
    atomic_write_json,
)
from healthai.config import load_config
from healthai.data import load_dataset
from healthai.evaluate import (
    bootstrap_confidence_intervals,
    calibration_summary,
    classification_metrics,
    explainability_summary,
    save_calibration_plot,
    save_feature_importance_plot,
    subgroup_bias_summary,
    subgroup_evaluation,
)
from healthai.features import build_model_pipeline
from healthai.input_validation import (
    prepare_and_validate_input,
    validation_rules_from_experiment,
)

LOGGER = logging.getLogger("healthai.ml.training")


def _log_event(event: str, **fields: Any) -> None:
    LOGGER.info(
        json.dumps(
            {"event": event, **fields},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256() -> str:
    digest = hashlib.sha256()
    roots = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parents[2] / "backend",
    ]
    for path in sorted(
        file for root in roots if root.exists() for file in root.rglob("*.py")
    ):
        digest.update(
            str(path.relative_to(Path(__file__).resolve().parents[2])).encode()
        )
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _package_versions() -> dict[str, str]:
    packages = ("healthai", "numpy", "pandas", "scikit-learn", "joblib", "pydantic")
    versions: dict[str, str] = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def _model_version(
    *,
    data_path: str | Path,
    config_path: str | Path,
    experiment_name: str,
    model_name: str,
    threshold: dict[str, object],
    validation: dict[str, object],
) -> str:
    """Cria versão reproduzível a partir dos dados e decisões de treinamento."""
    reproducible_validation = {
        "best_params": validation.get("best_params", {}),
        "outer_fold_best_params": validation.get("outer_fold_best_params", []),
        "fold_scores": validation.get("fold_scores", []),
    }
    version_data = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "data_sha256": _sha256_file(data_path),
        "config_sha256": _sha256_file(config_path),
        "code_sha256": _code_sha256(),
        "experiment": experiment_name,
        "model": model_name,
        "threshold": threshold,
        "validation": reproducible_validation,
    }
    encoded = json.dumps(version_data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _prepare_experiment(
    dataframe: pd.DataFrame,
    experiment: dict[str, Any],
    *,
    source_column: str,
    target: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Seleciona a fonte e aplica o mesmo contrato usado pela inferência."""
    source_value = experiment["source_value"]
    source_data = dataframe.loc[dataframe[source_column] == source_value].copy()
    if source_data.empty:
        raise ValueError(f"Nenhum registro encontrado para a fonte: {source_value}")

    exclusions: dict[str, int] = {}
    non_binary_target = source_data[target].notna() & ~source_data[target].isin([0, 1])
    if non_binary_target.any():
        invalid_values = sorted(
            str(value) for value in source_data.loc[non_binary_target, target].unique()
        )
        raise ValueError(
            f"Alvo não binário em {source_value}: valores {invalid_values}."
        )
    valid_target = source_data[target].isin([0, 1])
    exclusions["missing_or_invalid_target"] = int((~valid_target).sum())
    source_data = source_data.loc[valid_target].copy()
    source_data[target] = source_data[target].astype(int)

    rules = validation_rules_from_experiment(experiment)
    validation = prepare_and_validate_input(
        source_data,
        features=rules["features"],
        numeric_features=rules["numeric_features"],
        categorical_features=rules["categorical_features"],
        filters=rules["filters"],
        input_validation=rules["input_validation"],
        category_mappings=rules["category_mappings"],
        # Required fields describe the API contract. Missing source values remain
        # imputable and do not get dropped from the development sample.
        enforce_required=False,
    )
    for reasons in validation.exclusion_reasons:
        for reason in reasons:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    for warnings in validation.warnings:
        for warning in warnings:
            code = f"warning_{warning['code']}"
            exclusions[code] = exclusions.get(code, 0) + 1

    prepared = source_data.loc[validation.eligibility].copy()
    prepared.loc[:, rules["features"]] = validation.dataframe.loc[
        validation.eligibility, rules["features"]
    ]
    if prepared.empty:
        raise ValueError(f"Todos os registros de {source_value} foram excluídos.")
    return prepared, exclusions


def _data_quality_summary(
    source_data: pd.DataFrame,
    prepared: pd.DataFrame,
    *,
    features: list[str],
    target: str,
    exclusions: dict[str, int],
) -> dict[str, Any]:
    target_counts = prepared[target].value_counts().sort_index()
    return {
        "n_source_records": int(len(source_data)),
        "n_eligible_records": int(len(prepared)),
        "duplicate_feature_target_rows": int(
            prepared.duplicated(subset=[*features, target]).sum()
        ),
        "target_distribution": {
            str(int(label)): int(count) for label, count in target_counts.items()
        },
        "target_prevalence": float(prepared[target].mean()),
        "missing_by_feature": {
            feature: {
                "count": int(prepared[feature].isna().sum()),
                "rate": float(prepared[feature].isna().mean()),
            }
            for feature in features
        },
        "exclusions_and_transformations": exclusions,
        "checks": {
            "target_binary": bool(prepared[target].isin([0, 1]).all()),
            "both_target_classes_present": bool(prepared[target].nunique() == 2),
            "all_required_columns_present": bool(
                set([*features, target]).issubset(prepared.columns)
            ),
        },
    }


def _enabled_models(experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    enabled = {
        name: settings
        for name, settings in experiment["models"].items()
        if settings.get("enabled", False)
    }
    if not enabled:
        raise ValueError("Nenhum modelo está habilitado no experimento.")
    return enabled


def _external_validation_note(
    experiment_name: str,
    experiment: dict[str, Any],
) -> dict[str, object]:
    configured = experiment.get("external_validation", {})
    return {
        "status": configured.get("status", "not_performed"),
        "target_dataset": configured.get("target_dataset"),
        "reason": configured.get("reason")
        or (
            "Validação externa verdadeira não foi executada neste "
            f"experimento ({experiment_name}). O teste isolado vem da mesma "
            "fonte de dados usada no treino."
        ),
        "recommended_protocol": configured.get("recommended_protocol")
        or [
            "congelar variáveis, pré-processamento, hiperparâmetros e limiar",
            "aplicar o artefato salvo a uma coorte independente compatível",
            "reportar métricas, calibração, intervalos de confiança e subgrupos",
            "não reajustar o modelo nem o limiar com a coorte externa",
        ],
    }


def _optimize_threshold(
    y_true: pd.Series | np.ndarray,
    probabilities: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, float | str]:
    """Seleciona o limiar por F-beta exclusivamente em previsões OOF."""
    beta = float(settings.get("beta", 2.0))
    minimum = float(settings.get("minimum", 0.1))
    maximum = float(settings.get("maximum", 0.9))
    step = float(settings.get("step", 0.01))
    thresholds = np.arange(minimum, maximum + (step / 2), step)

    candidates = []
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        candidates.append(
            {
                "value": float(round(threshold, 10)),
                "f_beta": float(
                    fbeta_score(y_true, predictions, beta=beta, zero_division=0)
                ),
                "precision": float(
                    precision_score(y_true, predictions, zero_division=0)
                ),
                "recall": float(recall_score(y_true, predictions, zero_division=0)),
            }
        )

    best = max(
        candidates,
        key=lambda candidate: (
            candidate["f_beta"],
            candidate["recall"],
            -abs(candidate["value"] - 0.5),
        ),
    )
    return {
        "method": "maximize_fbeta_on_training_oof_predictions",
        "dataset": "training_out_of_fold",
        "metric": settings.get("metric", "fbeta"),
        "beta": beta,
        "constraints": [],
        **best,
    }


def _effective_folds(y: pd.Series, requested: int, *, context: str) -> int:
    minimum_class = int(y.value_counts().min())
    folds = min(int(requested), minimum_class)
    if folds < 2:
        raise ValueError(
            f"{context} requer ao menos dois exemplos em cada classe; "
            f"mínimo observado={minimum_class}."
        )
    return folds


def _selection_score(
    metric: str,
    y_true: pd.Series | np.ndarray,
    probabilities: np.ndarray,
) -> float:
    metric = metric.lower()
    labels = np.asarray(y_true)
    if metric in {"average_precision", "pr_auc"}:
        return float(average_precision_score(labels, probabilities))
    if metric == "roc_auc":
        return float(roc_auc_score(labels, probabilities))
    if metric in {"neg_brier_score", "brier_score"}:
        return float(-brier_score_loss(labels, probabilities))
    if metric in {"f1", "f2", "fbeta"}:
        beta = 1.0 if metric == "f1" else 2.0
        return float(
            fbeta_score(
                labels,
                (probabilities >= 0.5).astype(int),
                beta=beta,
                zero_division=0,
            )
        )
    raise ValueError(
        f"Métrica de seleção não suportada para probabilidades OOF: {metric}."
    )


def _search_scoring(metric: str) -> str:
    return {
        "pr_auc": "average_precision",
        "brier_score": "neg_brier_score",
        "f2": "f1",
        "fbeta": "f1",
    }.get(metric, metric)


def _fit_search(
    pipeline: Any,
    settings: dict[str, Any],
    x: pd.DataFrame,
    y: pd.Series,
    *,
    inner_folds: int,
    selection_config: dict[str, Any],
    random_state: int,
) -> tuple[Any, dict[str, Any]]:
    search_params = settings.get("search_params", {})
    if not search_params:
        fitted = clone(pipeline).fit(x, y)
        return fitted, {}
    available_parameters = pipeline.get_params(deep=True)
    normalized_search_params: dict[str, list[Any]] = {}
    for name, values in search_params.items():
        normalized_name = name
        if name not in available_parameters and name.startswith("classifier__"):
            calibrated_name = name.replace(
                "classifier__",
                "classifier__estimator__",
                1,
            )
            if calibrated_name in available_parameters:
                normalized_name = calibrated_name
        normalized_search_params[normalized_name] = values
    inner_cv = StratifiedKFold(
        n_splits=_effective_folds(y, inner_folds, context="CV interna"),
        shuffle=selection_config.get("shuffle", True),
        random_state=random_state if selection_config.get("shuffle", True) else None,
    )
    search = RandomizedSearchCV(
        estimator=clone(pipeline),
        param_distributions=normalized_search_params,
        n_iter=int(selection_config.get("search_iterations", 8)),
        scoring=_search_scoring(str(selection_config["model_metric"])),
        cv=inner_cv,
        random_state=random_state,
        n_jobs=selection_config.get("n_jobs", -1),
        refit=True,
        error_score="raise",
    )
    search.fit(x, y)
    return search.best_estimator_, dict(search.best_params_)


def _tune_and_validate(
    pipeline: Any,
    settings: dict[str, Any],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    cross_validator: StratifiedKFold | None,
    selection_config: dict[str, Any],
    random_state: int,
) -> tuple[Any, dict[str, object], dict[str, float | str]]:
    """Executa CV aninhada, gera OOF e reajusta no conjunto de treino completo."""
    nested = selection_config.get("nested_cv", {})
    nested_enabled = nested.get("enabled", True)
    outer_requested = int(
        nested.get(
            "outer_folds",
            selection_config.get("cv_folds", 5),
        )
    )
    inner_requested = int(
        nested.get("inner_folds", selection_config.get("cv_folds", 5))
    )
    outer_folds = _effective_folds(y_train, outer_requested, context="CV externa")
    if cross_validator is None or cross_validator.n_splits != outer_folds:
        cross_validator = StratifiedKFold(
            n_splits=outer_folds,
            shuffle=selection_config.get("shuffle", True),
            random_state=(
                random_state if selection_config.get("shuffle", True) else None
            ),
        )

    probabilities = np.full(len(y_train), np.nan, dtype=float)
    fold_scores: list[float] = []
    fold_params: list[dict[str, Any]] = []
    fold_sizes: list[dict[str, int]] = []
    metric = str(selection_config.get("model_metric") or selection_config["scoring"])
    if not nested_enabled:
        final_pipeline, final_best_params = _fit_search(
            pipeline,
            settings,
            x_train,
            y_train,
            inner_folds=inner_requested,
            selection_config=selection_config,
            random_state=random_state,
        )
        for fold, (development_indices, validation_indices) in enumerate(
            cross_validator.split(x_train, y_train),
            start=1,
        ):
            fold_pipeline = clone(final_pipeline).fit(
                x_train.iloc[development_indices],
                y_train.iloc[development_indices],
            )
            fold_probability = fold_pipeline.predict_proba(
                x_train.iloc[validation_indices]
            )[:, 1]
            probabilities[validation_indices] = fold_probability
            fold_scores.append(
                _selection_score(
                    metric,
                    y_train.iloc[validation_indices],
                    fold_probability,
                )
            )
            fold_params.append(final_best_params)
            fold_sizes.append(
                {
                    "fold": fold,
                    "development": int(len(development_indices)),
                    "validation": int(len(validation_indices)),
                }
            )
        threshold = _optimize_threshold(
            y_train,
            probabilities,
            selection_config.get("threshold", {}),
        )
        validation = {
            "method": "non_nested_stratified_cross_validation",
            "model_selection_metric": metric,
            "mean": float(np.mean(fold_scores)),
            "std": float(np.std(fold_scores)),
            "minimum": float(np.min(fold_scores)),
            "maximum": float(np.max(fold_scores)),
            "fold_scores": [float(score) for score in fold_scores],
            "fold_sizes": fold_sizes,
            "outer_folds": outer_folds,
            "inner_folds_requested": inner_requested,
            "outer_fold_best_params": fold_params,
            "best_params": final_best_params,
            "oof_metric_value": _selection_score(metric, y_train, probabilities),
            "oof_probabilities": [float(value) for value in probabilities],
            "oof_row_indices": [str(value) for value in x_train.index],
            "hyperparameter_search_scope": (
                "full_training_before_cv_non_nested_optimistic"
            ),
            "final_refit_scope": "full_training_partition_only",
        }
        return final_pipeline, validation, threshold

    for fold, (development_indices, validation_indices) in enumerate(
        cross_validator.split(x_train, y_train),
        start=1,
    ):
        x_development = x_train.iloc[development_indices]
        y_development = y_train.iloc[development_indices]
        fitted, best_params = _fit_search(
            pipeline,
            settings,
            x_development,
            y_development,
            inner_folds=inner_requested,
            selection_config=selection_config,
            random_state=random_state + fold,
        )
        fold_probability = fitted.predict_proba(x_train.iloc[validation_indices])[:, 1]
        probabilities[validation_indices] = fold_probability
        fold_score = _selection_score(
            metric,
            y_train.iloc[validation_indices],
            fold_probability,
        )
        fold_scores.append(fold_score)
        fold_params.append(best_params)
        fold_sizes.append(
            {
                "fold": fold,
                "development": int(len(development_indices)),
                "validation": int(len(validation_indices)),
            }
        )

    if np.isnan(probabilities).any():
        raise RuntimeError(
            "CV externa não gerou probabilidade para todos os registros."
        )

    threshold = _optimize_threshold(
        y_train,
        probabilities,
        selection_config.get("threshold", {}),
    )
    final_pipeline, final_best_params = _fit_search(
        pipeline,
        settings,
        x_train,
        y_train,
        inner_folds=inner_requested,
        selection_config=selection_config,
        random_state=random_state,
    )
    validation: dict[str, object] = {
        "method": (
            "nested_stratified_cross_validation"
            if nested_enabled
            else "stratified_cross_validation"
        ),
        "model_selection_metric": metric,
        "mean": float(np.mean(fold_scores)),
        "std": float(np.std(fold_scores)),
        "minimum": float(np.min(fold_scores)),
        "maximum": float(np.max(fold_scores)),
        "fold_scores": [float(score) for score in fold_scores],
        "fold_sizes": fold_sizes,
        "outer_folds": outer_folds,
        "inner_folds_requested": inner_requested,
        "outer_fold_best_params": fold_params,
        "best_params": final_best_params,
        "oof_metric_value": _selection_score(metric, y_train, probabilities),
        "oof_probabilities": [float(value) for value in probabilities],
        "oof_row_indices": [str(value) for value in x_train.index],
        "hyperparameter_search_scope": "inner_training_folds_only",
        "final_refit_scope": "full_training_partition_only",
    }
    return final_pipeline, validation, threshold


def _training_observed_ranges(
    x_train: pd.DataFrame,
    numeric_features: list[str],
) -> dict[str, dict[str, float]]:
    ranges: dict[str, dict[str, float]] = {}
    for feature in numeric_features:
        non_missing = pd.to_numeric(x_train[feature], errors="coerce").dropna()
        if not non_missing.empty:
            ranges[feature] = {
                "minimum": float(non_missing.min()),
                "maximum": float(non_missing.max()),
            }
    return ranges


def _index_sha256(index: pd.Index) -> str:
    encoded = json.dumps([str(value) for value in index]).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def train(config_path: str | Path) -> dict[str, object]:
    """Compara candidatos e salva o modelo selecionado de cada base."""
    config = load_config(config_path)
    data_config = config["data"]
    split_config = config["split"]
    selection_config = config["selection"]
    experiments = config["experiments"]
    output_config = config["outputs"]
    evaluation_config = config["evaluation"]

    target = data_config["target"]
    source_column = data_config["source_column"]
    all_features = sorted(
        {
            feature
            for experiment in experiments.values()
            for feature in [
                *experiment.get("numeric_features", []),
                *experiment.get("categorical_features", []),
                *[subgroup["column"] for subgroup in experiment.get("subgroups", [])],
            ]
        }
    )
    dataframe = load_dataset(
        data_config["path"],
        [source_column, *all_features],
        target,
    )

    models_dir = Path(output_config["models_dir"])
    metrics_path = Path(output_config["metrics_path"])
    figures_dir = Path(
        output_config.get("figures_dir") or metrics_path.parent / "figures"
    )
    quality_path = Path(
        output_config.get("data_quality_path")
        or metrics_path.parent / "data_quality.json"
    )
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    run_metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": _sha256_file(data_config["path"]),
        "config_sha256": _sha256_file(config_path),
        "code_sha256": _code_sha256(),
        "git_commit": _git_commit(),
        "package_versions": _package_versions(),
    }
    results: dict[str, object] = {}
    data_quality: dict[str, object] = {"run": run_metadata, "experiments": {}}

    for experiment_name, experiment in experiments.items():
        experiment_started_at = time.perf_counter()
        _log_event("experiment_started", experiment=experiment_name)
        numeric_features = experiment.get("numeric_features", [])
        categorical_features = experiment.get("categorical_features", [])
        features = [*numeric_features, *categorical_features]
        enabled_models = _enabled_models(experiment)
        subgroup_definitions = experiment.get("subgroups", [])
        subgroup_columns = sorted(
            {definition["column"] for definition in subgroup_definitions}
        )
        source_data = dataframe.loc[
            dataframe[source_column] == experiment["source_value"]
        ].copy()
        prepared, exclusions = _prepare_experiment(
            dataframe,
            experiment,
            source_column=source_column,
            target=target,
        )
        quality_summary = _data_quality_summary(
            source_data,
            prepared,
            features=features,
            target=target,
            exclusions=exclusions,
        )
        if not quality_summary["checks"]["both_target_classes_present"]:
            raise ValueError(f"{experiment_name} não contém ambas as classes do alvo.")
        data_quality["experiments"][experiment_name] = quality_summary
        _log_event(
            "data_prepared",
            experiment=experiment_name,
            source=experiment["source_value"],
            source_records=len(source_data),
            eligible_records=len(prepared),
            prevalence=float(prepared[target].mean()),
            exclusions=exclusions,
        )

        split_values = train_test_split(
            prepared[features],
            prepared[target],
            prepared[subgroup_columns],
            test_size=split_config["test_size"],
            random_state=split_config["random_state"],
            stratify=prepared[target],
        )
        x_train, x_test, y_train, y_test, _, subgroup_test = split_values
        shared_indices = x_train.index.intersection(x_test.index)
        split_integrity = {
            "shared_index_count": int(len(shared_indices)),
            "train_index_sha256": _index_sha256(x_train.index),
            "test_index_sha256": _index_sha256(x_test.index),
            "random_state": split_config["random_state"],
            "stratified": True,
        }
        if len(shared_indices):
            raise RuntimeError(
                f"Treino e teste de {experiment_name} compartilham índices."
            )
        observed_ranges = _training_observed_ranges(x_train, numeric_features)

        pipelines: dict[str, Any] = {}
        cross_validation: dict[str, dict[str, object]] = {}
        thresholds: dict[str, dict[str, float | str]] = {}
        for model_name, settings in enabled_models.items():
            candidate_started_at = time.perf_counter()
            _log_event(
                "candidate_started",
                experiment=experiment_name,
                model=model_name,
            )
            pipeline = build_model_pipeline(
                model_name,
                settings.get("params", {}),
                random_state=split_config["random_state"],
                numeric_features=numeric_features,
                categorical_features=categorical_features,
                calibration=evaluation_config.get("model_calibration", {}),
                training_sample_size=len(x_train),
            )
            fitted_pipeline, validation, threshold = _tune_and_validate(
                pipeline,
                settings,
                x_train,
                y_train,
                None,
                selection_config,
                split_config["random_state"],
            )
            pipelines[model_name] = fitted_pipeline
            cross_validation[model_name] = validation
            thresholds[model_name] = threshold
            _log_event(
                "candidate_completed",
                experiment=experiment_name,
                model=model_name,
                oof_metric=validation["oof_metric_value"],
                threshold=threshold["value"],
                best_params=validation["best_params"],
                duration_seconds=round(time.perf_counter() - candidate_started_at, 3),
            )

        selected_model = max(
            cross_validation,
            key=lambda name: cross_validation[name]["oof_metric_value"],
        )
        calibration_config = evaluation_config["calibration"]
        confidence_config = evaluation_config["confidence_intervals"]
        confidence_enabled = confidence_config.get("enabled", True)
        confidence_settings = {
            "confidence_level": confidence_config["confidence_level"],
            "n_bootstrap": confidence_config["n_bootstrap"],
            "random_state": confidence_config["random_state"],
        }
        subgroup_confidence_settings = {
            **confidence_settings,
            "n_bootstrap": (
                evaluation_config.get(
                    "subgroup_bootstrap",
                    confidence_settings["n_bootstrap"],
                )
                if confidence_enabled
                else 0
            ),
        }
        explainability_config = evaluation_config["explainability"]
        survey_weighting = experiment.get("survey_weighting", {})
        experiment_metrics: dict[str, Any] = {
            "source_dataset": experiment["source_value"],
            "target": {
                "column": target,
                "definition": experiment.get("target_definition"),
                "intended_use": experiment.get("intended_use"),
            },
            "selected_model": selected_model,
            "model_version": None,
            "selection": {
                "metric": selection_config["model_metric"],
                "scope": "training_only_nested_cv",
                "outer_folds": selection_config["nested_cv"]["outer_folds"],
                "inner_folds": selection_config["nested_cv"]["inner_folds"],
                "search_iterations": selection_config["search_iterations"],
                "threshold_metric": selection_config["threshold"]["metric"],
                "model_and_threshold_alignment": (
                    "modelos comparados por probabilidades OOF na mesma métrica; "
                    "limiar otimizado nas probabilidades OOF do candidato"
                ),
            },
            "records_excluded": exclusions,
            "n_train": len(x_train),
            "n_test": len(x_test),
            "training_prevalence": float(y_train.mean()),
            "test_prevalence": float(y_test.mean()),
            "split_integrity": split_integrity,
            "survey_weighting": survey_weighting,
            "population_estimates": bool(survey_weighting.get("applied", False)),
            "evaluation": {
                "dataset": "held_out_test",
                "calibration": calibration_config,
                "model_calibration": evaluation_config["model_calibration"],
                "confidence_intervals": confidence_config,
                "subgroup_minimum_size": evaluation_config["subgroup_minimum_size"],
                "subgroup_minimum_events": evaluation_config["subgroup_minimum_events"],
                "explainability": explainability_config,
                "decision_curve_analysis": {
                    "status": (
                        "performed"
                        if evaluation_config["decision_curve_analysis"]["enabled"]
                        else "not_performed"
                    ),
                    "reason": evaluation_config["decision_curve_analysis"].get("reason")
                    or "Desabilitada até definição clínica de probabilidades-limiar.",
                },
            },
            "external_validation": _external_validation_note(
                experiment_name, experiment
            ),
            "run_metadata": run_metadata,
            "data_quality": quality_summary,
            "models": {},
        }

        calibration_curves: dict[str, dict[str, object]] = {}
        for model_name, pipeline in pipelines.items():
            model_version = _model_version(
                data_path=data_config["path"],
                config_path=config_path,
                experiment_name=experiment_name,
                model_name=model_name,
                threshold=thresholds[model_name],
                validation=cross_validation[model_name],
            )
            probabilities = pipeline.predict_proba(x_test)[:, 1]
            decision_threshold = float(thresholds[model_name]["value"])
            predictions = (probabilities >= decision_threshold).astype(int)
            model_metrics = classification_metrics(y_test, predictions, probabilities)
            model_metrics["calibration"] = calibration_summary(
                y_test,
                probabilities,
                n_bins=calibration_config["n_bins"],
                strategy=calibration_config["strategy"],
            )
            calibration_curves[model_name] = model_metrics["calibration"]
            model_metrics["confidence_intervals"] = (
                bootstrap_confidence_intervals(
                    y_test,
                    predictions,
                    probabilities,
                    **confidence_settings,
                )
                if confidence_enabled
                else None
            )
            model_metrics["subgroups"] = subgroup_evaluation(
                y_test,
                predictions,
                probabilities,
                subgroup_test,
                subgroup_definitions,
                minimum_size=evaluation_config["subgroup_minimum_size"],
                minimum_events=evaluation_config["subgroup_minimum_events"],
                confidence_settings=subgroup_confidence_settings,
            )
            model_metrics["bias_summary"] = subgroup_bias_summary(
                model_metrics["subgroups"]
            )
            explain_selected = explainability_config.get("enabled", False) and (
                not explainability_config.get("final_model_only", True)
                or model_name == selected_model
            )
            if explain_selected:
                model_metrics["explainability"] = explainability_summary(
                    pipeline,
                    x_test,
                    y_test,
                    scoring=explainability_config["scoring"],
                    n_repeats=explainability_config["n_repeats"],
                    random_state=explainability_config["random_state"],
                    n_jobs=explainability_config.get("n_jobs"),
                )
                save_feature_importance_plot(
                    model_metrics["explainability"],
                    figures_dir / f"{experiment_name}_feature_importance.png",
                    title=(
                        "Importância por permutação — "
                        f"{experiment_name.upper()} ({model_name})"
                    ),
                    top_n=explainability_config["top_n"],
                )
            else:
                model_metrics["explainability"] = None
            model_metrics["cross_validation"] = cross_validation[model_name]
            model_metrics["threshold"] = thresholds[model_name]
            model_metrics["model_version"] = model_version
            experiment_metrics["models"][model_name] = model_metrics

            validation_rules = validation_rules_from_experiment(experiment)
            validation_rules["filters"] = dict(validation_rules["filters"])
            configured_applicability = validation_rules["filters"].get(
                "applicability_ranges", {}
            )
            validation_rules["filters"]["applicability_ranges"] = {
                **observed_ranges,
                **configured_applicability,
            }
            artifact = {
                "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
                "pipeline": pipeline,
                "features": features,
                "numeric_features": numeric_features,
                "categorical_features": categorical_features,
                "category_mappings": experiment.get("category_mappings", {}),
                "filters": experiment.get("filters", {}),
                "input_validation": experiment.get("input_validation", {}),
                "validation_rules": validation_rules,
                "target": target,
                "target_definition": experiment.get("target_definition"),
                "intended_use": experiment.get("intended_use"),
                "source_column": source_column,
                "source_value": experiment["source_value"],
                "experiment_name": experiment_name,
                "model_name": model_name,
                "model_version": model_version,
                "selection_metric": selection_config["model_metric"],
                "cross_validation": cross_validation[model_name],
                "decision_threshold": decision_threshold,
                "threshold_metrics": thresholds[model_name],
                "selected": model_name == selected_model,
                "observed_training_ranges": observed_ranges,
                "external_validation": experiment_metrics["external_validation"],
                "survey_weighting": survey_weighting,
                "training_metadata": {
                    **run_metadata,
                    "experiment": experiment_name,
                    "model": model_name,
                    "n_source": len(source_data),
                    "n_eligible": len(prepared),
                    "n_train": len(x_train),
                    "n_test": len(x_test),
                    "training_prevalence": float(y_train.mean()),
                    "test_prevalence": float(y_test.mean()),
                    "split_integrity": split_integrity,
                    "validation_and_exclusion_rules": validation_rules,
                },
            }
            atomic_joblib_dump(
                artifact,
                models_dir / f"{experiment_name}_{model_name}.joblib",
            )
            if artifact["selected"]:
                experiment_metrics["model_version"] = model_version
                atomic_joblib_dump(
                    artifact,
                    models_dir / f"{experiment_name}_selected.joblib",
                )

        save_calibration_plot(
            calibration_curves,
            figures_dir / f"{experiment_name}_calibration.png",
            title=f"Curva de calibração — {experiment_name.upper()}",
        )
        results[experiment_name] = experiment_metrics
        _log_event(
            "experiment_completed",
            experiment=experiment_name,
            selected_model=selected_model,
            model_version=experiment_metrics["model_version"],
            test_metrics={
                metric: experiment_metrics["models"][selected_model][metric]
                for metric in (
                    "average_precision",
                    "roc_auc",
                    "recall",
                    "specificity",
                    "brier_score",
                )
            },
            artifact_path=str(models_dir / f"{experiment_name}_selected.joblib"),
            duration_seconds=round(time.perf_counter() - experiment_started_at, 3),
        )

    atomic_write_json(results, metrics_path)
    atomic_write_json(data_quality, quality_path)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara candidatos e treina o modelo selecionado por base."
    )
    parser.add_argument(
        "--config", default="configs/models.yaml", help="Arquivo YAML do experimento."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    metrics = train(args.config)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
