import os
import re
from collections import Counter

import pandas as pd
import spacy
from rapidfuzz import fuzz


INPUT_PATH = "outputs/comment_signals.csv"
OUTPUT_PATH = "outputs/recipe_phrases.csv"


MIN_WORDS = 2
MAX_WORDS = 3
MIN_PHRASE_COUNT = 2
MIN_COMMENT_COVERAGE_PCT = 10.0
SPACY_BATCH_SIZE = 256
FUZZY_DUPLICATE_THRESHOLD = 92


NLP = spacy.load("en_core_web_sm", disable=["ner"])


LEADING_TRAILING_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "hers", "him", "his", "i",
    "if", "in", "into", "is", "it", "its", "it's", "me", "my", "of", "on",
    "or", "our", "ours", "she", "so", "that", "the", "their", "theirs",
    "them", "they", "this", "to", "too", "was", "we", "were", "with", "you",
    "your", "yours",
    "just", "really", "very", "more", "most", "much", "many", "not",
    "how", "what", "why", "when", "where", "who",
    "old", "thing", "things", "way", "ways", "time", "times",
    "then", "than", "also", "still", "even", "out", "up", "down",
    "again", "well", "there", "here"
}


BAD_PHRASES = {
    "dot com",
    "money back",
    "investment company",
    "click here",
    "visit site",
    "buy now",
    "telegram",
    "whatsapp",
    "crypto",
    "http",
    "www",
    "hrefhttps",
    "targetblank",
    "relnoopener",
    "noreferrer",
    "ugchttps",
    "i think",
    "i love",
    "i loved",
    "i like",
    "i liked",
    "i used",
    "i made",
    "i followed",
    "i added",
    "i didn't",
    "i dont",
    "not sure",
    "very good",
    "really good",
    "just like",
    "work out",
    "year old",
    "definitely not",
}


BAD_SUBSTRINGS = {
    "dot com",
    "money back",
    "investment company",
    "click here",
    "visit site",
    "buy now",
    "telegram",
    "whatsapp",
    "crypto",
    "http",
    "www",
    "hrefhttps",
    "targetblank",
    "relnoopener",
    "noreferrer",
    "ugchttps",
    "brand partnerships",
    "featured videos",
    "owner welcomes",
    "website cheese",
    "cheese recipies",
    "quality tested",
    "food categories",
    "offers a variety",
}


CONTENT_WORDS = {
    # ingredients
    "oil", "butter", "garlic", "onion", "shallot", "ginger", "lemon", "lime",
    "cream", "milk", "cheese", "cheddar", "parmesan", "mozzarella", "ricotta",
    "yogurt", "broth", "stock", "sauce", "paste", "tomato", "tomatoes",
    "basil", "parsley", "cilantro", "rosemary", "thyme", "oregano", "sage",
    "pepper", "peppers", "salt", "sugar", "honey", "vinegar", "mustard",
    "miso", "soy", "sesame", "coconut", "chocolate", "cocoa", "vanilla",
    "banana", "apple", "pumpkin", "potato", "potatoes", "spinach", "kale",
    "cabbage", "beans", "lentils", "rice", "pasta", "noodles", "flour",
    "egg", "eggs", "chicken", "beef", "pork", "lamb", "turkey", "shrimp",
    "salmon", "cod", "fish", "lobster", "tofu", "parsnips", "carrots",
    "avocado", "tomatillos",

    # dishes
    "cake", "cookies", "cookie", "bread", "brownies", "brownie", "pie",
    "lasagna", "meatloaf", "salad", "soup", "stew", "pudding", "curry",
    "sandwich", "mac", "cheesecake", "muffins", "muffin", "pancakes",
    "frittata", "gnocchi", "risotto", "stuffing", "gravy", "vinaigrette",
    "tenderloin", "meatballs", "dumplings", "cupcakes", "livers",

    # tools / methods / recipe concepts
    "pan", "pot", "oven", "skillet", "sheet", "processor", "blender",
    "mixer", "thermometer", "bowl", "whisk", "spatula", "scoop",
    "bake", "baked", "baking", "roast", "roasted", "roasting", "fried",
    "fry", "grill", "grilled", "saute", "sauteed", "simmer", "boil",
    "boiled", "cooked", "cooking",

    # texture / flavor / meaningful food descriptors
    "crispy", "crunchy", "tender", "moist", "dry", "bland", "salty", "sweet",
    "spicy", "rich", "creamy", "flavor", "flavors", "flavorful", "texture",
    "zest", "crumb", "crust",
}


