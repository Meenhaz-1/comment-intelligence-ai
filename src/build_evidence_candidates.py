import re
import pandas as pd

INPUT_PATH = "outputs/comment_signals.csv"
OUTPUT_PATH = "outputs/evidence_candidates.csv"

MIN_LEN = 30
MAX_LEN = 600
MAX_PER_RECIPE_PER_TYPE = 3

# Specific recipe problem language only.
SPECIFIC_ISSUE_PATTERNS = [
    r"\btoo salty\b",
    r"\btoo sweet\b",
    r"\btoo bitter\b",
    r"\btoo dry\b",
    r"\btoo wet\b",
    r"\btoo greasy\b",
    r"\btoo oily\b",
    r"\btoo thin\b",
    r"\btoo thick\b",
    r"\btoo bland\b",
    r"\bbland\b",
    r"\bbitter\b",
    r"\bdry\b",
    r"\bgreasy\b",
    r"\boily\b",
    r"\bwatery\b",
    r"\brunny\b",
    r"\bmushy\b",
    r"\bgummy\b",
    r"\brubbery\b",
    r"\bcrumbly\b",
    r"\btough\b",
    r"\bburnt\b",
    r"\bburned\b",
    r"\bundercooked\b",
    r"\bovercooked\b",
    r"\boverdone\b",
    r"\braw\b",
    r"\btoo much salt\b",
    r"\btoo much sugar\b",
    r"\btoo much seaweed\b",
    r"\btoo much cumin\b",
    r"\btoo much oil\b",
    r"\btoo much liquid\b",
    r"\btoo much filling\b",
    r"\bnot enough salt\b",
    r"\bnot enough flavor\b",
    r"\bnot enough seasoning\b",
    r"\bnot flavorful enough\b",
    r"\bneeded more salt\b",
    r"\bneeded more acid\b",
    r"\bneeded more acidity\b",
    r"\bneeded more flavor\b",
    r"\bneeded more seasoning\b",
    r"\boverpowered\b",
    r"\bmissing step\b",
    r"\bmissing ingredient\b",
    r"\bmissing instructions\b",
    r"\bconfusing instructions\b",
    r"\bthe ratio .* was off\b",
    r"\bratio .* was off\b",
    r"\bflavor was off\b",
    r"\bflavors were off\b",
    r"\bconsistency was off\b",
    r"\btoo hot\b",
    r"\btoo spicy\b",
    r"\btoo sour\b",
    r"\btoo bready\b",
    r"\btoo heavy\b",
    r"\btoo dense\b",
    r"\btoo loose\b",
    r"\btoo watery\b",
    r"\btoo runny\b",
    r"\btoo mushy\b",
    r"\btoo crumbly\b",
    r"\blacked depth\b",
    r"\blacked flavor\b",
    r"\blacking flavor\b",
    r"\blacked seasoning\b",
    r"\blacked\b",
]

# Vague negative sentiment. Not enough on its own.
VAGUE_NEGATIVE_PATTERNS = [
    r"\bdidn't work\b",
    r"\bdidnt work\b",
    r"\bdisappointing\b",
    r"\bawful\b",
    r"\bgross\b",
    r"\bbad\b",
    r"\bnot good\b",
    r"\bunderwhelming\b",
    r"\bnot my favorite\b",
    r"\bwouldn't make again\b",
    r"\bwouldnt make again\b",
    r"\bwould not make again\b",
    r"\bnot recommend\b",
    r"\bwould not recommend\b",
]

# Any explicit user change.
FIX_PATTERNS = [
    r"\badded\b",
    r"\badd more\b",
    r"\bused\b",
    r"\buse less\b",
    r"\buse more\b",
    r"\bsubstitute(?:d)?\b",
    r"\bsubstitution\b",
    r"\bswap(?:ped)?\b",
    r"\breplace(?:d)?\b",
    r"\breduced\b",
    r"\breduce\b",
    r"\bcut back\b",
    r"\bcut the\b",
    r"\bleft out\b",
    r"\bomit(?:ted)?\b",
    r"\bdouble(?:d)?\b",
    r"\bhalf\b",
    r"\bhalved\b",
    r"\bincrease(?:d)?\b",
    r"\bdecrease(?:d)?\b",
    r"\bserved .* on the side\b",
    r"\bused less\b",
    r"\bused more\b",
    r"\bturned down\b",
    r"\bcooked .* longer\b",
    r"\bcooked .* less\b",
    r"\bbaked .* longer\b",
    r"\bbaked .* less\b",
    r"\bmarinated .* longer\b",
    r"\badded lemon\b",
    r"\badded lime\b",
    r"\badded acid\b",
    r"\badded vinegar\b",
    r"\badded more salt\b",
    r"\badded more seasoning\b",
    r"\badded more spices\b",
    r"\bused fewer\b",
    r"\bused half\b",
]

