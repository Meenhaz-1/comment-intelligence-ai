from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd

from load_data import load_and_clean_comments


ROOT_DIR = Path(__file__).resolve().parent.parent
SUMMARY_OUTPUT_PATH = ROOT_DIR / "outputs" / "recipe_phrase_summary.csv"
RECIPE_OUTPUT_PATH = ROOT_DIR / "outputs" / "recipe_keyword_summary.csv"

TOP_K = 40
MIN_DOC_FREQ = 2
MIN_NGRAM_SIZE = 1
MAX_NGRAM_SIZE = 3

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "hers", "him", "his", "i",
    "if", "in", "into", "is", "it", "its", "me", "my", "of", "on", "or",
    "our", "ours", "she", "so", "that", "the", "their", "them", "there",
    "these", "they", "this", "those", "to", "too", "was", "we", "were",
    "what", "when", "which", "who", "will", "with", "you", "your", "yours",
    "im", "ive", "id", "ill", "youre", "youve", "dont", "didnt", "doesnt",
    "cant", "couldnt", "wasnt", "werent", "wont", "wouldnt", "shouldnt",
    "i'm", "i've", "i'd", "i'll", "you're", "you've", "don't", "didn't",
    "doesn't", "can't", "couldn't", "wasn't", "weren't", "won't", "wouldn't",
    "shouldn't", "it's",
    "recipe", "recipes", "made", "make", "making", "use", "used", "using",
    "comment", "comments", "review", "reviews", "reviewer", "reviewers",
    "search", "function", "site", "website", "page", "app", "author",
    "epicurious", "epi", "bon", "appetit", "appétit", "bonappetit",
    "bonapp", "appetitn", "appetitcom",
    "also", "just", "most", "out", "new", "then", "give", "like", "about",
    "can", "not", "get", "got", "really", "very", "still", "much", "one",
}

NOISE_PATTERNS = [
    r"targetblank",
    r"relnoopener",
    r"noreferrer",
    r"hrefhttps",
    r"http[s]?",
    r"www\.",
    r"\.com",
    r"ugchttps",
    r"valor",
    r"hack",
    r"recovery",
    r"recover",
    r"crypto",
    r"bitcoin",
    r"whatsapp",
    r"telegram",
    r"wallet",
    r"funds",
    r"rootkits",
    r"scam",
    r"fraud",
]

PHRASE_BLOCKLIST = {
    "targetblank relnoopener",
    "relnoopener noreferrer",
    "hrefhttpswwwflexpromealscom targetblank",
    "get hrefhttpswwwflexpromealscom",
    "ugchttpswwwflexpromealscoma delivered",
    "noreferrer ugchttpswwwflexpromealscoma",
    "bon appetit",
    "bon app tit",
}

BUCKET_PATTERNS = {
    "modification": [
        r"\bused\b", r"\badded\b", r"\badd\b", r"\binstead\b",
        r"\bsubbed\b", r"\bsubstitute\b", r"\bsubstituted\b",
        r"\bswap\b", r"\bswapped\b", r"\breplaced\b", r"\breplace\b",
        r"\bdoubled\b", r"\bhalved\b", r"\bcut\b", r"\breduced\b",
        r"\bomitted\b", r"\bskipped\b", r"\bupped\b", r"\bmodified\b",
        r"\balterations?\b", r"\btweaks?\b", r"\badjust(?:ed|ment|ments)?\b",
    ],
    "repeat_intent": [
        r"\bnext time\b", r"\bdefinitely\b", r"\bagain\b", r"\balways\b",
        r"\bevery time\b", r"\bfavorite\b", r"\brotation\b", r"\bkeeper\b",
        r"\bmake again\b", r"\bmake this again\b", r"\bwill make\b",
        r"\bregular\b", r"\bgoto\b", r"\bgo[- ]?to\b",
    ],
    "friction": [
        r"\bdry\b", r"\bbland\b", r"\bsalty\b", r"\bwrong\b", r"\bproblem\b",
        r"\bproblems\b", r"\bissue\b", r"\bissues\b", r"\bdisappointed\b",
        r"\bdisappointing\b", r"\binedible\b", r"\bawful\b", r"\bhorrible\b",
        r"\bunderwhelming\b", r"\bconfusing\b", r"\bunclear\b",
        r"\bovercooked\b", r"\bundercooked\b", r"\bwatery\b", r"\bsoggy\b",
        r"\bgreasy\b", r"\bmushy\b", r"\btoo much\b", r"\btoo little\b",
        r"\btoo salty\b", r"\btoo sweet\b", r"\btoo dry\b",
    ],
    "execution": [
        r"\beasy\b", r"\bquick\b", r"\bsimple\b", r"\bfollowed\b",
        r"\binstructions\b", r"\bdirections\b", r"\btime\b",
        r"\bminutes\b", r"\bcooking\b", r"\bcooked\b", r"\bworked\b",
        r"\bturn(?:ed|s)?\b", r"\bcame\b", r"\bexactly\b", r"\bwritten\b",
    ],
    "positive_sentiment": [
        r"\bdelicious\b", r"\bgood\b", r"\bgreat\b", r"\bamazing\b",
        r"\bperfect\b", r"\bloved\b", r"\bwonderful\b", r"\bfantastic\b",
        r"\bexcellent\b", r"\btasty\b", r"\byum\b", r"\byummy\b",
    ],
    "community_reference": [
        r"\breviews?\b", r"\breviewers?\b", r"\bcomments?\b", r"\bread\b",
        r"\bother reviewers\b", r"\bother reviews\b", r"\bagree\b",
    ],
}


