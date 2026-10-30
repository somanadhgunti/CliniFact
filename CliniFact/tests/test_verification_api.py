from fastapi.testclient import TestClient

from app.main import app, get_verification_service
from app.schemas.verification import EvidenceItem, EvidenceSource
from app.services.prediction_service import PredictionResult, PredictionServiceError
from app.services.clinical_trials_service import ClinicalTrialsHTTPError
from app.services.pubmed_service import PubMedHTTPError
from app.services.verification_service import VerificationService


class FakeRetriever:
    def __init__(self, items=None, error=None):
        self.items = items or []
        self.error = error
        self.calls = []

    def search(self, claim, max_results):
        self.calls.append((claim, max_results))
        if self.error:
            raise self.error
        return self.items


class FakePrediction:
    def __init__(self, result=None, error=None):
        self.result = result or PredictionResult(
            label_id=1,
            label="evidence",
            probabilities={"inconclusive": 0.1, "evidence": 0.8, "NEI": 0.1},
            predicted_probability=0.8,
        )
        self.error = error
        self.calls = []

    def predict(self, claim, context):
        self.calls.append((claim, context))
        if self.error:
            raise self.error
        return self.result


def item(source, title, *, pmid=None, nct_id=None, excerpt=None):
    return EvidenceItem(
        source=source,
        title=title,
        pmid=pmid,
        nct_id=nct_id,
        abstract_or_excerpt=excerpt,
        source_url="https://example.test",
    )


def override(pubmed, trials, prediction):
    service = VerificationService(pubmed, trials, prediction)
    app.dependency_overrides[get_verification_service] = lambda: service
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_success_combines_deduplicates_limits_and_builds_context():
    pubmed = FakeRetriever(
        [item(EvidenceSource.PUBMED, "Article", pmid="1", excerpt="Abstract")]
    )
    trials = FakeRetriever(
        [
            item(EvidenceSource.CLINICALTRIALS_GOV, "Trial", nct_id="NCT1"),
            item(EvidenceSource.PUBMED, "Duplicate", pmid="1"),
        ]
    )
    prediction = FakePrediction()
    response = override(pubmed, trials, prediction).post(
        "/api/verify",
        json={"claim": "A biomedical claim", "max_evidence_items": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["evidence"]) == 2
    assert body["prediction"]["label_id"] == 1
    assert body["prediction"]["probabilities"]["evidence"] == 0.8
    assert "PubMed: Article" in prediction.calls[0][1]
    assert "ClinicalTrials.gov: Trial" in prediction.calls[0][1]


def test_one_source_failure_preserves_success_and_warns():
    trials = FakeRetriever(
        [item(EvidenceSource.CLINICALTRIALS_GOV, "Trial", nct_id="NCT1")]
    )
    response = override(FakeRetriever(error=PubMedHTTPError("offline")), trials, FakePrediction()).post(
        "/api/verify", json={"claim": "claim"}
    )
    assert response.status_code == 200
    assert len(response.json()["evidence"]) == 1
    assert "PubMed evidence retrieval failed" in response.json()["warnings"][0]


def test_empty_sources_return_inconclusive_without_prediction():
    prediction = FakePrediction()
    response = override(FakeRetriever(), FakeRetriever(), prediction).post(
        "/api/verify", json={"claim": "claim"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "inconclusive"
    assert response.json()["prediction"] is None
    assert prediction.calls == []


def test_both_sources_fail_returns_controlled_error():
    response = override(
        FakeRetriever(error=PubMedHTTPError("pubmed down")),
        FakeRetriever(error=ClinicalTrialsHTTPError("trials down")),
        FakePrediction(),
    ).post("/api/verify", json={"claim": "claim"})
    assert response.status_code == 503
    assert "Both evidence sources failed" in response.json()["detail"]


def test_prediction_failure_returns_controlled_error():
    response = override(
        FakeRetriever([item(EvidenceSource.PUBMED, "Article", pmid="1")]),
        FakeRetriever(),
        FakePrediction(error=PredictionServiceError("checkpoint unavailable")),
    ).post("/api/verify", json={"claim": "claim"})
    assert response.status_code == 503
    assert "Prediction service failed" in response.json()["detail"]


def test_invalid_claim_is_rejected_and_health_remains_available():
    client = TestClient(app)
    response = client.post("/api/verify", json={"claim": "  "})
    assert response.status_code == 422
    assert client.get("/api/health").status_code == 200
