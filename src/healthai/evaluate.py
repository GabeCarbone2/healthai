"""Métricas de avaliação para classificação binária."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _metric_values(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_probability: np.ndarray,
) -> dict[str, float | None]:
    has_both_classes = len(np.unique(y_true)) > 1
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, zero_division=0)
        ),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": (
            float(roc_auc_score(y_true, y_probability))
            if has_both_classes
            else None
        ),
        "brier_score": float(brier_score_loss(y_true, y_probability)),
    }


def classification_metrics(
    y_true: Any, y_pred: Any, y_probability: Any
) -> dict[str, object]:
    """Calcula as métricas principais e uma matriz de confusão."""
    y_true_array = np.asarray(y_true)
    y_pred_array = np.asarray(y_pred)
    probability_array = np.asarray(y_probability)
    return {
        **_metric_values(y_true_array, y_pred_array, probability_array),
        "confusion_matrix": confusion_matrix(
            y_true_array,
            y_pred_array,
            labels=[0, 1],
        ).tolist(),
    }


def calibration_summary(
    y_true: Any,
    y_probability: Any,
    *,
    n_bins: int = 10,
    strategy: str = "quantile",
) -> dict[str, object]:
    """Calcula os pontos da curva de calibração e o ECE."""
    if n_bins < 2:
        raise ValueError("A curva de calibração requer ao menos dois bins.")
    if strategy not in {"quantile", "uniform"}:
        raise ValueError("Estratégia de calibração deve ser quantile ou uniform.")

    labels = np.asarray(y_true, dtype=float)
    probabilities = np.asarray(y_probability, dtype=float)
    if strategy == "quantile":
        edges = np.quantile(
            probabilities,
            np.linspace(0.0, 1.0, n_bins + 1),
        )
    else:
        edges = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.unique(edges)
    if len(edges) == 1:
        edges = np.array([0.0, 1.0])

    bin_ids = np.searchsorted(edges[1:-1], probabilities, side="right")
    points: list[dict[str, float | int]] = []
    absolute_error_sum = 0.0
    for bin_id in range(len(edges) - 1):
        mask = bin_ids == bin_id
        count = int(mask.sum())
        if count == 0:
            continue
        mean_probability = float(probabilities[mask].mean())
        observed_frequency = float(labels[mask].mean())
        absolute_error_sum += count * abs(
            observed_frequency - mean_probability
        )
        points.append(
            {
                "bin_lower": float(edges[bin_id]),
                "bin_upper": float(edges[bin_id + 1]),
                "mean_predicted_probability": mean_probability,
                "observed_frequency": observed_frequency,
                "count": count,
            }
        )

    return {
        "dataset": "test",
        "strategy": strategy,
        "requested_bins": n_bins,
        "effective_bins": len(points),
        "expected_calibration_error": float(
            absolute_error_sum / len(probabilities)
        ),
        "points": points,
    }


def bootstrap_confidence_intervals(
    y_true: Any,
    y_pred: Any,
    y_probability: Any,
    *,
    confidence_level: float = 0.95,
    n_bootstrap: int = 2000,
    random_state: int = 42,
) -> dict[str, object]:
    """Estima ICs percentis com reamostragem pareada das observações."""
    if not 0 < confidence_level < 1:
        raise ValueError("O nível de confiança deve estar entre zero e um.")
    if n_bootstrap < 1:
        raise ValueError("O número de reamostragens deve ser positivo.")

    labels = np.asarray(y_true)
    predictions = np.asarray(y_pred)
    probabilities = np.asarray(y_probability)
    estimates = _metric_values(labels, predictions, probabilities)
    samples: dict[str, list[float]] = {
        metric: [] for metric in estimates
    }
    generator = np.random.default_rng(random_state)
    for _ in range(n_bootstrap):
        indices = generator.integers(0, len(labels), size=len(labels))
        values = _metric_values(
            labels[indices],
            predictions[indices],
            probabilities[indices],
        )
        for metric, value in values.items():
            if value is not None:
                samples[metric].append(value)

    alpha = 1.0 - confidence_level
    intervals: dict[str, dict[str, float | int] | None] = {}
    for metric, estimate in estimates.items():
        metric_samples = samples[metric]
        if estimate is None or not metric_samples:
            intervals[metric] = None
            continue
        intervals[metric] = {
            "estimate": estimate,
            "lower": float(np.quantile(metric_samples, alpha / 2)),
            "upper": float(
                np.quantile(metric_samples, 1 - (alpha / 2))
            ),
            "valid_resamples": len(metric_samples),
        }

    return {
        "method": "paired_nonparametric_percentile_bootstrap",
        "dataset": "test",
        "confidence_level": confidence_level,
        "n_bootstrap": n_bootstrap,
        "random_state": random_state,
        "metrics": intervals,
    }


def subgroup_evaluation(
    y_true: Any,
    y_pred: Any,
    y_probability: Any,
    dataframe: pd.DataFrame,
    definitions: list[dict[str, Any]],
    *,
    minimum_size: int = 20,
    minimum_events: int = 10,
    confidence_settings: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Avalia desempenho por grupos definidos sem omitir amostras pequenas."""
    labels = np.asarray(y_true)
    predictions = np.asarray(y_pred)
    probabilities = np.asarray(y_probability)
    confidence_settings = confidence_settings or {}
    results: dict[str, object] = {}

    for definition in definitions:
        column = definition["column"]
        name = definition.get("name", column)
        if column not in dataframe.columns:
            raise ValueError(f"Coluna de subgrupo ausente: {column}")

        values = dataframe[column].reset_index(drop=True)
        if "bins" in definition:
            group_values = pd.cut(
                values,
                bins=definition["bins"],
                labels=definition["labels"],
                right=definition.get("right", False),
                include_lowest=True,
            ).astype(object)
            group_order = definition["labels"]
            display_labels = {
                str(value): str(value) for value in group_order
            }
        else:
            group_values = values.astype(object)
            configured_labels = definition.get("value_labels", {})
            observed_values = [
                value
                for value in pd.unique(group_values)
                if not pd.isna(value)
            ]
            group_order = observed_values
            if configured_labels:
                group_order = [
                    next(
                        (
                            value
                            for value in observed_values
                            if str(value) == configured_value
                        ),
                        configured_value,
                    )
                    for configured_value in configured_labels
                ]
            display_labels = {
                str(value): configured_labels.get(
                    str(value),
                    str(value),
                )
                for value in group_order
            }

        groups = []
        for value in group_order:
            mask = np.asarray(group_values == value)
            count = int(mask.sum())
            positives = int(labels[mask].sum()) if count else 0
            group_result: dict[str, object] = {
                "value": str(value),
                "label": display_labels[str(value)],
                "n": count,
                "positives": positives,
                "prevalence": float(positives / count) if count else None,
            }
            if count < minimum_size:
                group_result.update(
                    {
                        "metrics": None,
                        "confidence_intervals": None,
                        "status": "insufficient_sample",
                        "minimum_size": minimum_size,
                    }
                )
            else:
                limited_events = min(positives, count - positives) < minimum_events
                group_result.update(
                    {
                        "metrics": classification_metrics(
                            labels[mask],
                            predictions[mask],
                            probabilities[mask],
                        ),
                        "confidence_intervals": (
                            bootstrap_confidence_intervals(
                                labels[mask],
                                predictions[mask],
                                probabilities[mask],
                                **confidence_settings,
                            )
                            if confidence_settings.get("n_bootstrap", 0) > 0
                            else None
                        ),
                        "status": (
                            "limited_events"
                            if limited_events
                            else "estimated"
                        ),
                        "minimum_events": minimum_events,
                    }
                )
            groups.append(group_result)

        results[name] = {
            "column": column,
            "label": definition.get("label", name),
            "dataset": "test",
            "minimum_size": minimum_size,
            "minimum_events": minimum_events,
            "n_total": len(group_values),
            "missing_or_unassigned": int(pd.isna(group_values).sum()),
            "groups": groups,
        }
    return results


def save_calibration_plot(
    curves: dict[str, dict[str, object]],
    output_path: str | Path,
    *,
    title: str,
) -> None:
    """Salva um diagrama de confiabilidade para comparação dos modelos."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model_labels = {
        "logistic_regression": "Regressão Logística",
        "random_forest": "Random Forest",
        "svm": "SVM",
        "gradient_boosting": "Gradient Boosting",
    }
    figure, axis = plt.subplots(figsize=(7, 6))
    axis.plot([0, 1], [0, 1], "--", color="#666666", label="Calibração ideal")
    for model_name, curve in curves.items():
        points = curve["points"]
        ece = curve["expected_calibration_error"]
        axis.plot(
            [point["mean_predicted_probability"] for point in points],
            [point["observed_frequency"] for point in points],
            marker="o",
            label=f"{model_labels.get(model_name, model_name)} (ECE={ece:.3f})",
        )
    axis.set(
        title=title,
        xlabel="Probabilidade média prevista",
        ylabel="Frequência observada",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_path,
        dpi=180,
        facecolor="white",
        transparent=False,
    )
    plt.close(figure)
