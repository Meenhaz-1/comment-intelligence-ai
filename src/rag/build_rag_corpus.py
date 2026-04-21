#!/usr/bin/env python3
"""
Build a retrieval corpus for recipe-level RAG.

This script turns existing project outputs into a unified JSONL corpus that can be
embedded and retrieved later for recipe-specific Q&A.

Expected inputs
- editorial_intelligence.jsonl
- recipe_evidence.jsonl (optional)
- llm_editor_summaries.jsonl (optional)

Recommended output
- outputs/rag_corpus.jsonl

Design principles
- Retrieve over evidence-backed units, not raw comment dumps.
- Keep deterministic fields alongside evidence so retrieval has context.
- Preserve provenance aggressively so answer generation can cite evidence.
- Support nested upstream schemas without silently failing.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_EDITORIAL_PATH = "outputs/editorial_intelligence.jsonl"
DEFAULT_EVIDENCE_PATH = "outputs/recipe_evidence.jsonl"
DEFAULT_SUMMARIES_PATH = "outputs/llm_editor_summaries.jsonl"
DEFAULT_OUTPUT_PATH = "outputs/rag_corpus.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows

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


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def stable_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_whitespace(str(x)) for x in value if normalize_whitespace(str(x))]
    text = normalize_whitespace(str(value))
    return [text] if text else []


def coerce_bool_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value != 0)

    text = normalize_whitespace(str(value)).lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return 1
    if text in {"0", "false", "f", "no", "n", "", "none", "null"}:
        return 0
    return 0


def deep_get(row: Dict[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def first_present(row: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        value = deep_get(row, key)
        if value is not None:
            return value
    return None


def get_recipe_id(row: Dict[str, Any]) -> Optional[str]:
    for key in ("recipe_id", "content_id", "id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def build_recipe_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        recipe_id = get_recipe_id(row)
        if not recipe_id:
            continue
        lookup[recipe_id] = row
    return lookup


def build_summary_lookup(summary_rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for row in summary_rows:
        recipe_id = get_recipe_id(row)
        if not recipe_id:
            continue
        lookup[recipe_id] = row
    return lookup


def infer_rag_ready(editorial_row: Dict[str, Any]) -> Tuple[int, str]:
    readiness_candidates = [
        "llm_ready_for_rag",
        "rag_ready",
        "ready_for_rag",
        "llm_readiness.llm_ready_for_rag",
        "llm_readiness.rag_ready",
        "readiness.rag",
        "flags.llm_ready_for_rag",
    ]

    for key in readiness_candidates:
        value = deep_get(editorial_row, key)
        if value is not None:
            return coerce_bool_int(value), f"explicit:{key}"

    evidence_strength = normalize_whitespace(
        str(
            first_present(
                editorial_row,
                [
                    "llm_readiness.evidence_strength",
                    "evidence_strength",
                    "readiness.evidence_strength",
                ],
            )
            or "none"
        )
    ).lower()

    if evidence_strength in {"medium", "high"}:
        return 1, "fallback:evidence_strength"

    return 0, "fallback:none"


def get_recipe_metadata(editorial_row: Dict[str, Any], summary_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rag_ready, rag_ready_source = infer_rag_ready(editorial_row)

    return {
        "recipe_title": first_present(editorial_row, ["metadata.title", "title", "recipe_title"]) or "",
        "brand": first_present(editorial_row, ["metadata.brand", "brand"]) or "",
        "author": first_present(editorial_row, ["metadata.author", "author", "author_name"]) or "",
        "tags": stable_list(first_present(editorial_row, ["metadata.tags", "tags"])),
        "publish_date": first_present(editorial_row, ["metadata.publish_date", "publish_date"]),
        "url": first_present(editorial_row, ["metadata.url", "url"]),
        "llm_ready_for_rag": rag_ready,
        "llm_ready_for_rag_source": rag_ready_source,
        "evidence_strength": str(
            first_present(
                editorial_row,
                [
                    "llm_readiness.evidence_strength",
                    "evidence_strength",
                    "readiness.evidence_strength",
                ],
            )
            or "none"
        ),
        "issue_confidence": first_present(
            editorial_row,
            [
                "decision.issue.issue_confidence",
                "issue_confidence",
                "decision.issue_confidence",
            ],
        ),
        "issue_source": first_present(
            editorial_row,
            [
                "decision.issue.issue_source",
                "issue_source",
                "decision.issue_source",
            ],
        ),
        "display_issue": first_present(
            editorial_row,
            [
                "decision.issue.display_issue",
                "display_issue",
                "decision.display_issue",
            ],
        ),
        "recommended_edit": first_present(
            editorial_row,
            [
                "decision.recommended_edit",
                "recommended_edit",
            ],
        ),
        "why_it_matters": first_present(
            editorial_row,
            [
                "decision.why_it_matters",
                "why_it_matters",
            ],
        ),
        "llm_editor_summary": (summary_row or {}).get("llm_editor_summary")
        or first_present(editorial_row, ["llm_editor_summary"]),
    }


@dataclass
class RagChunk:
    chunk_id: str
    recipe_id: str
    chunk_type: str
    evidence_type: str
    recipe_title: str
    brand: str
    author: str
    tags: List[str]
    publish_date: Optional[str]
    url: Optional[str]
    llm_ready_for_rag: int
    llm_ready_for_rag_source: Optional[str]
    evidence_strength: str
    issue_confidence: Optional[str]
    issue_source: Optional[str]
    display_issue: Optional[str]
    recommended_edit: Optional[str]
    why_it_matters: Optional[str]
    llm_editor_summary: Optional[str]
    text: str
    retrieval_text: str
    source_table: str
    source_comment_id: Optional[str] = None
    source_comment_created_at: Optional[str] = None
    rank_within_recipe: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


def make_chunk_id(recipe_id: str, chunk_type: str, evidence_type: str, index: int) -> str:
    return f"{recipe_id}::{chunk_type}::{evidence_type}::{index}"


def build_retrieval_text(
    recipe_title: str,
    brand: str,
    author: str,
    tags: List[str],
    evidence_type: str,
    text: str,
    display_issue: Optional[str],
    recommended_edit: Optional[str],
    why_it_matters: Optional[str],
    llm_editor_summary: Optional[str],
) -> str:
    parts: List[str] = []

    if recipe_title:
        parts.append(f"Recipe: {recipe_title}")
    if brand:
        parts.append(f"Brand: {brand}")
    if author:
        parts.append(f"Author: {author}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    if display_issue:
        parts.append(f"Main issue: {display_issue}")
    if recommended_edit:
        parts.append(f"Recommended edit: {recommended_edit}")
    if why_it_matters:
        parts.append(f"Why it matters: {why_it_matters}")
    if llm_editor_summary:
        parts.append(f"Editor summary: {llm_editor_summary}")

    parts.append(f"Evidence type: {evidence_type}")
    parts.append(f"Evidence: {text}")

    return "\n".join(parts)


def yield_decision_chunks(recipe_id: str, meta: Dict[str, Any]) -> Iterable[RagChunk]:
    decision_fields = [
        ("decision", "issue", meta.get("display_issue")),
        ("decision", "recommended_edit", meta.get("recommended_edit")),
        ("decision", "why_it_matters", meta.get("why_it_matters")),
        ("summary", "summary", meta.get("llm_editor_summary")),
    ]

    i = 0
    for chunk_type, evidence_type, value in decision_fields:
        text = normalize_whitespace(str(value or ""))
        if not text:
            continue

        i += 1
        retrieval_text = build_retrieval_text(
            recipe_title=meta["recipe_title"],
            brand=meta["brand"],
            author=meta["author"],
            tags=meta["tags"],
            evidence_type=evidence_type,
            text=text,
            display_issue=meta.get("display_issue"),
            recommended_edit=meta.get("recommended_edit"),
            why_it_matters=meta.get("why_it_matters"),
            llm_editor_summary=meta.get("llm_editor_summary"),
        )

        yield RagChunk(
            chunk_id=make_chunk_id(recipe_id, chunk_type, evidence_type, i),
            recipe_id=recipe_id,
            chunk_type=chunk_type,
            evidence_type=evidence_type,
            recipe_title=meta["recipe_title"],
            brand=meta["brand"],
            author=meta["author"],
            tags=meta["tags"],
            publish_date=meta.get("publish_date"),
            url=meta.get("url"),
            llm_ready_for_rag=meta["llm_ready_for_rag"],
            llm_ready_for_rag_source=meta.get("llm_ready_for_rag_source"),
            evidence_strength=meta["evidence_strength"],
            issue_confidence=meta.get("issue_confidence"),
            issue_source=meta.get("issue_source"),
            display_issue=meta.get("display_issue"),
            recommended_edit=meta.get("recommended_edit"),
            why_it_matters=meta.get("why_it_matters"),
            llm_editor_summary=meta.get("llm_editor_summary"),
            text=text,
            retrieval_text=retrieval_text,
            source_table="editorial_intelligence",
            metadata={"kind": "deterministic_context"},
        )


def candidate_text_fields(item: Dict[str, Any]) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    for key in [
        "comment_text",
        "text",
        "issue_comment_text",
        "fix_comment_text",
        "mixed_comment_text",
        "adaptation_comment_text",
        "evidence_text",
        "snippet",
    ]:
        value = normalize_whitespace(str(item.get(key) or ""))
        if value:
            fields.append((key, value))
    return fields


def detect_evidence_items_from_editorial(editorial_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    field_map = [
        ("evidence.issue_evidence_comments", "issue"),
        ("evidence.fix_evidence_comments", "problem_solving_fix"),
        ("evidence.mixed_evidence_comments", "mixed"),
        ("evidence.adaptation_comments", "adaptation"),
    ]

    for path, evidence_type in field_map:
        comments = deep_get(editorial_row, path)
        if not isinstance(comments, list):
            continue

        for idx, comment in enumerate(comments, start=1):
            text = normalize_whitespace(str(comment or ""))
            if not text:
                continue

            items.append(
                {
                    "evidence_type": evidence_type,
                    "rank": idx,
                    "payload": {"text": text},
                    "source": "editorial_intelligence",
                }
            )

    return items


def detect_evidence_items_from_recipe_evidence(evidence_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    list_field_map = {
        "issue_evidence": "issue",
        "fix_evidence": "problem_solving_fix",
        "problem_solving_fix_evidence": "problem_solving_fix",
        "mixed_evidence": "mixed",
        "adaptation_evidence": "adaptation",
    }

    for field_name, evidence_type in list_field_map.items():
        raw = evidence_row.get(field_name)
        if isinstance(raw, list):
            for idx, item in enumerate(raw, start=1):
                if not isinstance(item, dict):
                    continue
                items.append(
                    {
                        "evidence_type": evidence_type,
                        "rank": idx,
                        "payload": item,
                        "source": "recipe_evidence",
                    }
                )

    if items:
        return items

    flat_patterns = [
        ("issue", ["top_issue_1", "top_issue_2", "issue_comment_1", "issue_comment_2"]),
        ("problem_solving_fix", ["top_fix_1", "top_fix_2", "fix_comment_1", "fix_comment_2"]),
        ("mixed", ["top_mixed_1", "mixed_comment_1"]),
        ("adaptation", ["top_adaptation_1", "adaptation_comment_1"]),
    ]

    for evidence_type, field_names in flat_patterns:
        rank = 0
        for field_name in field_names:
            value = normalize_whitespace(str(evidence_row.get(field_name) or ""))
            if not value:
                continue
            rank += 1
            items.append(
                {
                    "evidence_type": evidence_type,
                    "rank": rank,
                    "payload": {"text": value},
                    "source": "recipe_evidence",
                }
            )

    return items


def yield_evidence_chunks(
    recipe_id: str,
    meta: Dict[str, Any],
    editorial_row: Dict[str, Any],
    evidence_row: Optional[Dict[str, Any]],
) -> Iterable[RagChunk]:
    items = detect_evidence_items_from_editorial(editorial_row)

    if not items and evidence_row is not None:
        items = detect_evidence_items_from_recipe_evidence(evidence_row)

    for idx, item in enumerate(items, start=1):
        payload = item["payload"]
        text_candidates = candidate_text_fields(payload)

        if not text_candidates and "text" in payload:
            text_candidates = [("text", normalize_whitespace(str(payload["text"])))]

        if not text_candidates:
            continue

        _, text = text_candidates[0]
        evidence_type = item["evidence_type"]

        retrieval_text = build_retrieval_text(
            recipe_title=meta["recipe_title"],
            brand=meta["brand"],
            author=meta["author"],
            tags=meta["tags"],
            evidence_type=evidence_type,
            text=text,
            display_issue=meta.get("display_issue"),
            recommended_edit=meta.get("recommended_edit"),
            why_it_matters=meta.get("why_it_matters"),
            llm_editor_summary=meta.get("llm_editor_summary"),
        )

        yield RagChunk(
            chunk_id=make_chunk_id(recipe_id, "evidence", evidence_type, idx),
            recipe_id=recipe_id,
            chunk_type="evidence",
            evidence_type=evidence_type,
            recipe_title=meta["recipe_title"],
            brand=meta["brand"],
            author=meta["author"],
            tags=meta["tags"],
            publish_date=meta.get("publish_date"),
            url=meta.get("url"),
            llm_ready_for_rag=meta["llm_ready_for_rag"],
            llm_ready_for_rag_source=meta.get("llm_ready_for_rag_source"),
            evidence_strength=meta["evidence_strength"],
            issue_confidence=meta.get("issue_confidence"),
            issue_source=meta.get("issue_source"),
            display_issue=meta.get("display_issue"),
            recommended_edit=meta.get("recommended_edit"),
            why_it_matters=meta.get("why_it_matters"),
            llm_editor_summary=meta.get("llm_editor_summary"),
            text=text,
            retrieval_text=retrieval_text,
            source_table=item.get("source", "editorial_intelligence"),
            source_comment_id=payload.get("comment_id"),
            source_comment_created_at=payload.get("created_at") or payload.get("comment_created_at"),
            rank_within_recipe=item.get("rank"),
            metadata={"raw_payload": payload},
        )


def build_corpus(
    editorial_path: Path,
    evidence_path: Path,
    summaries_path: Optional[Path],
    output_path: Path,
    rag_only: bool,
) -> Dict[str, Any]:
    editorial_rows = load_jsonl(editorial_path)
    evidence_rows = load_jsonl(evidence_path)
    summary_rows = load_jsonl(summaries_path) if summaries_path else []

    editorial_lookup = build_recipe_lookup(editorial_rows)
    evidence_lookup = build_recipe_lookup(evidence_rows)
    summary_lookup = build_summary_lookup(summary_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    recipes_seen = 0
    chunks_written = 0
    decision_chunks = 0
    evidence_chunks = 0
    skipped_non_rag = 0
    rag_source_counter: Counter[str] = Counter()
    evidence_strength_counter: Counter[str] = Counter()

    with output_path.open("w", encoding="utf-8") as out:
        for recipe_id, editorial_row in editorial_lookup.items():
            summary_row = summary_lookup.get(recipe_id)
            evidence_row = evidence_lookup.get(recipe_id)
            meta = get_recipe_metadata(editorial_row, summary_row)

            rag_source_counter.update([meta["llm_ready_for_rag_source"]])
            evidence_strength_counter.update([str(meta["evidence_strength"]).lower()])

            if rag_only and meta["llm_ready_for_rag"] != 1:
                skipped_non_rag += 1
                continue

            recipes_seen += 1

            for chunk in yield_decision_chunks(recipe_id, meta):
                out.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
                chunks_written += 1
                decision_chunks += 1

            for chunk in yield_evidence_chunks(recipe_id, meta, editorial_row, evidence_row):
                out.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
                chunks_written += 1
                evidence_chunks += 1

    return {
        "recipes_in_editorial": len(editorial_lookup),
        "recipes_written": recipes_seen,
        "chunks_written": chunks_written,
        "decision_chunks": decision_chunks,
        "evidence_chunks": evidence_chunks,
        "skipped_non_rag": skipped_non_rag,
        "rag_ready_sources": dict(rag_source_counter),
        "evidence_strengths": dict(evidence_strength_counter),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a retrieval corpus for recipe RAG")
    parser.add_argument("--editorial", default=DEFAULT_EDITORIAL_PATH, help="Path to editorial_intelligence.jsonl")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_PATH, help="Path to recipe_evidence.jsonl")
    parser.add_argument("--summaries", default=DEFAULT_SUMMARIES_PATH, help="Path to llm_editor_summaries.jsonl")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Path to write rag_corpus.jsonl")
    parser.add_argument(
        "--rag-only",
        action="store_true",
        help="Only include recipes where llm_ready_for_rag == 1",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    stats = build_corpus(
        editorial_path=Path(args.editorial),
        evidence_path=Path(args.evidence),
        summaries_path=Path(args.summaries) if args.summaries else None,
        output_path=Path(args.output),
        rag_only=args.rag_only,
    )

    print("Built RAG corpus")
    for key, value in stats.items():
        print(f"- {key}: {value}")
    print(f"- output: {args.output}")


if __name__ == "__main__":
    main()