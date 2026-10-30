"""Create reproducible leakage-safe grouped dataset splits.

This script reads the existing row-level splits as source data, preserves every
source row, and writes new splits without changing the original files.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd


LABEL_NAMES = {0: "inconclusive", 1: "evidence", 2: "NEI"}
SPLIT_NAMES = ("train", "validation", "test")
SPLIT_FRACTIONS = {"train": 0.64, "validation": 0.16, "test": 0.20}
NCT_PATTERN = re.compile(r"^NCT\d{8}$")
GROUP_FIELDS = ("nctId", "PMID", "claim")


class UnionFind:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))
        self.size = [1] * count

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.size[left_root] < self.size[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.size[left_root] += self.size[right_root]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("data/processed/primary_outcome_publication_dataset"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/grouped_splits_v1"),
    )
    parser.add_argument("--seed", type=int, default=20261025)
    return parser.parse_args()


def load_source(source_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    source_files = [
        source_dir / "train_set.csv",
        source_dir / "validation_set.csv",
        source_dir / "test_set.csv",
    ]
    missing = [str(path) for path in source_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source CSV files: {missing}")

    frames = []
    expected_columns: list[str] | None = None
    for path in source_files:
        frame = pd.read_csv(
            path,
            dtype={"nctId": "string", "PMID": "string", "claim": "string"},
        )
        if expected_columns is None:
            expected_columns = list(frame.columns)
        elif list(frame.columns) != expected_columns:
            raise ValueError(f"Schema mismatch in {path}")
        frame["_source_file"] = path.name
        frames.append(frame)

    assert expected_columns is not None
    combined = pd.concat(frames, ignore_index=True)
    return combined, expected_columns


def validate_identifiers(frame: pd.DataFrame) -> dict[str, object]:
    missing = {}
    invalid = {}
    for field in GROUP_FIELDS:
        values = frame[field].astype("string")
        missing[field] = int(values.isna().sum() + (values.fillna("").str.strip() == "").sum())
        if field == "nctId":
            invalid[field] = int(
                (~values.fillna("").str.match(NCT_PATTERN)).sum()
            )
        else:
            invalid[field] = 0
    return {"missing": missing, "invalid": invalid}


def build_components(frame: pd.DataFrame) -> list[list[int]]:
    union_find = UnionFind(len(frame))
    for field in GROUP_FIELDS:
        first_row_for_value: dict[str, int] = {}
        for row_index, value in frame[field].items():
            normalized = str(value).strip()
            if not normalized:
                continue
            previous = first_row_for_value.get(normalized)
            if previous is None:
                first_row_for_value[normalized] = row_index
            else:
                union_find.union(row_index, previous)

    components: dict[int, list[int]] = defaultdict(list)
    for row_index in range(len(frame)):
        components[union_find.find(row_index)].append(row_index)
    return list(components.values())


def component_sort_key(frame: pd.DataFrame, rows: list[int]) -> tuple[int, str]:
    identifiers = [
        f"{field}={str(frame.iloc[rows[0]][field]).strip()}"
        for field in GROUP_FIELDS
    ]
    return (-len(rows), "|".join(identifiers))


def assign_components(
    frame: pd.DataFrame, components: list[list[int]], seed: int
) -> dict[str, list[int]]:
    total_rows = len(frame)
    target_rows = {
        name: SPLIT_FRACTIONS[name] * total_rows for name in SPLIT_NAMES
    }
    total_label_counts = frame["label"].value_counts().to_dict()
    target_labels = {
        name: {
            label: SPLIT_FRACTIONS[name] * total_label_counts.get(label, 0)
            for label in LABEL_NAMES
        }
        for name in SPLIT_NAMES
    }

    rng = random.Random(seed)
    by_size: dict[int, list[list[int]]] = defaultdict(list)
    for component in components:
        by_size[len(component)].append(component)
    ordered = []
    for size in sorted(by_size, reverse=True):
        tied_components = sorted(
            by_size[size], key=lambda rows: component_sort_key(frame, rows)
        )
        rng.shuffle(tied_components)
        ordered.extend(tied_components)

    assignments = {name: [] for name in SPLIT_NAMES}
    row_counts = {name: 0 for name in SPLIT_NAMES}
    label_counts = {
        name: {label: 0 for label in LABEL_NAMES} for name in SPLIT_NAMES
    }

    for component in ordered:
        component_labels = frame.iloc[component]["label"].value_counts().to_dict()

        def score(split_name: str) -> tuple[float, float, str]:
            projected_rows = row_counts[split_name] + len(component)
            projected_ratio = projected_rows / target_rows[split_name]
            row_error = abs(projected_rows - target_rows[split_name]) / total_rows
            label_error = sum(
                abs(
                    label_counts[split_name][label]
                    + component_labels.get(label, 0)
                    - target_labels[split_name][label]
                )
                / max(1, total_label_counts.get(label, 0))
                for label in LABEL_NAMES
            )
            return (projected_ratio + 0.05 * label_error, row_error, split_name)

        chosen = min(SPLIT_NAMES, key=score)
        assignments[chosen].extend(component)
        row_counts[chosen] += len(component)
        for label in LABEL_NAMES:
            label_counts[chosen][label] += component_labels.get(label, 0)

    return assignments


def identifier_overlap(split_frames: dict[str, pd.DataFrame], field: str) -> dict[str, int]:
    values = {
        name: set(frame[field].dropna().astype(str).str.strip())
        for name, frame in split_frames.items()
    }
    return {
        f"{left}_{right}": len(values[left] & values[right])
        for index, left in enumerate(SPLIT_NAMES)
        for right in SPLIT_NAMES[index + 1 :]
    }


def make_conflict_report(frame: pd.DataFrame, output_path: Path) -> dict[str, int]:
    label_counts = frame.groupby("claim", dropna=False)["label"].nunique()
    conflict_claims = set(label_counts[label_counts > 1].index)
    conflicts = frame[frame["claim"].isin(conflict_claims)].copy()
    conflicts = conflicts.sort_values(["claim", "nctId", "PMID", "label"])
    conflicts.to_csv(output_path, index=False)
    return {
        "conflicting_claims": len(conflict_claims),
        "conflicting_rows": len(conflicts),
        "conflicting_components": 0,
    }


def main() -> None:
    args = parse_args()
    frame, source_columns = load_source(args.source_dir)
    args.output_dir.mkdir(parents=True, exist_ok=False)

    identifier_quality = validate_identifiers(frame)
    if any(identifier_quality["missing"].values()) or any(
        identifier_quality["invalid"].values()
    ):
        raise ValueError(
            "Missing or invalid grouping identifiers prevent a defensible "
            f"connected-component split: {identifier_quality}"
        )

    if frame[source_columns].duplicated().any():
        raise ValueError("Exact duplicate source rows were found; refusing to discard them.")

    components = build_components(frame)
    conflict_report_path = args.output_dir / "label_conflicts.csv"
    conflict_summary = make_conflict_report(frame, conflict_report_path)
    conflict_component_count = sum(
        frame.iloc[component]["label"].nunique() > 1 for component in components
    )
    conflict_summary["conflicting_components"] = int(conflict_component_count)

    assignments = assign_components(frame, components, args.seed)
    split_frames: dict[str, pd.DataFrame] = {}
    for split_name in SPLIT_NAMES:
        rows = assignments[split_name]
        split = frame.iloc[rows][source_columns].copy()
        split.to_csv(args.output_dir / f"{split_name}_set.csv", index=False)
        split_frames[split_name] = split

    assigned_indices = sorted(index for rows in assignments.values() for index in rows)
    if assigned_indices != list(range(len(frame))):
        raise AssertionError("Not every source row was assigned exactly once.")

    split_details = {}
    for split_name, split in split_frames.items():
        counts = split["label"].value_counts().to_dict()
        split_details[split_name] = {
            "records": len(split),
            "proportion": len(split) / len(frame),
            "label_counts": {str(label): int(counts.get(label, 0)) for label in LABEL_NAMES},
            "label_proportions": {
                str(label): counts.get(label, 0) / len(split) for label in LABEL_NAMES
            },
            "unique_nctId": int(split["nctId"].nunique()),
            "unique_PMID": int(split["PMID"].nunique()),
            "unique_claim": int(split["claim"].nunique()),
        }

    overlap = {
        field: identifier_overlap(split_frames, field) for field in GROUP_FIELDS
    }
    leakage_report = {
        "policy": (
            "Connected components over exact non-empty nctId, PMID, and claim "
            "identifiers. Every component is assigned to one split."
        ),
        "source_records": len(frame),
        "components": len(components),
        "largest_component_records": max(map(len, components)),
        "identifier_quality": identifier_quality,
        "source_exact_duplicate_rows": int(frame[source_columns].duplicated().sum()),
        "conflicts": conflict_summary,
        "cross_split_overlap": overlap,
        "all_nctId_isolated": all(value == 0 for value in overlap["nctId"].values()),
        "all_PMID_isolated": all(value == 0 for value in overlap["PMID"].values()),
        "all_claim_isolated": all(value == 0 for value in overlap["claim"].values()),
    }
    with (args.output_dir / "leakage_report.json").open("w", encoding="utf-8") as file:
        json.dump(leakage_report, file, indent=2)

    summary = {
        "random_seed": args.seed,
        "source_files": [str(path) for path in sorted(args.source_dir.glob("*_set.csv"))],
        "source_columns": source_columns,
        "grouping_policy": leakage_report["policy"],
        "target_proportions": SPLIT_FRACTIONS,
        "split_details": split_details,
        "source_records": len(frame),
        "output_records": sum(detail["records"] for detail in split_details.values()),
        "records_excluded": 0,
        "components": len(components),
        "identifier_quality": identifier_quality,
        "conflicts": conflict_summary,
        "cross_split_overlap": overlap,
        "validation": {
            "all_source_records_accounted_for": assigned_indices == list(range(len(frame))),
            "schemas_match_source": all(
                list(split.columns) == source_columns for split in split_frames.values()
            ),
            "no_output_exact_duplicates": all(
                not split.duplicated().any() for split in split_frames.values()
            ),
            "nctId_isolated": leakage_report["all_nctId_isolated"],
            "PMID_isolated": leakage_report["all_PMID_isolated"],
            "claim_isolated": leakage_report["all_claim_isolated"],
        },
    }
    with (args.output_dir / "split_summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