GENERIC_WORDS = {
    "think", "love", "loved", "like", "liked", "good", "great", "amazing",
    "wonderful", "fantastic", "perfect", "delicious", "easy", "hard",
    "better", "best", "nice", "fine", "sure", "maybe", "probably", "definitely",
    "actually", "pretty", "quite", "rather", "really", "very", "just",
    "again", "still", "also", "ever", "never", "always", "often",
    "time", "times", "thing", "things", "way", "ways", "year", "years",
    "old", "new", "first", "second", "next", "last", "much", "little",
    "lot", "bit", "some", "any", "everything", "something", "nothing",
    "people", "person", "family", "husband", "wife", "daughter", "son",
    "today", "tonight", "morning", "evening", "week", "month",
    "recipe", "recipes", "comment", "comments", "review", "reviews",
    "fabulous", "awesome", "super", "lovely", "yum", "yummy", "favorite",
}


MEASUREMENT_WORDS = {
    "cup", "cups", "tsp", "tbsp", "oz", "lb", "lbs", "quart", "pint",
    "inch", "inches", "minutes", "minute", "hours", "hour", "degree",
    "degrees", "mins", "hrs"
}


NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "half", "quarter"
}


ABSTRACT_WORDS = {
    "flavor", "flavors", "flavorful", "texture", "textures",
    "construction", "consistency", "taste"
}


CONNECTOR_WORDS = {
    "and", "with", "in", "on", "of"
}


SAFE_BIGRAM_ENDINGS = {
    "oil", "milk", "cheese", "zest", "juice", "paste", "sauce", "stock",
    "broth", "flour", "sugar", "cake", "bread", "cookie", "cookies",
    "brownie", "brownies", "pie", "soup", "salad", "stew", "meatloaf",
    "curry", "risotto", "tenderloin", "livers", "processor", "pan", "skillet",
    "garlic"
}


LIST_LIKE_INGREDIENTS = {
    "carrot", "carrots", "onion", "onions", "garlic", "salt", "pepper",
    "rice", "lentils", "beans", "tomato", "tomatoes", "potato", "potatoes",
    "parsnips", "spinach", "kale", "cabbage"
}


QUANTITY_STYLE_WORDS = {
    "half", "quarter", "third", "few", "several", "many"
}


MIDDLE_FUNCTION_WORDS = {
    "the", "a", "an"
}


def normalize_phrase_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def looks_like_numeric_junk(phrase: str) -> bool:
    if not phrase:
        return True

    tokens = phrase.split()

    if all(re.fullmatch(r"\d+", token) for token in tokens):
        return True

    numeric_token_count = sum(bool(re.fullmatch(r"\d+", token)) for token in tokens)
    measurement_token_count = sum(token in MEASUREMENT_WORDS for token in tokens)

    if numeric_token_count >= 1 and numeric_token_count + measurement_token_count == len(tokens):
        return True

    return False


def has_bad_boundaries(tokens: list) -> bool:
    if not tokens:
        return True

    if tokens[0] in LEADING_TRAILING_STOPWORDS:
        return True

    if tokens[-1] in LEADING_TRAILING_STOPWORDS:
        return True

    return False


def has_recipe_content(tokens: list) -> bool:
    return any(token in CONTENT_WORDS for token in tokens)


def is_mostly_generic(tokens: list) -> bool:
    generic_count = sum(token in GENERIC_WORDS for token in tokens)
    return generic_count == len(tokens)


