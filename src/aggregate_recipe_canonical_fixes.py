#!/usr/bin/env python3
"""
Aggregate mapped raw fix phrases to recipe-level canonical fix signals.

Purpose
-------
Convert phrase-level fix mappings into recipe-level editorial signals.

Input
-----
outputs/raw_fix_phrases_mapped_with_rules.csv

Output
------
outputs/recipe_canonical_fixes.csv

Why this exists
---------------
Phrase-level mapping is intermediate.
What the product and decision layer need is one row per recipe with:
- top canonical fixes
- top fix families
- mapped fix counts
- confidence signals
"""

from __future__ import annotations

import pandas as pd

INPUT_PATH = "outputs/raw_fix_phrases_mapped_with_rules.csv"
OUTPUT_PATH = "outputs/recipe_canonical_fixes.csv"


def normalize_text(text: object) -> str:
    if pd.isna(text):
        return ""
    return " ".join(str(text).strip().split())


def top_n_counts(df: pd.DataFrame, group_col: str, value_col: str, n: int = 2) -> pd.DataFrame:
    counts = (
        df.groupby([group_col, value_col], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values([group_col, "count", value_col], ascending=[True, False, True])
    )

    counts["rank"] = counts.groupby(group_col)["count"].rank(method="first", ascending=False)

    out = counts[counts["rank"] <= n].copy()
    out["rank"] = out["rank"].astype(int)

    wide = out.pivot(index=group_col, columns="rank", values=value_col)
    wide.columns = [f"top_{value_col}_{col}" for col in wide.columns]

    wide_counts = out.pivot(index=group_col, columns="rank", values="count")
    wide_counts.columns = [f"top_{value_col}_{col}_count" for col in wide_counts.columns]

    return wide.join(wide_counts, how="outer").reset_index()


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    required_cols = [
        "recipe_id",
        "canonical_fix",
        "fix_family",
        "mapping_status",
        "is_mapped",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["canonical_fix"] = df["canonical_fix"].map(normalize_text)
    df["fix_family"] = df["fix_family"].map(normalize_text)
    df["mapping_status"] = df["mapping_status"].map(normalize_text)

    mapped = df[df["is_mapped"] == True].copy()

    if mapped.empty:
        raise ValueError("No mapped rows found. Check upstream mapping outputs.")

    summary = (
        mapped.groupby("recipe_id")
        .agg(
            mapped_fix_rows=("recipe_id", "size"),
            unique_canonical_fixes=("canonical_fix", "nunique"),
            unique_fix_families=("fix_family", "nunique"),
            exact_mapped_rows=("mapping_status", lambda s: (s == "mapped_exact").sum()),
            rule_mapped_rows=("mapping_status", lambda s: (s == "mapped_rule").sum()),
        )
        .reset_index()
    )

    top_fixes = top_n_counts(mapped, "recipe_id", "canonical_fix", n=2)
    top_families = top_n_counts(mapped, "recipe_id", "fix_family", n=2)

    out = summary.merge(top_fixes, on="recipe_id", how="left").merge(top_families, on="recipe_id", how="left")

    # Simple confidence heuristic
    def confidence(row):
        if row["mapped_fix_rows"] >= 3 and row["unique_canonical_fixes"] <= 2:
            return "high"
        if row["mapped_fix_rows"] >= 2:
            return "medium"
        return "low"

    out["fix_confidence"] = out.apply(confidence, axis=1)

    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved recipe-level fix output to {OUTPUT_PATH}")
    print(f"Recipes with mapped fixes: {len(out)}")
    print("\nFix confidence breakdown:")
    print(out["fix_confidence"].value_counts(dropna=False))


if __name__ == "__main__":
    main()