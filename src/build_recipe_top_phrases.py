import os

import pandas as pd


INPUT_PATH = "outputs/recipe_phrases.csv"
OUTPUT_PATH = "outputs/recipe_top_phrases.csv"

TOP_N = 5


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = [
        "recipe_id",
        "phrase",
        "phrase_word_count",
        "total_count",
        "unique_comment_count",
        "recipe_comment_count",
        "comment_coverage_pct",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {df.columns.tolist()}"
        )

    print(f"Recipe phrase rows loaded: {len(df):,}")
    print(f"Unique recipes found: {df['recipe_id'].nunique():,}")

    # Sort phrases within each recipe by strength
    df = df.sort_values(
        by=[
            "recipe_id",
            "unique_comment_count",
            "comment_coverage_pct",
            "total_count",
            "phrase_word_count",
            "phrase",
        ],
        ascending=[True, False, False, False, False, True],
    ).copy()

    # Rank phrases within each recipe
    df["phrase_rank"] = df.groupby("recipe_id").cumcount() + 1

    # Keep only top N phrases per recipe
    top_df = df[df["phrase_rank"] <= TOP_N].copy()

    preferred_order = [
        "recipe_id",
        "phrase_rank",
        "phrase",
        "phrase_word_count",
        "total_count",
        "unique_comment_count",
        "recipe_comment_count",
        "comment_coverage_pct",
    ]

    ordered_cols = [col for col in preferred_order if col in top_df.columns]
    remaining_cols = [col for col in top_df.columns if col not in ordered_cols]
    top_df = top_df[ordered_cols + remaining_cols]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    top_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved recipe top phrases to {OUTPUT_PATH}")
    print(f"Total recipe-phrase rows kept: {len(top_df):,}")
    print(f"Total recipes with top phrases: {top_df['recipe_id'].nunique():,}")

    print("\nSample:")
    print(top_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()