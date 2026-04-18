import pandas as pd


INPUT_PATH = "outputs/recipe_intelligence_with_summary.csv"
OUTPUT_PATH = "outputs/recipe_editorial_mvp.csv"


def main():
    df = pd.read_csv(INPUT_PATH)

    # Select only columns that matter for editorial decisions
    mvp_cols = [
        "title",
        "classification",
        "opportunity_score",
        "total_comments",
        "pct_friction",
        "pct_modification",
        "top_friction_phrase_1",
        "top_modification_phrase_1",
        "summary",
    ]

    # Keep only existing columns
    mvp_cols = [col for col in mvp_cols if col in df.columns]

    mvp_df = df[mvp_cols].copy()

    # Remove low-signal recipes from the editorial priority view
    if "classification" in mvp_df.columns:
        mvp_df = mvp_df[mvp_df["classification"] != "Low Signal"].copy()

    # Fill missing issue / fix phrases with clearer fallback labels
    if "top_friction_phrase_1" in mvp_df.columns:
        mvp_df["top_friction_phrase_1"] = mvp_df["top_friction_phrase_1"].fillna("multiple issues")

    if "top_modification_phrase_1" in mvp_df.columns:
        mvp_df["top_modification_phrase_1"] = mvp_df["top_modification_phrase_1"].fillna("varied modifications")

    # Sort by priority
    if "opportunity_score" in mvp_df.columns:
        mvp_df = mvp_df.sort_values("opportunity_score", ascending=False)

    # Save file
    mvp_df.to_csv(OUTPUT_PATH, index=False)

    # Print preview
    print("\nTop 10 Recipes (Editorial View):\n")
    print(mvp_df.head(10).to_string(index=False))

    print(f"\nSaved file: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()