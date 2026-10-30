# CliniFact Backend Foundation

The repository now contains a FastAPI application skeleton. This task does not
implement BioBERT inference, PubMed retrieval, ClinicalTrials.gov retrieval, a
verification endpoint, or a frontend.

## Install application dependencies

From the repository root, using the approved Python environment:

```powershell
python -m pip install -r requirements-app.txt
```

The existing research/ML dependencies remain in
[requirements-biobert.txt](../requirements-biobert.txt). No packages were
installed as part of creating this foundation.

## Start the development server

From the repository root:

```powershell
python -m uvicorn app.main:app --reload
```

The API listens by default on `http://127.0.0.1:8000`.

## Development endpoints

- Health: `http://127.0.0.1:8000/api/health`
- OpenAPI UI: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

The health endpoint reports that the API process is running, but explicitly marks
model and evidence-source readiness as `not_implemented`.

## Configuration

Optional environment variables:

- `CLINIFACT_APPLICATION_NAME`
- `CLINIFACT_APPLICATION_VERSION`
- `CLINIFACT_DEBUG`
- `CLINIFACT_ALLOWED_ORIGINS` (comma-separated explicit origins)
- `CLINIFACT_REQUEST_LENGTH_LIMIT`

No API keys or other secrets are read by this foundation. Do not copy credentials
from legacy research scripts.
