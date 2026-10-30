# BioBERT Prediction Service

The reusable prediction service is implemented in
`app/services/prediction_service.py`. It is intentionally separate from the
training script and is not imported by `app.main`, so importing or starting the
FastAPI foundation does not load model weights.

## Initialization

```python
from app.services.prediction_service import PredictionService

service = PredictionService()
result = service.predict(
    claim="The intervention improved the primary outcome.",
    evidence_context="Article title. Article abstract or selected evidence excerpt.",
)
```

Model and tokenizer loading occurs on the first `predict` call. Loading is local
only and requires a complete checkpoint manifest.

## Configuration

The default development checkpoint is the existing smoke checkpoint. It is
configured through:

- `CLINIFACT_MODEL_CHECKPOINT_DIR`
- `CLINIFACT_MODEL_REVISION`
- `CLINIFACT_MODEL_SEQUENCE_LENGTH`

The default revision is
`924f12e0c3db7f156a765ad53fb6b11e7afedbc8`. The service rejects other revisions,
incomplete manifests, missing weights, and incompatible label metadata. It never
downloads a replacement checkpoint.

## Input contract and limitation

The training pipeline encodes the claim as the first text and combines article
title/abstract as the paired text. The prediction service accepts the same
two-part representation as `claim` and `evidence_context`, truncating the pair to
512 tokens by default.

The current smoke checkpoint is an experimental one-seed, one-epoch model. Its
classification head was trained for a smoke run, but it is not a validated final
research baseline or a medical decision system. The service does not establish
that a claim is medically true.

## Output semantics

`PredictionResult` returns:

- `label_id`
- `label`
- Class softmax scores for `inconclusive`, `evidence`, and `NEI`
- The predicted class's softmax score

These scores are model scores, not calibrated medical confidence, proof, or
clinical advice.

## Later API integration

A future verification route can initialize one service instance during an
application-controlled lifecycle, retrieve evidence separately, and pass a
selected evidence context to `predict`. Retrieved evidence and the model result
must remain separate response fields.
