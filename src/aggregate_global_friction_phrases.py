import pandas as pd

INPUT_PATH = "outputs/recipe_behavioral_phrases.csv"
OUTPUT_PATH = "outputs/global_friction_phrases_labeled.csv"


def get_initial_mapping():
    """
    Pre-fill obvious mappings based on current dataset.
    This is NOT exhaustive — just accelerates manual work.
    """
    return {
        # Flavor
        "bland": ("under-seasoned", "flavor", 1),
        "too salty": ("over-seasoned", "flavor", 1),
        "too sweet": ("too sweet", "flavor", 1),
        "too much sugar": ("too sweet", "flavor", 1),
        "too spicy": ("too spicy", "flavor", 1),

        # Fat
        "too oily": ("too oily", "fat", 1),

        # Moisture
        "too dry": ("too dry", "moisture", 1),
        "too watery": ("too wet", "moisture", 1),
        "too wet": ("too wet", "moisture", 1),
        "too thick": ("too thick", "moisture", 1),

        # Texture
        "mushy": ("mushy texture", "texture", 1),
        "soggy": ("mushy texture", "texture", 1),
        "rubbery": ("rubbery texture", "texture", 1),
        "grainy": ("grainy texture", "texture", 1),

        # Cooking
        "burnt": ("burnt", "cooking", 1),
        "overcooked": ("overcooked", "cooking", 1),
        "undercooked": ("undercooked", "cooking", 1),

        # Structure
        "fell apart": ("structural failure", "structure", 1),
        "curdled": ("structural failure", "structure", 1),

        # Generic
        "didn't work": ("recipe failed", "generic", 0),
    }


def main():
    # Load data
    df = pd.read_csv(INPUT_PATH)

    # Step 1: Filter friction phrases
    friction_df = df[df["category"] == "friction"].copy()

    # Step 2: Aggregate globally
    agg = (
        friction_df
        .groupby("phrase")
        .agg(
            total_count=("total_count", "sum"),
            unique_comment_count=("unique_comment_count", "sum"),
            recipe_count=("recipe_id", "nunique")
        )
        .reset_index()
    )

    # Step 3: Rank phrases
    agg = agg.sort_values(
        by=["recipe_count", "unique_comment_count", "total_count"],
        ascending=False
    )

    # Step 4: Add taxonomy columns
    agg["normalized_issue"] = ""
    agg["issue_family"] = ""
    agg["keep_flag"] = ""

    # Step 5: Apply initial mapping
    mapping = get_initial_mapping()

    for idx, row in agg.iterrows():
        phrase = row["phrase"]
        if phrase in mapping:
            norm_issue, family, keep = mapping[phrase]
            agg.at[idx, "normalized_issue"] = norm_issue
            agg.at[idx, "issue_family"] = family
            agg.at[idx, "keep_flag"] = keep

    # Step 6: Save output
    agg.to_csv(OUTPUT_PATH, index=False)

    # Step 7: Preview
    print("\nTop 20 Friction Phrases (with initial labels):\n")
    print(agg.head(20))


if __name__ == "__main__":
    main()