# Strong bridge between issue and change.
CAUSAL_PATTERNS = [
    r"\bso\b",
    r"\bbecause\b",
    r"\bto fix\b",
    r"\bto balance\b",
    r"\bto offset\b",
    r"\bto help\b",
    r"\bhelped\b",
    r"\bworked better\b",
    r"\bnext time\b",
    r"\binstead\b",
    r"\botherwise\b",
    r"\bwhich helped\b",
    r"\bthat helped\b",
    r"\bthat fixed it\b",
    r"\bthis fixed it\b",
    r"\bmade it better\b",
    r"\bto make it better\b",
]

# Things that are not recipe-quality evidence for this layer.
META_EXCLUDE_PATTERNS = [
    r"\bwebsite\b",
    r"\bweb site\b",
    r"\brecipe box\b",
    r"\bsaved recipes\b",
    r"\bsearch function\b",
    r"\bsubscription\b",
    r"\bpaywall\b",
    r"\bapp\b",
    r"\bprogram\b",
    r"\bbon appetit site\b",
    r"\bepicurious app\b",
    r"\bgmail dot com\b",
    r"\binvestment\b",
    r"\bcrypto\b",
    r"\btelegram\b",
    r"\bdownload the app\b",
    r"\bproblem solved\b",
    r"\bthere are no instructions any longer\b",
    r"\bno instructions any longer\b",
    r"\bold copy\b",
    r"\byou completely changed the original recipe\b",
    r"\bchanged the original recipe\b",
    r"\bversion of this recipe\b",
    r"\bingredient list\b",
    r"\bsite user\b",
    r"\bpublished\b",
    r"\bthe recipe no longer\b",
    r"\bmissing from the site\b",
    r"\bfrom the site\b",
]

QUESTION_PATTERNS = [
    r"^\s*does anyone know",
    r"^\s*has anyone tried",
    r"^\s*question\b",
    r"\?$",
    r"\bam i missing something\b",
    r"\bshould i\b",
    r"\bhow do i\b",
    r"\bwhat do i do\b",
    r"\bcan i\b",
]

PRAISE_PATTERNS = [
    r"\bdelicious\b",
    r"\bamazing\b",
    r"\bfantastic\b",
    r"\bgreat\b",
    r"\bwonderful\b",
    r"\bkeeper\b",
    r"\bin the rotation\b",
    r"\bmake again\b",
    r"\bwill make again\b",
    r"\bhit\b",
    r"\bloved it\b",
    r"\blove this\b",
    r"\bgo to\b",
]

FILLER_PATTERNS = [
    r"\bi think\b",
    r"\bi feel like\b",
    r"\bhonestly\b",
    r"\bpersonally\b",
    r"\boverall\b",
    r"\bto be fair\b",
    r"\breally\b",
    r"\bvery\b",
    r"\bkind of\b",
    r"\bsort of\b",
]

# These indicate the comment is about a recipe problem specifically,
# not just a general tweak.
PROBLEM_CONTEXT_PATTERNS = [
    r"\btoo\b",
    r"\bnot enough\b",
    r"\bneeded more\b",
    r"\bneeded less\b",
    r"\boverpowered\b",
    r"\bwas off\b",
    r"\bwere off\b",
    r"\bturned out\b",
    r"\bcame out\b",
    r"\bended up\b",
    r"\bto balance\b",
    r"\bto offset\b",
    r"\bto fix\b",
    r"\bworked better\b",
    r"\bhelped\b",
]

# These are neutral riff/adaptation cues.
ADAPTATION_CUES = [
    r"\bif you have\b",
    r"\bi didn't have\b",
    r"\bi didnt have\b",
    r"\bsince that's what i had\b",
    r"\bsince that is what i had\b",
    r"\bon hand\b",
    r"\bfor extra flavor\b",
    r"\bfor a little kick\b",
    r"\bfor garnish\b",
    r"\bserved with\b",
]


def normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def has_match(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def count_matches(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text))


def trim_comment(text: str, max_len: int = 160) -> str:
    text = normalize_text(text)
    for pat in FILLER_PATTERNS:
        text = re.sub(pat, "", text)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return text[:max_len]

    def sent_score(sentence: str) -> int:
        score = 0
        if has_match(sentence, SPECIFIC_ISSUE_PATTERNS):
            score += 4
        if has_match(sentence, FIX_PATTERNS):
            score += 3
        if has_match(sentence, CAUSAL_PATTERNS):
            score += 3
        if has_match(sentence, META_EXCLUDE_PATTERNS):
            score -= 8
        if has_match(sentence, QUESTION_PATTERNS):
            score -= 6
        if has_match(sentence, PRAISE_PATTERNS) and not has_match(sentence, SPECIFIC_ISSUE_PATTERNS):
            score -= 1
        if len(sentence) < 20:
            score -= 1
        return score

    best = sorted(sentences, key=sent_score, reverse=True)[0]
    if len(best) > max_len:
        best = best[: max_len - 3].rstrip() + "..."
    return best


