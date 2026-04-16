from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/comments_sample.csv")
OUTPUT_PATH = Path("outputs/cleaned_comments.csv")


def parse_metadata(value: object) -> dict:
    """Parse the `meta data` JSON column safely."""
    if pd.isna(value):
        return {}

    text = str(value).strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def first_non_empty(*values: object) -> str | None:
    """Return the first non-empty value."""
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def load_and_clean_comments(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Normalize column names
    df = df.rename(
        columns={
            "Comment": "comment_text",
            "createdAt": "created_at",
            "storyID": "recipe_id",
            "Brand": "brand",
            "authorID": "author_id",
            "meta data": "meta_data",
            "location": "location",
            "displayName": "display_name",
            "willPrepareAgain": "will_prepare_again",
        }
    )

    required_cols = ["comment_text", "recipe_id"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Parse metadata JSON
    df["meta_parsed"] = df["meta_data"].apply(parse_metadata) if "meta_data" in df.columns else [{}] * len(df)

    df["meta_display_name"] = df["meta_parsed"].apply(lambda x: x.get("displayName"))
    df["meta_location"] = df["meta_parsed"].apply(lambda x: x.get("location"))
    df["meta_will_prepare_again"] = df["meta_parsed"].apply(lambda x: x.get("willPrepareAgain"))

    # Merge duplicate / messy fields
    df["display_name"] = df.apply(
        lambda row: first_non_empty(row.get("display_name"), row.get("meta_display_name")),
        axis=1,
    )
    df["location"] = df.apply(
        lambda row: first_non_empty(row.get("location"), row.get("meta_location")),
        axis=1,
    )
    df["will_prepare_again"] = df.apply(
        lambda row: row.get("will_prepare_again")
        if pd.notna(row.get("will_prepare_again"))
        else row.get("meta_will_prepare_again"),
        axis=1,
    )

    # Basic cleanup
    df["comment_text"] = df["comment_text"].astype(str).str.strip()
    df["recipe_id"] = df["recipe_id"].astype(str).str.strip()
    df["brand"] = df["brand"].astype(str).str.strip() if "brand" in df.columns else None
    df["author_id"] = df["author_id"].astype(str).str.strip() if "author_id" in df.columns else None

    df = df[df["comment_text"] != ""].copy()
    df = df[df["recipe_id"] != ""].copy()

    # Parse timestamp
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    # Final clean output
    clean_df = df[
        [
            "recipe_id",
            "comment_text",
            "created_at",
            "brand",
            "author_id",
            "display_name",
            "location",
            "will_prepare_again",
        ]
    ].copy()

    return clean_df


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    clean_df = load_and_clean_comments(INPUT_PATH)
    clean_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Loaded rows: {len(clean_df)}")
    print(f"Unique recipes: {clean_df['recipe_id'].nunique()}")
    print(f"Output written to: {OUTPUT_PATH}")
    print("\nSample:")
    print(clean_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
