"""Create a non-destructive diagnostic report for conflicting claim labels."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


LABEL_NAMES = {0: "inconclusive", 1: "evidence", 2: "NEI"}


def analyze(conflicts_path: Path, output_path: Path) -> None:
    data = pd.read_csv(conflicts_path, dtype={"nctId": "string", "PMID": "string"})
    data["label_name"] = data["label"].map(LABEL_NAMES)
    data["evidence_key"] = (
        data["article_title"].fillna("").astype(str)
        + "\n"
        + data["article_abstract"].fillna("").astype(str)
    )

    conflict_claims = data.groupby("claim")["label"].nunique()
    data = data[data["claim"].isin(conflict_claims[conflict_claims > 1].index)].copy()
    claims = []
    for claim, group in data.groupby("claim", sort=True):
        distinct_labels = sorted(int(label) for label in group["label"].unique())
        same_evidence_label_conflict = (
            group.groupby("evidence_key")["label"].nunique().max() > 1
        )
        same_pmid_label_conflict = group.groupby("PMID")["label"].nunique().max() > 1
        evidence_variants = int(group["evidence_key"].nunique())
        if same_pmid_label_conflict:
            classification = "likely_annotation_inconsistency"
        elif evidence_variants > 1:
            classification = "context_dependent_candidate"
        else:
            classification = "requires_human_review"
        claims.append(
            {
                "claim": claim,
                "labels": distinct_labels,
                "label_names": [LABEL_NAMES[label] for label in distinct_labels],
                "record_count": len(group),
                "pmids": sorted(group["PMID"].dropna().astype(str).unique()),
                "nct_ids": sorted(group["nctId"].dropna().astype(str).unique()),
                "evidence_text_variants": evidence_variants,
                "evidence_text_differs": evidence_variants > 1,
                "same_pmid_has_conflicting_labels": bool(same_pmid_label_conflict),
                "same_evidence_text_has_conflicting_labels": bool(
                    same_evidence_label_conflict
                ),
                "records": [
                    {
                        "index": int(row["index"]),
                        "label": int(row["label"]),
                        "label_name": row["label_name"],
                        "PMID": str(row["PMID"]),
                        "nctId": str(row["nctId"]),
                        "article_title": row["article_title"],
                        "article_abstract": row["article_abstract"],
                        "source_file": row.get("_source_file"),
                    }
                    for _, row in group.iterrows()
                ],
                "review_classification": classification,
            }
        )

    report = {
        "source": str(conflicts_path),
        "policy": {
            "labels_are_not_changed": True,
            "records_are_not_removed": True,
            "context_dependent_candidate": (
                "Same claim with different evidence text, PMID, or trial context; "
                "review whether the evidence supports different labels."
            ),
            "likely_annotation_inconsistency": (
                "Same claim and PMID have different labels; review source-label "
                "generation and publication mapping before relabeling."
            ),
            "requires_human_review": (
                "No automatic conclusion is made where context is insufficient."
            ),
        },
        "aggregate": {
            "conflicting_claims": len(claims),
            "conflicting_records": len(data),
            "distinct_pmids": int(data["PMID"].nunique()),
            "distinct_nct_ids": int(data["nctId"].nunique()),
            "claims_with_different_evidence_text": sum(
                item["evidence_text_differs"] for item in claims
            ),
            "claims_with_same_pmid_conflicting_labels": sum(
                item["same_pmid_has_conflicting_labels"] for item in claims
            ),
            "claims_with_same_evidence_text_conflicting_labels": sum(
                item["same_evidence_text_has_conflicting_labels"] for item in claims
            ),
            "review_classification_counts": pd.Series(
                item["review_classification"] for item in claims
            ).value_counts().to_dict(),
            "label_pair_counts": data.groupby("claim")["label_name"]
            .apply(lambda values: " | ".join(sorted(set(values))))
            .value_counts()
            .to_dict(),
        },
        "representative_examples": claims[:10],
        "claims": claims,
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    root = Path("data/processed/grouped_splits_v1")
    analyze(root / "label_conflicts.csv", root / "label_conflict_analysis.json")
