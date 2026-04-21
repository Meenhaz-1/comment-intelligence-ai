#!/usr/bin/env python3
"""
Apply rule-based canonical fix mapping to raw fix phrases.

Purpose
-------
This is the second-pass mapper after exact-match template mapping.

Pass 1:
- apply_fix_phrase_mapping.py
- maps only phrases that exactly match your labeled template

Pass 2:
- this script
- maps common phrase variants using lightweight rules

Why this exists
---------------
Exact matching is too brittle for messy user fix language.

Examples:
- cut salt in half
- halve salt
- use less salt
- low sodium soy sauce

All of these should land in the same canonical fix theme:
- reduce salt

This script expands coverage without forcing you to manually label
thousands of long-tail rows.

Inputs
------
outputs/raw_fix_phrases_mapped.csv

Expected columns
----------------
- recipe_id
- raw_fix_phrase
- canonical_fix
- fix_family
- is_mapped

Output
------
outputs/raw_fix_phrases_mapped_with_rules.csv

New / updated columns
---------------------
- canonical_fix
- fix_family
- is_mapped
- mapping_status

mapping_status values
---------------------
- mapped_exact
- mapped_rule
- unmapped

Usage
-----
python src/apply_fix_phrase_rules.py
"""

from __future__ import annotations

import pandas as pd


INPUT_PATH = "outputs/raw_fix_phrases_mapped.csv"
OUTPUT_PATH = "outputs/raw_fix_phrases_mapped_with_rules.csv"


def normalize_text(text: object) -> str:
    """
    Lowercase and normalize whitespace for matching.
    """
    if pd.isna(text):
        return ""
    return " ".join(str(text).lower().strip().split())


def apply_rule(phrase: str) -> tuple[str | None, str | None]:
    """
    Map a raw fix phrase to a canonical fix and fix family.

    Philosophy
    ----------
    - Prioritize editorially useful fix strategies
    - Avoid mapping generic pantry substitutions unless they clearly solve a problem
    - Keep ontology small and stable
    """
    p = normalize_text(phrase)

    # ----------------------------
    # SALT REDUCTION
    # ----------------------------
    if "salt" in p and any(
        x in p for x in ["cut", "halve", "half", "less", "reduce", "low sodium", "unsalted"]
    ):
        return "reduce salt", "salt"

    # ----------------------------
    # SUGAR REDUCTION
    # ----------------------------
    if "sugar" in p and any(
        x in p for x in ["cut", "halve", "half", "less", "reduce"]
    ):
        return "reduce sugar", "sweetness"

    # ----------------------------
    # ACIDITY / BRIGHTNESS
    # ----------------------------
    if any(
        x in p
        for x in [
            "lemon juice",
            "lime juice",
            "vinegar",
            "lemon zest",
            "lime zest",
            "extra lemon",
            "juice of half a lemon",
            "zest of half a lemon",
            "white wine vinegar",
        ]
    ):
        return "add acidity", "acidity"

    # ----------------------------
    # MOISTURE / LIQUID INCREASE
    # ----------------------------
    if any(
        x in p
        for x in [
            "add water",
            "more water",
            "extra water",
            "add broth",
            "extra broth",
            "more broth",
            "add milk",
            "more milk",
            "add buttermilk",
            "more buttermilk",
            "coconut milk",
            "more sauce",
            "double sauce",
            "add sauce",
            "additional 1 2 c milk",
            "cup of extra chicken broth",
        ]
    ):
        return "increase moisture", "moisture"

    if "replace water" in p:
        return "adjust liquid", "moisture"

    # ----------------------------
    # STRUCTURE / THICKENING / BINDING
    # ----------------------------
    if any(
        x in p
        for x in [
            "add egg",
            "extra egg",
            "more flour",
            "increase cornstarch",
            "add cornstarch",
        ]
    ):
        return "improve structure", "structure"

    # ----------------------------
    # FLAVOR BOOSTING
    # ----------------------------
    if p in {"add salt", "add more salt"}:
        return "increase seasoning", "flavor"

    if any(
        x in p
        for x in [
            "double garlic",
            "more garlic",
            "add garlic",
            "double spices",
            "add spices",
            "add cumin",
            "add oregano",
            "add vanilla",
            "black pepper",
            "garlic salt",
            "crushed red pepper",
            "chicken broth",
            "chicken stock",
            "white wine",
        ]
    ):
        return "boost flavor", "flavor"

    # ----------------------------
    # UMAMI
    # ----------------------------
    if any(x in p for x in ["fish sauce", "soy sauce", "miso", "bouillon"]):
        return "boost umami", "flavor"

    # ----------------------------
    # FAT / RICHNESS REDUCTION
    # ----------------------------
    if any(
        x in p
        for x in [
            "cut butter",
            "half the butter",
            "use half butter",
            "reduce butter",
            "cut olive oil",
            "less evoo",
            "1 4 cup of oil",
            "cut back on the olive oil",
        ]
    ):
        return "reduce fat", "texture"

    # ----------------------------
    # TEXTURE / RICHNESS ADJUSTMENT
    # ----------------------------
    if "two egg yolks" in p:
        return "adjust richness", "texture"

    if any(x in p for x in ["cold water to smooth out"]):
        return "adjust texture", "texture"

    # ----------------------------
    # COOK TIME
    # ----------------------------
    if any(
        x in p
        for x in [
            "cut back on the cooking time",
            "cook less",
            "bake 5 more minutes",
            "baking time down",
        ]
    ):
        return "adjust cook time", "cook_time"

    # ----------------------------
    # QUANTITY / YIELD
    # ----------------------------
    if any(
        x in p
        for x in [
            "cut recipe in half",
            "half recipe",
            "double mushrooms",
        ]
    ):
        return "adjust quantity", "quantity"

    return None, None


