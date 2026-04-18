import os
from pathlib import Path

import numpy as np
import pandas as pd


# =========================
# CONFIG
# =========================
RECIPE_MASTER_PATH = "data/recipe_master.csv"
RECIPE_COMMENT_FEATURES_PATH = "outputs/recipe_comment_features.csv"
BEHAVIORAL_PHRASES_WIDE_PATH = "outputs/recipe_behavioral_phrases_wide.csv"

OUTPUT_PATH = "outputs/recipe_intelligence.csv"


# =========================
# HELPERS
# =========================
def load_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing input file: {path}")
    return pd.read_csv(path, low_memory=False)


def standardize_recipe_id(df: pd.DataFrame, df_name: str) -> pd.DataFrame:
    """
    Ensure every input has a string recipe_id column.
    Falls back from content_id -> recipe_id if needed.
    """
    df = df.copy()

    if "recipe_id" not in df.columns:
        if "content_id" in df.columns:
            df = df.rename(columns={"content_id": "recipe_id"})
        else:
            raise KeyError(f"{df_name} is missing both 'recipe_id' and 'content_id'")

    df["recipe_id"] = df["recipe_id"].astype(str).str.strip()
    return df


def assert_unique_recipe_ids(df: pd.DataFrame, df_name: str) -> None:
    dupes = df[df["recipe_id"].duplicated(keep=False)].sort_values("recipe_id")
    if not dupes.empty:
        sample = dupes["recipe_id"].head(10).tolist()
        raise ValueError(
            f"{df_name} does not have one row per recipe. "
            f"Found duplicate recipe_id values. Sample: {sample}"
        )


