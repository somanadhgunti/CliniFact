"""Request and response contracts for future claim verification."""

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class PredictionLabel(str, Enum):
    INCONCLUSIVE = "inconclusive"
    EVIDENCE = "evidence"
    NEI = "NEI"


class EvidenceSource(str, Enum):
    PUBMED = "PubMed"
    CLINICALTRIALS_GOV = "ClinicalTrials.gov"


class VerificationStatus(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    INCONCLUSIVE = "inconclusive"
    COMPLETED = "completed"
    ERROR = "error"


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: Annotated[str, Field(min_length=1, max_length=settings.request_length_limit)]
    max_evidence_items: Annotated[int, Field(default=5, ge=1, le=20)]

    @field_validator("claim", mode="before")
    @classmethod
    def trim_claim(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: EvidenceSource
    title: Annotated[str, Field(min_length=1, max_length=500)]
    abstract_or_excerpt: str | None = None
    publication_date: date | None = None
    pmid: str | None = None
    nct_id: str | None = None
    source_url: str | None = None
    study_status: str | None = None
    start_date: date | None = None
    completion_date: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: PredictionLabel
    confidence: float | None = Field(default=None, ge=0, le=1)
    label_id: int | None = Field(default=None, ge=0, le=2)
    model_score: float | None = Field(default=None, ge=0, le=1)
    probabilities: dict[PredictionLabel, float] | None = None


class VerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    prediction: Prediction | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    status: VerificationStatus
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
