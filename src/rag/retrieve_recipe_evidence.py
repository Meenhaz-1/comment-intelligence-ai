#!/usr/bin/env python3
"""
Retrieve the most relevant RAG chunks for a recipe-specific question.

This is a baseline retrieval layer for the recipe editorial RAG system.
It intentionally starts simple:
- filter corpus to one recipe_id
- lexical scoring with light normalization
- strong chunk-type and evidence-type boosts
- query-intent boosts
- query-specific issue-anchor matching

Why this exists
- If retrieval is bad, RAG is bad.
- This script lets you inspect top chunks before involving an LLM.

Typical usage
python src/rag/retrieve_recipe_evidence.py \
  --recipe-id 669a6694ce501f7231beb7a9 \
  --query "why is this recipe too salty?" \
  --top-k 5
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_CORPUS_PATH = "outputs/rag_corpus.jsonl"
DEFAULT_TOP_K = 5

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "how",
    "i", "if", "in", "into", "is", "it", "its", "of", "on", "or", "s", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were", "what", "when", "why",
    "will", "with", "would", "you", "your"
}

QUERY_INTENT_KEYWORDS = {
    "issue": {
        "why", "problem", "issue", "wrong", "broken", "dry", "salty", "bland", "sweet",
        "dense", "burnt", "overcooked", "undercooked", "curdled", "watery", "tough"
    },
    "fix": {
        "fix", "change", "changed", "adjust", "adjusted", "substitute", "substitution",
        "swap", "swapped", "reduce", "reduced", "add", "added", "double", "doubled",
        "halve", "halved", "improve", "improved"
    },
    "editorial": {
        "editor", "editorial", "priority", "prioritize", "worth", "matter", "important",
        "recommend", "recommended", "should", "first"
    },
    "adaptation": {
        "adapt", "adaptation", "variation", "tweak", "tweaked", "version", "alternative"
    },
}

CHUNK_TYPE_BOOST = {
    "evidence": 2.0,
    "decision": 0.8,
    "summary": 0.5,
}

EVIDENCE_TYPE_BOOST = {
    "mixed": 1.6,
    "problem_solving_fix": 2.0,
    "issue": 1.5,
    "adaptation": 1.8,
    "recommended_edit": 1.0,
    "issue_summary": 0.9,
    "summary": 0.7,
    "why_it_matters": 0.5,
}

ISSUE_ANCHOR_MAP = {
    "salt": {
        "salt", "salty", "over seasoned", "over-seasoned", "too much salt",
        "cut the salt", "reduce salt", "less salt"
    },
    "dry": {
        "dry", "dryness", "drier", "more sauce", "double the sauce",
        "double the pumpkin sauce", "moisture"
    },
    "bland": {
        "bland", "under seasoned", "under-seasoned", "more seasoning",
        "more salt", "more flavor", "more flavour"
    },
    "sweet": {
        "sweet", "too sweet", "reduce sugar", "less sugar", "cut the sugar"
    },
    "filling": {
        "filling", "not enough filling", "more filling"
    },
    "curdled": {
        "curdled", "curdling", "not setting", "did not set", "split"
    },
    "watery": {
        "watery", "runny", "too loose", "liquid", "soupy"
    },
    "dense": {
        "dense", "heavy", "too thick"
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
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    return [t for t in normalize_text(text).split() if t and t not in STOPWORDS and len(t) > 1]


def is_editorial_query(query: str, query_tokens: List[str]) -> bool:
    query_norm = normalize_text(query)
    token_set = set(query_tokens)

    explicit_phrases = [
        "what should the editor change first",
        "what should the editor fix first",
        "what should the editor change",
        "what should the editor fix",
        "what should change first",
        "what should be changed first",
    ]
    if any(phrase in query_norm for phrase in explicit_phrases):
        return True

    editorial_keywords = QUERY_INTENT_KEYWORDS.get("editorial", set())
    return bool(token_set & editorial_keywords)


def detect_query_intents(query_tokens: List[str], query_text: str) -> List[str]:
    intents: List[str] = []
    token_set = set(query_tokens)

    if is_editorial_query(query_text, query_tokens):
        intents.append("editorial")

    for intent, words in QUERY_INTENT_KEYWORDS.items():
        if intent == "editorial":
            continue
        if token_set & words:
            intents.append(intent)

    return intents


def detect_issue_anchors(query_tokens: List[str], query_text: str) -> List[str]:
    query_norm = normalize_text(query_text)
    token_set = set(query_tokens)
    matched: List[str] = []

    for anchor, terms in ISSUE_ANCHOR_MAP.items():
        if anchor in token_set or any(normalize_text(term) in query_norm for term in terms):
            matched.append(anchor)

    return matched


def compute_term_overlap_score(query_tokens: List[str], doc_tokens: List[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0

    query_counter = Counter(query_tokens)
    doc_counter = Counter(doc_tokens)
    overlap = 0.0

    for token, q_count in query_counter.items():
        overlap += min(q_count, doc_counter.get(token, 0))

    normalized_overlap = overlap / math.sqrt(len(query_tokens) * max(len(doc_tokens), 1))
    return normalized_overlap


def phrase_match_boost(query: str, retrieval_text: str) -> float:
    query_norm = normalize_text(query)
    retrieval_norm = normalize_text(retrieval_text)
    if not query_norm or not retrieval_norm:
        return 0.0

    boost = 0.0
    if query_norm in retrieval_norm:
        boost += 1.0

    query_parts = query_norm.split()
    query_bigrams = [" ".join(query_parts[i:i + 2]) for i in range(max(0, len(query_parts) - 1))]
    for bigram in query_bigrams:
        if len(bigram) >= 5 and bigram in retrieval_norm:
            boost += 0.35

    return boost


def intent_boost(intents: List[str], chunk: Dict[str, Any]) -> float:
    score = 0.0
    evidence_type = str(chunk.get("evidence_type") or "")
    chunk_type = str(chunk.get("chunk_type") or "")

    if "issue" in intents:
        if evidence_type == "issue":
            score += 1.2
        if evidence_type == "mixed":
            score += 0.8

    if "fix" in intents:
        if evidence_type == "problem_solving_fix":
            score += 1.2
        if evidence_type == "mixed":
            score += 0.7
        if evidence_type == "adaptation":
            score += 1.0
        if evidence_type == "recommended_edit":
            score += 0.6

    if "editorial" in intents:
        # Strongly prefer decision-layer chunks for editorial questions.
        if chunk_type == "decision":
            score += 2.4

        if evidence_type == "recommended_edit":
            score += 2.3
        elif evidence_type == "why_it_matters":
            score += 2.0
        elif evidence_type == "issue":
            score += 1.6
        elif evidence_type == "problem_solving_fix":
            score += 0.4
        elif evidence_type == "mixed":
            score += 0.3
        elif evidence_type == "adaptation":
            score += 0.1

    if "adaptation" in intents and evidence_type == "adaptation":
        score += 1.0

    return score


def evidence_strength_boost(chunk: Dict[str, Any]) -> float:
    value = str(chunk.get("evidence_strength") or "none").lower()
    return {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.2,
        "none": 0.0,
    }.get(value, 0.0)


def confidence_boost(chunk: Dict[str, Any]) -> float:
    value = str(chunk.get("issue_confidence") or "").lower()
    return {
        "high": 0.5,
        "medium": 0.3,
        "low": 0.1,
    }.get(value, 0.0)


def chunk_matches_anchor_text_only(chunk: Dict[str, Any], anchor: str) -> bool:
    terms = ISSUE_ANCHOR_MAP.get(anchor, set())
    text = normalize_text(str(chunk.get("text") or ""))
    return any(normalize_text(term) in text for term in terms)


def chunk_matches_anchor_with_context(chunk: Dict[str, Any], anchor: str) -> bool:
    terms = ISSUE_ANCHOR_MAP.get(anchor, set())

    text = normalize_text(str(chunk.get("text") or ""))
    display_issue = normalize_text(str(chunk.get("display_issue") or ""))
    recommended_edit = normalize_text(str(chunk.get("recommended_edit") or ""))
    why_it_matters = normalize_text(str(chunk.get("why_it_matters") or ""))

    combined = " ".join([text, display_issue, recommended_edit, why_it_matters])
    return any(normalize_text(term) in combined for term in terms)


def anchor_match_boost(chunk: Dict[str, Any], anchors: List[str], intents: List[str]) -> float:
    if not anchors:
        return 0.0

    score = 0.0
    chunk_type = str(chunk.get("chunk_type") or "")
    evidence_type = str(chunk.get("evidence_type") or "")

    for anchor in anchors:
        if chunk_type == "evidence":
            if chunk_matches_anchor_text_only(chunk, anchor):
                if evidence_type == "adaptation":
                    score += 2.2
                elif evidence_type == "problem_solving_fix":
                    score += 2.0
                elif evidence_type == "issue":
                    score += 1.8
                elif evidence_type == "mixed":
                    score += 1.2
                else:
                    score += 1.0
        else:
            if chunk_matches_anchor_with_context(chunk, anchor):
                # For editorial queries, decision chunks with issue/edit context
                # should be strongly preferred.
                if "editorial" in intents:
                    if evidence_type == "recommended_edit":
                        score += 2.0
                    elif evidence_type == "why_it_matters":
                        score += 1.6
                    elif evidence_type == "issue":
                        score += 1.5
                    else:
                        score += 1.0
                else:
                    if evidence_type in {"issue", "recommended_edit"}:
                        score += 1.2
                    else:
                        score += 0.8

    return score


def anchor_miss_penalty(chunk: Dict[str, Any], anchors: List[str], intents: List[str]) -> float:
    if not anchors:
        return 0.0

    chunk_type = str(chunk.get("chunk_type") or "")
    evidence_type = str(chunk.get("evidence_type") or "")

    if chunk_type == "evidence":
        if any(chunk_matches_anchor_text_only(chunk, anchor) for anchor in anchors):
            return 0.0

        # For editorial queries, missing anchors on evidence chunks should
        # hurt more because we want decision-layer chunks to win.
        if "editorial" in intents:
            if evidence_type == "problem_solving_fix":
                return -2.0
            if evidence_type == "adaptation":
                return -1.8
            if evidence_type == "mixed":
                return -1.2
            if evidence_type == "issue":
                return -0.8
            return -1.2

        if evidence_type == "problem_solving_fix":
            return -1.6
        if evidence_type == "adaptation":
            return -1.2
        if evidence_type == "mixed":
            return -1.0
        if evidence_type == "issue":
            return -0.8
        return -1.0

    if any(chunk_matches_anchor_with_context(chunk, anchor) for anchor in anchors):
        return 0.0

    # Editorial queries should not punish decision chunks as aggressively for
    # missing explicit anchor words because they may still carry the canonical
    # editorial recommendation.
    if "editorial" in intents and chunk_type == "decision":
        if evidence_type == "recommended_edit":
            return -0.1
        if evidence_type in {"issue", "why_it_matters"}:
            return -0.15
        return -0.2

    return -0.4


def editorial_structure_boost(chunk: Dict[str, Any], intents: List[str]) -> float:
    """
    Additional ranking logic specifically for editorial questions.
    Goal: ensure 'what should the editor change first?' surfaces decision chunks
    instead of only user-fix evidence.
    """
    if "editorial" not in intents:
        return 0.0

    score = 0.0
    chunk_type = str(chunk.get("chunk_type") or "")
    evidence_type = str(chunk.get("evidence_type") or "")
    text = normalize_text(str(chunk.get("text") or ""))
    display_issue = normalize_text(str(chunk.get("display_issue") or ""))
    recommended_edit = normalize_text(str(chunk.get("recommended_edit") or ""))
    why_it_matters = normalize_text(str(chunk.get("why_it_matters") or ""))

    combined = " ".join([text, display_issue, recommended_edit, why_it_matters])

    if chunk_type == "decision":
        score += 2.2

    if evidence_type == "recommended_edit":
        score += 2.5
    elif evidence_type == "why_it_matters":
        score += 2.0
    elif evidence_type == "issue":
        score += 1.4

    if recommended_edit:
        score += 0.8
    if why_it_matters:
        score += 0.6
    if display_issue:
        score += 0.5

    # Penalize pure adaptation chunks for editorial questions.
    if chunk_type == "evidence" and evidence_type == "adaptation":
        score -= 1.2

    # Penalize fix-only evidence a bit so decision chunks can outrank them.
    if chunk_type == "evidence" and evidence_type == "problem_solving_fix":
        score -= 0.6

    if "should" in combined or "recommend" in combined or "worth fixing" in combined:
        score += 0.5

    return score


def score_chunk(query: str, chunk: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    query_tokens = tokenize(query)
    retrieval_text = str(chunk.get("retrieval_text") or "")
    text = str(chunk.get("text") or "")

    doc_tokens = tokenize(retrieval_text)
    text_tokens = tokenize(text)
    intents = detect_query_intents(query_tokens, query)
    anchors = detect_issue_anchors(query_tokens, query)

    retrieval_overlap = compute_term_overlap_score(query_tokens, doc_tokens)
    text_overlap = compute_term_overlap_score(query_tokens, text_tokens)
    phrase_boost = phrase_match_boost(query, retrieval_text)
    type_boost = CHUNK_TYPE_BOOST.get(str(chunk.get("chunk_type") or ""), 0.0)
    evidence_type_boost = EVIDENCE_TYPE_BOOST.get(str(chunk.get("evidence_type") or ""), 0.0)
    query_intent_boost = intent_boost(intents, chunk)
    strength = evidence_strength_boost(chunk)
    confidence = confidence_boost(chunk)
    anchor_boost = anchor_match_boost(chunk, anchors, intents)
    anchor_penalty = anchor_miss_penalty(chunk, anchors, intents)
    editorial_boost = editorial_structure_boost(chunk, intents)

    score = (
        (retrieval_overlap * 2.5)
        + (text_overlap * 5.0)
        + phrase_boost
        + type_boost
        + evidence_type_boost
        + query_intent_boost
        + strength
        + confidence
        + anchor_boost
        + anchor_penalty
        + editorial_boost
    )

    breakdown = {
        "retrieval_overlap": round(retrieval_overlap, 4),
        "text_overlap": round(text_overlap, 4),
        "phrase_boost": round(phrase_boost, 4),
        "chunk_type_boost": round(type_boost, 4),
        "evidence_type_boost": round(evidence_type_boost, 4),
        "intent_boost": round(query_intent_boost, 4),
        "evidence_strength_boost": round(strength, 4),
        "confidence_boost": round(confidence, 4),
        "anchor_boost": round(anchor_boost, 4),
        "anchor_penalty": round(anchor_penalty, 4),
        "editorial_structure_boost": round(editorial_boost, 4),
        "final_score": round(score, 4),
    }
    return score, breakdown


def retrieve_chunks(corpus: List[Dict[str, Any]], recipe_id: str, query: str, top_k: int) -> List[Dict[str, Any]]:
    candidates = [row for row in corpus if str(row.get("recipe_id")) == recipe_id]
    if not candidates:
        return []

    scored: List[Tuple[float, Dict[str, Any], Dict[str, float]]] = []
    for chunk in candidates:
        score, breakdown = score_chunk(query, chunk)
        scored.append((score, chunk, breakdown))

    scored.sort(
        key=lambda x: (
            x[0],
            1 if str(x[1].get("chunk_type")) == "decision" else 0,
            1 if str(x[1].get("chunk_type")) == "evidence" else 0,
            x[1].get("rank_within_recipe") is not None,
            -int(x[1].get("rank_within_recipe") or 999),
        ),
        reverse=True,
    )

    results: List[Dict[str, Any]] = []
    for score, chunk, breakdown in scored[:top_k]:
        result = dict(chunk)
        result["score"] = round(score, 4)
        result["score_breakdown"] = breakdown
        results.append(result)
    return results


def print_human_readable(results: List[Dict[str, Any]], recipe_id: str, query: str) -> None:
    print(f"Recipe ID: {recipe_id}")
    print(f"Query: {query}")
    print(f"Results: {len(results)}")
    print("-" * 80)

    for i, row in enumerate(results, start=1):
        print(f"[{i}] score={row['score']}")
        print(f"chunk_id={row.get('chunk_id')}")
        print(f"chunk_type={row.get('chunk_type')} | evidence_type={row.get('evidence_type')}")
        print(f"issue={row.get('display_issue')} | recommended_edit={row.get('recommended_edit')}")
        print(f"text={row.get('text')}")
        print(f"score_breakdown={json.dumps(row.get('score_breakdown', {}), ensure_ascii=False)}")
        print("-" * 80)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve the most relevant RAG chunks for a recipe")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_PATH, help="Path to rag_corpus.jsonl")
    parser.add_argument("--recipe-id", required=True, help="Recipe ID to search within")
    parser.add_argument("--query", required=True, help="Question or search query")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Number of chunks to return")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human-readable output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus = load_jsonl(Path(args.corpus))
    results = retrieve_chunks(
        corpus=corpus,
        recipe_id=args.recipe_id,
        query=args.query,
        top_k=args.top_k,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_human_readable(results, args.recipe_id, args.query)


if __name__ == "__main__":
    main()