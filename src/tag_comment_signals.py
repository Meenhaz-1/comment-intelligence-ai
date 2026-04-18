import os
import re

import pandas as pd


INPUT_PATH = "outputs/cleaned_comments.csv"
OUTPUT_PATH = "outputs/comment_signals.csv"


SIGNAL_PATTERNS = {
    "signal_made": [
        r"\bi made\b",
        r"\bmade this\b",
        r"\bjust made\b",
        r"\bmade it\b",
        r"\bmade these\b",
        r"\btried it\b",
        r"\btried this\b",
        r"\bcooked this\b",
        r"\bbaked this\b",
        r"\bprepared this\b",
        r"\bmaking this\b",
        r"\bmade\b",
        r"\btried\b",
        r"\bcooked\b",
        r"\bbaked\b",
        r"\bprepared\b",
        r"\bmaking\b",
    ],
    "signal_modification": [
        r"\bi added\b",
        r"\badded\b",
        r"\bi used\b",
        r"\bused\b",
        r"\bextra\b",
        r"\bmore\b",
        r"\bless\b",
        r"\bcut back\b",
        r"\bincreased\b",
        r"\breduced\b",
        r"\bdoubled\b",
        r"\bhalved\b",
        r"\bleft out\b",
        r"\bomitted\b",
        r"\bchanged\b",
        r"\badjusted\b",
        r"\btweaked\b",
        r"\bcut the\b",
        r"\bcut back on\b",
        r"\badded extra\b",
        r"\bused extra\b",
    ],
    "signal_substitution": [
        r"\binstead of\b",
        r"\bin place of\b",
        r"\bsubbed\b",
        r"\bsubstitute[d]?\b",
        r"\bswapped\b",
        r"\bswap\b",
        r"\breplaced\b",
        r"\bused .* instead\b",
    ],
    "signal_positive": [
        r"\bdelicious\b",
        r"\bgreat\b",
        r"\bamazing\b",
        r"\bfantastic\b",
        r"\bperfect\b",
        r"\blove\b",
        r"\bloved\b",
        r"\bwonderful\b",
        r"\bexcellent\b",
        r"\btasty\b",
        r"\byummy\b",
        r"\bkeeper\b",
        r"\bhit\b",
        r"\boutstanding\b",
        r"\bfabulous\b",
        r"\bphenomenal\b",
        r"\bawesome\b",
        r"\bso good\b",
        r"\breally good\b",
    ],
    "signal_friction": [
        r"\bdry\b",
        r"\bbland\b",
        r"\btoo salty\b",
        r"\btoo sweet\b",
        r"\btoo spicy\b",
        r"\btoo much\b",
        r"\btoo little\b",
        r"\bwrong\b",
        r"\bproblem\b",
        r"\bissue\b",
        r"\bissues\b",
        r"\bdisappointed\b",
        r"\bdisappointing\b",
        r"\bconfusing\b",
        r"\bfrustrating\b",
        r"\bwatery\b",
        r"\bsalty\b",
        r"\bburnt\b",
        r"\bovercooked\b",
        r"\bundercooked\b",
        r"\bdidn't work\b",
        r"\bdidnt work\b",
        r"\bwent wrong\b",
        r"\bmissing something\b",
        r"\boff\b",
        r"\btook too long\b",
        r"\btwice as long\b",
        r"\bmore time\b",
        r"\blonger than\b",
        r"\bnot enough\b",
        r"\bnever thickened\b",
        r"\bdidn't caramelize\b",
        r"\bdidnt caramelize\b",
    ],
    "signal_repeat_intent": [
        r"\bmake again\b",
        r"\bmaking again\b",
        r"\bwill make\b",
        r"\bwill make again\b",
        r"\bwill be making again\b",
        r"\bdefinitely make\b",
        r"\bmake this again\b",
        r"\bkeeper\b",
        r"\bgo to\b",
        r"\bgo to recipe\b",
        r"\bgo-to recipe\b",
        r"\bin rotation\b",
        r"\bregular rotation\b",
        r"\bwill prepare again\b",
        r"\bcan't wait to make\b",
        r"\bcant wait to make\b",
        r"\bmake this often\b",
        r"\bmake often\b",
        r"\bi'll make again\b",
        r"\bill make again\b",
        r"\bnext time\b",
    ],
}


