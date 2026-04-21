#!/usr/bin/env python3
"""
Export rows where fix signals changed recommended_edit.

Purpose
-------
Create a small, high-signal review dataset to inspect how fix evidence
impacts recommendations.

Input
-----
outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv

Output
------
outputs/fix_aware_review_sample.csv
"""

from __future__ import annotations

import pandas as pd


INPUT_PATH = "outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv"
OUTPUT_PATH = "outputs/fix_aware_review_sample.csv"


def main() -> None:
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    # Only rows where fix logic was used
    review = df[
        df["recommended_edit_source"].isin(
            ["issue_fix_blend_medium", "fix_direct_high"]
        )
    ].copy()

    # Select useful columns for review
    cols = [
        "recipe_id",
        "display_issue",
        "recommended_edit",
        "recommended_edit_v2",
        "recommended_edit_source",
        "top_canonical_fix_1",
        "top_canonical_fix_2",
        "top_fix_family_1",
        "fix_confidence",
        "fix_signal_summary",
        "opportunity_score" if "opportunity_score" in df.columns else None,
    ]

    cols = [c for c in cols if c is not None and c in review.columns]

    review = review[cols]

    # Sort for easier inspection
    review = review.sort_values(
        ["fix_confidence", "recommended_edit_source"],
        ascending=[False, True],
    )

    review.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved review sample to {OUTPUT_PATH}")
    print(f"Rows: {len(review)}")

    print("\nBreakdown:")
    print(review["recommended_edit_source"].value_counts())


if __name__ == "__main__":
    main()