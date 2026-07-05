"""Contratos de entrada e saída da API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BrazilianState = Literal[
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    crm: str = Field(min_length=1, max_length=10, pattern=r"^\d{1,10}$")
    crm_uf: BrazilianState
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    privacy_accepted: Literal[True]

    @field_validator("name", "crm", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Informe um nome válido.")
        return value

    @field_validator("crm_uf", mode="before")
    @classmethod
    def normalize_crm_uf(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailInput(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResendEmailVerificationInput(BaseModel):
    email: EmailStr


class RegistrationResponse(BaseModel):
    email: EmailStr
    verification_required: Literal[True] = True
    expires_in_seconds: int
    email_sent: bool


class PrivacyConsentInput(BaseModel):
    accepted: Literal[True]


class DeleteAccountInput(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirmation: Literal["EXCLUIR"]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    crm: str | None
    crm_uf: str | None
    role: str
    created_at: datetime
    email_verified_at: datetime | None
    privacy_accepted_at: datetime | None
    privacy_notice_version: str | None


class PatientPredictionInput(BaseModel):
    """Dados de identificação comuns às avaliações persistidas."""

    patient_identifier: str = Field(
        min_length=12,
        max_length=24,
        pattern=r"^PAC-[A-Z0-9]{8,20}$",
    )

    @field_validator("patient_identifier", mode="before")
    @classmethod
    def normalize_patient_identifier(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class PimaPredictionInput(PatientPredictionInput):
    """Variáveis usadas pelo modelo Pima."""

    pregnancies: int = Field(ge=0, le=20)
    glucose_mg_dl: float | None = Field(default=None, ge=20, le=600)
    diastolic_bp_mmhg: float | None = Field(default=None, ge=30, le=180)
    skin_thickness_mm: float | None = Field(default=None, ge=1, le=100)
    serum_insulin_muu_ml: float | None = Field(default=None, ge=1, le=1000)
    bmi_kg_m2: float | None = Field(default=None, ge=10, le=80)
    diabetes_pedigree_function: float | None = Field(default=None, ge=0, le=3)
    age_years: int = Field(ge=21, le=100)


class NhanesPredictionInput(PatientPredictionInput):
    """Variáveis usadas pelo modelo NHANES."""

    sex: Literal["female", "male"]
    age_years: int = Field(ge=18, le=100)
    bmi_kg_m2: float | None = Field(default=None, ge=10, le=90)
    systolic_bp_mmhg: float | None = Field(default=None, ge=60, le=260)
    diastolic_bp_mmhg: float | None = Field(default=None, ge=30, le=180)
    hba1c_percent: float | None = Field(default=None, ge=2, le=20)
    glucose_mg_dl: float | None = Field(default=None, ge=20, le=600)


class PredictionResponse(BaseModel):
    """Resultado acadêmico retornado por um modelo selecionado."""

    experiment: str
    model: str
    predicted_class: int
    probability: float
    decision_threshold: float


class PatientResultResponse(BaseModel):
    """Resultado persistido e vinculado ao usuário autenticado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_identifier: str
    created_at: datetime
    experiment: str
    model: str
    predicted_class: int
    probability: float
    decision_threshold: float


class PatientResultPageResponse(BaseModel):
    """Página do histórico de avaliações."""

    items: list[PatientResultResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PrivacyInfoResponse(BaseModel):
    notice_version: str
    result_retention_days: int
    contact: str
