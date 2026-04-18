# analyze_comment_corpus.py
#
# Goal:
# Analyze the full comment corpus to discover candidate stopwords and noisy phrases.
#
# Outputs:
# - outputs/top_words_by_frequency.csv
# - outputs/top_words_by_recipe_coverage.csv
# - outputs/top_bigrams_by_frequency.csv
# - outputs/top_bigrams_by_recipe_coverage.csv
#
# Assumptions:
# - comments file is at data/comments_sample.csv
# - recipe id is in storyID or content_id
# - comment text is in one of: comment, comment_text, body, text

from __future__ import annotations

import re
import string
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "comments_sample.csv"
OUTPUT_DIR = BASE_DIR / "outputs"

MIN_TERM_COUNT = 5
MIN_TOKEN_LEN = 3

GENERIC_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so",
    "of", "in", "on", "at", "to", "for", "from", "by", "with", "about",
    "as", "is", "it", "its", "this", "that", "these", "those", "be",
    "been", "being", "was", "were", "are", "am", "i", "me", "my", "we",
    "our", "you", "your", "he", "she", "they", "them", "their", "his",
    "her", "him", "have", "has", "had", "do", "does", "did", "done",
    "can", "could", "would", "should", "will", "just", "very", "really",
    "also", "too", "not", "no", "yes", "all", "any", "some", "more",
    "most", "less", "few", "many", "much", "only", "even", "still",
    "again", "out", "up", "down", "over", "under", "into", "after",
    "before", "when", "while", "where", "what", "which", "who", "whom",
    "because", "how", "there", "here"
}


def detect_column(columns: list[str], candidates: list[str]) -> str:
    lower_map = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    raise ValueError(f"Could not find any of these columns: {candidates}")


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    tokens = text.split()
    cleaned = [
        token for token in tokens
        if len(token) >= MIN_TOKEN_LEN
        and token not in GENERIC_STOPWORDS
        and not token.isdigit()
    ]
    return cleaned


def make_bigrams(tokens: list[str]) -> list[str]:
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def build_term_stats(df: pd.DataFrame, recipe_col: str, text_col: str):
    word_total_count = Counter()
    word_comment_ids = defaultdict(set)
    word_recipe_ids = defaultdict(set)

    bigram_total_count = Counter()
    bigram_comment_ids = defaultdict(set)
    bigram_recipe_ids = defaultdict(set)

    total_recipes = df[recipe_col].nunique()

    for idx, row in df.iterrows():
        recipe_id = str(row[recipe_col])
        text = normalize_text(row[text_col])

        if not text:
            continue

        tokens = tokenize(text)
        if not tokens:
            continue

        bigrams = make_bigrams(tokens)

        unique_words_in_comment = set(tokens)
        unique_bigrams_in_comment = set(bigrams)

        word_total_count.update(tokens)
        bigram_total_count.update(bigrams)

        for word in unique_words_in_comment:
            word_comment_ids[word].add(idx)
            word_recipe_ids[word].add(recipe_id)

        for bigram in unique_bigrams_in_comment:
            bigram_comment_ids[bigram].add(idx)
            bigram_recipe_ids[bigram].add(recipe_id)

    word_rows = []
    for term, total_count in word_total_count.items():
        if total_count < MIN_TERM_COUNT:
            continue
        unique_comments = len(word_comment_ids[term])
        unique_recipes = len(word_recipe_ids[term])
        recipe_coverage_pct = round((unique_recipes / total_recipes) * 100, 2)
        word_rows.append({
            "term": term,
            "total_count": total_count,
            "unique_comments": unique_comments,
            "unique_recipes": unique_recipes,
            "recipe_coverage_pct": recipe_coverage_pct,
        })

    bigram_rows = []
    for term, total_count in bigram_total_count.items():
        if total_count < MIN_TERM_COUNT:
            continue
        unique_comments = len(bigram_comment_ids[term])
        unique_recipes = len(bigram_recipe_ids[term])
        recipe_coverage_pct = round((unique_recipes / total_recipes) * 100, 2)
        bigram_rows.append({
            "term": term,
            "total_count": total_count,
            "unique_comments": unique_comments,
            "unique_recipes": unique_recipes,
            "recipe_coverage_pct": recipe_coverage_pct,
        })

    words_df = pd.DataFrame(word_rows)
    bigrams_df = pd.DataFrame(bigram_rows)

    return words_df, bigrams_df


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Could not find input file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, low_memory=False)

    recipe_col = detect_column(df.columns.tolist(), ["storyID", "content_id"])
    text_col = detect_column(
        df.columns.tolist(),
        ["Comment", "comment", "comment_text", "body", "text"],
    )

    df = df[[recipe_col, text_col]].dropna()
    df = df[df[text_col].astype(str).str.strip() != ""]

    words_df, bigrams_df = build_term_stats(df, recipe_col, text_col)

    words_by_freq = words_df.sort_values(
        ["total_count", "unique_recipes"], ascending=[False, False]
    )
    words_by_coverage = words_df.sort_values(
        ["recipe_coverage_pct", "total_count"], ascending=[False, False]
    )

    bigrams_by_freq = bigrams_df.sort_values(
        ["total_count", "unique_recipes"], ascending=[False, False]
    )
    bigrams_by_coverage = bigrams_df.sort_values(
        ["recipe_coverage_pct", "total_count"], ascending=[False, False]
    )

    words_by_freq.to_csv(OUTPUT_DIR / "top_words_by_frequency.csv", index=False)
    words_by_coverage.to_csv(OUTPUT_DIR / "top_words_by_recipe_coverage.csv", index=False)
    bigrams_by_freq.to_csv(OUTPUT_DIR / "top_bigrams_by_frequency.csv", index=False)
    bigrams_by_coverage.to_csv(OUTPUT_DIR / "top_bigrams_by_recipe_coverage.csv", index=False)

    print("Done.")
    print(f"Rows analyzed: {len(df):,}")
    print(f"Unique recipes: {df[recipe_col].nunique():,}")
    print("Files written:")
    print(f"- {OUTPUT_DIR / 'top_words_by_frequency.csv'}")
    print(f"- {OUTPUT_DIR / 'top_words_by_recipe_coverage.csv'}")
    print(f"- {OUTPUT_DIR / 'top_bigrams_by_frequency.csv'}")
    print(f"- {OUTPUT_DIR / 'top_bigrams_by_recipe_coverage.csv'}")


if __name__ == "__main__":
    main()
