#!/usr/bin/env python3

from __future__ import annotations

import pandas as pd

INPUT_PATH = "outputs/evidence_candidates.csv"
RAW_OUTPUT_PATH = "outputs/raw_fix_phrases.csv"
REVIEW_OUTPUT_PATH = "outputs/raw_fix_phrase_review.csv"


FIX_CATEGORIES = {"problem_solving_fix", "adaptation", "mixed"}


def clean_text(value: str) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    # Adjust these if your actual schema differs
    category_col = "category"
    fix_col = "phrase"            # change if the extracted fix phrase column has a different name
    comment_col = "comment_text"  # change if needed
    recipe_col = "recipe_id"

    out = df[df[category_col].isin(FIX_CATEGORIES)].copy()
    out[fix_col] = out[fix_col].map(clean_text)
    out[comment_col] = out[comment_col].map(clean_text)

    out = out[out[fix_col] != ""].copy()

    out["raw_fix_phrase"] = out[fix_col]
    out["source_file"] = INPUT_PATH

    raw_cols = [
        recipe_col,
        category_col,
        "raw_fix_phrase",
        comment_col,
        "source_file",
    ]

    existing_raw_cols = [c for c in raw_cols if c in out.columns]
    raw_out = out[existing_raw_cols].copy()
    raw_out.to_csv(RAW_OUTPUT_PATH, index=False)

    review = (
        raw_out.groupby("raw_fix_phrase", dropna=False)
        .agg(
            total_rows=("raw_fix_phrase", "size"),
            unique_recipes=(recipe_col, "nunique"),
            sample_comment=(comment_col, "first"),
        )
        .reset_index()
        .sort_values(["unique_recipes", "total_rows", "raw_fix_phrase"], ascending=[False, False, True])
    )

    review.to_csv(REVIEW_OUTPUT_PATH, index=False)

    print(f"Saved raw fix rows to {RAW_OUTPUT_PATH}")
    print(f"Saved grouped review table to {REVIEW_OUTPUT_PATH}")
    print(f"Total raw fix rows: {len(raw_out)}")
    print(f"Unique raw fix phrases: {review['raw_fix_phrase'].nunique()}")


if __name__ == "__main__":
    main()