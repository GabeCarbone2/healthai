"""Treinamento e selecao dos modelos do HealthAI por conjunto de dados."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import fbeta_score, precision_score, recall_score
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_predict,
    cross_val_score,
    train_test_split,
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


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    metadata = {
        "data_sha256": _sha256_file(data_path),
        "config_sha256": _sha256_file(config_path),
        "experiment": experiment_name,
        "model": model_name,
        "threshold": threshold,
        "best_params": validation.get("best_params", {}),
    }
    encoded = json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _prepare_experiment(
    dataframe: pd.DataFrame,
    experiment: dict[str, Any],
    *,
    source_column: str,
    target: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Seleciona a fonte e aplica as mesmas regras de limpeza dos notebooks."""
    source_value = experiment["source_value"]
    prepared = dataframe.loc[dataframe[source_column] == source_value].copy()
    if prepared.empty:
        raise ValueError(f"Nenhum registro encontrado para a fonte: {source_value}")

    exclusions: dict[str, int] = {}
    valid_target = prepared[target].isin([0, 1])
    exclusions["missing_or_invalid_target"] = int((~valid_target).sum())
    prepared = prepared.loc[valid_target].copy()
    prepared[target] = prepared[target].astype(int)

    for column, mapping in experiment.get("category_mappings", {}).items():
        prepared[column] = prepared[column].map(mapping)

    filters = experiment.get("filters", {})
    for column, minimum in filters.get("minimum_values", {}).items():
        valid_value = prepared[column].ge(minimum)
        exclusions[f"{column}_below_{minimum}"] = int((~valid_value).sum())
        prepared = prepared.loc[valid_value].copy()

    for column, minimum in filters.get("invalid_below", {}).items():
        invalid_value = prepared[column].lt(minimum)
        exclusions[f"{column}_set_missing_below_{minimum}"] = int(invalid_value.sum())
        prepared.loc[invalid_value, column] = pd.NA

    return prepared, exclusions


