#!/usr/bin/env python3
"""
Build fix-aware recommended_edit values.

Purpose
-------
Update recommended_edit using:
1. issue / display_issue as the primary truth
2. canonical fix signal only when fix confidence is medium or high

This keeps the system deterministic and confidence-aware, while improving
language quality so outputs sound less repetitive and more editorial.

Input
-----
outputs/editorial_intelligence_with_fixes.csv

Output
------
outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv

New columns
-----------
- recommended_edit_v2
- recommended_edit_source
- fix_signal_summary

Logic
-----
- If fix_confidence is high:
    use canonical fix directly when it aligns with the issue
- If fix_confidence is medium:
    blend issue framing + fix signal with light template variation
- If fix_confidence is low/none:
    keep issue-driven deterministic recommendation
"""

from __future__ import annotations

import pandas as pd


INPUT_PATH = "outputs/editorial_intelligence_with_fixes.csv"
OUTPUT_PATH = "outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv"


def norm(x: object) -> str:
    if pd.isna(x):
        return ""
    return " ".join(str(x).strip().lower().split())


def issue_default_edit(display_issue: str) -> str:
    """
    Deterministic fallback edit from issue alone.
    """
    issue = norm(display_issue)

    if issue in {"over-seasoned", "too salty"}:
        return "Reduce salt in the base recipe to improve balance."

    if issue in {"under-seasoned", "bland"}:
        return "Increase seasoning and improve flavor balance."

    if issue in {"dry", "too dry", "dry texture"}:
        return "Increase moisture in the base recipe or reduce drying during cooking."

    if issue in {"too sweet", "overly sweet"}:
        return "Reduce sugar or rebalance sweetness with acid or bitterness."

    if issue in {"quantity issue", "not enough filling", "too much filling", "filling amount is off"}:
        return "Adjust ingredient quantities so the recipe yield and proportions are correct."

    if issue in {"custard / setting issue", "not setting properly", "did not set", "curdled"}:
        return "Adjust the ratio, temperature, or method so the mixture sets reliably."

    return "Review the recipe for the main source of friction and tighten the base method or ingredient balance."


def canonical_fix_to_edit(canonical_fix: str, confidence: str = "") -> str:
    """
    Convert canonical fix directly into an editorial recommendation.

    For medium confidence, keep a bit more nuance where useful.
    For high confidence, stay more direct.
    """
    fix = norm(canonical_fix)
    conf = norm(confidence)

    medium_mapping = {
        "reduce salt": "Reduce salt in the base recipe.",
        "reduce sugar": "Reduce sugar in the base recipe.",
        "add acidity": "Add more acidity to improve balance and brighten flavor.",
        "increase moisture": "Increase moisture in the base recipe or add more liquid or sauce.",
        "improve structure": "Adjust the recipe to improve structure and help it hold together or set properly.",
        "boost flavor": "Strengthen seasoning and flavor development.",
        "boost umami": "Increase umami and depth of flavor.",
        "increase seasoning": "Increase seasoning and improve flavor balance.",
        "reduce fat": "Reduce fat or richness so the finished dish feels more balanced.",
        "adjust richness": "Adjust richness so the final texture feels lighter and more balanced.",
        "adjust texture": "Adjust the method or ingredient balance to improve final texture.",
        "adjust cook time": "Adjust cook time so the recipe does not overcook or dry out.",
        "adjust quantity": "Adjust ingredient quantities so the recipe yield and proportions are correct.",
        "adjust liquid": "Adjust liquid levels so the final texture is not too thick or too thin.",
    }

    high_mapping = {
        "reduce salt": "Reduce salt in the base recipe.",
        "reduce sugar": "Reduce sugar in the base recipe.",
        "add acidity": "Add more acidity to improve balance and brighten flavor.",
        "increase moisture": "Increase moisture in the base recipe or add more liquid or sauce.",
        "improve structure": "Adjust the recipe to improve structure and help it hold together or set properly.",
        "boost flavor": "Strengthen seasoning and flavor development in the base recipe.",
        "boost umami": "Increase umami and depth of flavor in the base recipe.",
        "increase seasoning": "Increase seasoning in the base recipe.",
        "reduce fat": "Reduce fat or richness so the finished dish feels more balanced.",
        "adjust richness": "Adjust richness so the final texture feels lighter and more balanced.",
        "adjust texture": "Adjust the method or ingredient balance to improve final texture.",
        "adjust cook time": "Adjust cook time so the recipe does not overcook or dry out.",
        "adjust quantity": "Adjust ingredient quantities so the recipe yield and proportions are correct.",
        "adjust liquid": "Adjust liquid levels so the final texture is not too thick or too thin.",
    }

    mapping = high_mapping if conf == "high" else medium_mapping

    return mapping.get(
        fix,
        "Adjust the base recipe to address the most common user fix pattern."
    )


