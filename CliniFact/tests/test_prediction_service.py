import json
from pathlib import Path

import pytest
import torch

from app.services.prediction_service import (
    AUTHORIZED_REVISION,
    InvalidCheckpointError,
    InvalidPredictionInput,
    LABEL_MAPPING,
    PredictionService,
    build_model_input,
    validate_checkpoint_metadata,
)


class FakeTokenizer:
    def __init__(self):
        self.calls = []

    def encode_plus(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "input_ids": torch.tensor([[101, 102]]),
            "attention_mask": torch.tensor([[1, 1]]),
        }


class FakeConfig:
    num_labels = 3
    label2id = {"inconclusive": 0, "evidence": 1, "NEI": 2}


class FakeModel:
    config = FakeConfig()

    def __init__(self):
        self.eval_called = False
        self.device = None

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        self.eval_called = True
        return self

    def __call__(self, **inputs):
        return type("Outputs", (), {"logits": torch.tensor([[0.0, 2.0, 1.0]])})()


def make_checkpoint(tmp_path: Path, revision=AUTHORIZED_REVISION) -> Path:
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    (checkpoint / "checkpoint_manifest.json").write_text(
        json.dumps({"status": "complete", "required_revision": revision}),
        encoding="utf-8",
    )
    (checkpoint / "config.json").write_text("{}", encoding="utf-8")
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    return checkpoint


def test_label_mapping_is_explicit():
    assert LABEL_MAPPING == {0: "inconclusive", 1: "evidence", 2: "NEI"}


def test_input_builder_preserves_pair_and_truncation_contract():
    tokenizer = FakeTokenizer()
    build_model_input(tokenizer, " Claim ", " Evidence ", max_length=512)
    call = tokenizer.calls[0]
    assert call["text"] == "Claim"
    assert call["text_pair"] == "Evidence"
    assert call["max_length"] == 512
    assert call["truncation"] is True
    assert call["return_tensors"] == "pt"


@pytest.mark.parametrize("claim,evidence", [("", "context"), ("claim", ""), ("  ", "context")])
def test_input_builder_rejects_empty_inputs(claim, evidence):
    with pytest.raises(InvalidPredictionInput):
        build_model_input(FakeTokenizer(), claim, evidence)


def test_checkpoint_metadata_rejects_incomplete_or_wrong_revision(tmp_path):
    checkpoint = make_checkpoint(tmp_path, revision="wrong")
    with pytest.raises(InvalidCheckpointError):
        validate_checkpoint_metadata(checkpoint)
    (checkpoint / "checkpoint_manifest.json").write_text(
        json.dumps({"status": "running", "required_revision": AUTHORIZED_REVISION}),
        encoding="utf-8",
    )
    with pytest.raises(InvalidCheckpointError):
        validate_checkpoint_metadata(checkpoint)


def test_service_is_lazy_and_returns_cpu_prediction(tmp_path):
    checkpoint = make_checkpoint(tmp_path)
    calls = {"tokenizer": 0, "model": 0}
    tokenizer = FakeTokenizer()
    model = FakeModel()

    def tokenizer_loader(*args, **kwargs):
        calls["tokenizer"] += 1
        return tokenizer

    def model_loader(*args, **kwargs):
        calls["model"] += 1
        return model

    service = PredictionService(
        checkpoint_dir=checkpoint,
        device_name="cpu",
        tokenizer_loader=tokenizer_loader,
        model_loader=model_loader,
    )
    assert calls == {"tokenizer": 0, "model": 0}
    result = service.predict("A claim", "A selected evidence context")
    assert calls == {"tokenizer": 1, "model": 1}
    assert result.label_id == 1
    assert result.label == "evidence"
    assert result.predicted_probability == pytest.approx(0.6652409)
    assert all(0 <= value <= 1 for value in result.probabilities.values())
    assert model.eval_called is True
    assert model.device.type == "cpu"


def test_service_rejects_incompatible_model_class_count(tmp_path):
    checkpoint = make_checkpoint(tmp_path)

    class BadModel(FakeModel):
        class config:
            num_labels = 2
            label2id = {"inconclusive": 0, "evidence": 1}

    with pytest.raises(InvalidCheckpointError, match="exactly three"):
        PredictionService(
            checkpoint_dir=checkpoint,
            tokenizer_loader=lambda *args, **kwargs: FakeTokenizer(),
            model_loader=lambda *args, **kwargs: BadModel(),
        ).predict("A claim", "Evidence")