def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""

    normalized = str(text)
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("“", '"').replace("”", '"')
    normalized = normalized.lower()
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"http\S+|www\.\S+", " ", normalized)

    for pattern in NOISE_PATTERNS:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)

    normalized = re.sub(r"[^a-z0-9'\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_noise_comment(text: str) -> bool:
    if not text:
        return True

    token_count = len(text.split())
    if token_count <= 1:
        return True

    noise_hits = sum(bool(re.search(pattern, text, flags=re.IGNORECASE)) for pattern in NOISE_PATTERNS)
    return noise_hits >= 2


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []

    for token in text.split():
        if token in STOPWORDS:
            continue
        if len(token) <= 1 or token.isdigit():
            continue
        if token.startswith("nn"):
            continue
        if re.fullmatch(r"[a-z]*\d+[a-z\d]*", token):
            continue
        tokens.append(token)

    return tokens


def generate_ngrams(tokens: list[str], min_n: int, max_n: int) -> list[str]:
    ngrams: list[str] = []

    for ngram_size in range(min_n, max_n + 1):
        for index in range(len(tokens) - ngram_size + 1):
            phrase = " ".join(tokens[index:index + ngram_size])
            if phrase in PHRASE_BLOCKLIST or len(phrase) < 3:
                continue
            ngrams.append(phrase)

    return ngrams


def assign_bucket(phrase: str) -> str:
    for bucket, patterns in BUCKET_PATTERNS.items():
        if any(re.search(pattern, phrase) for pattern in patterns):
            return bucket
    return "uncategorized"


def build_recipe_phrase_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for recipe_id, group in df.groupby("recipe_id", dropna=False):
        comments = group["clean_comment"].tolist()
        total_comments = len(comments)

        phrase_total_counter: Counter[str] = Counter()
        phrase_comment_counter: Counter[str] = Counter()

        for comment in comments:
            tokens = tokenize(comment)
            if not tokens:
                continue

            phrases = generate_ngrams(tokens, MIN_NGRAM_SIZE, MAX_NGRAM_SIZE)
            phrase_total_counter.update(phrases)
            phrase_comment_counter.update(set(phrases))

        candidate_phrases = [
            phrase
            for phrase, doc_freq in phrase_comment_counter.items()
            if doc_freq >= MIN_DOC_FREQ
        ]

        ranked = sorted(
            candidate_phrases,
            key=lambda phrase: (
                phrase_comment_counter[phrase] / total_comments if total_comments else 0,
                phrase_total_counter[phrase],
                len(phrase.split()),
            ),
            reverse=True,
        )[:TOP_K]

        for phrase in ranked:
            unique_comments = phrase_comment_counter[phrase]
            total_count = phrase_total_counter[phrase]
            coverage_pct = round((unique_comments / total_comments) * 100, 2) if total_comments else 0.0

            rows.append(
                {
                    "recipe_id": str(recipe_id),
                    "phrase": phrase,
                    "ngram_size": len(phrase.split()),
                    "total_count": total_count,
                    "unique_comments": unique_comments,
                    "total_comments_for_recipe": total_comments,
                    "comment_coverage_pct": coverage_pct,
                    "bucket": assign_bucket(phrase),
                }
            )

    summary_df = pd.DataFrame(rows)
    if summary_df.empty:
        return summary_df

    return summary_df.sort_values(
        by=["recipe_id", "comment_coverage_pct", "unique_comments", "total_count"],
        ascending=[True, False, False, False],
    )


def build_recipe_keyword_rollup(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame(
            columns=[
                "recipe_id",
                "top_keywords",
                "top_phrases",
                "keyword_buckets",
                "top_keywords_with_counts",
            ]
        )

    rows: list[dict[str, str]] = []

    for recipe_id, group in summary_df.groupby("recipe_id", sort=False):
        top_keywords = group[group["ngram_size"] == 1].head(8)
        top_phrases = group[group["ngram_size"] >= 2].head(8)
        top_buckets = group[group["bucket"] != "uncategorized"]["bucket"].drop_duplicates().head(5)

        rows.append(
            {
                "recipe_id": str(recipe_id),
                "top_keywords": " | ".join(top_keywords["phrase"].tolist()),
                "top_phrases": " | ".join(top_phrases["phrase"].tolist()),
                "keyword_buckets": " | ".join(top_buckets.tolist()),
                "top_keywords_with_counts": " | ".join(
                    f"{row.phrase} ({row.unique_comments})"
                    for row in top_keywords.itertuples()
                ),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    SUMMARY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    comments_df = load_and_clean_comments()
    comments_df["clean_comment"] = comments_df["comment_text"].map(normalize_text)
    comments_df = comments_df[~comments_df["clean_comment"].map(is_noise_comment)].copy()

    summary_df = build_recipe_phrase_summary(comments_df)
    recipe_rollup_df = build_recipe_keyword_rollup(summary_df)

    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)
    recipe_rollup_df.to_csv(RECIPE_OUTPUT_PATH, index=False)

    print(f"Saved phrase summary to: {SUMMARY_OUTPUT_PATH}")
    print(f"Saved recipe keyword summary to: {RECIPE_OUTPUT_PATH}")
    print(f"Phrase summary rows: {len(summary_df):,}")
    print(f"Recipe summary rows: {len(recipe_rollup_df):,}")


if __name__ == "__main__":
    main()
