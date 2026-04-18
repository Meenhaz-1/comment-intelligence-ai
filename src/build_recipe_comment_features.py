import os

import pandas as pd


SIGNAL_SUMMARY_PATH = "outputs/recipe_signal_summary.csv"
TOP_PHRASES_WIDE_PATH = "outputs/recipe_top_phrases_wide.csv"
OUTPUT_PATH = "outputs/recipe_comment_features.csv"


def main():
    signal_df = pd.read_csv(SIGNAL_SUMMARY_PATH, low_memory=False)
    phrase_df = pd.read_csv(TOP_PHRASES_WIDE_PATH, low_memory=False)

    if "recipe_id" not in signal_df.columns:
        raise ValueError("recipe_id missing from recipe_signal_summary.csv")

    if "recipe_id" not in phrase_df.columns:
        raise ValueError("recipe_id missing from recipe_top_phrases_wide.csv")

    print(f"Signal summary rows loaded: {len(signal_df):,}")
    print(f"Top phrases wide rows loaded: {len(phrase_df):,}")

    out = signal_df.merge(phrase_df, on="recipe_id", how="left")

    print(f"Merged recipe rows: {len(out):,}")

    preferred_order = [
        "recipe_id",
        "total_comments",
        "eligible_comments",
        "noise_comments",
        "signal_any_behavior_comments",
        "signal_made_comments",
        "signal_modification_comments",
        "signal_substitution_comments",
        "signal_positive_comments",
        "signal_friction_comments",
        "signal_repeat_intent_comments",
        "pct_signal_any_behavior",
        "pct_signal_made",
        "pct_signal_modification",
        "pct_signal_substitution",
        "pct_signal_positive",
        "pct_signal_friction",
        "pct_signal_repeat_intent",
        "avg_total_signal_count",
        "will_prepare_again_true_count",
        "will_prepare_again_false_count",
        "will_prepare_again_known_count",
        "pct_will_prepare_again_true",
        "top_phrase_1",
        "top_phrase_1_coverage_pct",
        "top_phrase_1_unique_comment_count",
        "top_phrase_2",
        "top_phrase_2_coverage_pct",
        "top_phrase_2_unique_comment_count",
        "top_phrase_3",
        "top_phrase_3_coverage_pct",
        "top_phrase_3_unique_comment_count",
        "top_phrase_4",
        "top_phrase_4_coverage_pct",
        "top_phrase_4_unique_comment_count",
        "top_phrase_5",
        "top_phrase_5_coverage_pct",
        "top_phrase_5_unique_comment_count",
    ]

    ordered_cols = [col for col in preferred_order if col in out.columns]
    remaining_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + remaining_cols]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved recipe comment features to {OUTPUT_PATH}")
    print(f"Total recipes in final file: {len(out):,}")

    print("\nSample:")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()