import os
import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

import pandas as pd


INPUT_PATH = "outputs/comment_signals.csv"
OUTPUT_LONG_PATH = "outputs/recipe_behavioral_phrases.csv"
OUTPUT_WIDE_PATH = "outputs/recipe_behavioral_phrases_wide.csv"

MIN_TOTAL_COUNT = 2

MIN_UNIQUE_COMMENT_COUNT_FRICTION = 2
MIN_UNIQUE_COMMENT_COUNT_MODIFICATION = 1

MIN_COMMENT_COVERAGE_PCT_FRICTION = 5.0
MIN_COMMENT_COVERAGE_PCT_MODIFICATION = 1.0

TOP_N_PER_CATEGORY = 5

REQUIRE_ELIGIBLE_FOR_ANALYSIS = True
REQUIRE_SIGNAL_ANY_BEHAVIOR = True
USE_SIGNAL_GATING = True

SPAM_PATTERNS = [
    r"crypto",
    r"telegram",
    r"whatsapp",
    r"investment",
    r"forex",
    r"loan",
    r"money back",
    r"dot com",
    r"\.com",
    r"http",
    r"www\.",
]

BAD_EDGE_WORDS = {
    "a", "an", "and", "as", "at", "be", "but", "by", "for", "from", "i", "if",
    "in", "into", "is", "it", "me", "my", "of", "on", "or", "so", "that",
    "the", "this", "to", "was", "we", "with", "you"
}

BAD_FULL_PHRASES = {
    "i think",
    "i guess",
    "i feel",
    "this recipe",
    "recipe was",
    "turned out",
    "came out",
    "for me",
    "to me",
    "a little",
    "little bit",
    "bit too",
}

BAD_MODIFICATION_PHRASES = {
    "used",
    "used about",
    "used only",
    "used more",
    "used less",
    "added",
    "added about",
    "added more",
    "substituted",
    "replaced",
    "swapped",
    "reduced",
    "increased",
    "doubled",
    "halved",
    "left out",
    "skipped",
    "instead of",
}

MODIFICATION_END_STOPWORDS = {
    "and", "but", "because", "so", "then", "though", "which", "that", "just",
    "there", "here", "ended", "turn", "turned", "turns", "out", "with", "for",
    "had", "have", "has", "was", "were", "is", "are", "what", "when", "while",
    "after", "before", "than", "into", "onto"
}

MODIFICATION_FILLER_OBJECTS = {
    "about", "only", "more", "less", "some", "little", "bit", "few", "several"
}

MODIFICATION_TOOL_STARTS = {
    "my cookie scoop",
    "cookie scoop",
    "a cookie scoop",
    "my scoop",
    "a pan",
    "pan",
    "sheet pan",
    "baking dish",
    "glass baking dish",
    "bowl",
    "mixer",
    "food processor",
}

FRICTION_NORMALIZATION_MAP = {
    "burned": "burnt",
    "very salty": "too salty",
    "too much salt": "too salty",
    "oversalted": "too salty",
    "was salty": "too salty",
    "came out salty": "too salty",
    "really bland": "bland",
    "very bland": "bland",
    "bland flavor": "bland",
    "was bland": "bland",
    "came out bland": "bland",
    "came out dry": "too dry",
    "was dry": "too dry",
    "too much oil": "too oily",
    "was greasy": "too greasy",
}


