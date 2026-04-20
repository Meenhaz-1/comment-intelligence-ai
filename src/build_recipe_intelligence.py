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
GLOBAL_FRICTION_LOOKUP_PATH = "outputs/global_friction_phrases_labeled.csv"

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
    repeat_intent = row["pct_repeat_intent_prop"]
    comments = row["total_comments"]

    if comments < 5:
        return "Low Signal"

    if f > 0.30:
        if r > 0.15:
            return "High Opportunity"
        elif r > 0.02:
            return "Needs Improvement"
        else:
            return "Needs Fix"

    if r > 0.02:
        return "Needs Improvement"

    if f < 0.15 and repeat_intent > 0.20:
        return "Performing Well"

    return "Low Signal"


def build_phrase_lookup(df: pd.DataFrame) -> dict[str, dict]:
    """
    Build lookup from phrase -> normalized issue metadata.
    Only keep rows with keep_flag == 1.
    """
    required_cols = ["phrase", "normalized_issue", "issue_family", "keep_flag"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"global_friction_phrases_labeled is missing required columns: {missing}"
        )

    work = df.copy()
    work["phrase"] = work["phrase"].fillna("").astype(str).str.strip().str.lower()
    work["normalized_issue"] = work["normalized_issue"].fillna("").astype(str).str.strip()
    work["issue_family"] = work["issue_family"].fillna("").astype(str).str.strip()
    work["keep_flag"] = pd.to_numeric(work["keep_flag"], errors="coerce").fillna(0).astype(int)

    work = work[(work["phrase"] != "") & (work["keep_flag"] == 1)].copy()

    if work["phrase"].duplicated().any():
        dupes = work[work["phrase"].duplicated(keep=False)].sort_values("phrase")
        sample = dupes.head(20).to_string(index=False)
        raise ValueError(
            "global_friction_phrases_labeled has duplicate phrases after filtering keep_flag == 1.\n"
            f"Sample duplicate rows:\n{sample}"
        )

    return {
        row["phrase"]: {
            "normalized_issue": row["normalized_issue"],
            "issue_family": row["issue_family"],
            "keep_flag": row["keep_flag"],
        }
        for _, row in work.iterrows()
    }


def canonicalize_phrase(raw_phrase: str) -> str:
    """
    Light canonicalization before phrase lookup.
    """
    phrase = "" if pd.isna(raw_phrase) else str(raw_phrase).strip().lower()
    phrase = phrase.replace("didnt", "didn't")
    phrase = " ".join(phrase.split())

    fallback_map = {
        "dry": "too dry",
        "salty": "too salty",
        "sweet": "too sweet",
        "spicy": "too spicy",
        "watery": "too watery",
        "wet": "too wet",
        "thick": "too thick",
        "oily": "too oily",
        "burned": "burnt",
    }

    return fallback_map.get(phrase, phrase)


def lookup_issue_fields(phrase: str, phrase_lookup: dict[str, dict]) -> dict[str, object]:
    """
    Map a raw friction phrase to normalized issue fields.
    """
    raw = "" if pd.isna(phrase) else str(phrase).strip()
    key = canonicalize_phrase(raw)

    if key in phrase_lookup:
        match = phrase_lookup[key]
        return {
            "issue_phrase": raw,
            "normalized_issue": match["normalized_issue"],
            "issue_family": match["issue_family"],
            "keep_flag": match["keep_flag"],
            "issue_source": "phrase",
            "issue_confidence": "high",
        }

    return {
        "issue_phrase": "",
        "normalized_issue": "",
        "issue_family": "",
        "keep_flag": 0,
        "issue_source": "",
        "issue_confidence": "",
    }


