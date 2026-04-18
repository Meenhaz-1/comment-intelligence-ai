import os

import pandas as pd


INPUT_PATH = "outputs/recipe_top_phrases.csv"
OUTPUT_PATH = "outputs/recipe_top_phrases_wide.csv"

TOP_N = 5


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = ["recipe_id", "phrase_rank", "phrase"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {df.columns.tolist()}"
        )

    print(f"Top phrase rows loaded: {len(df):,}")
    print(f"Unique recipes found: {df['recipe_id'].nunique():,}")

    # Keep only expected top ranks
    df = df[df["phrase_rank"].between(1, TOP_N)].copy()

    # Pivot phrases wide
    phrase_wide = (
        df.pivot_table(
            index="recipe_id",
            columns="phrase_rank",
            values="phrase",
            aggfunc="first",
        )
        .rename(columns=lambda x: f"top_phrase_{int(x)}")
        .reset_index()
    )

    # Optional: also pivot coverage
    coverage_wide = (
        df.pivot_table(
            index="recipe_id",
            columns="phrase_rank",
            values="comment_coverage_pct",
            aggfunc="first",
        )
        .rename(columns=lambda x: f"top_phrase_{int(x)}_coverage_pct")
        .reset_index()
    )

    # Optional: also pivot unique comment count
    unique_comment_wide = (
        df.pivot_table(
            index="recipe_id",
            columns="phrase_rank",
            values="unique_comment_count",
            aggfunc="first",
        )
        .rename(columns=lambda x: f"top_phrase_{int(x)}_unique_comment_count")
        .reset_index()
    )

    # Merge into one recipe-level table
    out = phrase_wide.merge(coverage_wide, on="recipe_id", how="left")
    out = out.merge(unique_comment_wide, on="recipe_id", how="left")

    preferred_order = ["recipe_id"]
    for i in range(1, TOP_N + 1):
        preferred_order.extend(
            [
                f"top_phrase_{i}",
                f"top_phrase_{i}_coverage_pct",
                f"top_phrase_{i}_unique_comment_count",
            ]
        )

    ordered_cols = [col for col in preferred_order if col in out.columns]
    remaining_cols = [col for col in out.columns if col not in ordered_cols]
    out = out[ordered_cols + remaining_cols]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved wide recipe top phrases to {OUTPUT_PATH}")
    print(f"Total recipes in wide file: {len(out):,}")

    print("\nSample:")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    ma