import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.verification import (
    EvidenceItem,
    EvidenceSource,
    Prediction,
    PredictionLabel,
    VerificationRequest,
)


client = TestClient(app)


def test_health_reports_api_without_claiming_readiness():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["api"] == "available"
    assert body["model"] == "not_implemented"
    assert body["evidence_sources"] == "not_implemented"


def test_request_schema_trims_valid_claim():
    request = VerificationRequest(claim="  A clinical claim.  ")
    assert request.claim == "A clinical claim."
    assert request.max_evidence_items == 5


@pytest.mark.parametrize("claim", ["", "   "])
def test_request_schema_rejects_empty_claim(claim):
    with pytest.raises(ValidationError):
        VerificationRequest(claim=claim)


def test_request_schema_rejects_claim_above_limit():
    with pytest.raises(ValidationError):
        VerificationRequest(claim="x" * 4001)


@pytest.mark.parametrize("value", [0, -1, 21])
def test_request_schema_rejects_invalid_evidence_limit(value):
    with pytest.raises(ValidationError):
        VerificationRequest(claim="A claim", max_evidence_items=value)


def test_prediction_schema_rejects_invalid_values():
    with pytest.raises(ValidationError):
        Prediction(label="unsupported")
    with pytest.raises(ValidationError):
        Prediction(label=PredictionLabel.EVIDENCE, confidence=1.1)


def test_evidence_item_accepts_valid_pubmed_example():
    item = EvidenceItem(
        source=EvidenceSource.PUBMED,
        title="A clinical study",
        abstract_or_excerpt="Study excerpt.",
        pmid="12345678",
        source_url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
    )
    assert item.source is EvidenceSource.PUBMED
    assert item.pmid == "12345678"


def test_importing_app_does_not_import_model_or_retrieval_modules():
    assert "experiments.biobert_baseline" not in sys.modules
    assert "transformers" not in sys.modules
    assert "metapub" not in sys.modules
    module = importlib.import_module("app.main")
    assert module.app is app
