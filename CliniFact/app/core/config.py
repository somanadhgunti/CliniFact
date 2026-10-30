"""Environment-backed configuration for the CliniFact API foundation."""

from dataclasses import dataclass
import os
from pathlib import Path


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _parse_origins(value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
    if not origins:
        raise ValueError("CLINIFACT_ALLOWED_ORIGINS must contain an origin")
    if "*" in origins:
        raise ValueError("Wildcard CORS origins are not allowed")
    return origins


@dataclass(frozen=True)
class Settings:
    application_name: str = "CliniFact API"
    application_version: str = "0.1.0"
    debug: bool = False
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://localhost:4200",
    )
    request_length_limit: int = 4000
    model_checkpoint_dir: Path = Path(
        "experiments/results/biobert_grouped_v1_smoke/runs/"
        "run_20261025T134856Z_29052/seed_13/best_model"
    )
    model_revision: str = "924f12e0c3db7f156a765ad53fb6b11e7afedbc8"
    model_sequence_length: int = 512
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None
    pubmed_timeout_seconds: float = 10.0
    pubmed_max_results: int = 10
    clinical_trials_timeout_seconds: float = 10.0
    clinical_trials_max_results: int = 10

    @classmethod
    def from_environment(cls) -> "Settings":
        limit = int(os.getenv("CLINIFACT_REQUEST_LENGTH_LIMIT", "4000"))
        if limit < 1:
            raise ValueError("CLINIFACT_REQUEST_LENGTH_LIMIT must be positive")
        sequence_length = int(os.getenv("CLINIFACT_MODEL_SEQUENCE_LENGTH", "512"))
        if sequence_length < 1:
            raise ValueError("CLINIFACT_MODEL_SEQUENCE_LENGTH must be positive")
        timeout = float(os.getenv("CLINIFACT_PUBMED_TIMEOUT_SECONDS", "10"))
        if timeout <= 0:
            raise ValueError("CLINIFACT_PUBMED_TIMEOUT_SECONDS must be positive")
        max_results = int(os.getenv("CLINIFACT_PUBMED_MAX_RESULTS", "10"))
        if max_results < 1 or max_results > 20:
            raise ValueError("CLINIFACT_PUBMED_MAX_RESULTS must be between 1 and 20")
        clinical_trials_timeout = float(
            os.getenv("CLINIFACT_CLINICAL_TRIALS_TIMEOUT_SECONDS", "10")
        )
        if clinical_trials_timeout <= 0:
            raise ValueError(
                "CLINIFACT_CLINICAL_TRIALS_TIMEOUT_SECONDS must be positive"
            )
        clinical_trials_max_results = int(
            os.getenv("CLINIFACT_CLINICAL_TRIALS_MAX_RESULTS", "10")
        )
        if clinical_trials_max_results < 1 or clinical_trials_max_results > 20:
            raise ValueError(
                "CLINIFACT_CLINICAL_TRIALS_MAX_RESULTS must be between 1 and 20"
            )
        return cls(
            application_name=os.getenv("CLINIFACT_APPLICATION_NAME", cls.application_name),
            application_version=os.getenv(
                "CLINIFACT_APPLICATION_VERSION", cls.application_version
            ),
            debug=_parse_bool(os.getenv("CLINIFACT_DEBUG", "false"), "CLINIFACT_DEBUG"),
            allowed_origins=_parse_origins(
                os.getenv(
                    "CLINIFACT_ALLOWED_ORIGINS",
                    "http://localhost:3000,http://localhost:4200",
                )
            ),
            request_length_limit=limit,
            model_checkpoint_dir=Path(
                os.getenv(
                    "CLINIFACT_MODEL_CHECKPOINT_DIR",
                    str(cls.model_checkpoint_dir),
                )
            ),
            model_revision=os.getenv(
                "CLINIFACT_MODEL_REVISION", cls.model_revision
            ),
            model_sequence_length=sequence_length,
            ncbi_api_key=os.getenv("NCBI_API_KEY") or None,
            ncbi_email=os.getenv("NCBI_EMAIL") or None,
            pubmed_timeout_seconds=timeout,
            pubmed_max_results=max_results,
            clinical_trials_timeout_seconds=clinical_trials_timeout,
            clinical_trials_max_results=clinical_trials_max_results,
        )


settings = Settings.from_environment()
