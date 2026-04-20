from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


EDITORIAL_PATH = Path("outputs/editorial_intelligence.jsonl")
SUMMARIES_PATH = Path("outputs/llm_editor_summaries.jsonl")

OUTPUT_EVAL_PATH = Path("outputs/llm_summary_eval_auto.csv")
OUTPUT_FLAGGED_PATH = Path("outputs/llm_summary_eval_flagged.csv")


ISSUE_PATTERNS = {
    "over-seasoned": [
        "too salty", "salty", "over seasoned", "over-seasoned", "too much salt"
    ],
    "under-seasoned": [
        "bland", "under seasoned", "under-seasoned", "not enough flavor", "tasteless"
    ],
    "too sweet": [
        "too sweet", "overly sweet", "sickly sweet", "cloying"
    ],
    "dry": [
        "dry", "too dry", "dried out"
    ],
    "watery": [
        "watery", "soupy", "thin"
    ],
    "curdled": [
        "curdled", "split", "did not set", "failed to set"
    ],
    "burning": [
        "burned", "burnt", "blackened", "too dark"
    ],
    "crumbly": [
        "crumbly", "fell apart", "fall apart"
    ],
    "unclear": [
        "confusing", "unclear", "not clear"
    ],
}

ACTION_WORDS = {
    "reduce", "increase", "cut", "rebalance", "adjust", "add", "remove",
    "clarify", "review", "lower", "boost", "fix", "change", "use less", "use more"
}

