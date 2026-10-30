"""Lazy, local-checkpoint BioBERT prediction service."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings


LABEL_NAMES = ("inconclusive", "evidence", "NEI")
LABEL_MAPPING = {index: name for index, name in enumerate(LABEL_NAMES)}
AUTHORIZED_REVISION = "924f12e0c3db7f156a765ad53fb6b11e7afedbc8"


class PredictionServiceError(RuntimeError):
    """Base error for prediction-service configuration or inference failures."""


class InvalidCheckpointError(PredictionServiceError):
    """Raised when a checkpoint cannot be trusted for application inference."""


class InvalidPredictionInput(ValueError):
    """Raised when claim/evidence input is empty or invalid."""


@dataclass(frozen=True)
class PredictionResult:
    label_id: int
    label: str
    probabilities: dict[str, float]
    predicted_probability: float


def build_model_input(
    tokenizer: Any,
    claim: str,
    evidence_context: str,
    max_length: int = settings.model_sequence_length,
) -> dict[str, Any]:
    claim = claim.strip() if isinstance(claim, str) else ""
    evidence_context = (
        evidence_context.strip() if isinstance(evidence_context, str) else ""
    )
    if not claim:
        raise InvalidPredictionInput("claim must not be empty")
    if not evidence_context:
        raise InvalidPredictionInput("evidence_context must not be empty")
    if max_length < 1:
        raise InvalidPredictionInput("max_length must be positive")
    return tokenizer.encode_plus(
        text=claim,
        text_pair=evidence_context,
        add_special_tokens=True,
        max_length=max_length,
        padding=False,
        truncation=True,
        return_tensors="pt",
    )


def _expected_label_mapping() -> dict[str, str]:
    return {str(index): name for index, name in enumerate(LABEL_NAMES)}


def validate_checkpoint_metadata(
    checkpoint_dir: Path,
    expected_revision: str = AUTHORIZED_REVISION,
) -> dict[str, Any]:
    checkpoint_dir = checkpoint_dir.expanduser().resolve(strict=False)
    manifest_path = checkpoint_dir / "checkpoint_manifest.json"
    if not manifest_path.is_file():
        raise InvalidCheckpointError(
            f"Checkpoint manifest is missing: {manifest_path}"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidCheckpointError(
            f"Checkpoint manifest is unreadable: {manifest_path}"
        ) from error
    if manifest.get("status") != "complete":
        raise InvalidCheckpointError("Checkpoint manifest is not complete")
    if manifest.get("required_revision") != expected_revision:
        raise InvalidCheckpointError(
            "Checkpoint revision does not match the authorized revision"
        )
    if not (checkpoint_dir / "config.json").is_file():
        raise InvalidCheckpointError("Checkpoint config.json is missing")
    if not any(
        (checkpoint_dir / filename).is_file()
        for filename in ("model.safetensors", "pytorch_model.bin")
    ):
        raise InvalidCheckpointError("Checkpoint model weights are missing")
    return manifest


@dataclass
class PredictionService:
    checkpoint_dir: Path = settings.model_checkpoint_dir
    revision: str = settings.model_revision
    max_length: int = settings.model_sequence_length
    device_name: str | None = None
    tokenizer_loader: Callable[..., Any] | None = None
    model_loader: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        self.checkpoint_dir = Path(self.checkpoint_dir)
        self._tokenizer = None
        self._model = None
        self._torch = None
        self._device = None

    def _load_components(self) -> None:
        if self._model is not None:
            return
        if self.revision != AUTHORIZED_REVISION:
            raise InvalidCheckpointError(
                "Configured model revision is not the authorized BioBERT revision"
            )
        validate_checkpoint_metadata(self.checkpoint_dir, self.revision)
        if self.tokenizer_loader is None or self.model_loader is None:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
            except ImportError as error:
                raise PredictionServiceError(
                    "Prediction requires torch and transformers"
                ) from error
            self._torch = torch
            self.tokenizer_loader = AutoTokenizer.from_pretrained
            self.model_loader = AutoModelForSequenceClassification.from_pretrained
        else:
            import torch

            self._torch = torch
        self._tokenizer = self.tokenizer_loader(
            self.checkpoint_dir, local_files_only=True
        )
        self._model = self.model_loader(
            self.checkpoint_dir,
            local_files_only=True,
            num_labels=len(LABEL_NAMES),
            label2id={name: index for index, name in LABEL_MAPPING.items()},
            id2label=LABEL_MAPPING,
        )
        config = self._model.config
        if getattr(config, "num_labels", None) != len(LABEL_NAMES):
            raise InvalidCheckpointError("Checkpoint must expose exactly three labels")
        label2id = {
            str(key): value for key, value in getattr(config, "label2id", {}).items()
        }
        if label2id and label2id != {
            name: index for index, name in LABEL_MAPPING.items()
        }:
            raise InvalidCheckpointError("Checkpoint label mapping is incompatible")
        selected_device = self.device_name or (
            "cuda" if self._torch.cuda.is_available() else "cpu"
        )
        if selected_device == "cuda" and not self._torch.cuda.is_available():
            raise PredictionServiceError("CUDA was requested but is unavailable")
        self._device = self._torch.device(selected_device)
        self._model.to(self._device)
        self._model.eval()

    def predict(self, claim: str, evidence_context: str) -> PredictionResult:
        self._load_components()
        inputs = build_model_input(
            self._tokenizer, claim, evidence_context, self.max_length
        )
        inputs = {
            key: value.to(self._device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with self._torch.inference_mode():
            outputs = self._model(**inputs)
        logits = outputs.logits
        probabilities = self._torch.softmax(logits, dim=-1)[0].detach().cpu().tolist()
        if len(probabilities) != len(LABEL_NAMES) or not all(
            math.isfinite(float(value)) and 0 <= float(value) <= 1
            for value in probabilities
        ):
            raise PredictionServiceError("Model returned invalid class probabilities")
        label_id = int(self._torch.argmax(logits, dim=-1)[0].item())
        return PredictionResult(
            label_id=label_id,
            label=LABEL_MAPPING[label_id],
            probabilities={
                LABEL_MAPPING[index]: float(value)
                for index, value in enumerate(probabilities)
            },
            predicted_probability=float(probabilities[label_id]),
        )
