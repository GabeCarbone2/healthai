"""Pré-processamento e construção do baseline."""

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_baseline_pipeline(
    *, max_iter: int = 1000, class_weight: str | None = "balanced"
) -> Pipeline:
    """Cria um pipeline de imputação, escala e regressão logística."""
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=max_iter,
                    class_weight=class_weight,
                ),
            ),
        ]
    )