def _enabled_models(experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Retorna os modelos candidatos habilitados."""
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
    """Documenta o estado da validação externa do experimento."""
    configured = experiment.get("external_validation", {})
    return {
        "status": configured.get("status", "not_performed"),
        "target_dataset": configured.get("target_dataset"),
        "reason": configured.get(
            "reason",
            (
                "Validação externa verdadeira não foi executada neste "
                f"experimento ({experiment_name}). O teste isolado vem da "
                "mesma fonte de dados usada no treino."
            ),
        ),
        "recommended_protocol": configured.get(
            "recommended_protocol",
            [
                "congelar variáveis, pré-processamento, hiperparâmetros e limiar",
                "aplicar o artefato salvo a uma coorte independente compatível",
                "reportar métricas, calibração, intervalos de confiança e subgrupos",
                "não reajustar o modelo nem o limiar com a coorte externa",
            ],
        ),
    }


def _optimize_threshold(
    y_true: pd.Series,
    probabilities: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, float | str]:
    """Seleciona o limiar pelo F-beta sem consultar o conjunto de teste."""
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
                    fbeta_score(
                        y_true,
                        predictions,
                        beta=beta,
                        zero_division=0,
                    )
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
        "metric": settings.get("metric", f"f{beta:g}"),
        "beta": beta,
        **best,
    }


def _tune_and_validate(
    pipeline: Any,
    settings: dict[str, Any],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    cross_validator: StratifiedKFold,
    selection_config: dict[str, Any],
    random_state: int,
) -> tuple[Any, dict[str, object], dict[str, float | str]]:
    """Ajusta hiperparâmetros, mede CV e aprende o limiar out-of-fold."""
    scoring = selection_config.get("scoring", "f1")
    search_params = settings.get("search_params", {})
    if search_params:
        search = RandomizedSearchCV(
            estimator=pipeline,
            param_distributions=search_params,
            n_iter=selection_config.get("search_iterations", 8),
            scoring=scoring,
            cv=cross_validator,
            random_state=random_state,
            n_jobs=selection_config.get("n_jobs", -1),
            refit=True,
        )
        search.fit(x_train, y_train)
        fitted_pipeline = search.best_estimator_
        best_index = search.best_index_
        scores = np.array(
            [
                search.cv_results_[f"split{fold}_test_score"][best_index]
                for fold in range(cross_validator.n_splits)
            ]
        )
        best_params = search.best_params_
    else:
        scores = cross_val_score(
            pipeline,
            x_train,
            y_train,
            cv=cross_validator,
            scoring=scoring,
        )
        fitted_pipeline = pipeline.fit(x_train, y_train)
        best_params = {}

    out_of_fold_probabilities = cross_val_predict(
        fitted_pipeline,
        x_train,
        y_train,
        cv=cross_validator,
        method="predict_proba",
        n_jobs=selection_config.get("n_jobs", -1),
    )[:, 1]
    threshold = _optimize_threshold(
        y_train,
        out_of_fold_probabilities,
        selection_config.get("threshold", {}),
    )
    validation = {
        "mean": float(scores.mean()),
        "std": float(scores.std()),
        "fold_scores": [float(score) for score in scores],
        "best_params": best_params,
    }
    return fitted_pipeline, validation, threshold


def train(config_path: str | Path) -> dict[str, object]:
    """Compara candidatos e salva o modelo selecionado de cada base."""
    config = load_config(config_path)
    data_config = config["data"]
    split_config = config["split"]
    selection_config = config.get("selection", {})
    experiments = config["experiments"]
    output_config = config["outputs"]
    evaluation_config = config.get("evaluation", {})

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
        output_config.get("figures_dir", metrics_path.parent / "figures")
    )
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, object] = {}
    for experiment_name, experiment in experiments.items():
        numeric_features = experiment.get("numeric_features", [])
        categorical_features = experiment.get("categorical_features", [])
        features = [*numeric_features, *categorical_features]
        enabled_models = _enabled_models(experiment)
        subgroup_definitions = experiment.get("subgroups", [])
        subgroup_columns = sorted(
            {definition["column"] for definition in subgroup_definitions}
        )
        prepared, exclusions = _prepare_experiment(
            dataframe,
            experiment,
            source_column=source_column,
            target=target,
        )

        (
            x_train,
            x_test,
            y_train,
            y_test,
            _,
            subgroup_test,
        ) = train_test_split(
            prepared[features],
            prepared[target],
            prepared[subgroup_columns],
            test_size=split_config["test_size"],
            random_state=split_config["random_state"],
            stratify=prepared[target],
        )

        cv_folds = selection_config.get("cv_folds", 5)
        scoring = selection_config.get("scoring", "f1")
        cross_validator = StratifiedKFold(
            n_splits=cv_folds,
            shuffle=selection_config.get("shuffle", True),
            random_state=(
                split_config["random_state"]
                if selection_config.get("shuffle", True)
                else None
            ),
        )
        pipelines: dict[str, Any] = {}
        cross_validation: dict[str, dict[str, object]] = {}
        thresholds: dict[str, dict[str, float | str]] = {}
        for model_name, settings in enabled_models.items():
            pipeline = build_model_pipeline(
                model_name,
                settings.get("params", {}),
                random_state=split_config["random_state"],
                numeric_features=numeric_features,
                categorical_features=categorical_features,
            )
            fitted_pipeline, validation, threshold = _tune_and_validate(
                pipeline,
                settings,
                x_train,
                y_train,
                cross_validator,
                selection_config,
                split_config["random_state"],
            )
            pipelines[model_name] = fitted_pipeline
            cross_validation[model_name] = validation
            thresholds[model_name] = threshold

        selected_model = max(
            cross_validation,
            key=lambda model_name: cross_validation[model_name]["mean"],
        )
        experiment_metrics: dict[str, object] = {
            "source_dataset": experiment["source_value"],
            "selected_model": selected_model,
            "model_version": None,
            "selection": {
                "metric": scoring,
                "cv_folds": cv_folds,
                "scope": "training_only",
                "search_iterations": selection_config.get("search_iterations", 0),
                "threshold_metric": selection_config.get("threshold", {}).get(
                    "metric", "f2"
                ),
            },
            "records_excluded": exclusions,
            "n_train": len(x_train),
            "n_test": len(x_test),
            "evaluation": {
                "dataset": "held_out_test",
                "calibration": evaluation_config.get(
                    "calibration",
                    {"n_bins": 10, "strategy": "quantile"},
                ),
                "confidence_intervals": evaluation_config.get(
                    "confidence_intervals",
                    {},
                ),
                "subgroup_minimum_size": evaluation_config.get(
                    "subgroup_minimum_size",
                    20,
                ),
                "subgroup_minimum_events": evaluation_config.get(
                    "subgroup_minimum_events",
                    10,
                ),
                "explainability": evaluation_config.get(
                    "explainability",
                    {"enabled": False},
                ),
            },
            "external_validation": _external_validation_note(
                experiment_name,
                experiment,
            ),
            "models": {},
        }

        calibration_config = evaluation_config.get("calibration", {})
        confidence_config = evaluation_config.get(
            "confidence_intervals",
            {},
        )
        confidence_enabled = confidence_config.get("enabled", True)
        confidence_settings = {
            "confidence_level": confidence_config.get(
                "confidence_level",
                0.95,
            ),
            "n_bootstrap": confidence_config.get("n_bootstrap", 2000),
            "random_state": confidence_config.get(
                "random_state",
                split_config["random_state"],
            ),
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
        explainability_config = evaluation_config.get("explainability", {})
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
                n_bins=calibration_config.get("n_bins", 10),
                strategy=calibration_config.get("strategy", "quantile"),
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
                minimum_size=evaluation_config.get(
                    "subgroup_minimum_size",
                    20,
                ),
                minimum_events=evaluation_config.get(
                    "subgroup_minimum_events",
                    10,
                ),
                confidence_settings=subgroup_confidence_settings,
            )
            model_metrics["bias_summary"] = subgroup_bias_summary(
                model_metrics["subgroups"]
            )
            if (
                explainability_config.get("enabled", False)
                and model_name == selected_model
            ):
                model_metrics["explainability"] = explainability_summary(
                    pipeline,
                    x_test,
                    y_test,
                    scoring=explainability_config.get("scoring", "roc_auc"),
                    n_repeats=explainability_config.get("n_repeats", 10),
                    random_state=explainability_config.get(
                        "random_state",
                        split_config["random_state"],
                    ),
                    n_jobs=explainability_config.get("n_jobs"),
                )
                save_feature_importance_plot(
                    model_metrics["explainability"],
                    figures_dir / f"{experiment_name}_feature_importance.png",
                    title=(
                        "Importância por permutação — "
                        f"{experiment_name.upper()} ({model_name})"
                    ),
                    top_n=explainability_config.get("top_n", 12),
                )
            else:
                model_metrics["explainability"] = None
            model_metrics["cross_validation"] = cross_validation[model_name]
            model_metrics["threshold"] = thresholds[model_name]
            model_metrics["model_version"] = model_version
            experiment_metrics["models"][model_name] = model_metrics

            artifact = {
                "pipeline": pipeline,
                "features": features,
                "numeric_features": numeric_features,
                "categorical_features": categorical_features,
                "category_mappings": experiment.get("category_mappings", {}),
                "filters": experiment.get("filters", {}),
                "target": target,
                "source_column": source_column,
                "source_value": experiment["source_value"],
                "experiment_name": experiment_name,
                "model_name": model_name,
                "model_version": model_version,
                "selection_metric": scoring,
                "cross_validation": cross_validation[model_name],
                "decision_threshold": decision_threshold,
                "threshold_metrics": thresholds[model_name],
                "selected": model_name == selected_model,
            }
            model_path = models_dir / f"{experiment_name}_{model_name}.joblib"
            joblib.dump(artifact, model_path)
            if artifact["selected"]:
                experiment_metrics["model_version"] = model_version
                joblib.dump(artifact, models_dir / f"{experiment_name}_selected.joblib")

        save_calibration_plot(
            calibration_curves,
            figures_dir / f"{experiment_name}_calibration.png",
            title=f"Curva de calibração — {experiment_name.upper()}",
        )
        results[experiment_name] = experiment_metrics

    metrics_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara candidatos e treina o modelo selecionado por base."
    )
    parser.add_argument(
        "--config", default="configs/models.yaml", help="Arquivo YAML do experimento."
    )
    args = parser.parse_args()
    metrics = train(args.config)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
