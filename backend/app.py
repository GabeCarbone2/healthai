"""Aplicação FastAPI do HealthAI."""

from contextlib import asynccontextmanager
from datetime import date, datetime, time
from math import ceil
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.auth import get_consented_user
from backend.auth import router as auth_router
from backend.database import SessionLocal, get_db, init_database
from backend.model_service import (
    EXPERIMENT_LABELS,
    MODEL_LABELS,
    get_catalog,
    predict_record,
)
from backend.models import PredictionResult, User
from backend.privacy import (
    PRIVACY_NOTICE_VERSION,
    privacy_contact,
    purge_expired_results,
    result_retention_days,
)
from backend.schemas import (
    NhanesPredictionInput,
    PatientResultPageResponse,
    PatientResultResponse,
    PimaPredictionInput,
    PrivacyInfoResponse,
)

AuthenticatedUser = Annotated[User, Depends(get_consented_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    with SessionLocal() as db:
        purge_expired_results(db)
        db.commit()
    yield


app = FastAPI(
    title="HealthAI API",
    description="Inferência acadêmica dos modelos Pima e NHANES.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/privacy", response_model=PrivacyInfoResponse)
def privacy() -> dict[str, Any]:
    return {
        "notice_version": PRIVACY_NOTICE_VERSION,
        "result_retention_days": result_retention_days(),
        "contact": privacy_contact(),
    }


@app.get("/models")
def models(_: AuthenticatedUser) -> dict[str, Any]:
    return get_catalog()


@app.post("/predict/pima", response_model=PatientResultResponse)
def predict_pima(
    data: PimaPredictionInput,
    user: AuthenticatedUser,
    db: DatabaseSession,
) -> PredictionResult:
    prediction = predict_record(
        "pima", data.model_dump(exclude={"patient_identifier"})
    )
    return save_result(db, user, data.patient_identifier, prediction)


@app.post("/predict/nhanes", response_model=PatientResultResponse)
def predict_nhanes(
    data: NhanesPredictionInput,
    user: AuthenticatedUser,
    db: DatabaseSession,
) -> PredictionResult:
    prediction = predict_record(
        "nhanes", data.model_dump(exclude={"patient_identifier"})
    )
    return save_result(db, user, data.patient_identifier, prediction)


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
        predicted_class=prediction["predicted_class"],
        probability=prediction["probability"],
        decision_threshold=prediction["decision_threshold"],
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.get("/results", response_model=PatientResultPageResponse)
def results(
    user: AuthenticatedUser,
    db: DatabaseSession,
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

    purge_expired_results(db, user.id)
    db.commit()
    conditions = [PredictionResult.user_id == user.id]
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
            PredictionResult.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to:
        conditions.append(
            PredictionResult.created_at <= datetime.combine(date_to, time.max)
        )

    total = db.scalar(
        select(func.count(PredictionResult.id)).where(*conditions)
    ) or 0
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


@app.delete("/results", status_code=status.HTTP_204_NO_CONTENT)
def clear_results(user: AuthenticatedUser, db: DatabaseSession) -> None:
    db.execute(
        delete(PredictionResult).where(PredictionResult.user_id == user.id)
    )
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
