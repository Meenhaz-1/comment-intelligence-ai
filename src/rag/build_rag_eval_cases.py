#!/usr/bin/env python3
"""
Build RAG eval sets for recipe-level QA.

Supports two modes:

1. clean
- canonical, high-confidence eval set
- stricter issue alignment
- best for baseline benchmarking

2. hard
- noisier, more realistic eval set
- allows mixed signals, lower evidence, weaker canonical alignment
- best for stress testing

Inputs
- outputs/editorial_intelligence.jsonl
- outputs/rag_corpus.jsonl

Output
- outputs/rag_eval_cases.jsonl (or custom path)
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


DEFAULT_EDITORIAL_PATH = "outputs/editorial_intelligence.jsonl"
DEFAULT_CORPUS_PATH = "outputs/rag_corpus.jsonl"
DEFAULT_OUTPUT_PATH = "outputs/rag_eval_cases.jsonl"


CLEAN_TARGET_BUCKETS = {
    "over-seasoned": 2,
    "dry": 2,
    "under-seasoned": 2,
    "too sweet": 2,
    "quantity": 1,
    "custard / setting": 1,
}

HARD_TARGET_BUCKETS = {
    "over-seasoned": 3,
    "dry": 3,
    "under-seasoned": 3,
    "too sweet": 3,
    "quantity": 2,
    "custard / setting": 2,
}


QUERY_CONFIG: Dict[str, Dict[str, Any]] = {
    "over-seasoned": {
        "queries": [
            {"query": "why are users saying this is too salty?", "query_type": "issue"},
            {"query": "what are users doing to fix the salt issue?", "query_type": "fix"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "high friction",
                    "clear fix signals",
                    "seasoning issue is fixable",
                ],
            },
        ],
        "expected_issue": "over-seasoned",
        "acceptable_issues": ["over-seasoned", "too salty"],
        "acceptable_fix_themes": [
            "reduce salt",
            "reduce salty ingredients",
            "reduce feta",
            "reduce olives",
            "add acidity",
            "dilute seasoning",
        ],
    },
    "dry": {
        "queries": [
            {"query": "why are users saying this is too dry?", "query_type": "issue"},
            {"query": "what are users doing to fix the dryness issue?", "query_type": "fix"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "high friction",
                    "clear fix signals",
                    "texture issue is fixable",
                ],
            },
        ],
        "expected_issue": "dry",
        "acceptable_issues": ["dry", "too dry", "dry texture"],
        "acceptable_fix_themes": [
            "increase moisture",
            "add more sauce",
            "add more liquid",
            "adjust cook time",
            "adjust fat or eggs",
        ],
    },
    "under-seasoned": {
        "queries": [
            {"query": "why are users saying this is bland?", "query_type": "issue"},
            {"query": "what are users doing to improve the flavor?", "query_type": "fix"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "high friction",
                    "clear flavor fixes",
                    "seasoning issue is fixable",
                ],
            },
        ],
        "expected_issue": "under-seasoned",
        "acceptable_issues": ["under-seasoned", "bland"],
        "acceptable_fix_themes": [
            "boost flavor",
            "increase seasoning",
            "add acid",
            "add aromatics",
            "add spice",
        ],
    },
    "too sweet": {
        "queries": [
            {"query": "why are users saying this is too sweet?", "query_type": "issue"},
            {"query": "what are users doing to reduce the sweetness?", "query_type": "fix"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "high friction",
                    "clear sweetness fixes",
                    "sweetness issue is fixable",
                ],
            },
        ],
        "expected_issue": "too sweet",
        "acceptable_issues": ["too sweet", "overly sweet"],
        "acceptable_fix_themes": [
            "reduce sugar",
            "reduce sweetness",
            "add bitterness",
            "add acid",
            "adjust spice balance",
        ],
    },
    "quantity": {
        "queries": [
            {"query": "what are users saying about the filling quantity?", "query_type": "issue"},
            {"query": "what are users saying about the filling quantity and how are they adjusting it?", "query_type": "mixed"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "recipe instructions or ratios need correction",
                    "quantity issue affects execution",
                ],
            },
        ],
        "expected_issue": "quantity issue",
        "acceptable_issues": [
            "quantity issue",
            "not enough filling",
            "too much filling",
            "filling amount is off",
        ],
        "acceptable_fix_themes": [
            "adjust filling amount",
            "scale filling",
            "use different pan size",
            "match yield to pan",
        ],
    },
    "custard / setting": {
        "queries": [
            {"query": "why are users saying this is not setting properly?", "query_type": "issue"},
            {"query": "what are users saying about why this is not setting properly, and how are they adjusting it?", "query_type": "mixed"},
            {
                "query": "what should the editor change first?",
                "query_type": "editorial",
                "expected_priority": "high",
                "expected_reasoning": [
                    "recipe method or ratios need correction",
                    "setting issue affects core success",
                ],
            },
        ],
        "expected_issue": "custard / setting issue",
        "acceptable_issues": [
            "custard / setting issue",
            "not setting properly",
            "curdled",
            "did not set",
        ],
        "acceptable_fix_themes": [
            "fix setting or custard ratio",
            "adjust custard ratio",
            "adjust bake time",
            "adjust temperature or method",
        ],
    },
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path} line {line_number}: {exc}") from exc
    return rows


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deep_get(row: Dict[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def canonical_issue_bucket(display_issue: str) -> Optional[str]:
    issue = normalize_text(display_issue)

    if issue in {"over seasoned", "over-seasoned", "too salty"}:
        return "over-seasoned"

    if issue in {"dry", "too dry", "dry texture"}:
        return "dry"

    if issue in {"under seasoned", "under-seasoned", "bland"}:
        return "under-seasoned"

    if issue in {"too sweet", "overly sweet"}:
        return "too sweet"

    if issue in {
        "quantity issue",
        "not enough filling",
        "too much filling",
        "filling amount is off",
    }:
        return "quantity"

    if issue in {
        "custard / setting issue",
        "not setting properly",
        "did not set",
        "curdled",
    }:
        return "custard / setting"

    return None


def infer_eval_bucket(display_issue: str, recommended_edit: str, summary: str) -> Optional[str]:
    canonical_bucket = canonical_issue_bucket(display_issue)
    if canonical_bucket is not None:
        return canonical_bucket

    edit = normalize_text(recommended_edit)
    summary_norm = normalize_text(summary)
    blob = " ".join([edit, summary_norm])

    if any(x in blob for x in ["reduce salt", "less salt", "salty"]):
        return "over-seasoned"

    if any(
        x in blob
        for x in [
            "more sauce",
            "double the sauce",
            "double the pumpkin sauce",
            "moisture",
            "dry texture",
        ]
    ):
        return "dry"

    if any(x in blob for x in ["more seasoning", "more flavor", "more flavour", "bland"]):
        return "under-seasoned"

    if any(x in blob for x in ["reduce sugar", "less sugar", "cut sugar", "overly sweet"]):
        return "too sweet"

    if any(x in blob for x in ["filling amount", "quantity", "too much filling", "not enough filling"]):
        return "quantity"

    if any(x in blob for x in ["curdled", "not setting", "did not set", "custard"]):
        return "custard / setting"

    return None


def build_corpus_lookup(corpus_rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    lookup: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in corpus_rows:
        recipe_id = str(row.get("recipe_id") or "").strip()
        if recipe_id:
            lookup[recipe_id].append(row)
    return lookup


def get_bucket_keywords(bucket: str) -> List[str]:
    mapping = {
        "over-seasoned": ["salt", "salty", "over seasoned", "reduce salt", "less salt", "acid", "lemon", "feta", "olives"],
        "dry": ["dry", "sauce", "moisture", "water", "egg", "flour", "liquid", "butter", "oil"],
        "under-seasoned": ["bland", "seasoning", "flavor", "flavour", "salt", "spice", "acid", "lime", "lemon"],
        "too sweet": ["sweet", "sugar", "bitter", "acid", "spice", "less sugar"],
        "quantity": ["filling", "quantity", "too much", "not enough", "yield", "pan"],
        "custard / setting": ["curdled", "setting", "set", "custard", "ratio", "temperature", "bake"],
    }
    return mapping.get(bucket, [])


def score_chunk_for_bucket(chunk: Dict[str, Any], bucket: str, query_type: str) -> int:
    chunk_type = str(chunk.get("chunk_type") or "")
    evidence_type = str(chunk.get("evidence_type") or "")
    text = normalize_text(str(chunk.get("text") or ""))
    display_issue = normalize_text(str(chunk.get("display_issue") or ""))
    recommended_edit = normalize_text(str(chunk.get("recommended_edit") or ""))
    why_it_matters = normalize_text(str(chunk.get("why_it_matters") or ""))
    combined = " ".join([text, display_issue, recommended_edit, why_it_matters])

    score = 0

    if chunk_type == "evidence":
        score += 5
    elif chunk_type == "decision":
        score += 2

    if query_type == "issue":
        if evidence_type == "issue":
            score += 6
        elif evidence_type == "mixed":
            score += 4
        elif evidence_type == "problem_solving_fix":
            score += 1
    elif query_type == "fix":
        if evidence_type == "problem_solving_fix":
            score += 6
        elif evidence_type == "adaptation":
            score += 4
        elif evidence_type == "mixed":
            score += 3
        elif evidence_type == "recommended_edit":
            score += 2
    elif query_type == "mixed":
        if evidence_type == "mixed":
            score += 6
        elif evidence_type == "problem_solving_fix":
            score += 4
        elif evidence_type == "issue":
            score += 3
        elif evidence_type == "adaptation":
            score += 2
    elif query_type == "editorial":
        if chunk_type == "decision":
            score += 6
        if evidence_type == "recommended_edit":
            score += 4
        elif evidence_type == "issue":
            score += 3
        elif evidence_type == "problem_solving_fix":
            score += 3
        elif evidence_type == "mixed":
            score += 2

    bucket_keywords = get_bucket_keywords(bucket)
    keyword_hits = sum(1 for keyword in bucket_keywords if keyword in combined)
    score += min(keyword_hits, 4)

    return score


def choose_must_include_any_chunks(
    chunks: List[Dict[str, Any]],
    bucket: str,
    query_type: str,
) -> List[str]:
    scored: List[Tuple[int, str]] = []

    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id:
            continue

        score = score_chunk_for_bucket(chunk, bucket, query_type)
        if score > 0:
            scored.append((score, chunk_id))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [chunk_id for _, chunk_id in scored[:3]]


def choose_must_include_any_chunk_types(chunks: List[Dict[str, Any]], query_type: str) -> List[str]:
    available_types: Set[str] = set()

    for chunk in chunks:
        chunk_type = str(chunk.get("chunk_type") or "").strip()
        evidence_type = str(chunk.get("evidence_type") or "").strip()

        if chunk_type:
            available_types.add(chunk_type)
        if evidence_type:
            available_types.add(evidence_type)

    preferred_by_query = {
        "issue": ["issue", "mixed", "evidence"],
        "fix": ["problem_solving_fix", "adaptation", "mixed", "evidence"],
        "mixed": ["mixed", "issue", "problem_solving_fix", "evidence"],
        "editorial": ["decision", "recommended_edit", "issue", "problem_solving_fix"],
    }

    ordered = preferred_by_query.get(query_type, [])
    selected = [item for item in ordered if item in available_types]
    return selected[:3]


def has_sufficient_chunk_support(chunks: List[Dict[str, Any]], query_type: str, mode: str) -> bool:
    evidence_types = {str(chunk.get("evidence_type") or "") for chunk in chunks}
    chunk_types = {str(chunk.get("chunk_type") or "") for chunk in chunks}

    if query_type == "issue":
        return "issue" in evidence_types or "mixed" in evidence_types

    if query_type == "fix":
        if mode == "hard":
            return (
                "problem_solving_fix" in evidence_types
                or "adaptation" in evidence_types
                or "mixed" in evidence_types
                or "recommended_edit" in evidence_types
            )
        return "problem_solving_fix" in evidence_types or "adaptation" in evidence_types or "mixed" in evidence_types

    if query_type == "mixed":
        return ("mixed" in evidence_types) or (
            ("issue" in evidence_types) and ("problem_solving_fix" in evidence_types or "adaptation" in evidence_types)
        )

    if query_type == "editorial":
        if mode == "hard":
            return (
                "decision" in chunk_types
                or "recommended_edit" in evidence_types
                or "issue" in evidence_types
            )
        return "decision" in chunk_types or "recommended_edit" in evidence_types

    return False


def row_quality_score(row: Dict[str, Any], mode: str) -> float:
    evidence_strength = str(deep_get(row, "llm_readiness.evidence_strength") or "").lower()
    evidence_score_map_clean = {
        "high": 3.0,
        "medium": 2.0,
        "low": 0.5,
        "none": 0.0,
    }
    evidence_score_map_hard = {
        "high": 1.5,
        "medium": 2.0,
        "low": 2.5,
        "none": 0.5,
    }

    evidence_score_map = evidence_score_map_clean if mode == "clean" else evidence_score_map_hard

    total_comments = deep_get(row, "signals.total_comments")
    if total_comments is None:
        total_comments = row.get("total_comments")
    try:
        total_comments_value = float(total_comments or 0)
    except (TypeError, ValueError):
        total_comments_value = 0.0

    friction_score = deep_get(row, "signals.friction_score")
    try:
        friction_value = float(friction_score or 0)
    except (TypeError, ValueError):
        friction_value = 0.0

    issue_confidence = str(deep_get(row, "decision.issue.issue_confidence") or row.get("issue_confidence") or "").lower()
    confidence_bonus = {
        "high": 1.0,
        "medium": 0.5,
        "low": 0.1,
    }.get(issue_confidence, 0.0)

    if mode == "hard":
        confidence_bonus *= 0.5

    return evidence_score_map.get(evidence_strength, 0.0) + min(total_comments_value / 10.0, 3.0) + min(friction_value, 2.0) + confidence_bonus


def row_hardness_score(row: Dict[str, Any], chunks: List[Dict[str, Any]]) -> float:
    """
    Higher score = messier / more realistic case.
    Used only in hard mode.
    """
    evidence_strength = str(deep_get(row, "llm_readiness.evidence_strength") or "").lower()
    issue_confidence = str(deep_get(row, "decision.issue.issue_confidence") or row.get("issue_confidence") or "").lower()
    display_issue = str(deep_get(row, "decision.issue.display_issue") or "")
    recommended_edit = str(deep_get(row, "decision.recommended_edit") or "")
    summary = str(row.get("llm_editor_summary") or "")

    canonical_bucket = canonical_issue_bucket(display_issue)
    inferred_bucket = infer_eval_bucket(display_issue, recommended_edit, summary)

    evidence_types = {str(chunk.get("evidence_type") or "") for chunk in chunks}

    score = 0.0

    if evidence_strength == "low":
        score += 2.0
    elif evidence_strength == "medium":
        score += 1.0

    if issue_confidence == "low":
        score += 2.0
    elif issue_confidence == "medium":
        score += 1.0

    if canonical_bucket is None:
        score += 2.0

    if canonical_bucket is not None and inferred_bucket is not None and canonical_bucket != inferred_bucket:
        score += 2.5

    if "mixed" in evidence_types:
        score += 1.5

    if "issue" in evidence_types and "problem_solving_fix" not in evidence_types and "adaptation" not in evidence_types:
        score += 1.0

    if "adaptation" in evidence_types and "problem_solving_fix" not in evidence_types:
        score += 0.5

    return score


def editorial_row_to_cases(
    row: Dict[str, Any],
    corpus_lookup: Dict[str, List[Dict[str, Any]]],
    bucket: str,
    mode: str,
) -> List[Dict[str, Any]]:
    recipe_id = str(row.get("recipe_id") or "").strip()
    if not recipe_id:
        return []

    chunks = corpus_lookup.get(recipe_id, [])
    if not chunks:
        return []

    config = QUERY_CONFIG[bucket]
    cases: List[Dict[str, Any]] = []

    for query_config in config["queries"]:
        query_type = str(query_config["query_type"])

        if not has_sufficient_chunk_support(chunks, query_type, mode):
            continue

        must_include_any_chunk_ids = choose_must_include_any_chunks(
            chunks=chunks,
            bucket=bucket,
            query_type=query_type,
        )

        must_include_any_chunk_types = choose_must_include_any_chunk_types(
            chunks=chunks,
            query_type=query_type,
        )

        if not must_include_any_chunk_ids and not must_include_any_chunk_types:
            continue

        case: Dict[str, Any] = {
            "recipe_id": recipe_id,
            "query": query_config["query"],
            "query_type": query_type,
            "expected_issue": config["expected_issue"],
            "acceptable_issues": config["acceptable_issues"],
            "acceptable_fix_themes": config["acceptable_fix_themes"],
            "must_include_any_chunk_ids": must_include_any_chunk_ids,
            "must_include_any_chunk_types": must_include_any_chunk_types,
        }

        if query_type == "editorial":
            case["expected_priority"] = query_config.get("expected_priority", "high")
            case["expected_reasoning"] = query_config.get("expected_reasoning", [])

        cases.append(case)

    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RAG eval case file")
    parser.add_argument("--editorial", default=DEFAULT_EDITORIAL_PATH, help="Path to editorial_intelligence.jsonl")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_PATH, help="Path to rag_corpus.jsonl")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Path to output rag_eval_cases.jsonl")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for stable selection")
    parser.add_argument(
        "--mode",
        default="clean",
        choices=["clean", "hard"],
        help="Eval build mode: clean or hard",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    editorial_rows = load_jsonl(Path(args.editorial))
    corpus_rows = load_jsonl(Path(args.corpus))
    corpus_lookup = build_corpus_lookup(corpus_rows)

    target_buckets = CLEAN_TARGET_BUCKETS if args.mode == "clean" else HARD_TARGET_BUCKETS
    bucketed_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in editorial_rows:
        display_issue = str(deep_get(row, "decision.issue.display_issue") or "")
        recommended_edit = str(deep_get(row, "decision.recommended_edit") or "")
        summary = str(row.get("llm_editor_summary") or "")

        llm_ready_for_rag = deep_get(row, "llm_readiness.llm_ready_for_rag")
        if llm_ready_for_rag is not True:
            continue

        canonical_bucket = canonical_issue_bucket(display_issue)
        inferred_bucket = infer_eval_bucket(display_issue, recommended_edit, summary)

        if args.mode == "clean":
            if canonical_bucket is None:
                continue
            bucket = canonical_bucket
        else:
            bucket = inferred_bucket
            if bucket is None:
                continue

        bucketed_rows[bucket].append(row)

    selected_cases: List[Dict[str, Any]] = []

    for bucket, target_count in target_buckets.items():
        candidates = bucketed_rows.get(bucket, [])
        if not candidates:
            continue

        if args.mode == "clean":
            candidates = sorted(candidates, key=lambda row: row_quality_score(row, args.mode), reverse=True)
        else:
            # In hard mode, prefer harder rows first, then quality.
            candidates = sorted(
                candidates,
                key=lambda row: (
                    row_hardness_score(row, corpus_lookup.get(str(row.get("recipe_id") or ""), [])),
                    row_quality_score(row, args.mode),
                ),
                reverse=True,
            )

        # Shuffle small windows for variety while keeping broad ranking.
        grouped_candidates: List[Dict[str, Any]] = []
        window_size = 5
        for start_idx in range(0, len(candidates), window_size):
            window = candidates[start_idx : start_idx + window_size]
            random.shuffle(window)
            grouped_candidates.extend(window)

        picked = 0
        seen_recipe_ids: Set[str] = set()

        for row in grouped_candidates:
            recipe_id = str(row.get("recipe_id") or "")
            if not recipe_id or recipe_id in seen_recipe_ids:
                continue

            cases = editorial_row_to_cases(
                row=row,
                corpus_lookup=corpus_lookup,
                bucket=bucket,
                mode=args.mode,
            )
            if not cases:
                continue

            selected_cases.extend(cases)
            seen_recipe_ids.add(recipe_id)
            picked += 1

            if picked >= target_count:
                break

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for case in selected_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    summary = defaultdict(int)
    for case in selected_cases:
        summary[case["expected_issue"]] += 1

    print(f"Built RAG eval cases ({args.mode} mode)")
    print(f"- total_cases: {len(selected_cases)}")
    print(f"- output: {args.output}")
    print("- distribution:")
    for issue, count in sorted(summary.items()):
        print(f"  - {issue}: {count}")


if __name__ == "__main__":
    main()