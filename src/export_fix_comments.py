#!/usr/bin/env python3

from __future__ import annotations

import pandas as pd

INPUT_PATH = "outputs/evidence_candidates.csv"
RAW_OUTPUT_PATH = "outputs/fix_comments_raw.csv"
REVIEW_OUTPUT_PATH = "outputs/fix_comments_review.csv"

KEEP_EVIDENCE_TYPES = {"problem_solving_fix", "mixed"}


def clean_text(value: str) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    required_cols = [
        "recipe_id",
        "comment_id",
        "evidence_type",
        "evidence_score",
        "rank_within_recipe_type",
        "trimmed_comment",
        "clean_comment_text",
        "signal_friction",
        "signal_modification",
        "signal_substitution",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df[df["evidence_type"].isin(KEEP_EVIDENCE_TYPES)].copy()

    out["trimmed_comment"] = out["trimmed_comment"].map(clean_text)
    out["clean_comment_text"] = out["clean_comment_text"].map(clean_text)

    # Keep only rows with actual modification/substitution behavior
    out = out[
        (out["signal_modification"] == 1) | (out["signal_substitution"] == 1)
    ].copy()

    out = out.sort_values(
        ["evidence_type", "evidence_score", "rank_within_recipe_type"],
        ascending=[True, False, True],
    )

    raw_cols = [
        "recipe_id",
        "comment_id",
        "evidence_type",
        "evidence_score",
        "rank_within_recipe_type",
        "trimmed_comment",
        "clean_comment_text",
        "signal_friction",
        "signal_modification",
        "signal_substitution",
    ]

    raw_out = out[raw_cols].copy()
    raw_out.to_csv(RAW_OUTPUT_PATH, index=False)

    review = (
        raw_out.groupby("evidence_type", dropna=False)
        .agg(
            total_rows=("comment_id", "size"),
            unique_recipes=("recipe_id", "nunique"),
            avg_evidence_score=("evidence_score", "mean"),
            sample_comment=("trimmed_comment", "first"),
        )
        .reset_index()
        .sort_values("total_rows", ascending=False)
    )

    review.to_csv(REVIEW_OUTPUT_PATH, index=False)

    print(f"Saved raw fix comments to {RAW_OUTPUT_PATH}")
    print(f"Saved review table to {REVIEW_OUTPUT_PATH}")
    print(f"Total rows: {len(raw_out)}")
    print(f"Unique recipes: {raw_out['recipe_id'].nunique()}")


if __name__ == "__main__":
    main()