NEGATED_FRICTION_PHRASES = [
    "not too sweet",
    "not too salty",
    "not too spicy",
    "not too rich",
    "not too heavy",
    "not too dry",
    "not too bland",
]


def compile_patterns(signal_patterns: dict) -> dict:
    """
    Compile regex patterns once for speed and cleanliness.
    """
    compiled = {}
    for signal_name, patterns in signal_patterns.items():
        compiled[signal_name] = [
            re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns
        ]
    return compiled


def has_any_pattern(text: str, compiled_patterns: list) -> bool:
    """
    Return True if any compiled regex matches the text.
    """
    if pd.isna(text):
        return False

    text = str(text)
    for pattern in compiled_patterns:
        if pattern.search(text):
            return True

    return False


def count_matches(text: str, compiled_patterns: list) -> int:
    """
    Count unique pattern matches for a signal in the text.
    Useful for debugging signal strength.
    """
    if pd.isna(text):
        return 0

    text = str(text)
    match_count = 0

    for pattern in compiled_patterns:
        if pattern.search(text):
            match_count += 1

    return match_count


def remove_negated_friction_phrases(text: str) -> str:
    """
    Remove clearly positive negated friction phrases so they do not trigger friction.
    """
    if pd.isna(text):
        return ""

    text = str(text)

    for phrase in NEGATED_FRICTION_PHRASES:
        text = text.replace(phrase, " ")

    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = ["comment_id", "recipe_id", "clean_comment_text", "is_noise"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {df.columns.tolist()}"
        )

    compiled_signal_patterns = compile_patterns(SIGNAL_PATTERNS)

    # Friction gets its own cleaned input so negated complaints do not misfire
    df["friction_text"] = df["clean_comment_text"].apply(remove_negated_friction_phrases)

    # Create binary signal flags
    for signal_name, patterns in compiled_signal_patterns.items():
        source_col = (
            "friction_text" if signal_name == "signal_friction" else "clean_comment_text"
        )
        df[signal_name] = (
            df[source_col].apply(lambda x: has_any_pattern(x, patterns)).astype(int)
        )

    # Optional: add match counts for debugging
    for signal_name, patterns in compiled_signal_patterns.items():
        count_col = f"{signal_name}_match_count"
        source_col = (
            "friction_text" if signal_name == "signal_friction" else "clean_comment_text"
        )
        df[count_col] = df[source_col].apply(lambda x: count_matches(x, patterns))

    # Create a simple total signal count
    signal_cols = list(compiled_signal_patterns.keys())
    df["total_signal_count"] = df[signal_cols].sum(axis=1)

    # Create a broad engagement signal
    df["signal_any_behavior"] = (df["total_signal_count"] > 0).astype(int)

    # Recommended filtered analysis version
    df["eligible_for_analysis"] = (
        (df["is_noise"] == False)
        & (df["clean_comment_text"].fillna("").str.strip() != "")
    ).astype(int)

    preferred_order = [
        "comment_id",
        "recipe_id",
        "comment_text",
        "clean_comment_text",
        "is_noise",
        "eligible_for_analysis",
        "signal_any_behavior",
        "signal_made",
        "signal_modification",
        "signal_substitution",
        "signal_positive",
        "signal_friction",
        "signal_repeat_intent",
        "signal_made_match_count",
        "signal_modification_match_count",
        "signal_substitution_match_count",
        "signal_positive_match_count",
        "signal_friction_match_count",
        "signal_repeat_intent_match_count",
        "total_signal_count",
        "created_at",
        "brand",
        "author_id",
        "display_name",
        "location",
        "will_prepare_again",
        "meta_data",
    ]

    ordered_cols = [col for col in preferred_order if col in df.columns]
    remaining_cols = [
        col for col in df.columns if col not in ordered_cols and col != "friction_text"
    ]
    df = df[ordered_cols + remaining_cols]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved tagged comments to {OUTPUT_PATH}")
    print(df.head(10).to_string(index=False))

    print("\nSignal totals:")
    for signal_name in signal_cols:
        print(f"{signal_name}: {int(df[signal_name].sum())}")


if __name__ == "__main__":
    main()