from __future__ import annotations

from pathlib import Path

import pandas as pd

from load_data import load_recipe_data, load_recipe_save


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "recipe_master.csv"
KEYWORD_SUMMARY_PATH = ROOT_DIR / "outputs" / "recipe_keyword_summary.csv"


def clean_recipe_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean recipe metadata + pageviews to one row per content_id."""
    df = df.copy()

    df = df.rename(
        columns={
            "app_id": "brand",
            "content_title": "title",
            "count(DISTINCTweb_page.id)": "page_views",
            "clean_url": "url",
            "onsite_keywords": "tags",
        }
    )

    df["page_views"] = pd.to_numeric(df["page_views"], errors="coerce").fillna(0)
    df["has_url"] = df["url"].notna().astype(int)

    # Prefer rows with a real URL, then higher page views
    df = df.sort_values(
        by=["content_id", "has_url", "page_views"],
        ascending=[True, False, False],
    )

    df = df.drop_duplicates(subset="content_id", keep="first")

    df = df[
        [
            "content_id",
            "brand",
            "title",
            "url",
            "author_name",
            "author_id",
            "tags",
            "page_views",
        ]
    ].copy()

    return df


def clean_recipe_save(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate save data to one row per content_id."""
    df = df.copy()

    df = df.rename(
        columns={
            "content_title": "save_title",
            "content_url": "save_url",
        }
    )

    for col in ["save_sessions_app", "save_sessions_web", "total_save_sessions"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    recipe_save = (
        df.groupby("content_id", as_index=False)
        .agg(
            {
                "save_title": "first",
                "save_url": "first",
                "save_sessions_app": "max",
                "save_sessions_web": "sum",
                "total_save_sessions": "sum",
            }
        )
    )

    recipe_save["total_save_sessions_clean"] = (
        recipe_save["save_sessions_app"] + recipe_save["save_sessions_web"]
    )

    return recipe_save


def load_recipe_keyword_summary(path: Path = KEYWORD_SUMMARY_PATH) -> pd.DataFrame:
    """Load optional per-recipe keyword summary."""
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "recipe_id",
                "top_keywords",
                "top_phrases",
                "keyword_buckets",
                "top_keywords_with_counts",
            ]
        )

    df = pd.read_csv(path)
    return df


def main() -> None:
    recipe_data = load_recipe_data()
    recipe_save = load_recipe_save()

    print("Raw recipe_data rows:", len(recipe_data))
    print("Raw recipe_save rows:", len(recipe_save))

    print("Raw unique content_id in recipe_data:", recipe_data["content_id"].nunique())
    print("Raw unique content_id in recipe_save:", recipe_save["content_id"].nunique())

    recipe_data_clean = clean_recipe_data(recipe_data)
    recipe_save_clean = clean_recipe_save(recipe_save)
    recipe_keyword_summary = load_recipe_keyword_summary()

    print("\nClean recipe_data rows:", len(recipe_data_clean))
    print("Clean recipe_save rows:", len(recipe_save_clean))
    print("Recipe keyword summary rows:", len(recipe_keyword_summary))

    recipe_master = recipe_data_clean.merge(
        recipe_save_clean,
        on="content_id",
        how="left",
    )
    recipe_master = recipe_master.merge(
        recipe_keyword_summary,
        left_on="content_id",
        right_on="recipe_id",
        how="left",
    )

    recipe_master = recipe_master[
        [
            "content_id",
            "brand",
            "title",
            "url",
            "author_name",
            "author_id",
            "tags",
            "page_views",
            "save_sessions_app",
            "save_sessions_web",
            "total_save_sessions_clean",
            "top_keywords",
            "top_phrases",
            "keyword_buckets",
            "top_keywords_with_counts",
        ]
    ].copy()

    recipe_master = recipe_master.rename(
        columns={"total_save_sessions_clean": "total_save_sessions"}
    )

    print("\nMerged recipe_master rows:", len(recipe_master))
    print("Merged recipe_master columns:")
    print(recipe_master.columns.tolist())

    recipe_master.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved merged file to {OUTPUT_PATH}")

    print("\nSample:")
    print(recipe_master.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