def has_any_generic_word(tokens: list) -> bool:
    return any(token in GENERIC_WORDS for token in tokens)


def has_number_word(tokens: list) -> bool:
    return any(token in NUMBER_WORDS for token in tokens)


def has_enough_content_words(tokens: list, min_content_words: int = 2) -> bool:
    content_count = sum(token in CONTENT_WORDS for token in tokens)
    return content_count >= min_content_words


def count_abstract_words(tokens: list) -> int:
    return sum(token in ABSTRACT_WORDS for token in tokens)


def is_valid_two_word_ngram(tokens: list) -> bool:
    if len(tokens) != 2:
        return True

    first, second = tokens

    if second not in SAFE_BIGRAM_ENDINGS:
        return False

    if first in LIST_LIKE_INGREDIENTS and second in LIST_LIKE_INGREDIENTS:
        return False

    return True


def looks_like_bare_list_phrase(tokens: list) -> bool:
    if not tokens:
        return False

    if any(token in CONNECTOR_WORDS for token in tokens):
        return False

    content_count = sum(token in CONTENT_WORDS for token in tokens)

    if len(tokens) == 3 and content_count >= 2:
        return True

    return False


def looks_like_quantity_phrase(tokens: list) -> bool:
    if len(tokens) != 3:
        return False

    if tokens[0] in QUANTITY_STYLE_WORDS and tokens[1] in MIDDLE_FUNCTION_WORDS:
        return True

    return False


def is_valid_phrase(phrase: str) -> bool:
    if not phrase:
        return False

    phrase = phrase.strip()
    if not phrase:
        return False

    if phrase in BAD_PHRASES:
        return False

    for bad in BAD_SUBSTRINGS:
        if bad in phrase:
            return False

    if looks_like_numeric_junk(phrase):
        return False

    tokens = phrase.split()

    if len(tokens) < MIN_WORDS or len(tokens) > MAX_WORDS:
        return False

    if has_bad_boundaries(tokens):
        return False

    if looks_like_quantity_phrase(tokens):
        return False

    if any(len(token) == 1 and token not in {"x"} for token in tokens):
        return False

    if is_mostly_generic(tokens):
        return False

    if not has_recipe_content(tokens):
        return False

    return True


def is_valid_ngram_phrase(phrase: str) -> bool:
    if not is_valid_phrase(phrase):
        return False

    tokens = phrase.split()

    if has_any_generic_word(tokens):
        return False

    if has_number_word(tokens):
        return False

    if any(re.search(r"\d", token) for token in tokens):
        return False

    if not has_enough_content_words(tokens, min_content_words=2):
        return False

    if count_abstract_words(tokens) >= 2:
        return False

    if not is_valid_two_word_ngram(tokens):
        return False

    if looks_like_bare_list_phrase(tokens):
        return False

    if looks_like_quantity_phrase(tokens):
        return False

    return True


def is_subphrase(shorter: str, longer: str) -> bool:
    if shorter == longer:
        return False

    return f" {shorter} " in f" {longer} "


def are_near_duplicates(a: str, b: str, threshold: int = FUZZY_DUPLICATE_THRESHOLD) -> bool:
    return fuzz.token_sort_ratio(a, b) >= threshold


def dedupe_recipe_phrases(phrase_stats: list) -> list:
    phrase_stats = sorted(
        phrase_stats,
        key=lambda x: (
            -x["unique_comment_count"],
            -x["comment_coverage_pct"],
            -x["total_count"],
            -x["phrase_word_count"],
            x["phrase"],
        ),
    )

    kept = []

    for candidate in phrase_stats:
        phrase = candidate["phrase"]
        duplicate_found = False

        for existing in kept:
            existing_phrase = existing["phrase"]

            if is_subphrase(phrase, existing_phrase):
                duplicate_found = True
                break

            if are_near_duplicates(phrase, existing_phrase):
                duplicate_found = True
                break

        if not duplicate_found:
            kept.append(candidate)

    return kept