def classify_evidence_type(text: str) -> str:
    specific_issue = has_match(text, SPECIFIC_ISSUE_PATTERNS)
    vague_negative = has_match(text, VAGUE_NEGATIVE_PATTERNS)
    fix = has_match(text, FIX_PATTERNS)
    causal = has_match(text, CAUSAL_PATTERNS)
    meta = has_match(text, META_EXCLUDE_PATTERNS)
    question = has_match(text, QUESTION_PATTERNS)
    praise = has_match(text, PRAISE_PATTERNS)
    problem_context = has_match(text, PROBLEM_CONTEXT_PATTERNS)

    if meta or question:
        return "exclude"

    # Mixed must be explicit and should be rare.
    if specific_issue and fix and causal:
        if praise:
            return "problem_solving_fix"
        return "mixed"

    # Problem-solving fix must have an explicit issue.
    if fix and specific_issue:
        return "problem_solving_fix"

    # Issue only must be specific and not praise-heavy.
    if specific_issue:
        if praise:
            return "exclude"
        if not problem_context:
            return "exclude"
        return "issue"

    # Neutral adaptation: change without a clear problem.
    if fix:
        return "adaptation"

    # Vague negativity alone is not useful enough.
    if vague_negative:
        return "exclude"

    return "exclude"


def evidence_score(text: str, evidence_type: str) -> float:
    score = 0.0

    specific_issue_count = count_matches(text, SPECIFIC_ISSUE_PATTERNS)
    fix_count = count_matches(text, FIX_PATTERNS)
    causal_count = count_matches(text, CAUSAL_PATTERNS)
    praise_count = count_matches(text, PRAISE_PATTERNS)
    vague_negative = has_match(text, VAGUE_NEGATIVE_PATTERNS)
    adaptation_cue = has_match(text, ADAPTATION_CUES)

    if 40 <= len(text) <= 220:
        score += 1.5
    elif len(text) < 25:
        score -= 1.0
    elif len(text) > 300:
        score -= 0.75

    if evidence_type == "issue":
        score += 3.5
        score += specific_issue_count * 1.75
        if vague_negative:
            score -= 1.0
        if praise_count > 0:
            score -= 2.0

    elif evidence_type == "problem_solving_fix":
        score += 4.0
        score += specific_issue_count * 1.75
        score += fix_count * 1.0
        score += causal_count * 1.0
        if praise_count > 0 and specific_issue_count == 0:
            score -= 2.0

    elif evidence_type == "adaptation":
        score += 1.5
        score += fix_count * 0.5
        if adaptation_cue:
            score += 0.5
        if praise_count > 0:
            score += 0.25

    elif evidence_type == "mixed":
        score += 4.5
        score += specific_issue_count * 1.75
        score += fix_count * 1.0
        score += causal_count * 1.75
        if praise_count > 0:
            score -= 2.0

    if has_match(text, META_EXCLUDE_PATTERNS):
        score -= 10.0
    if has_match(text, QUESTION_PATTERNS):
        score -= 8.0
    if vague_negative and not has_match(text, SPECIFIC_ISSUE_PATTERNS):
        score -= 3.0

    return score


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    df = df[df["clean_comment_text"].notna()].copy()
    df["clean_comment_text"] = df["clean_comment_text"].astype(str)
    df["comment_length"] = df["clean_comment_text"].str.len()

    if "eligible_for_analysis" in df.columns:
        df = df[df["eligible_for_analysis"] == 1].copy()

    df = df[(df["comment_length"] >= MIN_LEN) & (df["comment_length"] <= MAX_LEN)].copy()

    df["normalized_comment"] = df["clean_comment_text"].map(normalize_text)
    df["evidence_type"] = df["normalized_comment"].map(classify_evidence_type)
    df = df[df["evidence_type"] != "exclude"].copy()

    df["trimmed_comment"] = df["normalized_comment"].map(trim_comment)
    df["evidence_score"] = df.apply(
        lambda row: evidence_score(row["normalized_comment"], row["evidence_type"]),
        axis=1,
    )

    df = df[df["evidence_score"] > 0].copy()

    df = df.sort_values(
        by=["recipe_id", "evidence_type", "evidence_score", "comment_length"],
        ascending=[True, True, False, True],
    ).copy()

    df["rank_within_recipe_type"] = (
        df.groupby(["recipe_id", "evidence_type"]).cumcount() + 1
    )
    df = df[df["rank_within_recipe_type"] <= MAX_PER_RECIPE_PER_TYPE].copy()

    out_cols = [
        "recipe_id",
        "comment_id" if "comment_id" in df.columns else None,
        "evidence_type",
        "evidence_score",
        "rank_within_recipe_type",
        "trimmed_comment",
        "clean_comment_text",
        "signal_friction",
        "signal_modification",
        "signal_substitution",
    ]
    out_cols = [col for col in out_cols if col is not None]

    out = df[out_cols].copy()
    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(out):,} rows to {OUTPUT_PATH}")
    print("\nEvidence type counts:")
    print(out["evidence_type"].value_counts())


if __name__ == "__main__":
    main()