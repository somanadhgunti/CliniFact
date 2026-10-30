# ClinicalTrials.gov Evidence Retrieval Service

The reusable adapter is implemented in
`app/services/clinical_trials_service.py`. It uses the official ClinicalTrials.gov
API v2 studies endpoint:

```text
https://clinicaltrials.gov/api/v2/studies
```

## Search workflow

`ClinicalTrialsService.search`:

1. Validates and trims the submitted clinical claim.
2. Sends the claim as the API v2 `query.term` parameter.
3. Sends the requested limit as `pageSize`.
4. Normalizes returned study records into the existing `EvidenceItem` schema.

The adapter does not scrape the website and does not import the legacy local JSON
extraction scripts.

## Returned fields

Normalized records include, when available:

- Source: `ClinicalTrials.gov`
- Brief title, falling back to official title
- Brief summary
- Overall study status
- Start date
- Completion date
- NCT identifier
- Official study URL

Records without a usable NCT identifier or title are skipped rather than fabricated.
Missing optional fields remain `None`.

## Configuration

Environment variables:

- `CLINIFACT_CLINICAL_TRIALS_TIMEOUT_SECONDS` (default `10`)
- `CLINIFACT_CLINICAL_TRIALS_MAX_RESULTS` (default `10`, maximum `20`)

No API key is required by this adapter and no credentials are stored in source.

## Error behavior

- Empty or overlong claims raise `ValueError`.
- Invalid result limits raise `ValueError`.
- Timeouts and HTTP failures raise `ClinicalTrialsHTTPError`.
- Malformed JSON or API structures raise `ClinicalTrialsResponseError`.
- Empty result sets return an empty list.

Search presence is not evidence that a trial supports or contradicts a claim.
Relevance, study-quality assessment, and medical interpretation belong to the
future verification orchestration layer.

## Tests

Run the mocked tests from the repository root:

```powershell
python -m pytest .\tests\test_clinical_trials_service.py -q
```

No live ClinicalTrials.gov requests are made by the tests.

## Future orchestration

A future verification service can call this adapter alongside the PubMed adapter,
keep trial evidence separate from model predictions, and pass selected context to
the prediction service. This task intentionally adds no `/api/verify` route and no
frontend.
