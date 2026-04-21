#!/usr/bin/env python3
"""
Extract raw fix phrases from fix-bearing comment rows.

Purpose
-------
This script takes the output of `fix_comments_raw.csv` and extracts short,
reviewable raw fix phrases from comment text.

This is an intermediate step in the fix-canonicalization pipeline.

Pipeline position
-----------------
You are here:

evidence_candidates.csv
    -> export_fix_comments.py
    -> fix_comments_raw.csv
    -> extract_raw_fix_phrases.py   <-- this script
    -> raw_fix_phrases_long.csv
    -> raw_fix_phrases_review.csv
    -> canonical fix mapping
    -> recipe-level fix aggregation

Why this script exists
----------------------
Your current evidence layer tells you which comments are likely to contain
problem-solving fixes, but it does not yet give you a clean normalized
"fix phrase" field.

This script extracts raw phrases like:
- added lemon juice
- used less feta
- reduced salt
- cut the sugar
- added extra egg

These raw phrases are then reviewed and mapped into canonical fix themes like:
- add acidity
- reduce salty ingredients
- reduce sugar
- increase moisture

Design principles
-----------------
1. Prioritize useful review output over perfect NLP.
2. Keep extraction deterministic and inspectable.
3. Over-extract slightly, then filter aggressively.
4. Produce outputs that are easy to audit in CSV.

Inputs
------
outputs/fix_comments_raw.csv

Expected columns:
- recipe_id
- comment_id
- evidence_type
- evidence_score
- rank_within_recipe_type
- trimmed_comment
- clean_comment_text
- signal_friction
- signal_modification
- signal_substitution

Outputs
-------
1. outputs/raw_fix_phrases_long.csv
   One row per extracted raw fix phrase.

2. outputs/raw_fix_phrases_review.csv
   Aggregated review table for ontology building.

Long output columns
-------------------
- recipe_id
- comment_id
- evidence_type
- evidence_score
- raw_fix_phrase
- trigger_verb
- source_text

Review output columns
---------------------
- raw_fix_phrase
- trigger_verb
- total_rows
- unique_recipes
- avg_evidence_score
- sample_source_text

Usage
-----
python src/extract_raw_fix_phrases.py
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

import pandas as pd


INPUT_PATH = "outputs/fix_comments_raw.csv"
OUTPUT_LONG_PATH = "outputs/raw_fix_phrases_long.csv"
OUTPUT_REVIEW_PATH = "outputs/raw_fix_phrases_review.csv"

# Limit how many phrases a single comment can contribute.
# This prevents one long comment from dominating the output.
MAX_PHRASES_PER_COMMENT = 5

# Words that usually indicate the end of a useful extracted object span.
BOUNDARY_WORDS = {
    "because", "but", "and", "which", "that", "who", "while", "although",
    "though", "then", "so", "if", "when", "where", "after", "before",
    "with", "without", "instead", "except", "plus", "since", "until",
}

# Low-value object words. These usually create junk phrases like:
# "used it", "added this", "reduced some"
STOP_OBJECTS = {
    "it", "this", "that", "them", "these", "those", "everything", "anything",
    "nothing", "all", "some", "more", "less", "bit", "little", "lot",
    "amount", "thing", "things", "one", "ones",
}

# Full phrases that should always be dropped.
BAD_FULL_PHRASES = {
    "used it",
    "used this",
    "used that",
    "added it",
    "added this",
    "added that",
    "made it",
    "made this",
    "made that",
    "reduced it",
    "reduced this",
    "reduced that",
    "increased it",
    "increased this",
    "increased that",
}

# Regex patterns for extracting action + object spans.
# These patterns deliberately capture broad spans first.
# We clean and cut them down afterward.
VERB_PATTERNS: List[Tuple[str, str]] = [
    (r"\badded?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "add"),
    (r"\bused\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "use"),
    (r"\bsubstitut(?:ed|ing)?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "substitute"),
    (r"\breplaced?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "replace"),
    (r"\bdoubled?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "double"),
    (r"\bhalved?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "halve"),
    (r"\breduced?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "reduce"),
    (r"\bincreased?\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "increase"),
    (r"\bcut\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,80})", "cut"),
]

# More targeted patterns for common fix behavior that does not always fit neatly
# into a generic verb-object pattern.
SPECIAL_PATTERNS: List[Tuple[str, str, str]] = [
    # "used less feta"
    (r"\bused\s+less\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,60})", "use less", "use less"),
    # "added more lemon juice"
    (r"\badded?\s+more\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,60})", "add more", "add more"),
    # "cut back on sugar"
    (r"\bcut\s+back\s+on\s+(?P<object>[a-z0-9][a-z0-9\s\-]{1,60})", "cut back on", "cut back"),
    # "used half the sugar"
    (r"\bused\s+half\s+(?:the\s+)?(?P<object>[a-z0-9][a-z0-9\s\-]{1,60})", "use half", "use half"),
    # "reduced the salt"
    (r"\breduced?\s+(?:the\s+)?(?P<object>[a-z0-9][a-z0-9\s\-]{1,60})", "reduce", "reduce"),
]

# Noise tokens that commonly appear in broken extractions.
NOISE_TOKENS = {
    "recipe", "recipes", "time", "times", "thing", "things", "way", "ways",
    "bit", "little", "lot", "lots", "kind", "sort",
}


def clean_text(value: object) -> str:
    """
    Normalize whitespace and lowercase text safely.

    Why:
    - Input comments can contain inconsistent spacing, punctuation artifacts,
      and uppercase text.
    - Lowercasing makes regex extraction more stable.

    Returns:
        Cleaned string, or empty string if input is null-like.
    """
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_object_text(text: str) -> str:
    """
    Clean the captured object span after regex extraction.

    What this does:
    - trims punctuation-ish edges
    - normalizes whitespace
    - removes leading filler words
    - removes trailing filler words

    Example:
        "the lemon juice and" -> "lemon juice"
    """
    text = text.strip(" -,:;.")
    text = re.sub(r"\s+", " ", text).strip()

    # Remove common leading articles/fillers.
    text = re.sub(r"^(the|a|an|some|extra)\s+", "", text).strip()

    # Remove common trailing filler.
    text = re.sub(r"\s+(too|though|instead|again|also|actually)$", "", text).strip()

    return text


def cut_at_boundary_words(text: str) -> str:
    """
    Cut an extracted object span at the first obvious boundary word.

    Why:
    Regex capture is intentionally broad.
    This function trims it back.

    Example:
        "lemon juice because it was bland"
        -> "lemon juice"
    """
    tokens = text.split()
    kept: List[str] = []

    for token in tokens:
        if token in BOUNDARY_WORDS:
            break
        kept.append(token)

    return " ".join(kept).strip()


def trim_to_reasonable_length(text: str, max_words: int = 5) -> str:
    """
    Limit extracted object spans to a small number of words.

    Why:
    Real fix phrases are usually short.
    Long spans are usually noise or over-capture.

    Example:
        "extra lemon juice and more parsley"
        -> "extra lemon juice and more"
        then later boundary cleaning reduces further
    """
    words = text.split()
    return " ".join(words[:max_words]).strip()


def is_valid_object(text: str) -> bool:
    """
    Decide whether an extracted object span is usable.

    Reject if:
    - empty
    - single bad token like "it"
    - mostly numeric
    - too generic / noisy
    """
    if not text:
        return False

    words = text.split()

    if len(words) == 0:
        return False

    if len(words) == 1 and words[0] in STOP_OBJECTS:
        return False

    if all(re.fullmatch(r"\d+", w) for w in words):
        return False

    if words[0] in STOP_OBJECTS:
        return False

    if words[-1] in STOP_OBJECTS:
        return False

    if all(w in NOISE_TOKENS for w in words):
        return False

    return True


def build_phrase(trigger_verb: str, obj: str) -> Optional[str]:
    """
    Combine trigger verb and cleaned object into a candidate phrase.

    Returns None if the final phrase is obviously low-quality.
    """
    obj = normalize_object_text(obj)
    obj = cut_at_boundary_words(obj)
    obj = trim_to_reasonable_length(obj, max_words=5)
    obj = normalize_object_text(obj)

    if not is_valid_object(obj):
        return None

    phrase = f"{trigger_verb} {obj}".strip()
    phrase = re.sub(r"\s+", " ", phrase)

    if phrase in BAD_FULL_PHRASES:
        return None

    # Reject very short phrases like "added more"
    if len(phrase.split()) < 2:
        return None

    return phrase


def extract_from_special_patterns(text: str) -> List[Tuple[str, str]]:
    """
    Extract phrases from special-case patterns first.

    Why:
    These patterns capture important fix behaviors more cleanly than generic
    verb-object extraction.

    Returns:
        List of (raw_fix_phrase, trigger_verb)
    """
    found: List[Tuple[str, str]] = []

    for pattern, phrase_prefix, trigger_verb in SPECIAL_PATTERNS:
        for match in re.finditer(pattern, text):
            obj = match.group("object")
            phrase = build_phrase(phrase_prefix, obj)
            if phrase:
                found.append((phrase, trigger_verb))

    return found


def extract_from_verb_patterns(text: str) -> List[Tuple[str, str]]:
    """
    Extract phrases from generic verb-object patterns.

    Returns:
        List of (raw_fix_phrase, trigger_verb)
    """
    found: List[Tuple[str, str]] = []

    for pattern, trigger_verb in VERB_PATTERNS:
        for match in re.finditer(pattern, text):
            obj = match.group("object")
            phrase = build_phrase(trigger_verb, obj)
            if phrase:
                found.append((phrase, trigger_verb))

    return found


def dedupe_preserve_order(items: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Remove duplicate phrase rows while preserving the original order.

    Why:
    Multiple regexes may extract the same fix phrase from the same comment.
    """
    seen: Set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []

    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)

    return out


