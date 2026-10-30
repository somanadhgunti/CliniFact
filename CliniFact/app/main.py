"""FastAPI application foundation for CliniFact."""

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.clinical_trials_service import ClinicalTrialsService
from app.services.prediction_service import PredictionService
from app.services.pubmed_service import PubMedService
from app.services.verification_service import (
    EvidenceRetrievalError,
    PredictionExecutionError,
    VerificationService,
)


app = FastAPI(
    title=settings.application_name,
    version=settings.application_version,
    debug=settings.debug,
    description="Backend foundation for the CliniFact research application.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "application": settings.application_name,
        "message": "CliniFact API foundation is running",
    }


@app.get("/api/health", tags=["system"])
def health() -> dict[str, object]:
    return {
        "status": "running",
        "api": "available",
        "model": "not_implemented",
        "evidence_sources": "not_implemented",
    }


@lru_cache
def get_verification_service() -> VerificationService:
    return VerificationService(
        pubmed=PubMedService(),
        clinical_trials=ClinicalTrialsService(),
        prediction=PredictionService(),
    )


@app.post(
    "/api/verify",
    response_model=VerificationResponse,
    tags=["verification"],
)
async def verify(
    request: VerificationRequest,
    service: VerificationService = Depends(get_verification_service),
) -> VerificationResponse:
    try:
        return await run_in_threadpool(
            service.verify, request.claim, request.max_evidence_items
        )
    except EvidenceRetrievalError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except PredictionExecutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
