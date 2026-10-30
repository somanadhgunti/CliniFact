"""Verification orchestration for retrieval and prediction services."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.verification import (
    EvidenceItem,
    Prediction,
    PredictionLabel,
    VerificationResponse,
    VerificationStatus,
)
from app.services.prediction_service import PredictionResult, PredictionService
from app.services.prediction_service import PredictionServiceError
from app.services.clinical_trials_service import ClinicalTrialsServiceError
from app.services.pubmed_service import PubMedServiceError


class EvidenceRetriever(Protocol):
    def search(self, claim: str, max_results: int) -> list[EvidenceItem]:
        ...


class VerificationServiceError(RuntimeError):
    """Base error for controlled verification failures."""


class EvidenceRetrievalError(VerificationServiceError):
    """Raised when neither evidence source can be queried."""


class PredictionExecutionError(VerificationServiceError):
    """Raised when the model cannot produce a prediction."""


@dataclass(frozen=True)
class RetrievalOutcome:
    items: list[EvidenceItem]
    warning: str | None = None


def _deduplicate(items: list[EvidenceItem]) -> list[EvidenceItem]:
    unique: list[EvidenceItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if item.pmid:
            key = ("pmid", item.pmid.strip())
        elif item.nct_id:
            key = ("nct", item.nct_id.strip().upper())
        else:
            key = ("fallback", f"{item.source.value}:{item.title.strip().lower()}")
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def build_evidence_context(items: list[EvidenceItem]) -> str:
    parts = []
    for item in items:
        text = f"{item.source.value}: {item.title}"
        if item.abstract_or_excerpt:
            text += f"\n{item.abstract_or_excerpt.strip()}"
        parts.append(text)
    return "\n\n".join(parts)


def _prediction(result: PredictionResult) -> Prediction:
    probabilities = {
        PredictionLabel(label): score for label, score in result.probabilities.items()
    }
    return Prediction(
        label=PredictionLabel(result.label),
        label_id=result.label_id,
        confidence=result.predicted_probability,
        model_score=result.predicted_probability,
        probabilities=probabilities,
    )


class VerificationService:
    def __init__(
        self,
        pubmed: EvidenceRetriever,
        clinical_trials: EvidenceRetriever,
        prediction: PredictionService,
    ) -> None:
        self._pubmed = pubmed
        self._clinical_trials = clinical_trials
        self._prediction = prediction

    def verify(self, claim: str, max_evidence_items: int) -> VerificationResponse:
        outcomes: list[EvidenceItem] = []
        warnings: list[str] = []
        failures = 0
        for name, service in (
            ("PubMed", self._pubmed),
            ("ClinicalTrials.gov", self._clinical_trials),
        ):
            try:
                outcomes.extend(service.search(claim, max_evidence_items))
            except (PubMedServiceError, ClinicalTrialsServiceError) as error:
                failures += 1
                warnings.append(f"{name} evidence retrieval failed: {error}")

        evidence = _deduplicate(outcomes)[:max_evidence_items]
        if not evidence:
            if failures == 2:
                raise EvidenceRetrievalError(
                    "Both evidence sources failed; no verification was performed"
                )
            return VerificationResponse(
                claim=claim,
                status=VerificationStatus.INCONCLUSIVE,
                warnings=warnings
                + ["No evidence was retrieved; no model prediction was produced."],
                limitations=[
                    "Search results are not proof that a claim is supported or contradicted."
                ],
            )

        try:
            result = self._prediction.predict(claim, build_evidence_context(evidence))
        except (PredictionServiceError, ValueError) as error:
            raise PredictionExecutionError(
                f"Prediction service failed: {error}"
            ) from error
        return VerificationResponse(
            claim=claim,
            prediction=_prediction(result),
            evidence=evidence,
            status=VerificationStatus.COMPLETED,
            warnings=warnings,
            limitations=[
                "The prediction is a model output, not calibrated medical confidence or proof.",
                "Retrieved evidence relevance does not establish support or contradiction.",
                "The current BioBERT smoke checkpoint is experimental and not a validated final research model.",
            ],
        )
