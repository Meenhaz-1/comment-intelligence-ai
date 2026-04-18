import hashlib
import json
import os
import re

import pandas as pd


INPUT_PATH = "data/comments_sample.csv"
OUTPUT_PATH = "outputs/cleaned_comments.csv"


NOISE_TERMS = [
    "targetblank",
    "relnoopener",
    "noreferrer",
    "hrefhttps",
    "http",
    "www.",
    ".com",
    "ugchttps",
    "valor",
    "hack",
    "recovery",
    "recover",
    "crypto",
    "bitcoin",
    "telegram",
    "whatsapp",
    "wallet",
    "funds",
    "rootkits",
    "scam",
    "fraud",
]


def make_comment_id(recipe_id: str, created_at: str, comment_text: str) -> str:
    """
    Build a stable unique comment ID from recipe_id + created_at + comment_text.
    """
    raw = f"{recipe_id}|{created_at}|{comment_text}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """
    Clean comment text while keeping it readable enough for phrase extraction.
    """
    if pd.isna(text):
        return ""

    text = str(text)

    # Normalize apostrophes and quotes
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )

    # Normalize both real line breaks and escaped line breaks
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("\\n", " ").replace("\\r", " ")

    # Lowercase
    text = text.lower()

    # Remove urls
    text = re.sub(r"http\S+|www\.\S+", " ", text)

    # Remove html-like residue
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove known junk tokens
    for term in NOISE_TERMS:
        text = re.sub(re.escape(term), " ", text)

    # Keep letters, numbers, apostrophes, and spaces
    text = re.sub(r"[^a-z0-9'\s]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def detect_noise(clean_comment_text: str) -> bool:
    """
    Flag comments that are likely junk and should be excluded from analysis.
    """
    if not clean_comment_text:
        return True

    tokens = clean_comment_text.split()

    # Too short to be useful
    if len(tokens) <= 1:
        return True

    # If it is mostly obvious spam/recovery language
    noise_hits = sum(1 for term in NOISE_TERMS if term in clean_comment_text)
    if noise_hits >= 2:
        return True

    return False


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names so downstream code is stable.
    """
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("\ufeff", "", regex=False)
        .str.replace(r"\s+", "_", regex=True)
    )

    rename_map = {
        "comment": "comment_text",
        "storyid": "recipe_id",
        "createdat": "created_at",
        "authorid": "author_id",
        "displayname": "display_name",
        "willprepareagain": "will_prepare_again",
    }

    df = df.rename(columns=rename_map)
    return df


def parse_meta_data(meta_data_value):
    """
    Parse meta_data JSON safely.
    Returns a dict or empty dict if parsing fails.
    """
    if pd.isna(meta_data_value):
        return {}

    if isinstance(meta_data_value, dict):
        return meta_data_value

    try:
        return json.loads(str(meta_data_value))
    except Exception:
        return {}


def coalesce_series(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    """
    Fill missing values in primary with fallback.
    """
    primary_clean = primary.replace("", pd.NA)
    return primary_clean.combine_first(fallback)


def normalize_boolean(value):
    """
    Convert common true/false representations to Python booleans.
    Leave unknown values as-is.
    """
    if pd.isna(value):
        return value

    if isinstance(value, bool):
        return value

    value_str = str(value).strip().lower()

    if value_str == "true":
        return True
    if value_str == "false":
        return False

    return value


def load_existing_cleaned_comments(output_path: str) -> pd.DataFrame:
    """
    Load previously cleaned comments if the file exists.
    """
    if os.path.exists(output_path):
        return pd.read_csv(output_path, low_memory=False)

    return pd.DataFrame()


def apply_metadata_backfill(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse meta_data JSON and backfill useful top-level fields.
    """
    if "meta_data" not in df.columns:
        return df

    meta_parsed = df["meta_data"].apply(parse_meta_data)

    meta_display_name = meta_parsed.apply(lambda x: x.get("displayName"))
    meta_location = meta_parsed.apply(lambda x: x.get("location"))
    meta_will_prepare_again = meta_parsed.apply(lambda x: x.get("willPrepareAgain"))

    if "display_name" in df.columns:
        df["display_name"] = coalesce_series(df["display_name"], meta_display_name)
    else:
        df["display_name"] = meta_display_name

    if "location" in df.columns:
        df["location"] = coalesce_series(df["location"], meta_location)
    else:
        df["location"] = meta_location

    if "will_prepare_again" in df.columns:
        df["will_prepare_again"] = coalesce_series(
            df["will_prepare_again"], meta_will_prepare_again
        )
    else:
        df["will_prepare_again"] = meta_will_prepare_again

    return df


def order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Put the most important columns first.
    """
    preferred_order = [
        "comment_id",
        "recipe_id",
        "comment_text",
        "clean_comment_text",
        "is_noise",
        "created_at",
        "brand",
        "author_id",
        "display_name",
        "location",
        "will_prepare_again",
        "meta_data",
    ]

    ordered_cols = [col for col in preferred_order if col in df.columns]
    remaining_cols = [col for col in df.columns if col not in ordered_cols]
    return df[ordered_cols + remaining_cols]


def main():
    # Load latest raw data
    raw_df = pd.read_csv(INPUT_PATH, low_memory=False)
    raw_df = normalize_columns(raw_df)

    print("Columns found:", raw_df.columns.tolist())
    print(f"Raw comments loaded: {len(raw_df):,}")

    required_cols = ["recipe_id", "comment_text", "created_at"]
    missing_cols = [col for col in required_cols if col not in raw_df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {raw_df.columns.tolist()}"
        )

    # Parse meta_data and backfill useful fields
    raw_df = apply_metadata_backfill(raw_df)

    # Normalize boolean values
    if "will_prepare_again" in raw_df.columns:
        raw_df["will_prepare_again"] = raw_df["will_prepare_again"].apply(normalize_boolean)

    # Create comment_id before dedupe / incremental filtering
    raw_df["comment_id"] = raw_df.apply(
        lambda row: make_comment_id(
            recipe_id=str(row.get("recipe_id", "")),
            created_at=str(row.get("created_at", "")),
            comment_text=str(row.get("comment_text", "")),
        ),
        axis=1,
    )

    # Load existing cleaned comments
    existing_df = load_existing_cleaned_comments(OUTPUT_PATH)

    if not existing_df.empty:
        print(f"Existing cleaned comments: {len(existing_df):,}")

        if "comment_id" not in existing_df.columns:
            raise ValueError(
                f"{OUTPUT_PATH} exists but does not contain 'comment_id'. "
                "Delete it and rerun a full rebuild."
            )

        existing_comment_ids = set(existing_df["comment_id"].astype(str))
        new_df = raw_df[~raw_df["comment_id"].astype(str).isin(existing_comment_ids)].copy()
    else:
        print("Existing cleaned comments: 0")
        new_df = raw_df.copy()

    print(f"New comments to process: {len(new_df):,}")

    if new_df.empty:
        print("No new comments found. cleaned_comments.csv is already up to date.")
        return

    # Clean only new comments
    new_df["clean_comment_text"] = new_df["comment_text"].apply(clean_text)
    new_df["is_noise"] = new_df["clean_comment_text"].apply(detect_noise)

    # Order columns before append
    new_df = order_columns(new_df)

    # Append to existing cleaned file
    if not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df.copy()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    final_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved cleaned comments to {OUTPUT_PATH}")
    print(f"Total cleaned comments after update: {len(final_df):,}")
    print("\nNewly processed sample:")
    print(new_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()