"""Aplicação FastAPI do HealthAI."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, time, timezone
from math import ceil
from time import perf_counter
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from backend.auth import get_consented_user
from backend.auth import router as auth_router
from backend.database import SessionLocal, get_db, get_read_db, init_database
from backend.model_service import (
    EXPERIMENT_LABELS,
    MODEL_LABELS,
    get_catalog,
    load_artifact,
    predict_record,
)
from backend.models import PredictionResult, User
from backend.privacy import (
    PRIVACY_NOTICE_VERSION,
    cleanup_interval_seconds,
    privacy_contact,
    purge_expired_auth_records,
    purge_expired_results,
    result_retention_cutoff,
    result_retention_days,
)
from backend.schemas import (
    NhanesPredictionInput,
    PatientPredictionResponse,
    PatientResultPageResponse,
    PimaPredictionInput,
    PrivacyInfoResponse,
    TermsInfoResponse,
)
from backend.security import (
    check_rate_limit,
    docs_enabled,
    trusted_origins,
    validate_unsafe_request_origin,
)
from backend.settings import setting, validate_production_settings
from backend.terms import TERMS_EFFECTIVE_DATE, TERMS_VERSION

AuthenticatedUser = Annotated[User, Depends(get_consented_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]
ReadDatabaseSession = Annotated[Session, Depends(get_read_db)]
logger = logging.getLogger("healthai.http")
logger.setLevel(logging.INFO)


def purge_expired_records() -> None:
    with SessionLocal() as db:
        purge_expired_results(db)
        purge_expired_auth_records(db)
        db.commit()


async def periodic_cleanup() -> None:
    while True:
        await asyncio.sleep(cleanup_interval_seconds())
        purge_expired_records()


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_settings()
    init_database()
    with SessionLocal() as db:
        purge_expired_results(db)
        purge_expired_auth_records(db)
        db.commit()
    cleanup_task = asyncio.create_task(periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


_docs_enabled = docs_enabled()
app = FastAPI(
    title="HealthAI API",
    description="Inferência acadêmica dos modelos Pima e NHANES.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(trusted_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.middleware("http")
async def log_request_without_query_data(request: Request, call_next):
    """Registra operação sem query string ou identificadores pseudonimizados."""
    started_at = perf_counter()
    response = await call_next(request)
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started_at) * 1000,
    )
    return response


@app.middleware("http")
async def reject_untrusted_unsafe_origins(request: Request, call_next):
    try:
        validate_unsafe_request_origin(request)
    except HTTPException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail},
        )
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Confirma banco, relatório e artefatos necessários à inferência."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        catalog = get_catalog()
        for experiment in catalog["experiments"]:
            artifact = load_artifact(experiment["id"])
            if artifact["model_name"] != experiment["selected_model"]:
                raise RuntimeError("Artefato e relatório de modelo divergentes.")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço ainda não está pronto.",
        ) from error
    return {"status": "ready"}


@app.get("/privacy", response_model=PrivacyInfoResponse)
def privacy() -> dict[str, Any]:
    return {
        "notice_version": PRIVACY_NOTICE_VERSION,
        "result_retention_days": result_retention_days(),
        "contact": privacy_contact(),
    }


@app.get("/terms", response_model=TermsInfoResponse)
def terms() -> dict[str, str]:
    return {
        "version": TERMS_VERSION,
        "effective_date": TERMS_EFFECTIVE_DATE,
    }


@app.get("/models")
def models(_: AuthenticatedUser) -> dict[str, Any]:
    return get_catalog()


@app.post(
    "/predict/pima",
    response_model=PatientPredictionResponse,
    response_model_exclude_none=True,
)
def predict_pima(
    data: PimaPredictionInput,
    user: AuthenticatedUser,
    db: DatabaseSession,
    request: Request,
) -> dict[str, Any]:
    check_rate_limit(
        request,
        scope="predict",
        limit=120,
        window_seconds=60,
        identifier=str(user.id),
    )
    prediction = predict_record("pima", data.model_dump(exclude={"patient_identifier"}))
    result = save_result(db, user, data.patient_identifier, prediction)
    return new_prediction_response(result, prediction)


@app.post(
    "/predict/nhanes",
    response_model=PatientPredictionResponse,
    response_model_exclude_none=True,
)
def predict_nhanes(
    data: NhanesPredictionInput,
    user: AuthenticatedUser,
    db: DatabaseSession,
    request: Request,
) -> dict[str, Any]:
    check_rate_limit(
        request,
        scope="predict",
        limit=120,
        window_seconds=60,
        identifier=str(user.id),
    )
    prediction = predict_record(
        "nhanes", data.model_dump(exclude={"patient_identifier"})
    )
    result = save_result(db, user, data.patient_identifier, prediction)
    return new_prediction_response(result, prediction)


def new_prediction_response(
    result: PredictionResult,
    prediction: dict[str, Any],
) -> dict[str, Any]:
    """Combina a saída persistida com a explicação mantida apenas em memória."""
    response = {
        "id": result.id,
        "patient_identifier": result.patient_identifier,
        "created_at": result.created_at,
        "experiment": result.experiment,
        "model": result.model,
        "model_version": result.model_version,
        "predicted_class": result.predicted_class,
        "probability": result.probability,
        "decision_threshold": result.decision_threshold,
        "input_completeness": result.input_completeness,
        "missing_feature_count": result.missing_feature_count,
        "local_explanation": prediction.get(
            "local_explanation",
            {
                "method": "single_feature_reference_replacement",
                "interpretation": "Explicação local indisponível para esta execução.",
                "features": [],
            },
        ),
    }
    for key in (
        "input_status",
        "validation_warnings",
        "missing_features",
        "imputed_features",
        "outside_applicability",
    ):
        if key in prediction:
            response[key] = prediction[key]
    return response


def save_result(
    db: Session,
    user: User,
    patient_identifier: str,
    prediction: dict[str, Any],
) -> PredictionResult:
    """Persiste somente a saída da avaliação, sem os valores clínicos."""
    purge_expired_results(db, user.id)
    result = PredictionResult(
        user_id=user.id,
        patient_identifier=patient_identifier,
        experiment=EXPERIMENT_LABELS.get(
            prediction["experiment"], prediction["experiment"]
        ),
        model=MODEL_LABELS.get(prediction["model"], prediction["model"]),
        model_version=prediction.get("model_version", "unversioned"),
        predicted_class=prediction["predicted_class"],
        probability=prediction["probability"],
        decision_threshold=prediction["decision_threshold"],
        input_completeness=prediction.get("input_completeness", 1.0),
        missing_feature_count=prediction.get("missing_feature_count", 0),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.get("/results", response_model=PatientResultPageResponse)
def results(
    user: AuthenticatedUser,
    db: ReadDatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    search: Annotated[str | None, Query(max_length=120)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="A data inicial não pode ser posterior à data final.",
        )

    conditions = [
        PredictionResult.user_id == user.id,
        PredictionResult.created_at >= result_retention_cutoff(),
    ]
    normalized_search = search.strip() if search else ""
    if normalized_search:
        escaped_search = (
            normalized_search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        conditions.append(
            PredictionResult.patient_identifier.ilike(
                f"%{escaped_search}%",
                escape="\\",
            )
        )
    if date_from:
        conditions.append(
            PredictionResult.created_at >= local_date_to_utc(date_from, time.min)
        )
    if date_to:
        conditions.append(
            PredictionResult.created_at <= local_date_to_utc(date_to, time.max)
        )

    total = db.scalar(select(func.count(PredictionResult.id)).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(PredictionResult)
            .where(*conditions)
            .order_by(PredictionResult.created_at.desc(), PredictionResult.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
    }


def local_date_to_utc(value: date, boundary: time) -> datetime:
    timezone_name = setting("HEALTHAI_TIMEZONE", "America/Sao_Paulo")
    try:
        local_timezone = ZoneInfo(timezone_name)
    except (KeyError, ValueError) as error:
        raise RuntimeError("HEALTHAI_TIMEZONE inválido.") from error
    return datetime.combine(value, boundary, tzinfo=local_timezone).astimezone(
        timezone.utc
    )


@app.delete("/results", status_code=status.HTTP_204_NO_CONTENT)
def clear_results(user: AuthenticatedUser, db: DatabaseSession) -> None:
    db.execute(delete(PredictionResult).where(PredictionResult.user_id == user.id))
    db.commit()


@app.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_result(
    result_id: int,
    user: AuthenticatedUser,
    db: DatabaseSession,
) -> None:
    deleted = db.execute(
        delete(PredictionResult).where(
            PredictionResult.id == result_id,
            PredictionResult.user_id == user.id,
        )
    )
    if deleted.rowcount == 0:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")
    db.commit()


def run() -> None:
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
