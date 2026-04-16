from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("outputs/recipe_insights.csv")


def parse_list_column(value: object) -> list[str]:
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        return []
    return []


def explode_column(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    temp = df.copy()
    temp[col_name] = temp[col_name].apply(parse_list_column)
    temp = temp.explode(col_name)
    temp = temp[temp[col_name].notna()]
    temp[col_name] = temp[col_name].astype(str).str.strip()
    temp = temp[temp[col_name] != ""]
    return temp


def main() -> None:
    df = pd.read_csv(INPUT_PATH)

    print("\nSentiment distribution:")
    print(df["sentiment"].value_counts(dropna=False).to_string())

    print("\nWould-make-again distribution:")
    print(df["would_make_again_signal"].value_counts(dropna=False).to_string())

    for col in ["complaints", "improvements", "substitutions"]:
        exploded = explode_column(df, col)
        print(f"\nTop {col}:")
        if len(exploded) == 0:
            print("No data")
        else:
            print(exploded[col].value_counts().head(15).to_string())


if __name__ == "__main__":
    main()