import pandas as pd

INPUT_PATH = "outputs/evidence_candidates.csv"


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    print(f"Loaded {len(df):,} rows from {INPUT_PATH}\n")

    print("Evidence type counts:")
    print(df["evidence_type"].value_counts(dropna=False))

    print("\nRows per recipe summary:")
    print(df.groupby("recipe_id").size().describe())

    for evidence_type in ["issue", "problem_solving_fix", "adaptation", "mixed"]:
        print(f"\n{'=' * 80}")
        print(evidence_type.upper())
        print(f"{'=' * 80}")

        subset = df[df["evidence_type"] == evidence_type].copy()

        if subset.empty:
            print("No rows found.")
            continue

        cols_to_show = ["trimmed_comment"]
        if "evidence_score" in subset.columns:
            cols_to_show.insert(0, "evidence_score")

        print(subset[cols_to_show].head(10).to_string(index=False))

    print(f"\n{'=' * 80}")
    print("TOP RECIPES BY EVIDENCE ROW COUNT")
    print(f"{'=' * 80}")
    print(df.groupby("recipe_id").size().sort_values(ascending=False).head(20).to_string())


if __name__ == "__main__":
    main()