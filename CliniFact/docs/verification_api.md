# Verification API

The verification endpoint coordinates the existing retrieval adapters and lazy
BioBERT prediction service:

```text
POST /api/verify
```

## Request

```json
{
  "claim": "Aspirin reduces the risk of recurrent cardiovascular events.",
  "max_evidence_items": 5
}
```

`claim` is trimmed, required, and limited by
`CLINIFACT_REQUEST_LENGTH_LIMIT`. `max_evidence_items` defaults to 5 and
controls the final combined evidence list.

## Workflow

The endpoint:

1. Searches PubMed.
2. Searches ClinicalTrials.gov API v2.
3. Deduplicates evidence by PMID, NCT identifier, or source/title.
4. Applies the requested combined evidence limit.
5. Builds model context from each source and title plus its available abstract or
   summary.
6. Calls the existing lazy `PredictionService`.
7. Returns retrieved evidence separately from the model prediction.

The synchronous adapters run in FastAPI's threadpool so network and local model
work do not block the asynchronous request handler.

## Response

Illustrative response only; these values are not an actual model result:

```json
{
  "claim": "Aspirin reduces the risk of recurrent cardiovascular events.",
  "prediction": {
    "label": "inconclusive",
    "label_id": 0,
    "confidence": 0.41,
    "model_score": 0.41,
    "probabilities": {
      "inconclusive": 0.41,
      "evidence": 0.35,
      "NEI": 0.24
    }
  },
  "evidence": [
    {
      "source": "PubMed",
      "title": "Illustrative article title",
      "abstract_or_excerpt": "Illustrative abstract excerpt.",
      "publication_date": "2024-01-01",
      "pmid": "12345678",
      "nct_id": null,
      "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    }
  ],
  "status": "completed",
  "warnings": [],
  "limitations": [
    "The prediction is a model output, not calibrated medical confidence or proof."
  ]
}
```

The labels retain the research mapping:

- `0 = inconclusive`
- `1 = evidence`
- `2 = NEI`

`evidence` is a model class name, not a claim that the medical statement is
true. Scores are model scores and are not calibrated medical confidence.

## Evidence and errors

Evidence source identity, PMIDs, NCT identifiers, and official URLs are
preserved. Missing abstracts or summaries are returned as absent metadata.
Search relevance does not establish support or contradiction.

If one source fails, results from the other source are retained and a
source-specific warning is returned. If both sources fail, the endpoint returns
HTTP 503 and does not produce a prediction. If both sources return no records,
the endpoint returns `inconclusive` status with no prediction and an explicit
insufficient-evidence warning. Prediction-service failures return HTTP 503.
Invalid request bodies return standard FastAPI HTTP 422 responses.

The current local BioBERT smoke checkpoint is experimental and is not a
validated final research model. It is loaded only when a verification request
has usable evidence and prediction is explicitly invoked. Importing the API or
calling `/api/health` does not load it.

## Running

From the repository root:

```powershell
python -m uvicorn app.main:app --reload
```

The endpoint is available at `http://127.0.0.1:8000/api/verify`; OpenAPI
documentation is available at `http://127.0.0.1:8000/docs`.

Run the mocked orchestration tests with:

```powershell
python -m pytest .\tests\test_verification_api.py -q
```

Tests use injected fake services and do not call live APIs or load model
weights.