def extract_candidate_phrases_from_doc(doc) -> list:
    phrases = []

    for chunk in doc.noun_chunks:
        phrase = normalize_phrase_text(chunk.text)

        if not phrase:
            continue

        if is_valid_phrase(phrase):
            phrases.append(phrase)

    tokens = [
        token.text.lower()
        for token in doc
        if not token.is_space and not token.is_punct
    ]

    for n in range(MIN_WORDS, MAX_WORDS + 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            phrase = normalize_phrase_text(phrase)

            if not phrase:
                continue

            if is_valid_ngram_phrase(phrase):
                phrases.append(phrase)

    return phrases


def build_recipe_phrase_table(df: pd.DataFrame) -> pd.DataFrame:
    recipe_rows = []

    df = df.copy()
    df["clean_comment_text"] = df["clean_comment_text"].fillna("").astype(str)

    print("Running spaCy in batches...")

    docs = NLP.pipe(df["clean_comment_text"].tolist(), batch_size=SPACY_BATCH_SIZE)

    phrase_lists = []
    total_comments = len(df)

    for i, doc in enumerate(docs, start=1):
        phrase_lists.append(extract_candidate_phrases_from_doc(doc))

        if i % 1000 == 0:
            print(f"Processed {i:,} / {total_comments:,} comments")

    df["candidate_phrases"] = phrase_lists

    grouped = df.groupby("recipe_id", dropna=False)

    for recipe_id, group in grouped:
        recipe_comment_count = len(group)

        phrase_total_counter = Counter()
        phrase_comment_counter = Counter()

        for phrases in group["candidate_phrases"]:
            if not phrases:
                continue

            phrase_total_counter.update(phrases)
            phrase_comment_counter.update(set(phrases))

        phrase_candidates = []

        for phrase, total_count in phrase_total_counter.items():
            unique_comment_count = phrase_comment_counter[phrase]
            comment_coverage_pct = round((unique_comment_count / recipe_comment_count) * 100, 2)

            if total_count < MIN_PHRASE_COUNT:
                continue

            if comment_coverage_pct < MIN_COMMENT_COVERAGE_PCT:
                continue

            phrase_candidates.append(
                {
                    "recipe_id": recipe_id,
                    "phrase": phrase,
                    "phrase_word_count": len(phrase.split()),
                    "total_count": total_count,
                    "unique_comment_count": unique_comment_count,
                    "recipe_comment_count": recipe_comment_count,
                    "comment_coverage_pct": comment_coverage_pct,
                }
            )

        deduped_candidates = dedupe_recipe_phrases(phrase_candidates)
        recipe_rows.extend(deduped_candidates)

    if not recipe_rows:
        return pd.DataFrame(
            columns=[
                "recipe_id",
                "phrase",
                "phrase_word_count",
                "total_count",
                "unique_comment_count",
                "recipe_comment_count",
                "comment_coverage_pct",
            ]
        )

    result = pd.DataFrame(recipe_rows)

    result = result.sort_values(
        by=[
            "recipe_id",
            "unique_comment_count",
            "comment_coverage_pct",
            "total_count",
            "phrase_word_count",
            "phrase",
        ],
        ascending=[True, False, False, False, False, True],
    ).reset_index(drop=True)

    return result


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = [
        "recipe_id",
        "clean_comment_text",
        "eligible_for_analysis",
        "signal_any_behavior",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}. "
            f"Available columns: {df.columns.tolist()}"
        )

    df = df[
        (df["eligible_for_analysis"] == 1) &
        (df["signal_any_behavior"] == 1)
    ].copy()

    print(f"Eligible comments after signal filter: {len(df):,}")

    phrase_df = build_recipe_phrase_table(df)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    phrase_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved recipe phrases to {OUTPUT_PATH}")
    print(f"Total recipe-phrase rows: {len(phrase_df):,}")
    print(f"Total recipes with phrases: {phrase_df['recipe_id'].nunique():,}")

    if len(phrase_df) > 0:
        print("\nSample:")
        print(phrase_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()