"""Métricas de avaliação para classificação binária."""

from typing import Any

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(
    y_true: Any, y_pred: Any, y_probability: Any
) -> dict[str, float | list[list[int]]]:
    """Calcula as métricas principais e uma matriz de confusão."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_probability)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }

