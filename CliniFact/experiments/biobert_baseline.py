import argparse
import json
import os
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

try:
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    TRAINING_IMPORT_ERROR = None
except ImportError as error:
    torch = None
    DataLoader = None
    Dataset = object
    AutoModelForSequenceClassification = None
    AutoTokenizer = None
    TRAINING_IMPORT_ERROR = error


LABEL_NAMES = ["inconclusive", "evidence", "NEI"]
LABEL_IDS = set(range(len(LABEL_NAMES)))
REQUIRED_COLUMNS = {"claim", "article_title", "article_abstract", "label"}
SEQUENCE_LENGTH = 512
DEFAULT_CONFIG = Path("experiments/results/biobert_grouped_v1/config.json")
ORIGINAL_DATA_DIR_NAME = "primary_outcome_publication_dataset"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DATA_DIR = (
    PROJECT_ROOT / "data" / "processed" / ORIGINAL_DATA_DIR_NAME
).resolve()
CHECKPOINT_REVISION = "924f12e0c3db7f156a765ad53fb6b11e7afedbc8"
ACTIVE_STATUS_PATH = None


def write_run_status(path: Path, status: str, **details) -> None:
    payload = {"status": status, "completed": status == "completed", **details}
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


class CliniFactDataset(Dataset):
    def __init__(self, data, tokenizer):
        self.labels = data["label"].astype(int).tolist()
        self.encodings = []

        for _, item in data.iterrows():
            claim = str(item["claim"])
            abstract = f"{item['article_title']} {item['article_abstract']}"

            encoded_length = len(
                tokenizer.encode(claim, abstract, add_special_tokens=True)
            )
            while encoded_length > SEQUENCE_LENGTH:
                sentences = abstract.split(". ")
                if len(sentences) > 1:
                    abstract = ". ".join(sentences[1:])
                else:
                    words = abstract.split()
                    if len(words) > 15:
                        abstract = " ".join(words[1:])
                    else:
                        break
                encoded_length = len(
                    tokenizer.encode(claim, abstract, add_special_tokens=True)
                )

            self.encodings.append(
                tokenizer.encode_plus(
                    text=claim,
                    text_pair=abstract,
                    add_special_tokens=True,
                    max_length=SEQUENCE_LENGTH,
                    padding=False,
                    truncation=True,
                )
            )

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        encoding = self.encodings[index]
        return {
            "input_ids": encoding["input_ids"],
            "attention_mask": encoding["attention_mask"],
            "labels": self.labels[index],
        }


def collate_batch(features, tokenizer):
    labels = torch.tensor([feature["labels"] for feature in features], dtype=torch.long)
    model_inputs = tokenizer.pad(
        [
            {
                "input_ids": feature["input_ids"],
                "attention_mask": feature["attention_mask"],
            }
            for feature in features
        ],
        padding=True,
        pad_to_multiple_of=8,
        return_tensors="pt",
    )
    model_inputs["labels"] = labels
    return model_inputs


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def evaluate(model, dataloader, device):
    model.eval()
    labels = []
    predictions = []
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids, attention_mask=attention_mask)
            predictions.extend(outputs.logits.argmax(dim=1).cpu().tolist())
            labels.extend(batch["labels"].tolist())
    return labels, predictions


def canonical_data_dir(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve(strict=False)


def reject_original_data_dir(data_dir: Path) -> Path:
    canonical = canonical_data_dir(data_dir)
    if canonical == ORIGINAL_DATA_DIR or canonical.name == ORIGINAL_DATA_DIR_NAME:
        raise ValueError(
            "The original row-level dataset is not allowed for this experiment"
        )
    return canonical


def load_tokenizer(model_name: str, revision: str):
    return AutoTokenizer.from_pretrained(model_name, revision=revision)


def load_model(model_name: str, revision: str):
    return AutoModelForSequenceClassification.from_pretrained(
        model_name,
        revision=revision,
        num_labels=len(LABEL_NAMES),
        label2id={name: index for index, name in enumerate(LABEL_NAMES)},
        id2label={index: name for index, name in enumerate(LABEL_NAMES)},
    )


def validate_checkpoint(checkpoint_dir: Path) -> None:
    marker = checkpoint_dir / "checkpoint_manifest.json"
    required = [
        checkpoint_dir / "config.json",
        checkpoint_dir / "tokenizer_config.json",
    ]
    has_weights = any(
        (checkpoint_dir / filename).is_file()
        for filename in ("pytorch_model.bin", "model.safetensors")
    )
    if not marker.is_file() or not all(path.is_file() for path in required) or not has_weights:
        raise RuntimeError(
            f"No valid completed checkpoint found at {checkpoint_dir}"
        )


def publish_checkpoint(model, tokenizer, checkpoint_dir: Path, seed: int) -> None:
    checkpoint_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".best_model_seed_{seed}_", dir=checkpoint_dir.parent)
    )
    try:
        model.save_pretrained(temporary_dir)
        tokenizer.save_pretrained(temporary_dir)
        with (temporary_dir / "checkpoint_manifest.json").open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(
                {
                    "status": "complete",
                    "seed": seed,
                    "required_revision": CHECKPOINT_REVISION,
                },
                file,
                indent=2,
            )
        validate_checkpoint(temporary_dir)
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir)
        temporary_dir.rename(checkpoint_dir)
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise


def summarize_runs(run_metrics: list[dict]) -> dict:
    if not run_metrics:
        raise ValueError("Cannot summarize a run with no completed seeds")
    seed_count = len(run_metrics)
    accuracy_values = [run["accuracy"] for run in run_metrics]
    f1_values = [run["f1_macro"] for run in run_metrics]
    return {
        "runs": run_metrics,
        "completed_seed_count": seed_count,
        "accuracy_mean": float(np.mean(accuracy_values)),
        "accuracy_std": (
            float(np.std(accuracy_values, ddof=1)) if seed_count > 1 else None
        ),
        "f1_macro_mean": float(np.mean(f1_values)),
        "f1_macro_std": (
            float(np.std(f1_values, ddof=1)) if seed_count > 1 else None
        ),
    }


def format_summary(summary: dict) -> str:
    seed_count = summary["completed_seed_count"]
    accuracy_std = (
        f"{summary['accuracy_std']:.4f}"
        if summary["accuracy_std"] is not None
        else "unavailable"
    )
    f1_std = (
        f"{summary['f1_macro_std']:.4f}"
        if summary["f1_macro_std"] is not None
        else "unavailable"
    )
    return (
        f"\n{seed_count}-seed test summary: "
        f"accuracy={summary['accuracy_mean']:.4f} +/- {accuracy_std}; "
        f"macro-F1={summary['f1_macro_mean']:.4f} +/- {f1_std}"
    )


def load_and_validate_split(data_dir: Path, split_name: str) -> pd.DataFrame:
    path = data_dir / f"{split_name}_set.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {split_name} dataset: {path}")
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS - set(data.columns)
    if missing_columns:
        raise ValueError(f"{path} is missing required columns: {sorted(missing_columns)}")
    if data.empty:
        raise ValueError(f"{path} contains no records")
    for column in ("claim", "article_title", "article_abstract"):
        missing_text = data[column].isna() | data[column].astype(str).str.strip().eq("")
        if missing_text.any():
            raise ValueError(
                f"{path} contains {int(missing_text.sum())} missing {column} values"
            )
    numeric_labels = pd.to_numeric(data["label"], errors="coerce")
    if numeric_labels.isna().any() or not numeric_labels.isin(LABEL_IDS).all():
        invalid = data.loc[
            numeric_labels.isna() | ~numeric_labels.isin(LABEL_IDS), "label"
        ].tolist()
        raise ValueError(f"{path} contains invalid labels: {invalid[:10]}")
    data["label"] = numeric_labels.astype(int)
    return data


def validate_data_dir(data_dir: Path) -> dict[str, int]:
    splits = {
        split_name: load_and_validate_split(data_dir, split_name)
        for split_name in ("train", "validation", "test")
    }
    return {split_name: len(data) for split_name, data in splits.items()}


def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        raise FileNotFoundError(f"Missing experiment configuration: {config_path}")
    with config_path.open(encoding="utf-8") as file:
        config = json.load(file)
    required = {
        "model_name",
        "model_revision",
        "data_dir",
        "output_dir",
        "seeds",
        "epochs",
        "patience",
        "train_batch_size",
        "micro_batch_size",
        "gradient_accumulation_steps",
        "cpu_threads",
        "eval_batch_size",
        "learning_rate",
        "sequence_length",
        "num_labels",
        "label_mapping",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"Configuration is missing fields: {missing}")
    if config["sequence_length"] != SEQUENCE_LENGTH:
        raise ValueError("Only sequence_length=512 is supported by this baseline")
    if config["model_revision"] != CHECKPOINT_REVISION:
        raise ValueError(
            f"model_revision must equal the authorized revision {CHECKPOINT_REVISION}"
        )
    if config["num_labels"] != len(LABEL_NAMES):
        raise ValueError(f"num_labels must be {len(LABEL_NAMES)}")
    expected_mapping = {str(index): name for index, name in enumerate(LABEL_NAMES)}
    if config["label_mapping"] != expected_mapping:
        raise ValueError(
            f"label_mapping must exactly equal {expected_mapping}, "
            f"got {config['label_mapping']}"
        )
    for name in (
        "gradient_accumulation_steps",
        "micro_batch_size",
        "train_batch_size",
    ):
        if (
            not isinstance(config[name], int)
            or isinstance(config[name], bool)
            or config[name] <= 0
        ):
            raise ValueError(f"{name} must be a positive integer")
    if (
        config["train_batch_size"]
        != config["micro_batch_size"] * config["gradient_accumulation_steps"]
    ):
        raise ValueError(
            "train_batch_size must equal micro_batch_size multiplied by "
            "gradient_accumulation_steps"
        )
    data_dir = Path(config["data_dir"])
    if not data_dir.is_absolute():
        data_dir = Path.cwd() / data_dir
    config["data_dir"] = str(reject_original_data_dir(data_dir))
    output_dir = Path(config["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    if output_dir.name == "biobert_baseline":
        raise ValueError("The legacy BioBERT output directory is not allowed")
    config["output_dir"] = str(output_dir.resolve(strict=False))
    return config


def apply_cli_overrides(config: dict, args: argparse.Namespace) -> dict:
    override_names = (
        "model_name",
        "data_dir",
        "output_dir",
        "seeds",
        "epochs",
        "patience",
        "train_batch_size",
        "micro_batch_size",
        "gradient_accumulation_steps",
        "cpu_threads",
        "eval_batch_size",
        "learning_rate",
    )
    for name in override_names:
        value = getattr(args, name)
        if value is not None:
            config[name] = value
    config["data_dir"] = str(reject_original_data_dir(Path(config["data_dir"])))
    config["output_dir"] = str(Path(config["output_dir"]).resolve(strict=False))
    if Path(config["output_dir"]).name == "biobert_baseline":
        raise ValueError("The legacy BioBERT output directory is not allowed")
    config = load_config_from_effective_values(config)
    return config


def load_config_from_effective_values(config: dict) -> dict:
    if config["model_revision"] != CHECKPOINT_REVISION:
        raise ValueError(
            f"model_revision must equal the authorized revision {CHECKPOINT_REVISION}"
        )
    for name in (
        "gradient_accumulation_steps",
        "micro_batch_size",
        "train_batch_size",
    ):
        if (
            not isinstance(config[name], int)
            or isinstance(config[name], bool)
            or config[name] <= 0
        ):
            raise ValueError(f"{name} must be a positive integer")
    if (
        config["train_batch_size"]
        != config["micro_batch_size"] * config["gradient_accumulation_steps"]
    ):
        raise ValueError(
            "train_batch_size must equal micro_batch_size multiplied by "
            "gradient_accumulation_steps"
        )
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Authoritative experiment JSON configuration",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--model-name", default=None
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--train-batch-size", type=int, default=None)
    parser.add_argument("--micro-batch-size", type=int, default=None)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=None)
    parser.add_argument("--cpu-threads", type=int, default=None)
    parser.add_argument("--eval-batch-size", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument(
        "--validate-data-only",
        action="store_true",
        help="Validate grouped CSV files without loading a tokenizer or model",
    )
    args = parser.parse_args()

    experiment_config = apply_cli_overrides(load_config(args.config), args)
    args = argparse.Namespace(
        **experiment_config, validate_data_only=args.validate_data_only
    )
    args.data_dir = Path(args.data_dir)
    args.output_dir = Path(args.output_dir)
    if args.train_batch_size % args.micro_batch_size:
        parser.error("--train-batch-size must be divisible by --micro-batch-size")
    if args.cpu_threads < 1:
        parser.error("--cpu-threads must be positive")
    row_counts = validate_data_dir(args.data_dir)
    if args.validate_data_only:
        print(json.dumps({"data_dir": str(args.data_dir.resolve()), "rows": row_counts}))
        return

    if TRAINING_IMPORT_ERROR is not None:
        raise ImportError(
            "Training requires torch and transformers; install the project "
            "training dependencies before starting a run."
        ) from TRAINING_IMPORT_ERROR

    args.output_dir.mkdir(parents=True, exist_ok=True)
    attempt_name = (
        f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}"
    )
    args.output_dir = args.output_dir / "runs" / attempt_name
    args.output_dir.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.cpu_threads)
    train_df = load_and_validate_split(args.data_dir, "train")
    val_df = load_and_validate_split(args.data_dir, "validation")
    test_df = load_and_validate_split(args.data_dir, "test")

    runtime_config = {
        "model_name": args.model_name,
        "model_revision": args.model_revision,
        "seeds": args.seeds,
        "epochs": args.epochs,
        "patience": args.patience,
        "train_batch_size": args.train_batch_size,
        "micro_batch_size": args.micro_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "cpu_threads": args.cpu_threads,
        "eval_batch_size": args.eval_batch_size,
        "learning_rate": args.learning_rate,
        "sequence_length": SEQUENCE_LENGTH,
        "data_dir": str(args.data_dir.resolve()),
        "rows": row_counts,
        "label_mapping": {str(index): name for index, name in enumerate(LABEL_NAMES)},
        "seed_policy": "Python, NumPy, PyTorch, and DataLoader generator seeded per run",
        "checkpoint_selection": "highest validation macro-F1",
        "effective_batch_size": (
            "micro_batch_size multiplied by gradient_accumulation_steps"
        ),
    }
    with (args.output_dir / "run_config.json").open("w", encoding="utf-8") as file:
        json.dump(runtime_config, file, indent=2)
    global ACTIVE_STATUS_PATH
    ACTIVE_STATUS_PATH = args.output_dir / "run_status.json"
    write_run_status(ACTIVE_STATUS_PATH, "running")

    tokenizer = load_tokenizer(args.model_name, args.model_revision)
    train_dataset = CliniFactDataset(train_df, tokenizer)
    val_dataset = CliniFactDataset(val_df, tokenizer)
    test_dataset = CliniFactDataset(test_df, tokenizer)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    run_metrics = []
    for seed in args.seeds:
        print(f"\nTraining seed {seed}")
        seed_everything(seed)
        generator = torch.Generator()
        generator.manual_seed(seed)
        train_loader = DataLoader(
            train_dataset,
            batch_size=args.micro_batch_size,
            shuffle=True,
            generator=generator,
            collate_fn=lambda features: collate_batch(features, tokenizer),
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=args.eval_batch_size,
            shuffle=False,
            collate_fn=lambda features: collate_batch(features, tokenizer),
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=args.eval_batch_size,
            shuffle=False,
            collate_fn=lambda features: collate_batch(features, tokenizer),
        )
        model = load_model(args.model_name, args.model_revision).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
        best_val_f1 = -1.0
        best_epoch = 0
        epochs_without_improvement = 0
        checkpoint_dir = args.output_dir / f"seed_{seed}" / "best_model"
        checkpoint_dir.parent.mkdir(parents=True, exist_ok=True)
        epoch_history = []

        for epoch in range(args.epochs):
            model.train()
            total_loss = 0.0
            optimizer.zero_grad()
            accumulation_steps = args.gradient_accumulation_steps
            for batch_index, batch in enumerate(train_loader):
                window_start = (
                    batch_index // accumulation_steps
                ) * accumulation_steps
                window_stop = min(
                    window_start + accumulation_steps, len(train_loader)
                )
                window_size = min(
                    (window_stop - window_start) * args.micro_batch_size,
                    len(train_dataset) - window_start * args.micro_batch_size,
                )
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = model(
                    input_ids, attention_mask=attention_mask, labels=labels
                )
                scaled_loss = outputs.loss * (labels.size(0) / window_size)
                scaled_loss.backward()
                total_loss += outputs.loss.item()
                if (batch_index + 1) == window_stop:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    optimizer.zero_grad()

            val_labels, val_predictions = evaluate(model, val_loader, device)
            val_f1 = f1_score(val_labels, val_predictions, average="macro")
            epoch_metrics = {
                "epoch": epoch + 1,
                "average_train_loss": total_loss / len(train_loader),
                "validation_accuracy": accuracy_score(val_labels, val_predictions),
                "validation_f1_macro": val_f1,
            }
            epoch_history.append(epoch_metrics)
            print(
                f"seed={seed} epoch={epoch + 1} "
                f"train_loss={epoch_metrics['average_train_loss']:.4f} "
                f"val_accuracy={epoch_metrics['validation_accuracy']:.4f} "
                f"val_f1_macro={val_f1:.4f}"
            )

            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_epoch = epoch + 1
                epochs_without_improvement = 0
                publish_checkpoint(model, tokenizer, checkpoint_dir, seed)
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= args.patience:
                    print(f"Early stopping at epoch {epoch + 1}")
                    break

        pd.DataFrame(epoch_history).to_csv(
            checkpoint_dir.parent / "training_metrics.csv", index=False
        )
        del model
        validate_checkpoint(checkpoint_dir)
        model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint_dir,
            num_labels=len(LABEL_NAMES),
            label2id={name: index for index, name in enumerate(LABEL_NAMES)},
            id2label={index: name for index, name in enumerate(LABEL_NAMES)},
        ).to(device)
        test_labels, test_predictions = evaluate(model, test_loader, device)
        metrics = {
            "seed": seed,
            "best_epoch": best_epoch,
            "best_validation_f1_macro": best_val_f1,
            "accuracy": accuracy_score(test_labels, test_predictions),
            "f1_macro": f1_score(test_labels, test_predictions, average="macro"),
            "classification_report": classification_report(
                test_labels,
                test_predictions,
                labels=[0, 1, 2],
                target_names=LABEL_NAMES,
                output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": confusion_matrix(
                test_labels, test_predictions, labels=[0, 1, 2]
            ).tolist(),
        }
        run_metrics.append(metrics)
        predictions_df = test_df[
            ["index", "nctId", "PMID", "claim", "label"]
        ].copy()
        predictions_df["Predicted_Label"] = test_predictions
        predictions_df.to_csv(
            checkpoint_dir.parent / "test_predictions.csv", index=False
        )
        with (checkpoint_dir.parent / "metrics.json").open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(metrics, file, indent=2)
        print(
            f"seed={seed} test_accuracy={metrics['accuracy']:.4f} "
            f"test_f1_macro={metrics['f1_macro']:.4f}"
        )
        del model

    summary = summarize_runs(run_metrics)
    with (args.output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    write_run_status(ACTIVE_STATUS_PATH, "completed")
    print(format_summary(summary))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if ACTIVE_STATUS_PATH is not None:
            write_run_status(
                ACTIVE_STATUS_PATH,
                "failed",
                error_type=type(error).__name__,
                error=str(error),
            )
        raise