def derive_recipe_issue_fields(
    df: pd.DataFrame,
    phrase_lookup: dict[str, dict],
) -> pd.DataFrame:
    """
    Derive recipe-level normalized issue fields from top friction phrases.
    Uses phrase_1 as primary if mapped and kept.
    Falls back to phrase_2 if phrase_1 is unmapped or suppressed.
    Also exposes secondary issue fields when available.
    """
    df = df.copy()

    primary_results = []
    secondary_results = []

    for _, row in df.iterrows():
        p1 = lookup_issue_fields(row.get("top_friction_phrase_1", ""), phrase_lookup)
        p2 = lookup_issue_fields(row.get("top_friction_phrase_2", ""), phrase_lookup)

        p1_cov = pd.to_numeric(row.get("top_friction_phrase_1_coverage_pct", 0), errors="coerce")
        p2_cov = pd.to_numeric(row.get("top_friction_phrase_2_coverage_pct", 0), errors="coerce")

        p1_cov = 0 if pd.isna(p1_cov) else p1_cov
        p2_cov = 0 if pd.isna(p2_cov) else p2_cov

        candidates = []
        if p1["normalized_issue"]:
            candidates.append(
                {
                    "rank_source": 1,
                    "issue_phrase": p1["issue_phrase"],
                    "normalized_issue": p1["normalized_issue"],
                    "issue_family": p1["issue_family"],
                    "keep_flag": p1["keep_flag"],
                    "coverage_pct": p1_cov,
                    "issue_source": p1["issue_source"],
                    "issue_confidence": p1["issue_confidence"],
                }
            )
        if p2["normalized_issue"]:
            candidates.append(
                {
                    "rank_source": 2,
                    "issue_phrase": p2["issue_phrase"],
                    "normalized_issue": p2["normalized_issue"],
                    "issue_family": p2["issue_family"],
                    "keep_flag": p2["keep_flag"],
                    "coverage_pct": p2_cov,
                    "issue_source": p2["issue_source"],
                    "issue_confidence": p2["issue_confidence"],
                }
            )

        if candidates:
            primary = sorted(
                candidates,
                key=lambda x: (-x["coverage_pct"], x["rank_source"])
            )[0]

            remaining = [
                x for x in candidates
                if not (
                    x["issue_phrase"] == primary["issue_phrase"]
                    and x["normalized_issue"] == primary["normalized_issue"]
                )
            ]

            secondary = sorted(
                remaining,
                key=lambda x: (-x["coverage_pct"], x["rank_source"])
            )[0] if remaining else None
        else:
            primary = {
                "issue_phrase": "",
                "normalized_issue": "",
                "issue_family": "",
                "keep_flag": 0,
                "coverage_pct": 0,
                "issue_source": "",
                "issue_confidence": "",
            }
            secondary = None

        primary_results.append(primary)
        secondary_results.append(secondary or {
            "issue_phrase": "",
            "normalized_issue": "",
            "issue_family": "",
            "keep_flag": 0,
            "coverage_pct": 0,
            "issue_source": "",
            "issue_confidence": "",
        })

    primary_df = pd.DataFrame(primary_results).rename(columns={
        "issue_phrase": "top_issue_phrase",
        "normalized_issue": "top_normalized_issue",
        "issue_family": "top_issue_family",
        "keep_flag": "top_issue_keep_flag",
        "coverage_pct": "top_issue_coverage_pct",
        "issue_source": "issue_source",
        "issue_confidence": "issue_confidence",
    })

    secondary_df = pd.DataFrame(secondary_results).rename(columns={
        "issue_phrase": "secondary_issue_phrase",
        "normalized_issue": "secondary_normalized_issue",
        "issue_family": "secondary_issue_family",
        "keep_flag": "secondary_issue_keep_flag",
        "coverage_pct": "secondary_issue_coverage_pct",
        "issue_source": "secondary_issue_source",
        "issue_confidence": "secondary_issue_confidence",
    })

    return pd.concat([df.reset_index(drop=True), primary_df, secondary_df], axis=1)


