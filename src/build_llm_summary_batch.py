# build_llm_summary_batch.py
#
# Purpose:
# Build a compact batch payload for the first LLM summary pass.
#
# Input:
#   outputs/editorial_intelligence.jsonl
#
# Output:
#   outputs/llm_summary_batch.jsonl
#   outputs/llm_summary_eval_sample.csv
#
# First-pass gating:
#   - llm_readiness.llm_ready_for_summary == True
#   - llm_readiness.evidence_strength in ("medium", "high")
#
# Optional later:
#   - include low in a second experiment only

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


INPUT_PATH = Path("outputs/editorial_intelligence.jsonl")
OUTPUT_BATCH_PATH = Path("outputs/llm_summary_batch.jsonl")
OUTPUT_EVAL_SAMPLE_PATH = Path("outputs/llm_summary_eval_sample.csv")

ALLOWED_EVIDENCE_STRENGTH = {"medium", "high"}

# How many evidence comments to carry forward into the payload.
# Keep this small to control tokens and reduce noise.
MAX_ISSUE_EVIDENCE = 2
MAX_FIX_EVIDENCE = 2
MAX_MIXED_EVIDENCE = 1
MAX_ADAPTATION_EVIDENCE = 1

# Eval sample settings
EVAL_SAMPLE_MEDIUM = 20
EVAL_SAMPLE_HIGH = 20


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc
    return rows


def normalize_bool_like(value: Any) -> bool:
    """
    Normalize bool-like values so the script works even if the source
    stores readiness as True, 1, '1', 'true', etc.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def truncate_evidence(items: list[Any], limit: int) -> list[Any]:
    return items[:limit]


def compact_evidence(recipe: dict[str, Any]) -> dict[str, Any]:
    """
    The source schema stores evidence in a nested 'evidence' object.
    We keep only the highest-value comments to control payload size.
    """
    evidence = recipe.get("evidence", {})

    return {
        "issue_evidence_comments": truncate_evidence(
            as_list(evidence.get("issue_evidence_comments")),
            MAX_ISSUE_EVIDENCE,
        ),
        "fix_evidence_comments": truncate_evidence(
            as_list(evidence.get("fix_evidence_comments")),
            MAX_FIX_EVIDENCE,
        ),
        "mixed_evidence_comments": truncate_evidence(
            as_list(evidence.get("mixed_evidence_comments")),
            MAX_MIXED_EVIDENCE,
        ),
        "adaptation_comments": truncate_evidence(
            as_list(evidence.get("adaptation_comments")),
            MAX_ADAPTATION_EVIDENCE,
        ),
        "has_issue_evidence": evidence.get("has_issue_evidence"),
        "has_fix_evidence": evidence.get("has_fix_evidence"),
        "has_mixed_evidence": evidence.get("has_mixed_evidence"),
        "total_selected_evidence_comments": evidence.get("total_selected_evidence_comments"),
    }


def build_prompt_input(recipe: dict[str, Any]) -> dict[str, Any]:
    """
    Build a compact, structured prompt payload.
    The source JSON is already clean and nested, so reuse that structure.
    """
    return {
        "recipe_id": recipe.get("recipe_id"),
        "metadata": recipe.get("metadata", {}),
        "decision": recipe.get("decision", {}),
        "signals": recipe.get("signals", {}),
        "evidence": compact_evidence(recipe),
        "llm_readiness": recipe.get("llm_readiness", {}),
        "llm_input": recipe.get("llm_input", {}),
    }


def build_batch_row(recipe: dict[str, Any]) -> dict[str, Any]:
    llm_readiness = recipe.get("llm_readiness", {})

    return {
        "recipe_id": recipe.get("recipe_id"),
        "evidence_strength": llm_readiness.get("evidence_strength"),
        "prompt_input": build_prompt_input(recipe),
        "output_schema": {
            "llm_editor_summary": (
                "1 to 2 sentences, grounded only in provided evidence and fields, "
                "editorial tone, no speculation"
            )
        },
    }


def filter_summary_ready(recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for recipe in recipes:
        llm_readiness = recipe.get("llm_readiness", {})

        ready = normalize_bool_like(llm_readiness.get("llm_ready_for_summary"))
        evidence_strength = normalize_str(llm_readiness.get("evidence_strength"))

        if not ready:
            continue

        if evidence_strength not in ALLOWED_EVIDENCE_STRENGTH:
            continue

        recipe_id = recipe.get("recipe_id")
        if not recipe_id:
            continue

        out.append(recipe)

    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def take_first_n(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    return rows[:n]


def write_eval_sample(path: Path, medium_rows: list[dict[str, Any]], high_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "recipe_id",
        "title",
        "brand",
        "evidence_strength",
        "classification",
        "display_issue",
        "recommended_edit",
        "why_it_matters",
        "issue_confidence",
        "groundedness_score",
        "correctness_score",
        "usefulness_score",
        "specificity_score",
        "notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for recipe in medium_rows + high_rows:
            metadata = recipe.get("metadata", {})
            decision = recipe.get("decision", {})
            issue = decision.get("issue", {})
            llm_readiness = recipe.get("llm_readiness", {})

            writer.writerow({
                "recipe_id": recipe.get("recipe_id"),
                "title": metadata.get("title"),
                "brand": metadata.get("brand"),
                "evidence_strength": llm_readiness.get("evidence_strength"),
                "classification": decision.get("classification"),
                "display_issue": issue.get("display_issue"),
                "recommended_edit": decision.get("recommended_edit"),
                "why_it_matters": decision.get("why_it_matters"),
                "issue_confidence": issue.get("issue_confidence"),
                "groundedness_score": "",
                "correctness_score": "",
                "usefulness_score": "",
                "specificity_score": "",
                "notes": "",
            })


def main() -> None:
    recipes = read_jsonl(INPUT_PATH)

    # Helpful debug so schema mismatches are obvious immediately.
    print("Sample raw values:")
    for recipe in recipes[:5]:
        llm_readiness = recipe.get("llm_readiness", {})
        print(
            recipe.get("recipe_id"),
            repr(llm_readiness.get("llm_ready_for_summary")),
            repr(llm_readiness.get("evidence_strength")),
        )

    ready_count = 0
    medium_high_count = 0

    for recipe in recipes:
        llm_readiness = recipe.get("llm_readiness", {})
        ready = normalize_bool_like(llm_readiness.get("llm_ready_for_summary"))
        evidence_strength = normalize_str(llm_readiness.get("evidence_strength"))

        if ready:
            ready_count += 1
        if evidence_strength in ALLOWED_EVIDENCE_STRENGTH:
            medium_high_count += 1

    print()
    print(f"Rows with summary-ready flag: {ready_count:,}")
    print(f"Rows with medium/high evidence: {medium_high_count:,}")
    print()

    filtered = filter_summary_ready(recipes)

    # Sort best candidates first for the first pass.
    # Evidence strength first, then opportunity score descending.
    evidence_rank = {"high": 2, "medium": 1}

    filtered.sort(
        key=lambda r: (
            evidence_rank.get(
                normalize_str(r.get("llm_readiness", {}).get("evidence_strength")),
                0,
            ),
            float(r.get("decision", {}).get("opportunity_score") or 0),
        ),
        reverse=True,
    )

    batch_rows = [build_batch_row(recipe) for recipe in filtered]
    write_jsonl(OUTPUT_BATCH_PATH, batch_rows)

    medium_rows = [
        r for r in filtered
        if normalize_str(r.get("llm_readiness", {}).get("evidence_strength")) == "medium"
    ]
    high_rows = [
        r for r in filtered
        if normalize_str(r.get("llm_readiness", {}).get("evidence_strength")) == "high"
    ]

    eval_medium = take_first_n(medium_rows, EVAL_SAMPLE_MEDIUM)
    eval_high = take_first_n(high_rows, EVAL_SAMPLE_HIGH)

    write_eval_sample(OUTPUT_EVAL_SAMPLE_PATH, eval_medium, eval_high)

    print(f"Read {len(recipes):,} recipes from {INPUT_PATH}")
    print(f"Filtered to {len(filtered):,} summary-ready recipes")
    print(f"Wrote batch file: {OUTPUT_BATCH_PATH}")
    print(f"Wrote eval sample: {OUTPUT_EVAL_SAMPLE_PATH}")
    print()

    print("Evidence strength breakdown in batch:")
    print(f"  medium: {len(medium_rows):,}")
    print(f"  high:   {len(high_rows):,}")

    if filtered:
        sample = filtered[0]
        print()
        print("Sample filtered row:")
        print(f"  recipe_id: {sample.get('recipe_id')}")
        print(f"  llm_readiness: {sample.get('llm_readiness')}")
        print(f"  classification: {sample.get('decision', {}).get('classification')}")
        print(f"  title: {sample.get('metadata', {}).get('title')}")


if __name__ == "__main__":
    main()