def reshape_behavioral_wide(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reshape behavioral phrase wide file into one row per recipe if it currently
    has one row per recipe + category.

    Expected input pattern:
    recipe_id | category | top_phrase_1 | top_phrase_1_coverage_pct | ...

    Output pattern:
    recipe_id | friction_top_phrase_1 | modification_top_phrase_1 | ...
    """
    df = df.copy()

    if df.empty:
        return df

    if df["recipe_id"].is_unique:
        return df

    if "category" not in df.columns:
        dupes = df[df["recipe_id"].duplicated(keep=False)].sort_values("recipe_id")
        sample = dupes.head(20).to_string(index=False)
        raise ValueError(
            "recipe_behavioral_phrases_wide has duplicate recipe_id values, "
            "but no 'category' column exists to reshape it.\n"
            f"Sample duplicate rows:\n{sample}"
        )

    df["category"] = df["category"].astype(str).str.strip().str.lower()
    value_columns = [c for c in df.columns if c not in ["recipe_id", "category"]]

    reshaped_frames = []

    for category in sorted(df["category"].dropna().unique()):
        subset = df[df["category"] == category].copy()

        if subset.empty:
            continue

        if subset["recipe_id"].duplicated().any():
            dupes = subset[subset["recipe_id"].duplicated(keep=False)].sort_values("recipe_id")
            sample = dupes.head(20).to_string(index=False)
            raise ValueError(
                f"Behavioral file still has duplicate recipe_id values within category='{category}'.\n"
                f"Sample duplicate rows:\n{sample}"
            )

        rename_map = {col: f"{category}_{col}" for col in value_columns}
        subset = subset.rename(columns=rename_map)

        keep_cols = ["recipe_id"] + list(rename_map.values())
        reshaped_frames.append(subset[keep_cols])

    if not reshaped_frames:
        return pd.DataFrame(columns=["recipe_id"])

    result = reshaped_frames[0]
    for frame in reshaped_frames[1:]:
        result = result.merge(frame, on="recipe_id", how="outer")

    return result


def coalesce_columns(
    df: pd.DataFrame,
    preferred: str,
    alternatives: list[str],
    default=None,
) -> pd.Series:
    """
    Return the first available non-null value across preferred + alternative columns.
    """
    if preferred in df.columns:
        result = df[preferred].copy()
    else:
        result = pd.Series(pd.NA, index=df.index, dtype="object")

    for col in alternatives:
        if col in df.columns:
            result = result.where(result.notna(), df[col])

    if default is not None:
        result = result.where(result.notna(), default)

    return result


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Add missing columns as NA so final column selection does not fail.
    """
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def pct_to_prop(series: pd.Series) -> pd.Series:
    """
    Convert percentage values on a 0-100 scale into proportions on a 0-1 scale.
    Leaves already-scaled 0-1 values untouched.
    """
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    if len(s) > 0 and s.max() > 1.0:
        s = s / 100.0
    return s


def classify_recipe(row: pd.Series) -> str:
    f = row["friction_score"]
    r = row["recoverability_score"]
    e = row["engagement_score"]
    repeat_intent = row["pct_repeat_intent_prop"]
    comments = row["total_comments"]

    # Low data → ignore
    if comments < 5:
        return "Low Signal"

    # High friction cases
    if f > 0.30:
        if r > 0.15:
            return "High Opportunity"
    elif r > 0.02:
        return "Needs Improvement"
    else:
        return "Needs Fix"

    # Low friction → good recipes
    if f < 0.15 and repeat_intent > 0.20:
        return "Performing Well"

    return "Low Signal"


# =========================
# MAIN
# =========================
def main() -> None:
    # -------------------------
    # Load inputs
    # -------------------------
    recipe_master = load_csv(RECIPE_MASTER_PATH)
    recipe_features = load_csv(RECIPE_COMMENT_FEATURES_PATH)
    behavioral_wide = load_csv(BEHAVIORAL_PHRASES_WIDE_PATH)

    # -------------------------
    # Standardize recipe_id
    # -------------------------
    recipe_master = standardize_recipe_id(recipe_master, "recipe_master")
    recipe_features = standardize_recipe_id(recipe_features, "recipe_comment_features")
    behavioral_wide = standardize_recipe_id(behavioral_wide, "recipe_behavioral_phrases_wide")

    # -------------------------
    # Reshape behavioral file if needed
    # -------------------------
    behavioral_wide = reshape_behavioral_wide(behavioral_wide)

    # -------------------------
    # Validate base uniqueness
    # -------------------------
    assert_unique_recipe_ids(recipe_master, "recipe_master")
    assert_unique_recipe_ids(recipe_features, "recipe_comment_features")
    assert_unique_recipe_ids(behavioral_wide, "recipe_behavioral_phrases_wide_reshaped")

    # -------------------------
    # Merge
    # -------------------------
    recipe_intelligence = (
        recipe_master
        .merge(recipe_features, on="recipe_id", how="left", suffixes=("", "_feat"))
        .merge(behavioral_wide, on="recipe_id", how="left", suffixes=("", "_beh"))
    )

    assert_unique_recipe_ids(recipe_intelligence, "recipe_intelligence")

    # -------------------------
    # Normalize / coalesce metadata fields
    # -------------------------
    recipe_intelligence["title"] = coalesce_columns(
        recipe_intelligence,
        preferred="title",
        alternatives=["recipe_title"],
        default=""
    )

    recipe_intelligence["author_name"] = coalesce_columns(
        recipe_intelligence,
        preferred="author_name",
        alternatives=["author", "creator", "recipe_creator"],
        default=""
    )

    recipe_intelligence["brand"] = coalesce_columns(
        recipe_intelligence,
        preferred="brand",
        alternatives=[],
        default=""
    )

    recipe_intelligence["tags"] = coalesce_columns(
        recipe_intelligence,
        preferred="tags",
        alternatives=[],
        default=""
    )

    recipe_intelligence["url"] = coalesce_columns(
        recipe_intelligence,
        preferred="url",
        alternatives=[],
        default=""
    )

    # -------------------------
    # Normalize volume / engagement fields
    # -------------------------
    recipe_intelligence["page_views"] = coalesce_columns(
        recipe_intelligence,
        preferred="page_views",
        alternatives=[],
        default=0
    )

    recipe_intelligence["save_sessions_app"] = coalesce_columns(
        recipe_intelligence,
        preferred="save_sessions_app",
        alternatives=[],
        default=0
    )

    recipe_intelligence["save_sessions_web"] = coalesce_columns(
        recipe_intelligence,
        preferred="save_sessions_web",
        alternatives=[],
        default=0
    )

    recipe_intelligence["total_save_sessions"] = coalesce_columns(
        recipe_intelligence,
        preferred="total_save_sessions",
        alternatives=[],
        default=0
    )

    recipe_intelligence["total_comments"] = coalesce_columns(
        recipe_intelligence,
        preferred="total_comments",
        alternatives=["recipe_comment_count", "comment_count"],
        default=0
    )

    recipe_intelligence["eligible_comments"] = coalesce_columns(
        recipe_intelligence,
        preferred="eligible_comments",
        alternatives=[],
        default=0
    )

    # -------------------------
    # Normalize behavioral percentage fields
    # -------------------------
    recipe_intelligence["pct_made"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_made",
        alternatives=["pct_signal_made", "made_pct"],
        default=0
    )

    recipe_intelligence["pct_modification"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_modification",
        alternatives=["pct_signal_modification", "modification_pct"],
        default=0
    )

    recipe_intelligence["pct_substitution"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_substitution",
        alternatives=["pct_signal_substitution", "substitution_pct"],
        default=0
    )

    recipe_intelligence["pct_friction"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_friction",
        alternatives=["pct_signal_friction", "friction_pct"],
        default=0
    )

    recipe_intelligence["pct_positive"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_positive",
        alternatives=["pct_signal_positive", "positive_pct"],
        default=0
    )

    recipe_intelligence["pct_repeat_intent"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_repeat_intent",
        alternatives=["pct_signal_repeat_intent", "repeat_intent_pct"],
        default=0
    )

    recipe_intelligence["avg_total_signal_count"] = coalesce_columns(
        recipe_intelligence,
        preferred="avg_total_signal_count",
        alternatives=["avg_signal_count"],
        default=0
    )

    recipe_intelligence["pct_will_prepare_again_true"] = coalesce_columns(
        recipe_intelligence,
        preferred="pct_will_prepare_again_true",
        alternatives=["will_prepare_again_true_pct"],
        default=0
    )

    # -------------------------
    # Normalize behavioral phrase columns after reshape
    # -------------------------
    recipe_intelligence["top_friction_phrase_1"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_friction_phrase_1",
        alternatives=[
            "friction_top_phrase_1",
            "friction_phrase_1",
            "top_behavioral_friction_phrase_1",
        ],
        default=""
    )

    recipe_intelligence["top_friction_phrase_1_coverage_pct"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_friction_phrase_1_coverage_pct",
        alternatives=[
            "friction_top_phrase_1_coverage_pct",
            "friction_phrase_1_coverage_pct",
        ],
        default=0
    )

    recipe_intelligence["top_friction_phrase_2"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_friction_phrase_2",
        alternatives=[
            "friction_top_phrase_2",
            "friction_phrase_2",
            "top_behavioral_friction_phrase_2",
        ],
        default=""
    )

    recipe_intelligence["top_friction_phrase_2_coverage_pct"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_friction_phrase_2_coverage_pct",
        alternatives=[
            "friction_top_phrase_2_coverage_pct",
            "friction_phrase_2_coverage_pct",
        ],
        default=0
    )

    recipe_intelligence["top_modification_phrase_1"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_modification_phrase_1",
        alternatives=[
            "modification_top_phrase_1",
            "modification_phrase_1",
            "top_behavioral_modification_phrase_1",
        ],
        default=""
    )

    recipe_intelligence["top_modification_phrase_1_coverage_pct"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_modification_phrase_1_coverage_pct",
        alternatives=[
            "modification_top_phrase_1_coverage_pct",
            "modification_phrase_1_coverage_pct",
        ],
        default=0
    )

    recipe_intelligence["top_modification_phrase_2"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_modification_phrase_2",
        alternatives=[
            "modification_top_phrase_2",
            "modification_phrase_2",
            "top_behavioral_modification_phrase_2",
        ],
        default=""
    )

    recipe_intelligence["top_modification_phrase_2_coverage_pct"] = coalesce_columns(
        recipe_intelligence,
        preferred="top_modification_phrase_2_coverage_pct",
        alternatives=[
            "modification_top_phrase_2_coverage_pct",
            "modification_phrase_2_coverage_pct",
        ],
        default=0
    )

    # -------------------------
    # Convenience flags
    # -------------------------
    recipe_intelligence["has_behavioral_signal"] = (
        (pd.to_numeric(recipe_intelligence["pct_friction"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(recipe_intelligence["pct_modification"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(recipe_intelligence["pct_substitution"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(recipe_intelligence["pct_repeat_intent"], errors="coerce").fillna(0) > 0)
    ).astype(int)

    recipe_intelligence["has_behavioral_phrase"] = (
        (recipe_intelligence["top_friction_phrase_1"].fillna("").astype(str).str.strip() != "")
        | (recipe_intelligence["top_modification_phrase_1"].fillna("").astype(str).str.strip() != "")
    ).astype(int)

    # -------------------------
    # Type cleanup
    # -------------------------
    numeric_columns = [
        "page_views",
        "save_sessions_app",
        "save_sessions_web",
        "total_save_sessions",
        "total_comments",
        "eligible_comments",
        "pct_made",
        "pct_modification",
        "pct_substitution",
        "pct_friction",
        "pct_positive",
        "pct_repeat_intent",
        "avg_total_signal_count",
        "pct_will_prepare_again_true",
        "top_friction_phrase_1_coverage_pct",
        "top_friction_phrase_2_coverage_pct",
        "top_modification_phrase_1_coverage_pct",
        "top_modification_phrase_2_coverage_pct",
        "has_behavioral_signal",
        "has_behavioral_phrase",
    ]

    for col in numeric_columns:
        recipe_intelligence[col] = pd.to_numeric(recipe_intelligence[col], errors="coerce").fillna(0)

    text_columns = [
        "title",
        "author_name",
        "brand",
        "tags",
        "url",
        "top_friction_phrase_1",
        "top_friction_phrase_2",
        "top_modification_phrase_1",
        "top_modification_phrase_2",
    ]

    for col in text_columns:
        recipe_intelligence[col] = recipe_intelligence[col].fillna("").astype(str)

    # -------------------------
    # Convert percentages to proportions for scoring
    # -------------------------
    recipe_intelligence["pct_made_prop"] = pct_to_prop(recipe_intelligence["pct_made"])
    recipe_intelligence["pct_modification_prop"] = pct_to_prop(recipe_intelligence["pct_modification"])
    recipe_intelligence["pct_substitution_prop"] = pct_to_prop(recipe_intelligence["pct_substitution"])
    recipe_intelligence["pct_friction_prop"] = pct_to_prop(recipe_intelligence["pct_friction"])
    recipe_intelligence["pct_positive_prop"] = pct_to_prop(recipe_intelligence["pct_positive"])
    recipe_intelligence["pct_repeat_intent_prop"] = pct_to_prop(recipe_intelligence["pct_repeat_intent"])
    recipe_intelligence["pct_will_prepare_again_true_prop"] = pct_to_prop(
        recipe_intelligence["pct_will_prepare_again_true"]
    )

    # -------------------------
    # Scoring layer
    # -------------------------
    recipe_intelligence["friction_score"] = recipe_intelligence["pct_friction_prop"]

    recipe_intelligence["engagement_score"] = np.log1p(
        pd.to_numeric(recipe_intelligence["total_comments"], errors="coerce").fillna(0)
    )

    recipe_intelligence["recoverability_score"] = recipe_intelligence["pct_modification_prop"]

    recipe_intelligence["opportunity_score"] = (
        recipe_intelligence["friction_score"]
        * recipe_intelligence["engagement_score"]
        * recipe_intelligence["recoverability_score"]
    )

    recipe_intelligence["classification"] = recipe_intelligence.apply(classify_recipe, axis=1)

    # -------------------------
    # Final column selection
    # -------------------------
    final_columns = [
        "recipe_id",
        "title",
        "author_name",
        "brand",
        "tags",
        "url",

        "page_views",
        "save_sessions_app",
        "save_sessions_web",
        "total_save_sessions",

        "total_comments",
        "eligible_comments",

        "pct_made",
        "pct_modification",
        "pct_substitution",
        "pct_friction",
        "pct_positive",
        "pct_repeat_intent",
        "avg_total_signal_count",
        "pct_will_prepare_again_true",

        "top_friction_phrase_1",
        "top_friction_phrase_1_coverage_pct",
        "top_friction_phrase_2",
        "top_friction_phrase_2_coverage_pct",

        "top_modification_phrase_1",
        "top_modification_phrase_1_coverage_pct",
        "top_modification_phrase_2",
        "top_modification_phrase_2_coverage_pct",

        "has_behavioral_signal",
        "has_behavioral_phrase",

        "friction_score",
        "engagement_score",
        "recoverability_score",
        "opportunity_score",
        "classification",
    ]

    recipe_intelligence = ensure_columns(recipe_intelligence, final_columns)
    recipe_intelligence = recipe_intelligence[final_columns]

    # -------------------------
    # Sort for readability
    # -------------------------
    recipe_intelligence = recipe_intelligence.sort_values(
        by=["opportunity_score", "total_comments", "total_save_sessions", "page_views"],
        ascending=[False, False, False, False]
    ).reset_index(drop=True)

    # -------------------------
    # Save
    # -------------------------
    Path(os.path.dirname(OUTPUT_PATH)).mkdir(parents=True, exist_ok=True)
    recipe_intelligence.to_csv(OUTPUT_PATH, index=False)

    # -------------------------
    # Validation summary
    # -------------------------
    total_recipes = len(recipe_intelligence)
    recipes_with_comments = (recipe_intelligence["total_comments"] > 0).sum()
    recipes_with_behavioral_phrases = (recipe_intelligence["has_behavioral_phrase"] > 0).sum()
    recipes_with_behavioral_signal = (recipe_intelligence["has_behavioral_signal"] > 0).sum()
    recipes_with_saves = (recipe_intelligence["total_save_sessions"] > 0).sum()
    recipes_with_pageviews = (recipe_intelligence["page_views"] > 0).sum()

    class_counts = recipe_intelligence["classification"].value_counts(dropna=False)

    print(f"Saved recipe intelligence file to: {OUTPUT_PATH}")
    print(f"Total recipes: {total_recipes:,}")
    print(f"Recipes with comments: {recipes_with_comments:,}")
    print(f"Recipes with behavioral phrases: {recipes_with_behavioral_phrases:,}")
    print(f"Recipes with behavioral signals: {recipes_with_behavioral_signal:,}")
    print(f"Recipes with saves: {recipes_with_saves:,}")
    print(f"Recipes with pageviews: {recipes_with_pageviews:,}")

    print("\nClassification counts:")
    print(class_counts.to_string())

    rankable = recipe_intelligence[
        (recipe_intelligence["total_comments"] >= 5)
        & (recipe_intelligence["has_behavioral_signal"] == 1)
        & (recipe_intelligence["classification"] != "Low Signal")
    ].copy()

    rankable = rankable.sort_values(
        by=["opportunity_score", "total_comments"],
        ascending=[False, False]
    )

    print("\nTop 15 REAL ranked recipes by opportunity score:")
    print(
        rankable[
            [
                "title",
                "total_comments",
                "friction_score",
                "recoverability_score",
                "opportunity_score",
                "classification",
                "top_friction_phrase_1",
                "top_modification_phrase_1",
            ]
        ]
        .head(15)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()