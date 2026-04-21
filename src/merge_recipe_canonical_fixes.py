#!/usr/bin/env python3

"""
Merge recipe-level canonical fixes into main recipe intelligence table.
"""

from __future__ import annotations

import pandas as pd


MAIN_PATH = "outputs/editorial_intelligence.csv"  # change if needed
FIX_PATH = "outputs/recipe_canonical_fixes.csv"
OUTPUT_PATH = "outputs/editorial_intelligence_with_fixes.csv"


def main() -> None:
    main_df = pd.read_csv(MAIN_PATH)
    fix_df = pd.read_csv(FIX_PATH)

    # sanity check
    if "recipe_id" not in main_df.columns:
        raise ValueError("recipe_id missing in main table")

    if "recipe_id" not in fix_df.columns:
        raise ValueError("recipe_id missing in fix table")

    # drop duplicate columns from fix table if needed
    fix_cols = [
        "recipe_id",
        "top_canonical_fix_1",
        "top_canonical_fix_2",
        "top_fix_family_1",
        "top_fix_family_2",
        "mapped_fix_rows",
        "unique_canonical_fixes",
        "unique_fix_families",
        "exact_mapped_rows",
        "rule_mapped_rows",
        "fix_confidence",
    ]

    fix_df = fix_df[[c for c in fix_cols if c in fix_df.columns]]

    # merge
    merged = main_df.merge(
        fix_df,
        on="recipe_id",
        how="left"
    )

    # fill nulls for clarity
    merged["fix_confidence"] = merged["fix_confidence"].fillna("none")
    merged["mapped_fix_rows"] = merged["mapped_fix_rows"].fillna(0)

    merged.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved merged table to {OUTPUT_PATH}")
    print(f"Rows: {len(merged)}")

    print("\nFix coverage:")
    print(merged["fix_confidence"].value_counts(dropna=False))


if __name__ == "__main__":
    main()