def issue_phrase_for_sentence(display_issue: str) -> str:
    """
    Convert issue label into cleaner sentence fragment.
    """
    issue = norm(display_issue)

    mapping = {
        "over-seasoned": "over-seasoned",
        "too salty": "over-seasoned",
        "under-seasoned": "under-seasoned",
        "bland": "under-seasoned",
        "dry": "too dry",
        "too dry": "too dry",
        "dry texture": "too dry",
        "too sweet": "too sweet",
        "overly sweet": "too sweet",
        "quantity issue": "out of proportion",
        "not enough filling": "out of proportion",
        "too much filling": "out of proportion",
        "filling amount is off": "out of proportion",
        "custard / setting issue": "unstable in execution",
        "not setting properly": "unstable in execution",
        "did not set": "unstable in execution",
        "curdled": "unstable in execution",
    }

    return mapping.get(issue, issue if issue else "hard to execute")


def fix_signal_summary(
    canonical_fix_1: str,
    canonical_fix_2: str,
    fix_confidence: str,
) -> str:
    """
    Human-readable summary of fix evidence.
    """
    conf = norm(fix_confidence)
    fix1 = norm(canonical_fix_1)
    fix2 = norm(canonical_fix_2)
    has_fix_signal = bool(fix1 or fix2)

    if conf in {"none", ""} and not has_fix_signal:
        return "No consistent user fixes identified."

    if conf in {"none", ""} and has_fix_signal:
        if fix1 and fix2 and fix1 != fix2:
            return f"Some readers try fixes like {fix1} and {fix2}, but the evidence is still limited."
        if fix1:
            return f"Some readers try fixes like {fix1}, but the evidence is still limited."
        return "Fix evidence is still limited."

    if conf == "low":
        if fix1 and fix2 and fix1 != fix2:
            return f"Some readers try fixes like {fix1} and {fix2}, but the pattern is still mixed."
        if fix1:
            return f"Some readers try fixes like {fix1}, but the pattern is still mixed."
        return "Fix patterns are weak and inconsistent."

    if conf == "medium":
        if fix1 and fix2 and fix1 != fix2:
            return f"Users often compensate by trying fixes like {fix1} and {fix2}."
        if fix1:
            return f"Users often compensate by trying fixes like {fix1}."
        return "Users often compensate, but fix patterns are still somewhat mixed."

    if conf == "high":
        if fix1 and fix2 and fix1 != fix2:
            return f"Users consistently fix this by {fix1}, with {fix2} as a secondary pattern."
        if fix1:
            return f"Users consistently fix this by {fix1}."
        return "Users show a consistent fix pattern."

    return "Fix evidence is still limited."


def fix_aligns_with_issue(display_issue: str, canonical_fix: str) -> bool:
    """
    Conservative alignment check.
    Fixes should only override issue logic when they make sense for that issue.
    """
    issue = norm(display_issue)
    fix = norm(canonical_fix)

    allowed = {
        "over-seasoned": {"reduce salt", "add acidity"},
        "too salty": {"reduce salt", "add acidity"},
        "under-seasoned": {"boost flavor", "increase seasoning", "boost umami", "add acidity"},
        "bland": {"boost flavor", "increase seasoning", "boost umami", "add acidity"},
        "dry": {"increase moisture", "adjust cook time", "reduce fat", "adjust liquid"},
        "too dry": {"increase moisture", "adjust cook time", "reduce fat", "adjust liquid"},
        "dry texture": {"increase moisture", "adjust cook time", "reduce fat", "adjust liquid"},
        "too sweet": {"reduce sugar", "add acidity"},
        "overly sweet": {"reduce sugar", "add acidity"},
        "quantity issue": {"adjust quantity"},
        "not enough filling": {"adjust quantity"},
        "too much filling": {"adjust quantity"},
        "filling amount is off": {"adjust quantity"},
        "custard / setting issue": {"improve structure", "adjust cook time", "adjust liquid", "adjust texture"},
        "not setting properly": {"improve structure", "adjust cook time", "adjust liquid", "adjust texture"},
        "did not set": {"improve structure", "adjust cook time", "adjust liquid", "adjust texture"},
        "curdled": {"improve structure", "adjust cook time", "adjust texture"},
    }

    if issue not in allowed:
        return False

    return fix in allowed[issue]