def infer_issue_from_signals(row: pd.Series) -> tuple[str, str, str, int, str, str]:
    """
    Fallback when no friction phrase exists.
    Uses modification phrases and broad heuristics.
    Returns:
    normalized_issue, issue_family, issue_phrase, keep_flag, issue_source, issue_confidence
    """
    mod1 = str(row.get("top_modification_phrase_1", "")).strip().lower()
    mod2 = str(row.get("top_modification_phrase_2", "")).strip().lower()
    mod_text = f"{mod1} | {mod2}"

    pct_friction = pd.to_numeric(row.get("pct_friction", 0), errors="coerce")
    pct_friction = 0 if pd.isna(pct_friction) else pct_friction

    if any(token in mod_text for token in [
        "reduce salty", "less salt", "reduce salt",
        "less feta", "reduce feta",
        "less olives", "reduce olives"
    ]):
        return "over-seasoned", "flavor", "", 1, "modification_inference", "medium"

    if any(token in mod_text for token in [
        "added lemon", "add lemon", "added lime", "add lime",
        "add acidity", "more seasoning", "increase seasoning",
        "more spice", "more spices", "added salt"
    ]):
        return "under-seasoned", "flavor", "", 1, "modification_inference", "medium"

    if any(token in mod_text for token in [
        "reduce liquid", "less liquid", "drain", "thicken"
    ]):
        return "too wet", "moisture", "", 1, "modification_inference", "medium"

    if any(token in mod_text for token in [
        "added broth", "more broth", "added stock", "more stock",
        "added liquid", "more liquid", "added sauce", "more sauce"
    ]):
        return "too dry", "moisture", "", 1, "modification_inference", "medium"

    if any(token in mod_text for token in ["cook longer", "bake longer"]):
        return "undercooked", "cooking", "", 1, "modification_inference", "medium"

    if any(token in mod_text for token in [
        "cook less", "bake less", "reduced cook time", "reduced baking time"
    ]):
        return "overcooked", "cooking", "", 1, "modification_inference", "medium"

    if pct_friction >= 50:
        return "unresolved friction", "generic", "", 0, "friction_inference", "low"

    return "", "", "", 0, "", ""


