# PubMed Evidence Retrieval Service

The reusable adapter is implemented in
`app/services/pubmed_service.py`. It uses the official NCBI E-utilities endpoints:

1. `ESearch` (`esearch.fcgi`) searches PubMed for the submitted claim.
2. `EFetch` (`efetch.fcgi`) retrieves article XML for the returned PMIDs.

The adapter normalizes results into the existing `EvidenceItem` schema with:

- `source: "PubMed"`
- Article title
- Abstract text when available
- Publication date when parseable
- PMID
- `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` URL

## Configuration

Optional environment variables:

- `NCBI_EMAIL`
- `NCBI_API_KEY`
- `CLINIFACT_PUBMED_TIMEOUT_SECONDS` (default `10`)
- `CLINIFACT_PUBMED_MAX_RESULTS` (default `10`, maximum `20`)

Credentials are never hard-coded, returned, or logged. The legacy data-preparation
scripts are not imported by this adapter.

## Error behavior

- Empty or overlong claims raise `ValueError`.
- Invalid result limits raise `ValueError`.
- Timeouts and HTTP failures raise `PubMedHTTPError`.
- Malformed JSON or XML raises `PubMedResponseError`.
- Empty search results return an empty list.
- Missing abstracts or publication dates remain `None`.

The adapter does not fabricate articles and does not infer that a retrieved article
supports or contradicts the submitted claim. Relevance and medical interpretation
remain responsibilities of a later orchestration layer.

## Tests

Run the focused tests from the repository root:

```powershell
python -m pytest .\tests\test_pubmed_service.py -q
```

Tests use mocked HTTP clients and do not contact PubMed.

## Future orchestration

A future verification service can call `PubMedService.search`, keep the returned
evidence separate from the BioBERT prediction, and pass selected article context
to the prediction service. This task intentionally adds no `/api/verify` route,
ClinicalTrials.gov adapter, or frontend.
