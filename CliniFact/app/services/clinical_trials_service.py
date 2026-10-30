"""ClinicalTrials.gov API v2 evidence retrieval without import-time side effects."""

from datetime import date
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.schemas.verification import EvidenceItem, EvidenceSource


CLINICAL_TRIALS_API_URL = "https://clinicaltrials.gov/api/v2/studies"
CLINICAL_TRIALS_STUDY_URL = "https://clinicaltrials.gov/study/{nct_id}"


class ClinicalTrialsServiceError(RuntimeError):
    """Base error for ClinicalTrials.gov retrieval failures."""


class ClinicalTrialsHTTPError(ClinicalTrialsServiceError):
    """Raised when the ClinicalTrials.gov API request fails."""


class ClinicalTrialsResponseError(ClinicalTrialsServiceError):
    """Raised when the API response is malformed or unusable."""


class _HTTPClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any:
        ...


def _validate_claim(claim: str) -> str:
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be a non-empty string")
    claim = claim.strip()
    if len(claim) > settings.request_length_limit:
        raise ValueError(
            f"claim exceeds the {settings.request_length_limit}-character limit"
        )
    return claim


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        parts = value.split("-")
        if len(parts) == 1:
            return date(int(parts[0]), 1, 1)
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1)
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _date_struct(module: dict[str, Any], key: str) -> date | None:
    value = module.get(key)
    if not isinstance(value, dict):
        return None
    return _parse_date(value.get("date"))


def _normalize_study(study: Any) -> EvidenceItem | None:
    if not isinstance(study, dict):
        return None
    protocol = study.get("protocolSection")
    if not isinstance(protocol, dict):
        return None
    identification = protocol.get("identificationModule")
    if not isinstance(identification, dict):
        return None
    nct_id = identification.get("nctId")
    title = identification.get("briefTitle") or identification.get("officialTitle")
    if not isinstance(nct_id, str) or not nct_id.strip():
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    description = protocol.get("descriptionModule")
    status = protocol.get("statusModule")
    description = description if isinstance(description, dict) else {}
    status = status if isinstance(status, dict) else {}
    nct_id = nct_id.strip()
    return EvidenceItem(
        source=EvidenceSource.CLINICALTRIALS_GOV,
        title=title.strip(),
        abstract_or_excerpt=description.get("briefSummary"),
        publication_date=None,
        nct_id=nct_id,
        source_url=CLINICAL_TRIALS_STUDY_URL.format(nct_id=nct_id),
        study_status=status.get("overallStatus"),
        start_date=_date_struct(status, "studyFirstSubmitDateStruct")
        or _date_struct(status, "startDateStruct"),
        completion_date=_date_struct(status, "completionDateStruct"),
    )


class ClinicalTrialsService:
    def __init__(
        self,
        client: _HTTPClient | None = None,
        *,
        endpoint: str = CLINICAL_TRIALS_API_URL,
        timeout_seconds: float = settings.clinical_trials_timeout_seconds,
        max_results: int = settings.clinical_trials_max_results,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results < 1
            or max_results > 20
        ):
            raise ValueError("max_results must be between 1 and 20")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results

    def search(self, claim: str, max_results: int = 5) -> list[EvidenceItem]:
        claim = _validate_claim(claim)
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results < 1
            or max_results > self._max_results
        ):
            raise ValueError(
                f"max_results must be between 1 and {self._max_results}"
            )
        try:
            response = self._client.get(
                self._endpoint,
                params={"query.term": claim, "pageSize": max_results},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ClinicalTrialsHTTPError(
                "ClinicalTrials.gov request timed out"
            ) from error
        except httpx.HTTPError as error:
            raise ClinicalTrialsHTTPError(
                "ClinicalTrials.gov request failed"
            ) from error
        try:
            payload = response.json()
        except (ValueError, TypeError) as error:
            raise ClinicalTrialsResponseError(
                "ClinicalTrials.gov response was not valid JSON"
            ) from error
        if not isinstance(payload, dict) or "studies" not in payload:
            raise ClinicalTrialsResponseError(
                "ClinicalTrials.gov response is missing studies"
            )
        studies = payload["studies"]
        if not isinstance(studies, list):
            raise ClinicalTrialsResponseError(
                "ClinicalTrials.gov studies field was malformed"
            )
        return [
            item
            for study in studies[:max_results]
            if (item := _normalize_study(study)) is not None
        ]