def blend_issue_and_fix(display_issue: str, fix_edit: str, canonical_fix_1: str) -> str:
    """
    Build a less robotic issue + fix sentence.

    We avoid repeating the issue every time with the exact same opener.
    We also avoid redundant phrasing when the fix already fully implies the issue.
    """
    issue = norm(display_issue)
    fix1 = norm(canonical_fix_1)
    issue_phrase = issue_phrase_for_sentence(issue)

    # If the fix is already the cleanest possible expression, do not add redundant framing.
    if issue in {"over-seasoned", "too salty"} and fix1 == "reduce salt":
        return "Reduce salt in the base recipe."

    if issue in {"too sweet", "overly sweet"} and fix1 == "reduce sugar":
        return "Reduce sugar in the base recipe."

    if issue in {"under-seasoned", "bland"} and fix1 in {"boost flavor", "increase seasoning"}:
        return fix_edit

    if issue in {"under-seasoned", "bland"} and fix1 in {"add acidity", "boost umami"}:
        return f"This recipe is frequently described as {issue_phrase}. {fix_edit}"

    if issue in {"dry", "too dry", "dry texture"}:
        return f"Users commonly report this recipe as {issue_phrase}. {fix_edit}"

    if issue in {"quantity issue", "not enough filling", "too much filling", "filling amount is off"}:
        return f"The recipe appears {issue_phrase}. {fix_edit}"

    if issue in {"custard / setting issue", "not setting properly", "did not set", "curdled"}:
        return f"Consistent feedback suggests the recipe is {issue_phrase}. {fix_edit}"

    return f"This recipe is frequently described as {issue_phrase}. {fix_edit}"


def build_recommended_edit(
    display_issue: str,
    existing_recommended_edit: str,
    canonical_fix_1: str,
    canonical_fix_2: str,
    fix_confidence: str,
) -> tuple[str, str]:
    """
    Returns:
    - recommended_edit_v2
    - recommended_edit_source
    """
    issue = norm(display_issue)
    existing = str(existing_recommended_edit).strip() if pd.notna(existing_recommended_edit) else ""
    fix1 = norm(canonical_fix_1)
    fix2 = norm(canonical_fix_2)
    conf = norm(fix_confidence)

    default_edit = existing if existing else issue_default_edit(issue)

    # No usable fix signal
    if conf in {"", "none", "low"}:
        return default_edit, "issue_default"

    # High confidence: use aligned fix directly
    if conf == "high":
        if fix1 and fix_aligns_with_issue(issue, fix1):
            return canonical_fix_to_edit(fix1, confidence="high"), "fix_direct_high"
        return default_edit, "issue_default"

    # Medium confidence: blend issue framing + fix signal
    if conf == "medium":
        if fix1 and fix_aligns_with_issue(issue, fix1):
            fix_edit = canonical_fix_to_edit(fix1, confidence="medium")
            blended = blend_issue_and_fix(issue, fix_edit, fix1)
            return blended, "issue_fix_blend_medium"
        return default_edit, "issue_default"

    return default_edit, "issue_default"


def main() -> None:
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required = ["recipe_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if "display_issue" not in df.columns:
        if "decision.issue.display_issue" in df.columns:
            df["display_issue"] = df["decision.issue.display_issue"]
        else:
            df["display_issue"] = ""

    if "recommended_edit" not in df.columns:
        if "decision.recommended_edit" in df.columns:
            df["recommended_edit"] = df["decision.recommended_edit"]
        else:
            df["recommended_edit"] = ""

    for col in ["top_canonical_fix_1", "top_canonical_fix_2", "fix_confidence"]:
        if col not in df.columns:
            df[col] = ""

    out = df.apply(
        lambda row: build_recommended_edit(
            display_issue=row.get("display_issue", ""),
            existing_recommended_edit=row.get("recommended_edit", ""),
            canonical_fix_1=row.get("top_canonical_fix_1", ""),
            canonical_fix_2=row.get("top_canonical_fix_2", ""),
            fix_confidence=row.get("fix_confidence", ""),
        ),
        axis=1,
        result_type="expand",
    )

    df["recommended_edit_v2"] = out[0]
    df["recommended_edit_source"] = out[1]

    df["fix_signal_summary"] = df.apply(
        lambda row: fix_signal_summary(
            canonical_fix_1=row.get("top_canonical_fix_1", ""),
            canonical_fix_2=row.get("top_canonical_fix_2", ""),
            fix_confidence=row.get("fix_confidence", ""),
        ),
        axis=1,
    )

    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved fix-aware output to {OUTPUT_PATH}")
    print("\nRecommended edit source breakdown:")
    print(df["recommended_edit_source"].value_counts(dropna=False))
    print("\nFix confidence breakdown:")
    print(df["fix_confidence"].fillna("none").value_counts(dropna=False))


if __name__ == "__main__":
    main()
