#!/usr/bin/env python3
"""
Build a manual mapping template for raw fix phrases.

Purpose
-------
Takes the aggregated raw fix phrase review table and prepares a
human-labeling sheet for canonical fix mapping.

Why this exists
---------------
Your raw fix extractor gets you to a useful review layer, but not to
stable editorial meaning. This script creates the table you will use to map:

raw_fix_phrase -> canonical_fix -> fix_family

This is the bridge between extraction and canonicalization.

Input
-----
outputs/raw_fix_phrases_review.csv

Output
------
outputs/fix_phrase_mapping_template.csv
"""

from __future__ import annotations

import pandas as pd

INPUT_PATH = "outputs/raw_fix_phrases_review.csv"
OUTPUT_PATH = "outputs/fix_phrase_mapping_template.csv"


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    required_cols = [
        "raw_fix_phrase",
        "trigger_verb",
        "total_rows",
        "unique_recipes",
        "avg_evidence_score",
        "sample_source_text",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df[required_cols].copy()

    # Manual labeling columns
    out["canonical_fix"] = ""
    out["fix_family"] = ""
    out["keep_flag"] = ""
    out["notes"] = ""

    # Sort highest-impact phrases first for faster review
    out = out.sort_values(
        ["unique_recipes", "total_rows", "avg_evidence_score", "raw_fix_phrase"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved mapping template to {OUTPUT_PATH}")
    print(f"Rows: {len(out)}")


if __name__ == "__main__":
    main()