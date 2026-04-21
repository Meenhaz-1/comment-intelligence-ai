#!/usr/bin/env python3
"""
Evaluate recipe-level RAG retrieval and answer quality against a curated test set.

Expected eval file format (JSONL)
One row per test case. Supports both old and new schemas.

Old schema example:
{
  "recipe_id": "669a6694ce501f7231beb7a9",
  "query": "what are users doing to fix the salt issue?",
  "query_type": "fix",
  "expected_issue": "over-seasoned",
  "acceptable_issues": ["over-seasoned", "too salty"],
  "expected_fix_themes": ["reduce salt"],
  "must_include_any_chunk_ids": [
    "669a6694ce501f7231beb7a9::evidence::adaptation::4"
  ]
}

New schema example:
{
  "recipe_id": "669a6694ce501f7231beb7a9",
  "query": "what should the editor change first?",
  "query_type": "editorial",
  "expected_issue": "over-seasoned",
  "acceptable_issues": ["over-seasoned", "too salty"],
  "acceptable_fix_themes": ["reduce salt", "add acidity"],
  "must_include_any_chunk_ids": [
    "669a6694ce501f7231beb7a9::evidence::problem_solving_fix::3"
  ],
  "must_include_any_chunk_types": ["decision", "recommended_edit", "issue"],
  "expected_priority": "high",
  "expected_reasoning": ["high friction", "clear fix signals"]
}

This script evaluates two layers separately:
1. Retrieval quality
2. Answer quality (heuristic, not LLM-as-judge yet)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


DEFAULT_CORPUS_PATH = "outputs/rag_corpus.jsonl"
DEFAULT_EVAL_FILE = "outputs/rag_eval_cases.jsonl"
DEFAULT_OUTPUT_PATH = "outputs/rag_eval_results.jsonl"
DEFAULT_TOP_K = 3


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


def run_answer_script(
    recipe_id: str,
    query: str,
    corpus_path: str,
    top_k: int,
    no_llm: bool,
    model: str,
) -> Dict[str, Any]:
    script_path = Path(__file__).with_name("answer_recipe_question.py")
    cmd = [
        sys.executable,
        str(script_path),
        "--corpus",
        corpus_path,
        "--recipe-id",
        recipe_id,
        "--query",
        query,
        "--top-k",
        str(top_k),
    ]

    if no_llm:
        cmd.append("--no-llm")
    else:
        cmd.extend(["--model", model])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Answer script failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Answer script did not return valid JSON.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        ) from exc


def get_expected_fix_themes(test_case: Dict[str, Any]) -> List[str]:
    """
    Backward compatible:
    - prefers acceptable_fix_themes
    - falls back to expected_fix_themes
    """
    acceptable = test_case.get("acceptable_fix_themes") or []
    expected = test_case.get("expected_fix_themes") or []
    if acceptable:
        return [str(x) for x in acceptable if x]
    return [str(x) for x in expected if x]


def retrieval_metrics(
    retrieved_chunks: List[Dict[str, Any]],
    must_include_any_chunk_ids: List[str],
    must_include_any_chunk_types: List[str],
) -> Dict[str, Any]:
    retrieved_ids = [str(chunk.get("chunk_id")) for chunk in retrieved_chunks if chunk.get("chunk_id")]

    retrieved_type_values: Set[str] = set()
    for chunk in retrieved_chunks:
        chunk_type = str(chunk.get("chunk_type") or "").strip()
        evidence_type = str(chunk.get("evidence_type") or "").strip()
        if chunk_type:
            retrieved_type_values.add(chunk_type)
        if evidence_type:
            retrieved_type_values.add(evidence_type)

    acceptable_ids = [str(x) for x in must_include_any_chunk_ids if x]
    acceptable_types = [str(x) for x in must_include_any_chunk_types if x]

    any_id_hit: Optional[bool]
    if acceptable_ids:
        any_id_hit = any(chunk_id in retrieved_ids for chunk_id in acceptable_ids)
    else:
        any_id_hit = None

    any_type_hit: Optional[bool]
    if acceptable_types:
        any_type_hit = any(chunk_type in retrieved_type_values for chunk_type in acceptable_types)
    else:
        any_type_hit = None

    hit_count = sum(1 for chunk_id in acceptable_ids if chunk_id in retrieved_ids)
    type_hit_count = sum(1 for chunk_type in acceptable_types if chunk_type in retrieved_type_values)
    precision_at_k = hit_count / len(retrieved_ids) if retrieved_ids else 0.0

    if acceptable_ids or acceptable_types:
        any_required_found = bool(any_id_hit) or bool(any_type_hit)
    else:
        any_required_found = None

    return {
        "retrieved_ids": retrieved_ids,
        "retrieved_type_values": sorted(retrieved_type_values),
        "hit_count": hit_count,
        "type_hit_count": type_hit_count,
        "precision_at_k": round(precision_at_k, 4),
        "any_required_id_found": any_id_hit,
        "any_required_type_found": any_type_hit,
        "any_required_found": any_required_found,
    }


def issue_match_score(predicted_issue: str, acceptable_issues: List[str], expected_issue: str) -> float:
    pred = normalize_text(predicted_issue)
    if not pred:
        return 0.0

    candidates = [normalize_text(expected_issue)] if expected_issue else []
    candidates.extend(normalize_text(x) for x in acceptable_issues if x)

    candidates = [c for c in candidates if c]
    if not candidates:
        return 0.0

    if pred in candidates:
        return 1.0

    if any(pred in candidate or candidate in pred for candidate in candidates):
        return 0.75

    # Soft semantic-ish fallback for very common editorial mappings
    synonyms = {
        "over-seasoned": {"too salty", "salty", "over seasoned"},
        "under-seasoned": {"bland", "needs more seasoning", "needs more flavor"},
        "dry": {"too dry", "dry texture"},
        "too sweet": {"overly sweet", "sweet"},
        "quantity issue": {"too much filling", "not enough filling", "filling amount is off"},
        "custard / setting issue": {"not setting properly", "did not set", "curdled"},
    }

    pred_expanded = {pred}
    for canonical, alts in synonyms.items():
        canonical_norm = normalize_text(canonical)
        alt_norms = {normalize_text(x) for x in alts}
        if pred == canonical_norm or pred in alt_norms:
            pred_expanded.add(canonical_norm)
            pred_expanded.update(alt_norms)

    for candidate in candidates:
        candidate_expanded = {candidate}
        for canonical, alts in synonyms.items():
            canonical_norm = normalize_text(canonical)
            alt_norms = {normalize_text(x) for x in alts}
            if candidate == canonical_norm or candidate in alt_norms:
                candidate_expanded.add(canonical_norm)
                candidate_expanded.update(alt_norms)

        if pred_expanded & candidate_expanded:
            return 0.75

    return 0.0


def canonicalize_fix_theme(text: str) -> List[str]:
    text_norm = normalize_text(text)
    themes: List[str] = []

    def add(theme: str) -> None:
        if theme not in themes:
            themes.append(theme)

    if any(
        x in text_norm
        for x in [
            "reduce salt",
            "less salt",
            "cut salt",
            "cut the salt",
            "use less salt",
            "too salty",
            "over seasoned",
            "reduce feta",
            "less feta",
            "reduce olives",
            "less olives",
        ]
    ):
        add("reduce salt")

    if any(
        x in text_norm
        for x in [
            "add acidity",
            "acid",
            "add lemon",
            "lemon juice",
            "added lemon",
            "lime juice",
            "vinegar",
            "squeeze of lemon",
        ]
    ):
        add("add acidity")

    if any(
        x in text_norm
        for x in [
            "use pancake mix",
            "pancake mix",
            "soften bitterness",
            "reduce bitterness",
            "bitter",
        ]
    ):
        themes.append("reduce bitterness")
        
    if any(
        x in text_norm
        for x in [
            "more sauce",
            "double sauce",
            "double the sauce",
            "add more sauce",
            "double the pumpkin sauce",
            "pumpkin sauce",
        ]
    ):
        add("add more sauce")

    if any(
        x in text_norm
        for x in [
            "add water",
            "extra egg",
            "add egg",
            "reduce flour",
            "less flour",
            "increase moisture",
            "more moisture",
            "hydration",
            "add liquid",
            "more liquid",
            "add broth",
            "add oil",
            "add butter",
            "add water",
            "extra egg",
            "add extra egg",
            "add egg",
            "reduce flour",
            "less flour",
            "adjust wet dry ratio",
            "adjust wet dry balance",
            "wet dry ratio",
            "more hydration",
        ]
    ):
        add("increase moisture")

    if any(
        x in text_norm
        for x in [
            "adjust cook time",
            "cook less",
            "bake less",
            "shorter bake",
            "reduce baking time",
            "didn t bake as long",
            "pull it earlier",
        ]
    ):
        add("adjust cook time")

    if any(
        x in text_norm
        for x in [
            "add seasoning",
            "more seasoning",
            "more flavor",
            "more flavour",
            "more salt",
            "bland",
            "under seasoned",
            "under seasoned",
            "add spices",
            "boost flavor",
            "increase seasoning",
            "increase spices",
            "use more chocolate",
            "more chocolate",
            "full chocolate bar",
            "different chocolate",
            "swap chocolate",
            "use chocolate",
        ]
    ):
        add("boost flavor")

    if any(
        x in text_norm
        for x in [
            "add aromatics",
            "more ginger",
            "increase ginger",
            "more lemongrass",
            "increase lemongrass",
            "more garlic",
            "more onion",
            "shallots",
            "aromatics",
        ]
    ):
        add("add aromatics")

    if any(
        x in text_norm
        for x in [
            "reduce sugar",
            "less sugar",
            "cut sugar",
            "too sweet",
            "use less sugar",
            "reduce sweetness",
        ]
    ):
        add("reduce sugar")

    if any(
        x in text_norm
        for x in [
            "add bitterness",
            "bitter",
            "dark chocolate",
            "swap chocolate",
            "more chocolate",
            "use chocolate",
            "coffee",
        ]
    ):
        add("add bitterness")

    if any(
        x in text_norm
        for x in [
            "adjust filling",
            "less filling",
            "more filling",
            "not enough filling",
            "too much filling",
            "adjust filling amount",
            "scale filling",
        ]
    ):
        add("adjust filling amount")

    if any(
        x in text_norm
        for x in [
            "different pan size",
            "deep dish",
            "deeper dish",
            "smaller pan",
            "larger pan",
            "match yield to pan",
            "use different pan",
        ]
    ):
        add("use different pan size")

    if any(
        x in text_norm
        for x in [
            "adjust custard",
            "improve setting",
            "not setting",
            "did not set",
            "curdled",
            "curdling",
            "fix filling ratio",
            "custard ratio",
            "adjust custard ratio",
        ]
    ):
        add("fix setting or custard ratio")

    if any(
        x in text_norm
        for x in [
            "adjust bake time",
            "bake longer",
            "bake more",
            "cook longer",
        ]
    ):
        add("adjust bake time")

    if any(
        x in text_norm
        for x in [
            "adjust temperature",
            "lower oven",
            "higher oven",
            "water bath",
            "change method",
            "temperature",
        ]
    ):
        add("adjust temperature or method")

    return themes


def theme_hit_count(answer_obj: Dict[str, Any], expected_fix_themes: List[str]) -> Tuple[int, List[str], List[str]]:
    answer_text = str(answer_obj.get("answer") or "")
    fixes = answer_obj.get("user_fixes_seen") or []
    recommended_edit = str(answer_obj.get("recommended_edit") or "")
    fix_blob = " ".join(str(x) for x in fixes)
    combined = f"{answer_text} {fix_blob} {recommended_edit}".strip()

    predicted_themes = canonicalize_fix_theme(combined)
    expected_themes = [normalize_text(str(x)) for x in expected_fix_themes if x]

    matched: List[str] = []
    for theme in expected_themes:
        if theme in predicted_themes:
            matched.append(theme)

    return len(matched), matched, predicted_themes


def supporting_type_values(answer_payload: Dict[str, Any], answer_obj: Dict[str, Any]) -> Set[str]:
    values: Set[str] = set()

    retrieved_chunks = answer_payload.get("retrieved_chunks") or []
    supporting_ids = {str(x) for x in (answer_obj.get("supporting_chunk_ids") or []) if x}

    for chunk in retrieved_chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id or chunk_id not in supporting_ids:
            continue

        chunk_type = str(chunk.get("chunk_type") or "").strip()
        evidence_type = str(chunk.get("evidence_type") or "").strip()
        if chunk_type:
            values.add(chunk_type)
        if evidence_type:
            values.add(evidence_type)

    return values


def editorial_priority_score(answer_obj: Dict[str, Any], expected_priority: str) -> float:
    if not expected_priority:
        return 0.0

    answer_text = normalize_text(str(answer_obj.get("answer") or ""))
    recommended_edit = normalize_text(str(answer_obj.get("recommended_edit") or ""))
    combined = f"{answer_text} {recommended_edit}".strip()

    priority_keywords = {
        "high": [
            "change first",
            "should fix first",
            "first thing to change",
            "priority",
            "high priority",
            "worth fixing",
            "should adjust",
            "should reduce",
            "should increase",
            "editor should",
        ],
        "medium": [
            "could improve",
            "consider adjusting",
            "may want to adjust",
        ],
        "low": [
            "minor",
            "low priority",
            "not urgent",
        ],
    }

    expected_norm = normalize_text(expected_priority)
    keywords = priority_keywords.get(expected_norm, [])
    if any(keyword in combined for keyword in keywords):
        return 1.0

    if expected_norm == "high" and recommended_edit:
        return 0.75

    return 0.0


def editorial_reasoning_score(answer_obj: Dict[str, Any], expected_reasoning: List[str]) -> Tuple[float, List[str]]:
    if not expected_reasoning:
        return 0.0, []

    answer_text = normalize_text(str(answer_obj.get("answer") or ""))
    why_it_matters = normalize_text(str(answer_obj.get("why_it_matters") or ""))
    combined = f"{answer_text} {why_it_matters}".strip()

    matched: List[str] = []

    reasoning_map = {
        "high friction": ["high friction", "many users report", "recurring complaint", "common complaint", "frequently reported"],
        "clear fix signals": ["users fix", "users adjust", "common fix", "clear fix", "users often", "adjust it by"],
        "seasoning issue is fixable": ["seasoning", "salt", "acid", "fixable", "easy adjustment"],
        "texture issue is fixable": ["dry", "moisture", "sauce", "liquid", "texture"],
        "clear flavor fixes": ["flavor", "seasoning", "spice", "aromatics", "acid"],
        "sweetness issue is fixable": ["sweet", "sugar", "bitterness", "acid"],
        "recipe instructions or ratios need correction": ["ratio", "instructions", "method", "correction"],
        "quantity issue affects execution": ["quantity", "filling", "too much", "not enough", "pan"],
        "recipe method or ratios need correction": ["method", "ratio", "custard", "setting", "temperature"],
        "setting issue affects core success": ["set", "setting", "curdled", "core success", "does not set"],
    }

    for reason in expected_reasoning:
        reason_norm = normalize_text(reason)
        keywords = reasoning_map.get(reason_norm, [reason_norm])
        if any(keyword in combined for keyword in keywords):
            matched.append(reason)

    score = len(matched) / len(expected_reasoning) if expected_reasoning else 0.0
    return score, matched


def answer_metrics(answer_payload: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    answer_obj = answer_payload.get("answer") or {}
    expected_issue = str(test_case.get("expected_issue") or "")
    acceptable_issues = [str(x) for x in (test_case.get("acceptable_issues") or [])]
    expected_fix_themes = get_expected_fix_themes(test_case)
    must_include_any_chunk_ids = [str(x) for x in (test_case.get("must_include_any_chunk_ids") or [])]
    must_include_any_chunk_types = [str(x) for x in (test_case.get("must_include_any_chunk_types") or [])]
    expected_priority = str(test_case.get("expected_priority") or "")
    expected_reasoning = [str(x) for x in (test_case.get("expected_reasoning") or [])]
    query_type = str(test_case.get("query_type") or "")

    predicted_issue = str(answer_obj.get("main_issue") or "")
    issue_score = issue_match_score(predicted_issue, acceptable_issues, expected_issue)

    hit_count, matched_themes, predicted_themes = theme_hit_count(answer_obj, expected_fix_themes)
    theme_recall = hit_count / len(expected_fix_themes) if expected_fix_themes else None

    supporting_ids = [str(x) for x in (answer_obj.get("supporting_chunk_ids") or [])]
    supporting_overlap = sum(1 for x in must_include_any_chunk_ids if x in supporting_ids)

    supporting_types = supporting_type_values(answer_payload, answer_obj)
    supporting_type_overlap = sum(1 for x in must_include_any_chunk_types if x in supporting_types)

    if must_include_any_chunk_ids or must_include_any_chunk_types:
        grounded = (supporting_overlap > 0) or (supporting_type_overlap > 0)
    else:
        grounded = len(supporting_ids) > 0

    priority_score = None
    reasoning_score = None
    matched_reasoning: List[str] = []

    if query_type == "editorial":
        priority_score = editorial_priority_score(answer_obj, expected_priority)
        reasoning_score, matched_reasoning = editorial_reasoning_score(answer_obj, expected_reasoning)

    if query_type == "issue":
        useful = issue_score >= 0.75 and grounded
    elif query_type == "fix":
        useful = grounded and (
        hit_count >= 1 or
        (theme_recall is not None and theme_recall >= 0.33)
    )
    elif query_type == "mixed":
        useful = issue_score >= 0.75 and grounded and (theme_recall is not None and theme_recall >= 0.5)
    elif query_type == "editorial":
        useful = (
            issue_score >= 0.75
            and grounded
            and (priority_score is not None and priority_score >= 0.75)
            and (reasoning_score is None or reasoning_score >= 0.5)
        )
    else:
        useful = issue_score >= 0.75 and grounded and (theme_recall is None or theme_recall >= 0.5)

    # Optional overall score so you can sort failures later
    score_components: List[float] = [issue_score, 1.0 if grounded else 0.0]
    if theme_recall is not None:
        score_components.append(theme_recall)
    if priority_score is not None:
        score_components.append(priority_score)
    if reasoning_score is not None:
        score_components.append(reasoning_score)

    overall_score = round(sum(score_components) / len(score_components), 4) if score_components else 0.0

    return {
        "predicted_issue": predicted_issue,
        "issue_score": round(issue_score, 4),
        "predicted_fix_themes": predicted_themes,
        "matched_fix_themes": matched_themes,
        "fix_theme_hit_count": hit_count,
        "fix_theme_recall": round(theme_recall, 4) if theme_recall is not None else None,
        "supporting_chunk_ids": supporting_ids,
        "supporting_overlap_count": supporting_overlap,
        "supporting_type_values": sorted(supporting_types),
        "supporting_type_overlap_count": supporting_type_overlap,
        "grounded": grounded,
        "priority_score": round(priority_score, 4) if priority_score is not None else None,
        "reasoning_score": round(reasoning_score, 4) if reasoning_score is not None else None,
        "matched_reasoning": matched_reasoning,
        "overall_score": overall_score,
        "useful": useful,
    }


def evaluate_case(
    test_case: Dict[str, Any],
    corpus_path: str,
    top_k: int,
    no_llm: bool,
    model: str,
) -> Dict[str, Any]:
    answer_payload = run_answer_script(
        recipe_id=str(test_case["recipe_id"]),
        query=str(test_case["query"]),
        corpus_path=corpus_path,
        top_k=top_k,
        no_llm=no_llm,
        model=model,
    )

    retrieved_chunks = answer_payload.get("retrieved_chunks") or []
    retrieval = retrieval_metrics(
        retrieved_chunks=retrieved_chunks,
        must_include_any_chunk_ids=test_case.get("must_include_any_chunk_ids") or [],
        must_include_any_chunk_types=test_case.get("must_include_any_chunk_types") or [],
    )
    answer_eval = answer_metrics(answer_payload, test_case)

    return {
        "recipe_id": test_case.get("recipe_id"),
        "query": test_case.get("query"),
        "query_type": test_case.get("query_type"),
        "expected_issue": test_case.get("expected_issue"),
        "acceptable_issues": test_case.get("acceptable_issues") or [],
        "acceptable_fix_themes": get_expected_fix_themes(test_case),
        "must_include_any_chunk_ids": test_case.get("must_include_any_chunk_ids") or [],
        "must_include_any_chunk_types": test_case.get("must_include_any_chunk_types") or [],
        "expected_priority": test_case.get("expected_priority"),
        "expected_reasoning": test_case.get("expected_reasoning") or [],
        "retrieval": retrieval,
        "answer_eval": answer_eval,
        "answer_payload": answer_payload,
    }


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results)
    if n == 0:
        return {
            "case_count": 0,
            "avg_precision_at_k": None,
            "required_chunk_hit_rate": None,
            "required_chunk_type_hit_rate": None,
            "avg_issue_score": None,
            "avg_fix_theme_recall": None,
            "grounded_rate": None,
            "avg_priority_score": None,
            "avg_reasoning_score": None,
            "avg_overall_score": None,
            "useful_rate": None,
            "query_type_breakdown": {},
        }

    precision_values = [r["retrieval"]["precision_at_k"] for r in results]
    required_hit_rate = sum(1 for r in results if r["retrieval"]["any_required_found"]) / n
    required_type_hit_rate = sum(1 for r in results if r["retrieval"]["any_required_type_found"]) / n

    issue_scores = [r["answer_eval"]["issue_score"] for r in results]
    theme_recalls = [r["answer_eval"]["fix_theme_recall"] for r in results if r["answer_eval"]["fix_theme_recall"] is not None]
    grounded_rate = sum(1 for r in results if r["answer_eval"]["grounded"]) / n
    useful_rate = sum(1 for r in results if r["answer_eval"]["useful"]) / n

    priority_scores = [r["answer_eval"]["priority_score"] for r in results if r["answer_eval"]["priority_score"] is not None]
    reasoning_scores = [r["answer_eval"]["reasoning_score"] for r in results if r["answer_eval"]["reasoning_score"] is not None]
    overall_scores = [r["answer_eval"]["overall_score"] for r in results]
    
    fix_hit_rate = sum(
    1 for r in results
    if r["query_type"] == "fix" and r["answer_eval"]["fix_theme_hit_count"] >= 1
) / max(1, sum(1 for r in results if r["query_type"] == "fix"))

    query_type_groups: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        query_type = str(result.get("query_type") or "unknown")
        query_type_groups.setdefault(query_type, []).append(result)

    query_type_breakdown: Dict[str, Dict[str, Any]] = {}
    for query_type, group in query_type_groups.items():
        group_n = len(group)
        group_theme_recalls = [r["answer_eval"]["fix_theme_recall"] for r in group if r["answer_eval"]["fix_theme_recall"] is not None]
        group_priority_scores = [r["answer_eval"]["priority_score"] for r in group if r["answer_eval"]["priority_score"] is not None]
        group_reasoning_scores = [r["answer_eval"]["reasoning_score"] for r in group if r["answer_eval"]["reasoning_score"] is not None]

        query_type_breakdown[query_type] = {
            "case_count": group_n,
            "avg_issue_score": round(sum(r["answer_eval"]["issue_score"] for r in group) / group_n, 4),
            "avg_fix_theme_recall": round(sum(group_theme_recalls) / len(group_theme_recalls), 4) if group_theme_recalls else None,
            "grounded_rate": round(sum(1 for r in group if r["answer_eval"]["grounded"]) / group_n, 4),
            "useful_rate": round(sum(1 for r in group if r["answer_eval"]["useful"]) / group_n, 4),
            "avg_priority_score": round(sum(group_priority_scores) / len(group_priority_scores), 4) if group_priority_scores else None,
            "avg_reasoning_score": round(sum(group_reasoning_scores) / len(group_reasoning_scores), 4) if group_reasoning_scores else None,
            "avg_overall_score": round(sum(r["answer_eval"]["overall_score"] for r in group) / group_n, 4),
        }

    return {
        "case_count": n,
        "avg_precision_at_k": round(sum(precision_values) / len(precision_values), 4),
        "required_chunk_hit_rate": round(required_hit_rate, 4),
        "required_chunk_type_hit_rate": round(required_type_hit_rate, 4),
        "avg_issue_score": round(sum(issue_scores) / len(issue_scores), 4),
        "avg_fix_theme_recall": round(sum(theme_recalls) / len(theme_recalls), 4) if theme_recalls else None,
        "grounded_rate": round(grounded_rate, 4),
        "avg_priority_score": round(sum(priority_scores) / len(priority_scores), 4) if priority_scores else None,
        "avg_reasoning_score": round(sum(reasoning_scores) / len(reasoning_scores), 4) if reasoning_scores else None,
        "avg_overall_score": round(sum(overall_scores) / len(overall_scores), 4),
        "useful_rate": round(useful_rate, 4),
        "query_type_breakdown": query_type_breakdown,
        "fix_hit_rate": round(fix_hit_rate, 4),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate recipe-level RAG retrieval and answer quality")
    parser.add_argument("--eval-file", default=DEFAULT_EVAL_FILE, help="Path to rag_eval_cases.jsonl")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_PATH, help="Path to rag_corpus.jsonl")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Top-k retrieved chunks to evaluate")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Path to write detailed eval results JSONL")
    parser.add_argument("--summary-output", default="", help="Optional path to write summary JSON")
    parser.add_argument("--no-llm", action="store_true", help="Evaluate deterministic fallback only")
    parser.add_argument("--model", default="gpt-5.4", help="Model to use when not running --no-llm")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    eval_cases = load_jsonl(Path(args.eval_file))
    results: List[Dict[str, Any]] = []

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as out:
        for case in eval_cases:
            result = evaluate_case(
                test_case=case,
                corpus_path=args.corpus,
                top_k=args.top_k,
                no_llm=args.no_llm,
                model=args.model,
            )
            results.append(result)
            out.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary = summarize_results(results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.summary_output:
        Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
        with Path(args.summary_output).open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()