def extract_fix_phrases(text: str) -> List[Tuple[str, str]]:
    """
    Main extraction function for one comment.

    Steps:
    1. Apply special-case patterns
    2. Apply generic verb-object patterns
    3. Dedupe
    4. Cap the number of phrases per comment

    Returns:
        List of (raw_fix_phrase, trigger_verb)
    """
    text = clean_text(text)
    if not text:
        return []

    phrases: List[Tuple[str, str]] = []
    phrases.extend(extract_from_special_patterns(text))
    phrases.extend(extract_from_verb_patterns(text))
    phrases = dedupe_preserve_order(phrases)

    return phrases[:MAX_PHRASES_PER_COMMENT]


def main() -> None:
    """
    Run the full extraction pipeline and write both long and review outputs.

    Long output:
    - one row per extracted phrase

    Review output:
    - aggregated table for manual ontology building
    """
    df = pd.read_csv(INPUT_PATH)

    required_cols = [
        "recipe_id",
        "comment_id",
        "evidence_type",
        "evidence_score",
        "clean_comment_text",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    rows = []

    for _, row in df.iterrows():
        recipe_id = row["recipe_id"]
        comment_id = row["comment_id"]
        evidence_type = row["evidence_type"]
        evidence_score = row["evidence_score"]
        source_text = clean_text(row["clean_comment_text"])

        phrases = extract_fix_phrases(source_text)

        for raw_fix_phrase, trigger_verb in phrases:
            rows.append(
                {
                    "recipe_id": recipe_id,
                    "comment_id": comment_id,
                    "evidence_type": evidence_type,
                    "evidence_score": evidence_score,
                    "raw_fix_phrase": raw_fix_phrase,
                    "trigger_verb": trigger_verb,
                    "source_text": source_text,
                }
            )

    long_df = pd.DataFrame(rows)

    if long_df.empty:
        print("No raw fix phrases extracted.")
        long_df.to_csv(OUTPUT_LONG_PATH, index=False)
        pd.DataFrame(
            columns=[
                "raw_fix_phrase",
                "trigger_verb",
                "total_rows",
                "unique_recipes",
                "avg_evidence_score",
                "sample_source_text",
            ]
        ).to_csv(OUTPUT_REVIEW_PATH, index=False)
        return

    long_df = long_df.sort_values(
        ["raw_fix_phrase", "evidence_score", "recipe_id"],
        ascending=[True, False, True],
    )

    long_df.to_csv(OUTPUT_LONG_PATH, index=False)

    review_df = (
        long_df.groupby(["raw_fix_phrase", "trigger_verb"], dropna=False)
        .agg(
            total_rows=("comment_id", "size"),
            unique_recipes=("recipe_id", "nunique"),
            avg_evidence_score=("evidence_score", "mean"),
            sample_source_text=("source_text", "first"),
        )
        .reset_index()
        .sort_values(
            ["unique_recipes", "total_rows", "avg_evidence_score", "raw_fix_phrase"],
            ascending=[False, False, False, True],
        )
    )

    review_df.to_csv(OUTPUT_REVIEW_PATH, index=False)

    print(f"Saved long output to {OUTPUT_LONG_PATH}")
    print(f"Saved review output to {OUTPUT_REVIEW_PATH}")
    print(f"Total extracted rows: {len(long_df)}")
    print(f"Unique raw fix phrases: {review_df['raw_fix_phrase'].nunique()}")
    print(f"Unique recipes covered: {long_df['recipe_id'].nunique()}")


if __name__ == "__main__":
    main()