import json
import importlib.util
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "experiments/results/biobert_grouped_v1/config.json"
DATA_DIR = ROOT / "data/processed/grouped_splits_v1"
BASELINE_PATH = ROOT / "experiments/biobert_baseline.py"


def load_baseline_module():
    spec = importlib.util.spec_from_file_location("biobert_baseline", BASELINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_grouped_configuration_is_authoritative():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["data_dir"] == "data/processed/grouped_splits_v1"
    assert config["output_dir"] == "experiments/results/biobert_grouped_v1"
    assert config["model_revision"] == (
        "924f12e0c3db7f156a765ad53fb6b11e7afedbc8"
    )
    assert config["gradient_accumulation_steps"] == 4
    assert config["label_mapping"] == {
        "0": "inconclusive",
        "1": "evidence",
        "2": "NEI",
    }
    assert config["training_status"] == "not_started"
    assert (ROOT / config["data_dir"]).is_dir()
    assert Path(config["output_dir"]).name != "biobert_baseline"


def test_baseline_loads_grouped_config_and_rejects_leaky_path():
    baseline = load_baseline_module()
    config = baseline.load_config(CONFIG_PATH)
    assert Path(config["data_dir"]).resolve() == DATA_DIR.resolve()
    assert Path(config["output_dir"]).name == "biobert_grouped_v1"
    leaky = dict(config, data_dir=str(ROOT / "data/processed/primary_outcome_publication_dataset"))
    try:
        baseline.apply_cli_overrides(
            leaky,
            Namespace(
                model_name=None,
                data_dir=None,
                output_dir=None,
                seeds=None,
                epochs=None,
                patience=None,
                train_batch_size=None,
                micro_batch_size=None,
                gradient_accumulation_steps=None,
                cpu_threads=None,
                eval_batch_size=None,
                learning_rate=None,
            ),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Leaky dataset path was not rejected")


def test_unspecified_cli_values_preserve_config_and_explicit_values_override():
    baseline = load_baseline_module()
    config = baseline.load_config(CONFIG_PATH)
    args = Namespace(
        model_name=None,
        data_dir=None,
        output_dir=None,
        seeds=None,
        epochs=7,
        patience=None,
        train_batch_size=None,
        micro_batch_size=None,
        gradient_accumulation_steps=None,
        cpu_threads=None,
        eval_batch_size=None,
        learning_rate=None,
    )
    effective = baseline.apply_cli_overrides(config, args)
    assert effective["data_dir"] == str(DATA_DIR.resolve())
    assert effective["epochs"] == 7
    assert effective["train_batch_size"] == 32
    assert effective["gradient_accumulation_steps"] == 4


def test_revision_is_propagated_without_network_requests(monkeypatch):
    baseline = load_baseline_module()
    calls = []

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls.append(("tokenizer", args, kwargs))
            return object()

    class FakeAutoModel:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls.append(("model", args, kwargs))
            return object()

    monkeypatch.setattr(baseline, "AutoTokenizer", FakeAutoTokenizer)
    monkeypatch.setattr(baseline, "AutoModelForSequenceClassification", FakeAutoModel)
    revision = "924f12e0c3db7f156a765ad53fb6b11e7afedbc8"
    baseline.load_tokenizer("test-model", revision)
    baseline.load_model("test-model", revision)

    assert calls[0][2]["revision"] == revision
    assert calls[1][2]["revision"] == revision
    assert calls[1][2]["num_labels"] == 3


def test_invalid_gradient_accumulation_is_rejected():
    baseline = load_baseline_module()
    config = baseline.load_config(CONFIG_PATH)
    config["gradient_accumulation_steps"] = 0
    with pytest.raises(ValueError, match="positive integer"):
        baseline.apply_cli_overrides(
            config,
            Namespace(**{name: None for name in (
                "model_name", "data_dir", "output_dir", "seeds", "epochs",
                "patience", "train_batch_size", "micro_batch_size",
                "gradient_accumulation_steps",
                "cpu_threads", "eval_batch_size", "learning_rate",
            )}),
        )


def test_mismatched_effective_batch_size_is_rejected():
    baseline = load_baseline_module()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["train_batch_size"] = 16
    with pytest.raises(ValueError, match="micro_batch_size"):
        baseline.load_config_from_effective_values(config)


def test_canonical_original_dataset_path_is_rejected():
    baseline = load_baseline_module()
    alias = ROOT / "data" / "processed" / "." / "primary_outcome_publication_dataset"
    with pytest.raises(ValueError, match="original row-level"):
        baseline.reject_original_data_dir(alias)


def test_checkpoint_is_published_only_with_completion_manifest(tmp_path):
    baseline = load_baseline_module()

    class FakeModel:
        @staticmethod
        def save_pretrained(path):
            (Path(path) / "config.json").write_text("{}", encoding="utf-8")
            (Path(path) / "pytorch_model.bin").write_bytes(b"weights")

    class FakeTokenizer:
        @staticmethod
        def save_pretrained(path):
            (Path(path) / "tokenizer_config.json").write_text(
                "{}", encoding="utf-8"
            )

    checkpoint = tmp_path / "best_model"
    baseline.publish_checkpoint(FakeModel(), FakeTokenizer(), checkpoint, 13)
    baseline.validate_checkpoint(checkpoint)
    manifest = json.loads(
        (checkpoint / "checkpoint_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["required_revision"] == baseline.CHECKPOINT_REVISION


def test_run_status_distinguishes_failed_from_completed(tmp_path):
    baseline = load_baseline_module()
    status_path = tmp_path / "run_status.json"
    baseline.write_run_status(status_path, "running")
    assert json.loads(status_path.read_text(encoding="utf-8"))["completed"] is False
    baseline.write_run_status(
        status_path, "failed", error_type="RuntimeError", error="test failure"
    )
    failed = json.loads(status_path.read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["error"] == "test failure"
    baseline.write_run_status(status_path, "completed")
    assert json.loads(status_path.read_text(encoding="utf-8"))["completed"] is True


def test_single_seed_summary_reports_unavailable_standard_deviations():
    baseline = load_baseline_module()
    summary = baseline.summarize_runs(
        [{"seed": 13, "accuracy": 0.6, "f1_macro": 0.4}]
    )
    assert summary["completed_seed_count"] == 1
    assert summary["accuracy_std"] is None
    assert summary["f1_macro_std"] is None
    formatted = baseline.format_summary(summary)
    assert "1-seed test summary" in formatted
    assert "Three-seed" not in formatted
    assert "unavailable" in formatted


def test_multi_seed_summary_uses_sample_standard_deviation():
    baseline = load_baseline_module()
    summary = baseline.summarize_runs(
        [
            {"seed": 13, "accuracy": 0.6, "f1_macro": 0.4},
            {"seed": 37, "accuracy": 0.8, "f1_macro": 0.6},
        ]
    )
    assert summary["completed_seed_count"] == 2
    assert summary["accuracy_mean"] == pytest.approx(0.7)
    assert summary["accuracy_std"] == pytest.approx(0.1414213562)
    assert summary["f1_macro_mean"] == pytest.approx(0.5)
    assert summary["f1_macro_std"] == pytest.approx(0.1414213562)
    assert "2-seed test summary" in baseline.format_summary(summary)


def test_grouped_splits_have_compatible_labels_and_inputs():
    required = {"claim", "article_title", "article_abstract", "label"}
    for split in ("train", "validation", "test"):
        data = pd.read_csv(DATA_DIR / f"{split}_set.csv")
        assert required.issubset(data.columns)
        assert not data[list(required)].isna().any().any()
        assert set(data["label"].unique()) <= {0, 1, 2}