VAGUE_PHRASES = [
    "may need attention",
    "likely deserves attention",
    "could benefit",
    "mixed feedback",
    "manual review",
    "may need editorial review",
    "deserves review",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "with", "on", "as",
    "is", "it", "this", "that", "these", "those", "be", "by", "from", "at",
    "can", "out", "up", "into", "than", "then", "still", "some", "more", "less",
    "very", "even", "also", "but", "if", "so", "while", "because", "when"
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    tokens = re.findall(r"[a-zA-Z']+", text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def extract_issue_hits(text: str) -> set[str]:
    text = normalize_text(text)
    hits = set()
    for label, patterns in ISSUE_PATTERNS.items():
        for p in patterns:
            if p in text:
                hits.add(label)
                break
    return hits


def extract_action_hits(text: str) -> set[str]:
    text = normalize_text(text)
    hits = set()
    for action in ACTION_WORDS:
        if action in text:
            hits.add(action)
    return hits


def evidence_text(recipe: dict[str, Any]) -> str:
    evidence = recipe.get("evidence", {})
    parts = []
    for key in [
        "issue_evidence_comments",
        "fix_evidence_comments",
        "mixed_evidence_comments",
        "adaptation_comments",
    ]:
        parts.extend(evidence.get(key, []) or [])
    return " ".join(parts)


def jaccard_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def score_groundedness(summary: str, recipe: dict[str, Any]) -> tuple[int, str]:
    ev_text = evidence_text(recipe)
    summary_tokens = set(tokenize(summary))
    evidence_tokens = set(tokenize(ev_text))

    token_overlap = jaccard_overlap(summary_tokens, evidence_tokens)

    summary_issues = extract_issue_hits(summary)
    evidence_issues = extract_issue_hits(ev_text)

    unsupported_issues = summary_issues - evidence_issues

    if unsupported_issues:
        return 1, f"unsupported_issue:{','.join(sorted(unsupported_issues))}"

    if summary_issues and summary_issues <= evidence_issues and token_overlap >= 0.10:
        return 5, "strong_issue_and_token_support"

    if token_overlap >= 0.08:
        return 4, "good_token_support"

    if token_overlap >= 0.05:
        return 3, "moderate_token_support"

    if token_overlap > 0:
        return 2, "weak_token_support"

    return 1, "no_support"


def score_correctness(summary: str, recipe: dict[str, Any]) -> tuple[int, str]:
    decision = recipe.get("decision", {})
    issue = decision.get("issue", {})
    display_issue = normalize_text(issue.get("display_issue"))
    issue_family = normalize_text(issue.get("issue_family"))

    summary_issues = extract_issue_hits(summary)

    if display_issue:
        if display_issue in summary:
            return 5, "matched_display_issue"

        mapped = extract_issue_hits(display_issue)
        if mapped and summary_issues & mapped:
            return 4, "matched_issue_semantics"

        if not summary_issues:
            return 2, "no_issue_in_summary"

        return 1, "wrong_issue"

    if issue_family:
        family_map = {
            "flavor": {"over-seasoned", "under-seasoned", "too sweet"},
            "texture": {"dry", "watery", "crumbly", "curdled"},
            "execution": {"burning", "unclear"},
        }
        expected = family_map.get(issue_family, set())
        if summary_issues & expected:
            return 4, "matched_issue_family"
        if "manual review" in normalize_text(summary):
            return 3, "unclear_but_safe"
        return 2, "family_not_matched"

    if "manual review" in normalize_text(summary):
        return 4, "safe_unclear_summary"

    return 3, "no_reference_issue"


def score_actionability(summary: str, recipe: dict[str, Any]) -> tuple[int, str]:
    summary_text = normalize_text(summary)
    summary_actions = extract_action_hits(summary_text)

    recommended_edit = normalize_text(recipe.get("decision", {}).get("recommended_edit"))
    recommended_tokens = set(tokenize(recommended_edit))

    summary_tokens = set(tokenize(summary_text))

    aligned = bool(recommended_tokens and (recommended_tokens & summary_tokens))

    if summary_actions and aligned:
        return 5, "explicit_action_aligned_to_recommended_edit"

    if summary_actions:
        return 4, "explicit_action_present"

    if "manual review" in summary_text:
        return 2, "manual_review_only"

    if "need" in summary_text or "should" in summary_text:
        return 3, "implicit_action"

    return 1, "not_actionable"


def score_specificity(summary: str) -> tuple[int, str]:
    summary_text = normalize_text(summary)
    issue_hits = extract_issue_hits(summary_text)
    action_hits = extract_action_hits(summary_text)

    vague_count = sum(1 for p in VAGUE_PHRASES if p in summary_text)
    token_count = len(tokenize(summary_text))

    if issue_hits and action_hits and vague_count == 0:
        return 5, "concrete_issue_and_fix"

    if issue_hits and token_count >= 10 and vague_count <= 1:
        return 4, "concrete_issue"

    if issue_hits:
        return 3, "issue_only"

    if vague_count >= 2:
        return 1, "too_vague"

    return 2, "weak_specificity"


def overall_score(scores: list[int]) -> float:
    return round(sum(scores) / len(scores), 2)


def flag_row(
    groundedness: int,
    correctness: int,
    actionability: int,
    specificity: int,
    summary: str,
) -> str:
    text = normalize_text(summary)

    if groundedness <= 2:
        return "hallucination_or_ungrounded"
    if correctness <= 2:
        return "wrong_issue"
    if actionability <= 2 and "manual review" not in text:
        return "not_actionable"
    if specificity <= 2:
        return "too_generic"
    if any(p in text for p in VAGUE_PHRASES):
        return "too_hedgy"
    return "pass"


def main() -> None:
    editorial_rows = read_jsonl(EDITORIAL_PATH)
    summary_rows = read_jsonl(SUMMARIES_PATH)

    editorial_by_id = {row["recipe_id"]: row for row in editorial_rows}
    summaries_by_id = {row["recipe_id"]: row for row in summary_rows if row.get("status") == "ok"}

    merged_rows = []
    for recipe_id, summary_row in summaries_by_id.items():
        recipe = editorial_by_id.get(recipe_id)
        if not recipe:
            continue

        summary = summary_row.get("llm_editor_summary", "")
        if not summary:
            continue

        groundedness, groundedness_reason = score_groundedness(summary, recipe)
        correctness, correctness_reason = score_correctness(summary, recipe)
        actionability, actionability_reason = score_actionability(summary, recipe)
        specificity, specificity_reason = score_specificity(summary)

        overall = overall_score([
            groundedness, correctness, actionability, specificity
        ])

        flag = flag_row(
            groundedness=groundedness,
            correctness=correctness,
            actionability=actionability,
            specificity=specificity,
            summary=summary,
        )

        merged_rows.append({
            "recipe_id": recipe_id,
            "title": recipe.get("metadata", {}).get("title"),
            "url": recipe.get("metadata", {}).get("url"),
            "brand": recipe.get("metadata", {}).get("brand"),
            "evidence_strength": recipe.get("llm_readiness", {}).get("evidence_strength"),
            "display_issue": recipe.get("decision", {}).get("issue", {}).get("display_issue"),
            "recommended_edit": recipe.get("decision", {}).get("recommended_edit"),
            "llm_editor_summary": summary,
            "groundedness": groundedness,
            "groundedness_reason": groundedness_reason,
            "correctness": correctness,
            "correctness_reason": correctness_reason,
            "actionability": actionability,
            "actionability_reason": actionability_reason,
            "specificity": specificity,
            "specificity_reason": specificity_reason,
            "overall_score": overall,
            "flag": flag,
        })

    fieldnames = list(merged_rows[0].keys()) if merged_rows else []

    OUTPUT_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_EVAL_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_rows)

    flagged_rows = [row for row in merged_rows if row["flag"] != "pass"]
    with OUTPUT_FLAGGED_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flagged_rows)

    print(f"Wrote {len(merged_rows):,} eval rows to {OUTPUT_EVAL_PATH}")
    print(f"Wrote {len(flagged_rows):,} flagged rows to {OUTPUT_FLAGGED_PATH}")

    if merged_rows:
        avg_groundedness = round(sum(r["groundedness"] for r in merged_rows) / len(merged_rows), 2)
        avg_correctness = round(sum(r["correctness"] for r in merged_rows) / len(merged_rows), 2)
        avg_actionability = round(sum(r["actionability"] for r in merged_rows) / len(merged_rows), 2)
        avg_specificity = round(sum(r["specificity"] for r in merged_rows) / len(merged_rows), 2)
        avg_overall = round(sum(r["overall_score"] for r in merged_rows) / len(merged_rows), 2)

        print()
        print(f"Average groundedness: {avg_groundedness}")
        print(f"Average correctness: {avg_correctness}")
        print(f"Average actionability: {avg_actionability}")
        print(f"Average specificity: {avg_specificity}")
        print(f"Average overall: {avg_overall}")

        flag_counts = Counter(r["flag"] for r in merged_rows)
        print()
        print("Flag distribution:")
        for flag, count in flag_counts.most_common():
            print(f"  {flag}: {count}")


if __name__ == "__main__":
    main()