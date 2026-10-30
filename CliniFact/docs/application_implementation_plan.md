# CliniFact Application Implementation Plan

## Audit scope and evidence

This document is based on a read-only inspection of the repository as it existed on
2026-10-25. No model inference, training, evaluation, download, dependency
installation, or source-data modification was performed.

Inspected areas include:

- `README.md`
- `requirements-biobert.txt`
- `experiments/biobert_baseline.py`
- `experiments/results/biobert_grouped_v1/config.json`
- The saved smoke-run metadata, checkpoint manifest, metrics, predictions, and model files
- `scripts/*.py`
- `tests/test_biobert_grouped_config.py`
- `data/processed/grouped_splits_v1/*`
- Existing experiment output directories

## 1. Existing project structure

The repository is currently a research/data-processing project rather than a web
application:

```text
CliniFact/
├── README.md
├── requirements-biobert.txt
├── CliniFact_Research_Report.pdf
├── assets/logo.png
├── data/
│   └── processed/
│       ├── grouped_splits_v1/
│       ├── primary_outcome_publication_dataset/
│       └── primary_outcome_publication_instruction/
├── experiments/
│   ├── biobert_baseline.py
│   └── results/
│       ├── biobert_grouped_v1/
│       ├── biobert_grouped_v1_smoke/
│       ├── biobert_baseline/
│       └── phase1_biobert_20261015/
├── scripts/
│   ├── dataset extraction and labeling scripts
│   ├── PubMed enrichment scripts
│   ├── LLM training/inference scripts
│   └── grouped split and conflict-analysis scripts
└── tests/
    └── test_biobert_grouped_config.py
```

### Existing entry points

The confirmed executable research entry points are:

- `experiments/biobert_baseline.py`: configuration loading, dataset validation,
  BioBERT training, validation checkpoint selection, and final test evaluation.
- `scripts/create_grouped_splits.py`: reproducible leakage-safe split generation.
- `scripts/analyze_label_conflicts.py`: conflict diagnostic generation.
- Several legacy pipeline scripts under `scripts/` that read/write intermediate
  JSON, JSONL, and CSV files.
- `scripts/llm_finetune.py` and `scripts/llm_inference.py`: separate LLM workflow.

There is no discovered FastAPI, Flask, Django, Streamlit, Gradio, React, static
HTML, JavaScript application, `uvicorn` entry point, or API route.

## 2. Existing ML capabilities

### Current model-loading path

`experiments/biobert_baseline.py` contains:

- `load_tokenizer(model_name, revision)`
- `load_model(model_name, revision)`
- `CliniFactDataset`
- `evaluate(model, dataloader, device)`
- Dataset and configuration validation helpers
- Training/checkpoint publication logic

The configured model is:

```text
dmis-lab/biobert-base-cased-v1.1
revision: 924f12e0c3db7f156a765ad53fb6b11e7afedbc8
```

The model is loaded as `AutoModelForSequenceClassification` with three labels.
The classification head was newly initialized for this task in the smoke run; the
base BioBERT encoder is pretrained.

### Model input contract

The current dataset loader expects these columns:

- `claim`
- `article_title`
- `article_abstract`
- `label`

For each record, the training loader sends the claim as the first text and the
article title plus abstract as the paired text. It tokenizes to a maximum sequence
length of 512 and uses attention masks.

An application prediction service should expose a separate inference input contract:

```json
{
  "claim": "string",
  "article_title": "optional string",
  "article_abstract": "optional string"
}
```

If the user supplies only a claim, the application must not pretend that a missing
article is evidence. It should either retrieve evidence first and classify a
selected evidence context, or return an explicit insufficient-information state.
That policy must be decided before implementation.

### Label mapping

The repository consistently defines:

```text
0 = inconclusive
1 = evidence
2 = NEI (No Information)
```

The application should return both the numeric identifier and human-readable label,
but the UI should display the human-readable label and explanatory text.

### Reusable checkpoint status

The smoke checkpoint exists at:

```text
experiments/results/biobert_grouped_v1_smoke/
runs/run_20261025T134856Z_29052/seed_13/best_model/
```

It contains model weights, tokenizer files, model configuration, and
`checkpoint_manifest.json`. The manifest records the required immutable revision
and `status: complete`; the checkpoint can be validated and reloaded.

However, it is **not a production-ready or final research model**:

- It was trained for one seed and one epoch only.
- Its classification head was newly initialized before training.
- It is a smoke-test artifact intended to verify the pipeline.
- Its recorded test metrics are smoke-run observations, not final research results.

The application must therefore treat this checkpoint as an explicitly configured
development model. Production or public-facing use should be blocked or clearly
marked until a separately approved multi-seed research baseline is completed.

### Inference without training

The checkpoint can technically be loaded independently of the training loop, but
there is currently no reusable prediction function or API wrapper. The first
application implementation should extract a narrowly scoped inference service from
the existing loading/tokenization conventions without importing or invoking the
training `main()` function.

Required runtime model files include:

- `model.safetensors` or equivalent model weights
- `config.json`
- `tokenizer.json`
- `tokenizer_config.json`
- `vocab.txt`
- Special-token metadata

The service should validate the checkpoint manifest and label mapping at startup.

## 3. Existing evidence-retrieval capabilities

### PubMed: partially implemented, offline pipeline only

PubMed access exists in dataset-generation scripts:

- `scripts/g_create_dataset_with_all_inputs_part2.py` uses `metapub.PubMedFetcher`
  to retrieve article titles and abstracts from PMIDs.
- `scripts/f_create_dataset_with_all_inputs.py` imports `PubMedFetcher`.
- `scripts/a_extract_relevancy_label.py` uses Biopython `Entrez` while processing
  local ClinicalTrials.gov records and references.

These scripts are batch data-preparation code. They are not application API clients:

- No request/response schema for user queries exists.
- No source URL builder is exposed as a reusable function.
- No runtime timeout, retry, rate-limit, cache, or user-facing error contract exists.
- Some scripts use hard-coded filesystem paths.
- The scripts are not safe to import into a web process because they contain
  pipeline execution assumptions and side effects.

### ClinicalTrials.gov: local extraction, no runtime integration

`scripts/b_extract_clinical_trials.py` parses local ClinicalTrials.gov JSON files
from a raw data directory and derives outcome/arm-group information. It also uses
BioBERT embeddings to map outcome groups to arm groups.

This is an offline extraction step, not a ClinicalTrials.gov application client:

- No HTTP API route or live ClinicalTrials.gov query function was found.
- No runtime source-link builder was found.
- No evidence-card schema was found.
- The existing processed rows contain `nctId` and trial-related fields that can
  support links, but the application must distinguish stored dataset context from
  freshly retrieved evidence.

### Retrieval conclusion

Evidence retrieval is **partially implemented for dataset construction and absent
as a user-facing runtime feature**. The application should add isolated PubMed and
ClinicalTrials.gov adapters rather than importing the batch scripts directly.

## 4. Recommended minimal architecture

Use a single Python service with a small static frontend:

```text
Browser
  └── static HTML/CSS/JavaScript
        └── FastAPI JSON API
              ├── prediction service
              │     └── validated local BioBERT checkpoint
              ├── PubMed adapter
              ├── ClinicalTrials.gov adapter
              └── response schemas and error handling
```

### Recommended request flow

1. Browser submits a claim to `POST /api/verify`.
2. API validates input length and content.
3. Retrieval adapters search supported sources when identifiers or query terms
   permit retrieval.
4. The service normalizes retrieved records into evidence cards with source,
   identifier, title, summary text, and URL.
5. The model classifies a clearly defined text context. The response identifies
   whether the prediction used user-provided text, retrieved evidence, or both.
6. API returns prediction and evidence as separate fields.
7. Frontend renders prediction, uncertainty/inconclusive messaging, evidence cards,
   source links, empty-result states, and the research disclaimer.

The model prediction must never be presented as if it were a PubMed or
ClinicalTrials.gov finding. Retrieval evidence and model output should remain
separate in the response schema and UI.

## 5. Proposed frontend and backend structure

This is a proposed structure; these files do not currently exist.

```text
app/
├── __init__.py
├── main.py                    # FastAPI application entry point
├── config.py                  # environment-based paths and API settings
├── schemas.py                 # request, prediction, evidence, and error models
├── api/
│   ├── __init__.py
│   └── routes.py              # /health and /api/verify routes
├── services/
│   ├── __init__.py
│   ├── prediction_service.py  # checkpoint validation, tokenization, inference
│   ├── evidence_service.py    # orchestration and source separation
│   ├── pubmed_client.py       # PubMed query/fetch adapter
│   └── clinicaltrials_client.py
├── model/
│   ├── __init__.py
│   └── checkpoint.py          # local model loading and label contract
└── templates/
    └── index.html             # optional server-served shell
static/
├── app.js
└── styles.css
tests/
├── test_api_contracts.py
├── test_prediction_service.py
├── test_evidence_adapters.py
└── test_frontend_contracts.py
```

The service should not import `experiments.biobert_baseline.main`. It should reuse
the established constants and loading behavior through a small inference-focused
module or a carefully extracted shared helper, while leaving the training script
and research artifacts unchanged.

## 6. Proposed initial UI

The first page should contain only:

- CliniFact title and one-sentence description.
- Claim text area.
- Optional evidence/article text fields if the chosen API contract needs them.
- `Verify Claim` button.
- Loading indicator with a clear non-blocking status.
- Prediction result:
  - Inconclusive
  - Evidence
  - NEI / No Information
- Short explanation that the label is a model prediction.
- Evidence cards, each containing:
  - Source (`PubMed` or `ClinicalTrials.gov`)
  - Article/trial title
  - PMID or NCT identifier
  - Brief retrieved/supporting summary
  - Original source link when available
- Empty-result state when no supported evidence is found.
- Error state for retrieval failure, invalid input, or model unavailability.
- Inconclusive state that does not imply the claim is false.
- Disclaimer:
  “This research tool does not replace professional medical judgment.”

The UI should not add authentication, payments, dashboards, saved histories, or
complex visualization in the first version.

## 7. Required dependencies and setup steps

### Existing dependencies

`requirements-biobert.txt` currently covers:

- PyTorch
- Transformers
- NumPy
- pandas
- scikit-learn
- pytest

The repository also imports packages from scripts that are not declared in that
manifest, including:

- Biopython
- `metapub`
- `nltk`
- `jsonlines`
- `python-dateutil`

The actual installed state should be audited before reusing those scripts. The
application should not depend on undeclared legacy pipeline imports.

### Dependencies needed for the proposed application

The implementation stage will likely need:

- FastAPI
- Uvicorn
- Pydantic (normally provided by FastAPI)
- An HTTP client such as `httpx`
- Optional caching/storage dependency if retrieval caching is introduced

These should be added only during the implementation task after confirming the
environment and selecting supported versions. No packages were installed during
this audit.

### Setup steps for a future implementation

1. Establish a project application environment using the approved Python 3.12
   interpreter.
2. Add an application dependency manifest separately from research dependencies,
   unless the project owner chooses a unified manifest.
3. Configure the local checkpoint path and immutable model revision through
   environment variables or application configuration.
4. Add startup validation for checkpoint files, manifest status, label mapping, and
   model revision.
5. Add API and adapter tests with mocked external responses.
6. Run the service locally with Uvicorn only after the above tests pass.

## 8. Incremental implementation plan

### Stage 1 — Define contracts and configuration

Create request/response schemas for:

- Claim submission
- Model prediction
- Evidence card
- Retrieval error
- Inconclusive/insufficient-information result

Tests:

- Required and optional field validation
- Maximum input length
- Stable label mapping
- Separation of prediction and evidence fields

### Stage 2 — Add checkpoint-backed inference

Implement a prediction service that:

- Loads the existing smoke checkpoint only when explicitly configured.
- Validates `checkpoint_manifest.json`.
- Verifies the three-label mapping and revision.
- Tokenizes without invoking the training loop.
- Returns label ID, label name, and prediction metadata.

Tests:

- Mocked model/tokenizer loading
- Deterministic label mapping
- Missing checkpoint and invalid manifest errors
- No training-side effects

The smoke checkpoint should be marked development-only in configuration and UI.

### Stage 3 — Add PubMed adapter

Implement a dedicated runtime adapter with:

- Query and PMID fetch operations
- Timeouts and bounded result counts
- Normalized title, abstract/summary, PMID, and URL
- Explicit unavailable/error states

Tests:

- Mock successful PubMed response
- Empty result
- Timeout/rate-limit response
- Malformed response
- URL construction

### Stage 4 — Add ClinicalTrials.gov adapter

Implement a separate adapter for NCT identifiers or supported search terms.

Tests:

- NCT URL construction
- Normalized trial title and identifier
- Empty result and service error
- No fabricated evidence when the API is unavailable

### Stage 5 — Compose `/api/verify`

Compose validation, retrieval, and model services while preserving source
boundaries in the response.

Tests:

- Claim-only request
- Claim plus retrieved evidence
- No evidence found
- Model unavailable
- Retrieval failure with prediction handling defined explicitly

### Stage 6 — Add the simple frontend

Implement static HTML/CSS/JavaScript with loading, success, error, inconclusive,
and empty-result states.

Tests:

- Request payload shape
- Loading-state transition
- Prediction label rendering
- Evidence-card rendering
- Source link rendering
- Error and disclaimer rendering

### Stage 7 — Operational hardening

Add bounded timeouts, structured logs, request-size limits, health checks, and
safe configuration handling. Do not log raw clinical claims or retrieved abstracts
by default.

Tests:

- `/health`
- Configuration errors
- Timeout behavior
- Sensitive-input logging policy
- Concurrent request behavior

## 9. Risks and blockers

### Model and research risks

- The available checkpoint is a one-seed, one-epoch smoke model, not a completed
  research baseline.
- Its classification head was newly initialized before smoke training.
- The low smoke-run inconclusive F1 is not sufficient to establish application
  quality.
- Training-time dataset input expects a claim plus article title/abstract pair;
  claim-only application behavior requires an explicit product decision.
- Loading a large BioBERT model per request would be slow and memory-expensive;
  the service must load once at startup and reuse the model.

### Evidence-service risks

- PubMed and ClinicalTrials.gov availability, rate limits, API policies, and
  response formats must be handled explicitly.
- External evidence may be incomplete, delayed, or unavailable.
- Retrieved evidence must not be represented as proof merely because it was found.
- Search relevance and evidence-to-claim matching are not implemented in the
  current repository.
- No existing runtime evidence summarizer or claim-evidence matching contract was
  found.

### Security, privacy, and integrity risks

- Clinical claims entered by users may contain sensitive information. Avoid
  persistent storage and avoid logging raw text by default.
- `scripts/g_create_dataset_with_all_inputs_part2.py` contains a hard-coded NCBI API
  key in source. It must not be reused or exposed by the web application; any
  credential handling should use environment variables and the exposed credential
  should be rotated outside this implementation.
- Existing scripts use hard-coded absolute paths and batch side effects, making them
  unsuitable as direct web request handlers.
- The original row-level dataset and grouped dataset must remain separate; runtime
  application configuration should point only to explicitly approved artifacts.

### Testing and dependency risks

- Current tests focus on grouped BioBERT configuration and safety, not HTTP,
  inference, frontend, or retrieval behavior.
- Existing scripts import dependencies not declared in
  `requirements-biobert.txt`.
- No frontend build/test tooling exists.
- External API tests must use mocks and must not depend on live services.

## 10. Reuse versus new creation

### Reuse

- Label mapping: `0/1/2` contract from `experiments/biobert_baseline.py`.
- Immutable model revision and checkpoint manifest validation rules.
- Smoke checkpoint only as a development/integration artifact, not as a final
  research model.
- Grouped dataset and leakage reports as preserved research artifacts.
- Existing PubMed and ClinicalTrials.gov field knowledge as reference for adapter
  normalization, not as request-handler code.
- Existing logo asset if desired for the simple page.
- Existing configuration and data-safety tests as regression coverage.

### Newly create

- FastAPI application entry point.
- Prediction-only service boundary.
- Pydantic request/response schemas.
- PubMed runtime adapter.
- ClinicalTrials.gov runtime adapter.
- Evidence orchestration and source-link builders.
- Static HTML/CSS/JavaScript frontend.
- API, inference, adapter, and frontend tests.
- Application-specific dependency/configuration documentation.

### Do not reuse directly

- `experiments.biobert_baseline.main` as a web handler.
- Batch dataset-generation scripts as request handlers.
- Hard-coded absolute paths.
- Hard-coded credentials.
- LLM fine-tuning or inference scripts for the BioBERT web prediction path.
- Smoke metrics as production-quality performance evidence.

## Recommended next decision

Before implementation, confirm the prediction context policy:

1. **Claim plus user-provided article context**, or
2. **Claim followed by retrieval, then classification of selected retrieved
   context**, or
3. **Claim-only classification with an explicit insufficient-context policy**.

Option 2 best matches the intended evidence-aware experience but requires a
retrieval relevance contract that does not currently exist. The smallest safe first
release can implement option 1 and clearly show when no evidence was supplied,
then add live retrieval behind the same response schema.

## Audit conclusion

CliniFact currently has a functional research data and BioBERT training pipeline,
but no existing web application, reusable inference API, or runtime evidence
retrieval integration. The smallest maintainable path is a FastAPI backend with a
prediction-only model service, isolated PubMed and ClinicalTrials.gov adapters, and
a static HTML/CSS/JavaScript frontend. The grouped data and smoke artifacts can be
preserved unchanged while application code is added around them.
