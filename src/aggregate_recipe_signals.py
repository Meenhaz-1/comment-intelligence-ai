import os

import numpy as np
import pandas as pd


INPUT_PATH = "outputs/comment_signals.csv"
OUTPUT_PATH = "outputs/recipe_signal_summary.csv"


SIGNAL_COLS = [
    "signal_any_behavior",
    "signal_made",
    "signal_modification",
    "signal_substitution",
    "signal_positive",
    "signal_friction",
    "signal_repeat_intent",
]


def safe_pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """
    Safe percentage calculation.
    Returns 0 when denominator is 0.
    """
    return np.where(denominator > 0, (numerator / denominator) * 100, 0)


def normalize_boolean(value):
    """
    Normalize common boolean-like values to True / False / NaN.
    """
    if pd.isna(value):
        return np.nan

    if isinstance(value, bool):
        return value

    value_str = str(value).strip().lower()

    if value_str == "true":
        return True
    if value_str == "false":
        return False

    return np.nan


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = ["recipe_id", "comment_id", "eligible_for_analysis", "is_noise"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {df.columns.tolist()}"
        )

    print(f"Tagged comments loaded: {len(df):,}")

    # Fill missing signal columns with 0 if needed
    for col in SIGNAL_COLS:
        if col not in df.columns:
            df[col] = 0

    # Normalize signal columns to numeric ints
    for col in SIGNAL_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Normalize match count if present
    if "total_signal_count" in df.columns:
        df["total_signal_count"] = pd.to_numeric(
            df["total_signal_count"], errors="coerce"
        ).fillna(0)

    # Normalize analysis flags
    df["eligible_for_analysis"] = pd.to_numeric(
        df["eligible_for_analysis"], errors="coerce"
    ).fillna(0).astype(int)

    df["is_noise"] = df["is_noise"].map(
        lambda x: True if str(x).strip().lower() == "true"
        else False if str(x).strip().lower() == "false"
        else bool(x)
    )

    # Normalize will_prepare_again if present
    if "will_prepare_again" in df.columns:
        df["will_prepare_again_normalized"] = df["will_prepare_again"].apply(normalize_boolean)
    else:
        df["will_prepare_again_normalized"] = np.nan

    # Base recipe-level aggregation
    recipe_summary = (
        df.groupby("recipe_id", dropna=False)
        .agg(
            total_comments=("comment_id", "count"),
            eligible_comments=("eligible_for_analysis", "sum"),
            noise_comments=("is_noise", "sum"),
            signal_any_behavior_comments=("signal_any_behavior", "sum"),
            signal_made_comments=("signal_made", "sum"),
            signal_modification_comments=("signal_modification", "sum"),
            signal_substitution_comments=("signal_substitution", "sum"),
            signal_positive_comments=("signal_positive", "sum"),
            signal_friction_comments=("signal_friction", "sum"),
            signal_repeat_intent_comments=("signal_repeat_intent", "sum"),
        )
        .reset_index()
    )

    # Add average total signal count if available
    if "total_signal_count" in df.columns:
        avg_signal_count = (
            df.groupby("recipe_id", dropna=False)["total_signal_count"]
            .mean()
            .reset_index(name="avg_total_signal_count")
        )
        recipe_summary = recipe_summary.merge(avg_signal_count, on="recipe_id", how="left")
    else:
        recipe_summary["avg_total_signal_count"] = 0

    # Add will_prepare_again summary if available
    will_prepare_df = df[df["will_prepare_again_normalized"].notna()].copy()

    if not will_prepare_df.empty:
        will_prepare_summary = (
            will_prepare_df.groupby("recipe_id", dropna=False)
            .agg(
                will_prepare_again_true_count=(
                    "will_prepare_again_normalized",
                    lambda x: int((x == True).sum()),
                ),
                will_prepare_again_false_count=(
                    "will_prepare_again_normalized",
                    lambda x: int((x == False).sum()),
                ),
                will_prepare_again_known_count=("will_prepare_again_normalized", "count"),
            )
            .reset_index()
        )

        recipe_summary = recipe_summary.merge(
            will_prepare_summary,
            on="recipe_id",
            how="left",
        )
    else:
        recipe_summary["will_prepare_again_true_count"] = 0
        recipe_summary["will_prepare_again_false_count"] = 0
        recipe_summary["will_prepare_again_known_count"] = 0

    # Fill NaNs after merge
    fill_zero_cols = [
        "avg_total_signal_count",
        "will_prepare_again_true_count",
        "will_prepare_again_false_count",
        "will_prepare_again_known_count",
    ]
    for col in fill_zero_cols:
        recipe_summary[col] = recipe_summary[col].fillna(0)

    # Add percentages based on eligible comments
    recipe_summary["pct_signal_any_behavior"] = safe_pct(
        recipe_summary["signal_any_behavior_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_made"] = safe_pct(
        recipe_summary["signal_made_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_modification"] = safe_pct(
        recipe_summary["signal_modification_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_substitution"] = safe_pct(
        recipe_summary["signal_substitution_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_positive"] = safe_pct(
        recipe_summary["signal_positive_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_friction"] = safe_pct(
        recipe_summary["signal_friction_comments"],
        recipe_summary["eligible_comments"],
    )
    recipe_summary["pct_signal_repeat_intent"] = safe_pct(
        recipe_summary["signal_repeat_intent_comments"],
        recipe_summary["eligible_comments"],
    )

    # Add will_prepare_again %
    recipe_summary["pct_will_prepare_again_true"] = safe_pct(
        recipe_summary["will_prepare_again_true_count"],
        recipe_summary["will_prepare_again_known_count"],
    )

    # Make count columns ints
    count_cols = [
        "total_comments",
        "eligible_comments",
        "noise_comments",
        "signal_any_behavior_comments",
        "signal_made_comments",
        "signal_modification_comments",
        "signal_substitution_comments",
        "signal_positive_comments",
        "signal_friction_comments",
        "signal_repeat_intent_comments",
        "will_prepare_again_true_count",
        "will_prepare_again_false_count",
        "will_prepare_again_known_count",
    ]
    for col in count_cols:
        recipe_summary[col] = recipe_summary[col].astype(int)

    # Round metric columns
    metric_cols = [
        "avg_total_signal_count",
        "pct_signal_any_behavior",
        "pct_signal_made",
        "pct_signal_modification",
        "pct_signal_substitution",
        "pct_signal_positive",
        "pct_signal_friction",
        "pct_signal_repeat_intent",
        "pct_will_prepare_again_true",
    ]
    for col in metric_cols:
        recipe_summary[col] = recipe_summary[col].round(2)

    # Optional sort
    recipe_summary = recipe_summary.sort_values(
        by=["eligible_comments", "total_comments"],
        ascending=[False, False],
    ).reset_index(drop=True)

    preferred_order = [
        "recipe_id",
        "total_comments",
        "eligible_comments",
        "noise_comments",
        "signal_any_behavior_comments",
        "signal_made_comments",
        "signal_modification_comments",
        "signal_substitution_comments",
        "signal_positive_comments",
        "signal_friction_comments",
        "signal_repeat_intent_comments",
        "pct_signal_any_behavior",
        "pct_signal_made",
        "pct_signal_modification",
        "pct_signal_substitution",
        "pct_signal_positive",
        "pct_signal_friction",
        "pct_signal_repeat_intent",
        "avg_total_signal_count",
        "will_prepare_again_true_count",
        "will_prepare_again_false_count",
        "will_prepare_again_known_count",
        "pct_will_prepare_again_true",
    ]

    ordered_cols = [col for col in preferred_order if col in recipe_summary.columns]
    remaining_cols = [col for col in recipe_summary.columns if col not in ordered_cols]
    recipe_summary = recipe_summary[ordered_cols + remaining_cols]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    recipe_summary.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved recipe-level summary to {OUTPUT_PATH}")
    print(f"Total recipes summarized: {len(recipe_summary):,}")
    print("\nSample:")
    print(recipe_summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()