def apply_issue_fallbacks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill blank normalized issue fields using fallback inference.
    """
    df = df.copy()

    mask = df["top_normalized_issue"].fillna("").astype(str).str.strip() == ""
    if mask.any():
        inferred = df.loc[mask].apply(infer_issue_from_signals, axis=1)
        inferred_df = pd.DataFrame(
            inferred.tolist(),
            index=df.loc[mask].index,
            columns=[
                "top_normalized_issue",
                "top_issue_family",
                "top_issue_phrase",
                "top_issue_keep_flag",
                "issue_source",
                "issue_confidence",
            ],
        )

        for col in inferred_df.columns:
            df.loc[mask, col] = inferred_df[col]

        df.loc[mask, "top_issue_coverage_pct"] = np.where(
            df.loc[mask, "top_issue_coverage_pct"].fillna(0).astype(float) > 0,
            df.loc[mask, "top_issue_coverage_pct"],
            0,
        )

    return df


def get_display_issue(row: pd.Series) -> str:
    """
    UI-safe issue label.
    """
    issue = str(row.get("top_normalized_issue", "")).strip()
    confidence = str(row.get("issue_confidence", "")).strip().lower()

    if not issue:
        return ""

    if confidence in {"high", "medium"}:
        return issue

    if confidence == "low" and issue == "unresolved friction":
        return "Needs manual review"

    return issue


def get_display_issue_reason(row: pd.Series) -> str:
    """
    Explanation for why the display label is shown this way.
    """
    issue = str(row.get("top_normalized_issue", "")).strip()
    source = str(row.get("issue_source", "")).strip().lower()
    confidence = str(row.get("issue_confidence", "")).strip().lower()

    if not issue:
        return ""

    if source == "phrase" and confidence == "high":
        return "Phrase-backed issue"

    if source == "modification_inference" and confidence == "medium":
        return "Inferred from user modifications"

    if source == "friction_inference" and confidence == "low":
        return "Strong friction signal but no recurring issue phrase"

    return "Derived issue label"


def get_display_issue_action_state(row: pd.Series) -> str:
    """
    Simple UI state for rendering.
    """
    issue = str(row.get("top_normalized_issue", "")).strip()
    source = str(row.get("issue_source", "")).strip().lower()
    confidence = str(row.get("issue_confidence", "")).strip().lower()

    if not issue:
        return ""

    if source == "phrase" and confidence == "high":
        return "show_normal"

    if source == "modification_inference" and confidence == "medium":
        return "show_inferred"

    if source == "friction_inference" and confidence == "low":
        return "show_manual_review"

    return "show_normal"


def get_why_it_matters(row: pd.Series) -> str:
    """
    Deterministic explanation of why this recipe deserves attention.
    """
    classification = str(row.get("classification", "")).strip()
    action_state = str(row.get("display_issue_action_state", "")).strip()
    display_issue = str(row.get("display_issue", "")).strip()

    if classification == "High Opportunity":
        if action_state == "show_manual_review":
            return "High friction and strong user engagement suggest this recipe is worth reviewing, but the primary issue is still unclear."
        return "High friction and strong user engagement suggest this recipe is worth fixing."

    if classification == "Needs Improvement":
        if action_state == "show_inferred":
            return "Users appear to be adapting the recipe, but the issue still shows up often enough to justify revision."
        if action_state == "show_manual_review":
            return "Users are encountering recurring friction, but the issue needs manual review before making a recipe change."
        return "Recurring user friction suggests this recipe could benefit from a targeted revision."

    if classification == "Needs Fix":
        if display_issue:
            return "Users encounter recurring friction without a clear workaround, suggesting the base recipe likely needs revision."
        return "Recurring friction suggests the base recipe likely needs revision."

    if classification == "Performing Well":
        return "User feedback suggests this recipe is working well with limited recurring friction."

    return "There is not enough evidence yet to make a strong recommendation."


def get_recommended_edit(row: pd.Series) -> str:
    """
    Deterministic editorial recommendation based on issue + confidence + common fix.
    """
    display_issue = str(row.get("display_issue", "")).strip()
    issue_confidence = str(row.get("issue_confidence", "")).strip().lower()
    mod1 = str(row.get("top_modification_phrase_1", "")).strip().lower()

    if not display_issue:
        return ""

    if display_issue == "Needs manual review":
        return "Review comment evidence manually to identify the primary issue before editing the recipe."

    if display_issue == "under-seasoned":
        if any(token in mod1 for token in ["added lemon", "add lemon", "added lime", "add lime"]):
            return "Increase seasoning and add acidity to improve flavor balance."
        if any(token in mod1 for token in ["more spice", "more spices", "increase seasoning", "added salt"]):
            return "Increase salt, spices, or aromatics in the base recipe to improve flavor intensity."
        return "Increase salt, spices, aromatics, or acidity to improve flavor balance."

    if display_issue == "over-seasoned":
        if any(token in mod1 for token in ["reduce salty", "less salt", "reduce salt"]):
            return "Reduce salt in the base recipe to improve balance."
        if any(token in mod1 for token in ["less feta", "reduce feta", "less olives", "reduce olives"]):
            return "Reduce salty ingredients in the base recipe or rebalance their quantity."
        return "Reduce salt or rebalance salty ingredients in the base recipe."

    if display_issue == "too dry":
        if any(token in mod1 for token in ["added broth", "more broth", "added stock", "more stock", "added sauce", "more sauce"]):
            return "Increase moisture in the base recipe or reduce cooking intensity to improve final texture."
        return "Increase moisture or reduce cooking intensity to improve final texture."

    if display_issue == "too wet":
        if any(token in mod1 for token in ["reduce liquid", "less liquid", "drain", "thicken"]):
            return "Reduce liquid or increase thickening to improve final texture."
        return "Reduce liquid or extend cooking time to improve final texture."

    if display_issue == "too thick":
        return "Increase liquid slightly or adjust ratios to improve consistency."

    if display_issue == "too sweet":
        return "Reduce sugar or rebalance sweetness with salt, acid, or bitter elements."

    if display_issue == "too spicy":
        return "Reduce heat level or rebalance spice with fat, sweetness, or acidity."

    if display_issue == "too oily":
        return "Reduce oil quantity or adjust ingredient balance to avoid a greasy final result."

    if display_issue == "mushy texture":
        return "Reduce moisture or cooking time to improve texture and structure."

    if display_issue == "rubbery texture":
        return "Reduce cooking intensity or adjust method to improve texture."

    if display_issue == "grainy texture":
        return "Review ingredient ratios and mixing method to improve texture consistency."

    if display_issue == "overcooked":
        return "Reduce cooking time or heat level to prevent overcooking."

    if display_issue == "undercooked":
        return "Increase cooking time or improve doneness guidance in the recipe."

    if display_issue == "burnt":
        return "Reduce cooking intensity or clarify timing and temperature guidance to prevent burning."

    if display_issue == "structural failure":
        return "Review ingredient ratios and method steps to improve stability and consistency."

    if display_issue == "unresolved friction" and issue_confidence == "low":
        return "Review comment evidence manually to identify the primary issue before editing the recipe."

    return "Review comment evidence and revise the base recipe to address the main recurring issue."


# =========================
# MAIN
# =========================
def main() -> None:
    recipe_master = load_csv(RECIPE_MASTER_PATH)
    recipe_features = load_csv(RECIPE_COMMENT_FEATURES_PATH)
    behavioral_wide = load_csv(BEHAVIORAL_PHRASES_WIDE_PATH)
    global_friction_lookup = load_csv(GLOBAL_FRICTION_LOOKUP_PATH)

    recipe_master = standardize_recipe_id(recipe_master, "recipe_master")
    recipe_features = standardize_recipe_id(recipe_features, "recipe_comment_features")
    behavioral_wide = standardize_recipe_id(behavioral_wide, "recipe_behavioral_phrases_wide")

    behavioral_wide = reshape_behavioral_wide(behavioral_wide)

    assert_unique_recipe_ids(recipe_master, "recipe_master")
    assert_unique_recipe_ids(recipe_features, "recipe_comment_features")
    assert_unique_recipe_ids(behavioral_wide, "recipe_behavioral_phrases_wide_reshaped")

    recipe_intelligence = (
        recipe_master
        .merge(recipe_features, on="recipe_id", how="left", suffixes=("", "_feat"))
        .merge(behavioral_wide, on="recipe_id", how="left", suffixes=("", "_beh"))
    )

    assert_unique_recipe_ids(recipe_intelligence, "recipe_intelligence")

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

    phrase_lookup = build_phrase_lookup(global_friction_lookup)
    recipe_intelligence = derive_recipe_issue_fields(recipe_intelligence, phrase_lookup)
    recipe_intelligence = apply_issue_fallbacks(recipe_intelligence)

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
        "top_issue_keep_flag",
        "top_issue_coverage_pct",
        "secondary_issue_keep_flag",
        "secondary_issue_coverage_pct",
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
        "top_issue_phrase",
        "top_normalized_issue",
        "top_issue_family",
        "issue_source",
        "issue_confidence",
        "secondary_issue_phrase",
        "secondary_normalized_issue",
        "secondary_issue_family",
        "secondary_issue_source",
        "secondary_issue_confidence",
    ]

    for col in text_columns:
        recipe_intelligence[col] = recipe_intelligence[col].fillna("").astype(str)

    recipe_intelligence["pct_made_prop"] = pct_to_prop(recipe_intelligence["pct_made"])
    recipe_intelligence["pct_modification_prop"] = pct_to_prop(recipe_intelligence["pct_modification"])
    recipe_intelligence["pct_substitution_prop"] = pct_to_prop(recipe_intelligence["pct_substitution"])
    recipe_intelligence["pct_friction_prop"] = pct_to_prop(recipe_intelligence["pct_friction"])
    recipe_intelligence["pct_positive_prop"] = pct_to_prop(recipe_intelligence["pct_positive"])
    recipe_intelligence["pct_repeat_intent_prop"] = pct_to_prop(recipe_intelligence["pct_repeat_intent"])
    recipe_intelligence["pct_will_prepare_again_true_prop"] = pct_to_prop(
        recipe_intelligence["pct_will_prepare_again_true"]
    )

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

    recipe_intelligence["display_issue"] = recipe_intelligence.apply(get_display_issue, axis=1)
    recipe_intelligence["display_issue_reason"] = recipe_intelligence.apply(get_display_issue_reason, axis=1)
    recipe_intelligence["display_issue_action_state"] = recipe_intelligence.apply(
        get_display_issue_action_state,
        axis=1
    )

    recipe_intelligence["why_it_matters"] = recipe_intelligence.apply(get_why_it_matters, axis=1)
    recipe_intelligence["recommended_edit"] = recipe_intelligence.apply(get_recommended_edit, axis=1)

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
        "top_issue_phrase",
        "top_normalized_issue",
        "top_issue_family",
        "issue_source",
        "issue_confidence",
        "display_issue",
        "display_issue_reason",
        "display_issue_action_state",
        "why_it_matters",
        "recommended_edit",
        "secondary_issue_phrase",
        "secondary_normalized_issue",
        "secondary_issue_family",
        "secondary_issue_source",
        "secondary_issue_confidence",
    ]

    for col in text_columns:
        recipe_intelligence[col] = recipe_intelligence[col].fillna("").astype(str)

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

        "top_normalized_issue",
        "top_issue_family",
        "top_issue_phrase",
        "top_issue_coverage_pct",
        "top_issue_keep_flag",
        "issue_source",
        "issue_confidence",

        "display_issue",
        "display_issue_reason",
        "display_issue_action_state",
        "why_it_matters",
        "recommended_edit",

        "secondary_normalized_issue",
        "secondary_issue_family",
        "secondary_issue_phrase",
        "secondary_issue_coverage_pct",
        "secondary_issue_keep_flag",
        "secondary_issue_source",
        "secondary_issue_confidence",

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

    recipe_intelligence = recipe_intelligence.sort_values(
        by=["opportunity_score", "total_comments", "total_save_sessions", "page_views"],
        ascending=[False, False, False, False]
    ).reset_index(drop=True)

    Path(os.path.dirname(OUTPUT_PATH)).mkdir(parents=True, exist_ok=True)
    recipe_intelligence.to_csv(OUTPUT_PATH, index=False)

    total_recipes = len(recipe_intelligence)
    recipes_with_comments = (recipe_intelligence["total_comments"] > 0).sum()
    recipes_with_behavioral_phrases = (recipe_intelligence["has_behavioral_phrase"] > 0).sum()
    recipes_with_behavioral_signal = (recipe_intelligence["has_behavioral_signal"] > 0).sum()
    recipes_with_saves = (recipe_intelligence["total_save_sessions"] > 0).sum()
    recipes_with_pageviews = (recipe_intelligence["page_views"] > 0).sum()
    recipes_with_normalized_issue = (
        recipe_intelligence["top_normalized_issue"].fillna("").astype(str).str.strip() != ""
    ).sum()

    class_counts = recipe_intelligence["classification"].value_counts(dropna=False)

    print(f"Saved recipe intelligence file to: {OUTPUT_PATH}")
    print(f"Total recipes: {total_recipes:,}")
    print(f"Recipes with comments: {recipes_with_comments:,}")
    print(f"Recipes with behavioral phrases: {recipes_with_behavioral_phrases:,}")
    print(f"Recipes with behavioral signals: {recipes_with_behavioral_signal:,}")
    print(f"Recipes with normalized issue: {recipes_with_normalized_issue:,}")
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
                "display_issue",
                "display_issue_reason",
                "why_it_matters",
                "recommended_edit",
                "top_modification_phrase_1",
            ]
        ]
        .head(15)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()