from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT_DIR / "outputs" / "recipe_insights.csv"


def parse_list(value):
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        return []
    return []


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Could not find input file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    required_columns = {
        "recipe_id",
        "comment_count",
        "sentiment",
        "would_make_again_signal",
        "complaints",
    }
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df["complaints_list"] = df["complaints"].apply(parse_list)
    df["complaint_count"] = df["complaints_list"].apply(len)

    print("\nAverage complaint count by sentiment:")
    print(df.groupby("sentiment")["complaint_count"].mean().sort_values(ascending=False).to_string())

    print("\nAverage complaint count by would_make_again_signal:")
    print(df.groupby("would_make_again_signal")["complaint_count"].mean().sort_values(ascending=False).to_string())

    print("\nRecipes with highest complaint count:")
    cols = ["recipe_id", "comment_count", "sentiment", "would_make_again_signal", "complaints"]
    print(df.sort_values(by="complaint_count", ascending=False)[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