def main() -> None:
    """
    Read the first-pass mapped file, apply rule-based mappings to
    unmapped rows, and write the expanded output.
    """
    df = pd.read_csv(INPUT_PATH)

    if "raw_fix_phrase" not in df.columns:
        raise ValueError("Missing required column: raw_fix_phrase")

    if "canonical_fix" not in df.columns:
        df["canonical_fix"] = None

    if "fix_family" not in df.columns:
        df["fix_family"] = None

    df["raw_fix_phrase_norm"] = df["raw_fix_phrase"].map(normalize_text)

    # Mark mapping origin
    df["mapping_status"] = "unmapped"

    exact_mask = df["canonical_fix"].notna() & (df["canonical_fix"].astype(str).str.strip() != "")
    df.loc[exact_mask, "mapping_status"] = "mapped_exact"

    before_mapped = exact_mask.sum()

    for idx, row in df.iterrows():
        existing_fix = row["canonical_fix"]

        if pd.notna(existing_fix) and str(existing_fix).strip() != "":
            continue

        canonical_fix, fix_family = apply_rule(row["raw_fix_phrase_norm"])

        if canonical_fix:
            df.at[idx, "canonical_fix"] = canonical_fix
            df.at[idx, "fix_family"] = fix_family
            df.at[idx, "mapping_status"] = "mapped_rule"

    df["is_mapped"] = df["canonical_fix"].notna() & (df["canonical_fix"].astype(str).str.strip() != "")

    after_mapped = df["is_mapped"].sum()
    new_rule_mapped = (df["mapping_status"] == "mapped_rule").sum()
    unmapped_remaining = (df["mapping_status"] == "unmapped").sum()

    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved rule-mapped output to {OUTPUT_PATH}")
    print(f"Mapped before rules: {before_mapped}")
    print(f"Mapped after rules: {after_mapped}")
    print(f"New rows mapped by rules: {new_rule_mapped}")
    print(f"Unmapped rows remaining: {unmapped_remaining}")
    print("\nMapping status breakdown:")
    print(df["mapping_status"].value_counts(dropna=False))


if __name__ == "__main__":
    main()