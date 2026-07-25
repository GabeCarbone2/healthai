"""Pré-processamento e construção dos modelos de classificação."""

from typing import Any

from sklearn.base import ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

SUPPORTED_MODELS = {
    "logistic_regression",
    "random_forest",
    "svm",
    "gradient_boosting",
}


def _build_classifier(
    model_name: str,
    params: dict[str, Any],
    random_state: int,
) -> ClassifierMixin:
    """Instancia o classificador solicitado."""
    model_params = params.copy()

    if model_name == "logistic_regression":
        model_params.setdefault("random_state", random_state)
        return LogisticRegression(**model_params)
    if model_name == "random_forest":
        model_params.setdefault("random_state", random_state)
        return RandomForestClassifier(**model_params)
    if model_name == "svm":
        calibration_cv = model_params.pop("calibration_cv", 5)
        model_params.setdefault("random_state", random_state)
        return CalibratedClassifierCV(
            estimator=SVC(**model_params),
            method="sigmoid",
            cv=calibration_cv,
            ensemble=False,
        )
    if model_name == "gradient_boosting":
        model_params.setdefault("random_state", random_state)
        return GradientBoostingClassifier(**model_params)

    supported = ", ".join(sorted(SUPPORTED_MODELS))
    raise ValueError(f"Modelo desconhecido: {model_name}. Opções: {supported}")


def build_model_pipeline(
    model_name: str,
    params: dict[str, Any] | None = None,
    *,
    random_state: int = 42,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
    calibration: dict[str, Any] | None = None,
    training_sample_size: int | None = None,
) -> Pipeline:
    """Cria o pipeline de pré-processamento e classificação escolhido."""
    classifier = _build_classifier(model_name, params or {}, random_state)
    calibration = calibration or {}
    if calibration.get("enabled", False) and model_name != "svm":
        method = calibration.get("method", "sigmoid")
        if (
            method == "isotonic"
            and training_sample_size is not None
            and training_sample_size < calibration.get("minimum_samples_isotonic", 1000)
        ):
            raise ValueError(
                "Calibração isotônica recusada: amostra de treino abaixo do "
                "minimum_samples_isotonic configurado."
            )
        classifier = CalibratedClassifierCV(
            estimator=classifier,
            method=method,
            cv=calibration.get("cv_folds", 5),
            ensemble=False,
        )

    # Mantém compatibilidade com matrizes puramente numéricas, inclusive nos
    # testes e em experimentos isolados com apenas uma das bases.
    if numeric_features is None and categorical_features is None:
        steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
        if model_name in {"logistic_regression", "svm"}:
            steps.append(("scaler", StandardScaler()))
        steps.append(("classifier", classifier))
        return Pipeline(steps=steps)

    # Escala é essencial para regressão logística e SVM. Modelos baseados em
    # árvores não dependem dela e preservam a escala original das variáveis.
    numeric_steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median"))
    ]
    if model_name in {"logistic_regression", "svm"}:
        numeric_steps.append(("scaler", StandardScaler()))

    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric_features:
        transformers.append(
            ("numeric", Pipeline(steps=numeric_steps), numeric_features)
        )
    if categorical_features:
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                (
                    "one_hot",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_features))
    if not transformers:
        raise ValueError("Informe ao menos uma variável numérica ou categórica.")

    preprocessor = ColumnTransformer(transformers=transformers)
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )
