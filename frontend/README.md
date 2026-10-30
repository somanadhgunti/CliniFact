# CliniFact Angular frontend

This is the independent Angular frontend for CliniFact. It is intentionally a
sibling project of the Python backend:

```text
4.2 project stuff/
├── CliniFact/   # FastAPI and research project
└── frontend/    # Angular application
```

## Versions and prerequisites

- Angular CLI: 20.3.33
- Angular framework: 20.3.x
- Node.js: 24.19.0 (local development environment)
- npm: 11.17.0

Install a compatible Node.js release, npm, and Angular CLI before working on
the frontend.

## Install and run

From this directory:

```powershell
npm install
npm start
```

Open `http://localhost:4200/`.

## Build and tests

```powershell
npm run build
npx tsc --noEmit -p tsconfig.app.json
npm test -- --watch=false --browsers=ChromeHeadless
```

## Routing

- `/` — Home foundation
- `/verification` — Claim submission and FastAPI verification workflow
- `/about` — About placeholder

Routes are standalone and lazy-loaded from `src/app/app.routes.ts`.

## API configuration

Typed backend contracts are in
`src/app/models/verification.models.ts`. The injectable API foundation is
`src/app/core/services/clinifact-api.service.ts`.

Development uses:

```text
http://localhost:8000
```

Edit `src/environments/environment.ts` to configure the development API URL.
Production builds use `src/environments/environment.prod.ts` through the
replacement configured in `angular.json`. Do not place API keys or backend
secrets in environment files.

The service exposes typed endpoints for:

- `GET /api/health`
- `POST /api/verify`

The verification page submits `claim` and `max_evidence_items` to
`POST /api/verify`. The request uses the backend constraints: claims up to
4,000 characters and 1–20 evidence results, with 5 as the default. The page
shows loading, controlled HTTP/network errors, and a completion indicator.

After a successful response, the same page renders a results dashboard using
the returned response only. It displays the verification status, the model's
research label and optional score/probabilities, plus separate PubMed and
ClinicalTrials.gov evidence groups. PMIDs, NCT identifiers, dates, summaries,
and official source links are shown only when returned by the API. Empty
evidence and missing prediction values have explicit states, and all returned
warnings and limitations are displayed.

The research labels retain their backend semantics: `0 = inconclusive`,
`1 = evidence`, and `2 = NEI`. The `evidence` label is a model class name, not
a finding that a medical claim is true. Scores and probabilities are
experimental model outputs, not calibrated medical confidence. Retrieved
articles are not automatically evidence supporting or contradicting a claim.
Detailed result state can be cleared with **Start a new verification**.

Start the backend separately from the sibling backend directory:

```powershell
cd ..\CliniFact
python -m uvicorn app.main:app --reload --port 8000
```

Then start Angular from this directory with `npm start`. The development API
base URL is configured in `src/environments/environment.ts`; production uses
`src/environments/environment.prod.ts`. No API keys or backend secrets belong
in these files.

Evidence retrieval remains inside FastAPI. The current backend may return
controlled `422` validation, `503` service, or network errors; the frontend
does not expose server stack traces. Detailed evidence and prediction
visualizations are intentionally deferred to the next frontend phase.

## Planned module sequence

1. Claim-entry and verification-state experience.
2. API integration with explicit loading and error states.
3. Evidence cards and source links.
4. Prediction and limitations presentation.
5. Accessibility, responsive refinement, and frontend tests.
