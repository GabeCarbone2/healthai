"""Contratos de entrada e saída da API."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

BrazilianState = Literal[
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
]
CrmStatus = Literal["pending", "approved", "rejected"]


def ensure_utc(value: datetime | None) -> datetime | None:
    """Marca timestamps SQLite sem fuso como UTC antes da serialização."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class CrmCredentialsInput(BaseModel):
    crm: str = Field(min_length=1, max_length=10, pattern=r"^\d{1,10}$")
    crm_uf: BrazilianState

    @field_validator("crm", mode="before")
    @classmethod
    def strip_crm(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("crm_uf", mode="before")
    @classmethod
    def normalize_crm_uf(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class RegisterInput(CrmCredentialsInput):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    privacy_accepted: Literal[True]
    terms_accepted: Literal[True]

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Informe um nome válido.")
        return value


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailInput(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResendEmailVerificationInput(BaseModel):
    email: EmailStr


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ResetPasswordInput(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class RegistrationResponse(BaseModel):
    email: EmailStr
    verification_required: Literal[True] = True
    expires_in_seconds: int
    email_sent: bool


class PrivacyConsentInput(BaseModel):
    accepted: Literal[True]


class TermsConsentInput(BaseModel):
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
    crm_status: CrmStatus | None
    crm_verified_at: datetime | None
    crm_verified_by: int | None
    crm_rejection_reason: str | None
    role: str
    created_at: datetime
    email_verified_at: datetime | None
    privacy_accepted_at: datetime | None
    privacy_notice_version: str | None
    terms_accepted_at: datetime | None
    terms_version: str | None

    @field_serializer(
        "created_at",
        "email_verified_at",
        "crm_verified_at",
        "privacy_accepted_at",
        "terms_accepted_at",
    )
    def serialize_datetimes(self, value: datetime | None) -> datetime | None:
        return ensure_utc(value)


class CrmVerificationChallengeResponse(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    download_url: str


class CrmVerificationStatusResponse(BaseModel):
    crm_status: CrmStatus | None
    active_challenge: CrmVerificationChallengeResponse | None


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

    pregnancies: int = Field(ge=0, le=30)
    glucose_mg_dl: float = Field(ge=0, le=1000)
    diastolic_bp_mmhg: float | None = Field(default=None, ge=0, le=300)
    skin_thickness_mm: float | None = Field(default=None, ge=0, le=200)
    serum_insulin_muu_ml: float | None = Field(default=None, ge=0, le=5000)
    bmi_kg_m2: float = Field(ge=0, le=150)
    diabetes_pedigree_function: float = Field(ge=0, le=10)
    age_years: int = Field(ge=0, le=130)


class NhanesPredictionInput(PatientPredictionInput):
    """Variáveis usadas pelo modelo NHANES."""

    sex: Literal["female", "male"]
    age_years: int = Field(ge=0, le=130)
    bmi_kg_m2: float = Field(ge=0, le=150)
    systolic_bp_mmhg: float | None = Field(default=None, ge=0, le=350)
    diastolic_bp_mmhg: float | None = Field(default=None, ge=0, le=300)
    hba1c_percent: float = Field(ge=0, le=30)
    glucose_mg_dl: float | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_clinical_completeness(self) -> "NhanesPredictionInput":
        measurements = (
            self.bmi_kg_m2,
            self.systolic_bp_mmhg,
            self.diastolic_bp_mmhg,
            self.hba1c_percent,
            self.glucose_mg_dl,
        )
        if sum(value is not None for value in measurements) < 3:
            raise ValueError(
                "Informe ao menos três das cinco medidas clínicas do perfil geral."
            )
        if (
            self.systolic_bp_mmhg is not None
            and self.diastolic_bp_mmhg is not None
            and self.systolic_bp_mmhg <= self.diastolic_bp_mmhg
        ):
            raise ValueError(
                "A pressão sistólica deve ser maior que a pressão diastólica."
            )
        return self


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
    model_version: str
    predicted_class: int
    probability: float
    decision_threshold: float
    input_completeness: float
    missing_feature_count: int

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> datetime:
        return ensure_utc(value) or value


class LocalFeatureEffect(BaseModel):
    feature: str
    probability_effect: float
    direction: Literal["increases", "decreases", "neutral"]


class LocalExplanation(BaseModel):
    method: Literal["single_feature_reference_replacement"]
    concept: Literal["local_sensitivity_to_training_reference"] | None = None
    interpretation: str
    features: list[LocalFeatureEffect]
    reference_effects: list[dict[str, object]] | None = None


class PatientPredictionResponse(PatientResultResponse):
    """Resultado recém-calculado com explicação efêmera, não persistida."""

    local_explanation: LocalExplanation
    input_status: Literal["predicted"] | None = None
    validation_warnings: list[dict[str, object]] | None = None
    missing_features: list[str] | None = None
    imputed_features: list[str] | None = None
    outside_applicability: list[str] | None = None


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


class TermsInfoResponse(BaseModel):
    version: str
    effective_date: str