CATEGORY_PATTERNS: Dict[str, List[re.Pattern]] = {
    "friction": [
        re.compile(r"\btoo\s+(salty|sweet|dry|wet|bland|greasy|oily|thin|thick|runny|dense|spicy)\b"),
        re.compile(r"\b(very|really|extremely|overly)\s+(salty|sweet|dry|bland|greasy|oily|dense|spicy|tough)\b"),
        re.compile(r"\b(underseasoned|overseasoned|oversalted|undercooked|overcooked)\b"),
        re.compile(r"\b(dry texture|bland flavor|too much salt|too much sugar|too much oil)\b"),
        re.compile(r"\b(was dry|was bland|was salty|was greasy|was tough|came out dry|came out bland)\b"),
        re.compile(r"\b(didn['’]?t work|did not work|didn['’]?t set|did not set|fell apart|too watery|too runny)\b"),
        re.compile(r"\b(curdled|burned|burnt|mushy|gummy|grainy|rubbery|gluey|soggy|bland)\b"),
        re.compile(r"\b(not enough salt|not enough flavor|lacked flavor|needed more salt|needed more acid)\b"),
    ],
    "modification": [
        re.compile(r"\badded\s+(?:more\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bused\s+(?:more\s+|less\s+|only\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bsubstituted\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\breplaced\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bswapped\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bcut\s+back\s+on\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bpull\s+back\s+on\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\breduced\s+(?:the\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bincreased\s+(?:the\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bdoubled\s+(?:the\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bhalved\s+(?:the\s+)?([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bleft\s+out\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bskipped\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\binstead\s+of\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\buse\s+less\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bused\s+less\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bless\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bmaybe\s+less\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\btoo much\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bamount of\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\s+(?:it\s+)?(?:calls\s+for\s+is\s+|was\s+)?too much\b"),
        re.compile(r"\bhalf\s+the\s+amount\s+of\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bless\s+salty\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\blook\s+for\s+a\s+less\s+salty\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\bbig\s+squeeze\s+of\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
        re.compile(r"\blemon\s+zest\s+and\s+([a-z][a-z\-']*(?:\s+[a-z][a-z\-']*){0,5})\b"),
    ],
    "execution": [
        re.compile(r"\bcooked\s+(it\s+)?(longer|shorter)\b"),
        re.compile(r"\bbaked\s+(it\s+)?(longer|shorter)\b"),
        re.compile(r"\broasted\s+(it\s+)?(longer|shorter)\b"),
        re.compile(r"\bneeded\s+\d+\s+(more\s+)?minutes\b"),
        re.compile(r"\btook\s+\d+\s+(more\s+)?minutes\b"),
        re.compile(r"\bfor\s+\d+\s+minutes\s+longer\b"),
        re.compile(r"\b(unclear instructions|instructions were unclear|directions were unclear)\b"),
        re.compile(r"\b(followed the directions|followed instructions exactly)\b"),
        re.compile(r"\bnext time i(?:'ll| will)\s+(cook|bake|roast|broil|simmer)\b"),
        re.compile(r"\bneeded\s+more\s+time\b"),
        re.compile(r"\bneeded\s+less\s+time\b"),
        re.compile(r"\bcook(?:ed|ing)?\s+time\s+was\s+(off|wrong)\b"),
        re.compile(r"\btemp(?:erature)?\s+was\s+(too high|too low|off|wrong)\b"),
        re.compile(r"\b(oven|stove|broiler)\s+ran\s+(hot|cold)\b"),
    ],
}


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_spam(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in SPAM_PATTERNS)


def normalize_friction_phrase(phrase: str) -> str:
    return FRICTION_NORMALIZATION_MAP.get(phrase, phrase)


def normalize_modification_phrase(phrase: str) -> str:
    phrase = phrase.strip().lower()
    phrase = re.sub(r"\s+", " ", phrase)

    tail_cutters = [
        r"\bbecause\b.*$",
        r"\bsince\b.*$",
        r"\bwhich\b.*$",
        r"\bthat\b.*$",
        r"\bthough\b.*$",
        r"\balong\b.*$",
        r"\bdelicious\b.*$",
    ]
    for pattern in tail_cutters:
        phrase = re.sub(pattern, "", phrase).strip()

    replacements = [
        (r"^cut back on\s+", "reduce "),
        (r"^pull back on\s+", "reduce "),
        (r"^reduced\s+", "reduce "),
        (r"^less\s+", "reduce "),
        (r"^maybe less\s+", "reduce "),
        (r"^use less\s+", "reduce "),
        (r"^used less\s+", "reduce "),
        (r"^too much\s+", "reduce "),
        (r"^amount of\s+", "reduce "),
        (r"^half the amount of\s+", "reduce "),
        (r"^halved\s+", "halve "),
        (r"^doubled\s+", "double "),
        (r"^increased\s+", "increase "),
        (r"^left out\s+", "omit "),
        (r"^skipped\s+", "omit "),
    ]
    for pattern, replacement in replacements:
        phrase = re.sub(pattern, replacement, phrase)

    phrase = re.sub(
        r"^(reduce|increase|double|halve|omit|added|used|substituted|replaced|swapped)\s+"
        r"(more|less|only|some|little|bit|few|several)\s+",
        r"\1 ",
        phrase,
    )

    object_replacements = [
        (r"\bcrumbled\s+", ""),
        (r"\bit calls\b.*$", ""),
        (r"\bcalls for\b.*$", ""),
        (r"\bthe recipe\b.*$", ""),
    ]
    for pattern, replacement in object_replacements:
        phrase = re.sub(pattern, replacement, phrase).strip()

    phrase = re.sub(r"^used\s+(.+?)\s+instead of\s+(.+)$", r"substitute \2 with \1", phrase)
    phrase = re.sub(r"^instead of\s+(.+)$", r"substitute \1", phrase)

    if phrase.startswith("added ") and "lemon" in phrase:
        return "added lemon"

    phrase = re.sub(r"\s+", " ", phrase).strip()
    phrase = phrase.strip(" -'")
    return phrase


def trim_object_words(words: List[str]) -> List[str]:
    while words and words[-1] in MODIFICATION_END_STOPWORDS:
        words = words[:-1]
    return words


def clean_modification_object(obj: str) -> str:
    obj = re.sub(r"\s+", " ", obj).strip()
    words = obj.split()

    cut_words = {
        "and", "but", "because", "so", "then", "though", "which", "that",
        "just", "there", "here", "ended", "turn", "turned", "turns", "out",
        "with", "for", "had", "have", "has", "was", "were", "is", "are",
        "what", "when", "while", "after", "before", "than", "into", "onto"
    }

    cleaned = []
    for w in words:
        if w in cut_words:
            break
        cleaned.append(w)

    while cleaned and cleaned[-1] in MODIFICATION_END_STOPWORDS:
        cleaned = cleaned[:-1]

    obj = " ".join(cleaned).strip()
    return obj


def reconstruct_modification_phrase(full_match: str, obj: str) -> str:
    full_match = full_match.strip().lower()
    obj = clean_modification_object(obj)

    if not obj:
        return ""

    if full_match.startswith("too much "):
        return f"reduce {obj}".strip()

    if full_match.startswith("less "):
        return f"reduce {obj}".strip()

    if full_match.startswith("maybe less "):
        return f"reduce {obj}".strip()

    if full_match.startswith("use less "):
        return f"reduce {obj}".strip()

    if full_match.startswith("used less "):
        return f"reduce {obj}".strip()

    if full_match.startswith("amount of "):
        return f"reduce {obj}".strip()

    if full_match.startswith("half the amount of "):
        return f"reduce {obj}".strip()

    if full_match.startswith("pull back on "):
        return f"reduce {obj}".strip()

    if full_match.startswith("less salty "):
        return f"use less salty {obj}".strip()

    if full_match.startswith("look for a less salty "):
        return f"use less salty {obj}".strip()

    if "big squeeze of " in full_match:
        return f"added {obj}".strip()

    if "lemon zest and " in full_match:
        return f"added {obj}".strip()

    prefix_map = [
        ("added ", "added"),
        ("used ", "used"),
        ("substituted ", "substituted"),
        ("replaced ", "replaced"),
        ("swapped ", "swapped"),
        ("cut back on ", "reduce"),
        ("reduced ", "reduce"),
        ("increased ", "increase"),
        ("doubled ", "double"),
        ("halved ", "halve"),
        ("left out ", "omit"),
        ("skipped ", "omit"),
        ("instead of ", "instead of"),
    ]

    for raw_prefix, normalized_prefix in prefix_map:
        if full_match.startswith(raw_prefix):
            return f"{normalized_prefix} {obj}".strip()

    return obj


def clean_extracted_phrase(phrase: str, category: str) -> str:
    phrase = phrase.lower().strip()
    phrase = re.sub(r"\s+", " ", phrase)
    phrase = phrase.strip(" -'")

    words = phrase.split()
    while words and words[0] in BAD_EDGE_WORDS:
        words = words[1:]
    while words and words[-1] in BAD_EDGE_WORDS:
        words = words[:-1]

    phrase = " ".join(words)
    phrase = re.sub(r"\s+", " ", phrase).strip()

    if category == "friction":
        phrase = normalize_friction_phrase(phrase)

    if category == "modification":
        phrase = normalize_modification_phrase(phrase)

    return phrase


def starts_with_tool_phrase(phrase: str) -> bool:
    for tool_phrase in MODIFICATION_TOOL_STARTS:
        if phrase == tool_phrase or phrase.startswith(tool_phrase + " "):
            return True
    return False


def is_valid_phrase(phrase: str, category: str) -> bool:
    if not phrase:
        return False

    if phrase in BAD_FULL_PHRASES:
        return False

    if contains_spam(phrase):
        return False

    if len(phrase) < 4:
        return False

    if phrase.isdigit():
        return False

    words = phrase.split()
    if len(words) < 1 or len(words) > 6:
        return False

    num_count = sum(1 for w in words if re.fullmatch(r"\d+", w))
    if num_count >= max(1, len(words) // 2):
        return False

    if category == "modification":
        if phrase in BAD_MODIFICATION_PHRASES:
            return False

        if len(words) < 2:
            return False

        if phrase.startswith("used to "):
            return False

        if phrase in {"used it", "used this", "used them", "used these"}:
            return False

        if phrase.startswith("used it "):
            return False

        if phrase.startswith("used this "):
            return False

        if phrase.startswith("used these "):
            return False

        if phrase.startswith("used them "):
            return False

        if phrase.endswith(" because") or phrase.endswith(" which") or phrase.endswith(" that"):
            return False

        if phrase.endswith(" along") or phrase.endswith(" since") or phrase.endswith(" delicious"):
            return False

        if phrase in {"added juice", "omit the arugu", "halve shallots"}:
            return False

        if phrase.startswith("reduce ") and len(words) >= 2:
            object_text = " ".join(words[1:])
            if object_text and not starts_with_tool_phrase(object_text):
                return True

        if phrase.startswith("use less salty ") and len(words) >= 4:
            object_text = " ".join(words[3:])
            if object_text and not starts_with_tool_phrase(object_text):
                return True

        if phrase.startswith("added ") and len(words) >= 2:
            object_text = " ".join(words[1:])
            if object_text and not starts_with_tool_phrase(object_text):
                return True

        if words[0] in {
            "used", "added", "substituted", "replaced", "swapped", "reduced",
            "increased", "doubled", "halved", "skipped", "left", "cut", "instead",
            "reduce", "increase", "double", "halve", "omit", "substitute"
        } and len(words) == 2 and words[1] in MODIFICATION_FILLER_OBJECTS:
            return False

        object_text = " ".join(words[1:]) if len(words) > 1 else ""
        if not object_text:
            return False

        if starts_with_tool_phrase(object_text):
            return False

    return True


def category_signal_gate(category: str, row: pd.Series) -> bool:
    if not USE_SIGNAL_GATING:
        return True

    if category == "friction":
        return int(row.get("signal_friction", 0)) == 1

    if category == "modification":
        return int(row.get("signal_modification", 0)) == 1 or int(row.get("signal_substitution", 0)) == 1

    if category == "execution":
        return (
            int(row.get("signal_friction", 0)) == 1
            or int(row.get("signal_modification", 0)) == 1
            or int(row.get("signal_substitution", 0)) == 1
        )

    return True


def extract_matches_for_category(text: str, category: str) -> List[str]:
    matches: List[str] = []

    for pattern in CATEGORY_PATTERNS[category]:
        for match in pattern.finditer(text):
            if category == "modification":
                full_match = match.group(0)
                obj = match.group(1) if match.lastindex else ""
                phrase = reconstruct_modification_phrase(full_match, obj)
            else:
                phrase = match.group(0)

            phrase = clean_extracted_phrase(phrase, category)

            if is_valid_phrase(phrase, category):
                matches.append(phrase)

    return dedupe_preserve_order(matches)


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def filter_input_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required_cols = ["recipe_id"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    text_col = None
    for candidate in ["clean_comment_text", "comment_text"]:
        if candidate in df.columns:
            text_col = candidate
            break

    if text_col is None:
        raise ValueError("Missing text column: expected clean_comment_text or comment_text")

    df["__text__"] = df[text_col].fillna("").astype(str)

    if "comment_id" not in df.columns:
        df["comment_id"] = (
            df["recipe_id"].astype(str)
            + "__"
            + df["__text__"].astype(str).str.slice(0, 80)
            + "__"
            + df.index.astype(str)
        )

    if REQUIRE_ELIGIBLE_FOR_ANALYSIS and "eligible_for_analysis" in df.columns:
        df = df[df["eligible_for_analysis"] == 1]

    if REQUIRE_SIGNAL_ANY_BEHAVIOR and "signal_any_behavior" in df.columns:
        df = df[df["signal_any_behavior"] == 1]

    if "is_noise" in df.columns:
        df = df[df["is_noise"] != 1]

    df["normalized_text"] = df["__text__"].map(normalize_text)
    df = df[df["normalized_text"].str.len() > 0]
    df = df[~df["normalized_text"].map(contains_spam)]

    return df


def build_phrase_rows(df: pd.DataFrame) -> pd.DataFrame:
    recipe_comment_counts = (
        df.groupby("recipe_id")["comment_id"]
        .nunique()
        .rename("recipe_comment_count")
        .reset_index()
    )

    phrase_counter: Dict[Tuple[str, str, str], int] = Counter()
    unique_comment_tracker: Dict[Tuple[str, str, str], set] = defaultdict(set)

    for _, row in df.iterrows():
        recipe_id = row["recipe_id"]
        comment_id = row["comment_id"]
        text = row["normalized_text"]

        for category in CATEGORY_PATTERNS.keys():
            if not category_signal_gate(category, row):
                continue

            phrases = extract_matches_for_category(text, category)
            for phrase in phrases:
                key = (recipe_id, category, phrase)
                phrase_counter[key] += 1
                unique_comment_tracker[key].add(comment_id)

    rows = []
    for (recipe_id, category, phrase), total_count in phrase_counter.items():
        unique_comment_count = len(unique_comment_tracker[(recipe_id, category, phrase)])
        rows.append(
            {
                "recipe_id": recipe_id,
                "category": category,
                "phrase": phrase,
                "phrase_word_count": len(phrase.split()),
                "total_count": total_count,
                "unique_comment_count": unique_comment_count,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out = out.merge(recipe_comment_counts, on="recipe_id", how="left")
    out["comment_coverage_pct"] = (
        out["unique_comment_count"] / out["recipe_comment_count"] * 100.0
    ).round(2)

    def passes_threshold(row):
        if row["category"] == "friction":
            return row["comment_coverage_pct"] >= MIN_COMMENT_COVERAGE_PCT_FRICTION
        if row["category"] == "modification":
            return row["comment_coverage_pct"] >= MIN_COMMENT_COVERAGE_PCT_MODIFICATION
        return False

    def passes_unique_threshold(row):
        if row["category"] == "friction":
            return row["unique_comment_count"] >= MIN_UNIQUE_COMMENT_COUNT_FRICTION
        if row["category"] == "modification":
            return row["unique_comment_count"] >= MIN_UNIQUE_COMMENT_COUNT_MODIFICATION
        return False

    out = out[
        (out["total_count"] >= MIN_TOTAL_COUNT)
        & (out.apply(passes_unique_threshold, axis=1))
        & (out.apply(passes_threshold, axis=1))
    ].copy()

    if out.empty:
        return out

    out = out.sort_values(
        by=[
            "recipe_id",
            "category",
            "unique_comment_count",
            "comment_coverage_pct",
            "total_count",
            "phrase_word_count",
            "phrase",
        ],
        ascending=[True, True, False, False, False, False, True],
    ).reset_index(drop=True)

    return out


def build_wide_output(long_df: pd.DataFrame, top_n: int = TOP_N_PER_CATEGORY) -> pd.DataFrame:
    if long_df.empty:
        return pd.DataFrame()

    records = []

    for (recipe_id, category), group in long_df.groupby(["recipe_id", "category"], sort=True):
        group = group.head(top_n).reset_index(drop=True)

        row = {
            "recipe_id": recipe_id,
            "category": category,
        }

        for i, (_, r) in enumerate(group.iterrows(), start=1):
            row[f"top_phrase_{i}"] = r["phrase"]
            row[f"top_phrase_{i}_coverage_pct"] = r["comment_coverage_pct"]
            row[f"top_phrase_{i}_unique_comment_count"] = r["unique_comment_count"]
            row[f"top_phrase_{i}_total_count"] = r["total_count"]

        records.append(row)

    return pd.DataFrame(records)


def main() -> None:
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, low_memory=False)
    print(f"Loaded {len(df):,} rows from {INPUT_PATH}")

    filtered_df = filter_input_df(df)
    print(f"Rows after filtering: {len(filtered_df):,}")

    long_df = build_phrase_rows(filtered_df)

    if long_df.empty:
        print("No behavioral phrases found after filtering.")
        pd.DataFrame().to_csv(OUTPUT_LONG_PATH, index=False)
        pd.DataFrame().to_csv(OUTPUT_WIDE_PATH, index=False)
        return

    os.makedirs(os.path.dirname(OUTPUT_LONG_PATH), exist_ok=True)

    long_df.to_csv(OUTPUT_LONG_PATH, index=False)
    print(f"Saved behavioral phrases to {OUTPUT_LONG_PATH}")
    print(f"Total recipe-category-phrase rows: {len(long_df):,}")
    print(f"Total recipes with behavioral phrases: {long_df['recipe_id'].nunique():,}")

    wide_df = build_wide_output(long_df, top_n=TOP_N_PER_CATEGORY)
    wide_df.to_csv(OUTPUT_WIDE_PATH, index=False)
    print(f"Saved wide behavioral phrase output to {OUTPUT_WIDE_PATH}")

    print("\nSample long output:")
    print(long_df.head(20).to_string(index=False))

    print("\nSample wide output:")
    print(wide_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()