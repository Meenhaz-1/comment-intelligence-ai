from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


NAIVE_INPUT_PATH = Path("outputs/experiments/naive_llm_comment_analysis.jsonl")
EDITORIAL_INPUT_PATH = Path("outputs/editorial_intelligence.jsonl")
OUTPUT_PATH = Path("outputs/experiments/naive_llm_comparison.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare naive LLM experiment to editorial intelligence.")
    parser.add_argument("--naive-input", type=Path, default=NAIVE_INPUT_PATH)
    parser.add_argument("--editorial-input", type=Path, default=EDITORIAL_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}") from exc
    return rows


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return " ".join(text.split())


def token_set(value: Any) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) > 1}


def rough_match(left: Any, right: Any) -> bool:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    return bool(overlap)


def extract_first_friction(parsed_json: dict[str, Any] | None) -> tuple[str, str]:
    if not isinstance(parsed_json, dict):
        return "", ""
    frictions = parsed_json.get("main_friction_points", [])
    if not isinstance(frictions, list) or not frictions:
        return "", ""
    first = frictions[0] if isinstance(frictions[0], dict) else {}
    return str(first.get("friction", "") or "").strip(), str(first.get("confidence", "") or "").strip()


def extract_first_fix(parsed_json: dict[str, Any] | None) -> str:
    if not isinstance(parsed_json, dict):
        return ""
    fixes = parsed_json.get("suggested_fixes", [])
    if not isinstance(fixes, list) or not fixes:
        return ""
    first = fixes[0] if isinstance(fixes[0], dict) else {}
    return str(first.get("fix", "") or "").strip()


def extract_snippet_count(parsed_json: dict[str, Any] | None) -> int:
    if not isinstance(parsed_json, dict):
        return 0

    count = 0
    for friction in parsed_json.get("main_friction_points", []):
        if isinstance(friction, dict):
            count += len(friction.get("supporting_snippets", []) or [])
    for fix in parsed_json.get("suggested_fixes", []):
        if isinstance(fix, dict):
            count += len(fix.get("supporting_snippets", []) or [])
    return count


def extract_uncertainty_notes(parsed_json: dict[str, Any] | None) -> str:
    if not isinstance(parsed_json, dict):
        return ""
    notes = parsed_json.get("uncertainty_notes", [])
    if not isinstance(notes, list):
        return ""
    clean = [str(note).strip() for note in notes if str(note).strip()]
    return " | ".join(clean)


def build_editorial_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        recipe_id = str(row.get("recipe_id", "") or "").strip()
        if not recipe_id:
            continue
        lookup[recipe_id] = row
    return lookup


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "recipe_id",
        "recipe_title",
        "llm_top_friction",
        "deterministic_display_issue",
        "llm_top_fix",
        "deterministic_recommended_edit",
        "llm_confidence",
        "deterministic_issue_confidence",
        "snippet_count",
        "uncertainty_notes",
        "rough_match_flag",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()

    naive_rows = read_jsonl(args.naive_input)
    editorial_rows = read_jsonl(args.editorial_input) if args.editorial_input.exists() else []
    editorial_lookup = build_editorial_lookup(editorial_rows)

    comparison_rows: list[dict[str, Any]] = []

    for row in naive_rows:
        parsed_json = row.get("parsed_json")
        recipe_id = str(row.get("recipe_id", "") or "").strip()
        recipe_title = str(row.get("recipe_title", "") or "").strip()
        llm_top_friction, llm_confidence = extract_first_friction(parsed_json)
        llm_top_fix = extract_first_fix(parsed_json)
        snippet_count = extract_snippet_count(parsed_json)
        uncertainty_notes = extract_uncertainty_notes(parsed_json)

        editorial = editorial_lookup.get(recipe_id, {})
        decision = editorial.get("decision", {}) if isinstance(editorial, dict) else {}
        issue = decision.get("issue", {}) if isinstance(decision, dict) else {}

        deterministic_display_issue = str(issue.get("display_issue", "") or "").strip()
        deterministic_recommended_edit = str(decision.get("recommended_edit", "") or "").strip()
        deterministic_issue_confidence = str(issue.get("issue_confidence", "") or "").strip()
        rough_match_flag = rough_match(llm_top_friction, deterministic_display_issue)

        comparison_rows.append(
            {
                "recipe_id": recipe_id,
                "recipe_title": recipe_title,
                "llm_top_friction": llm_top_friction,
                "deterministic_display_issue": deterministic_display_issue,
                "llm_top_fix": llm_top_fix,
                "deterministic_recommended_edit": deterministic_recommended_edit,
                "llm_confidence": llm_confidence,
                "deterministic_issue_confidence": deterministic_issue_confidence,
                "snippet_count": snippet_count,
                "uncertainty_notes": uncertainty_notes,
                "rough_match_flag": int(rough_match_flag),
            }
        )

    write_csv(args.output, comparison_rows)

    recipes_processed = len(naive_rows)
    recipes_with_friction = sum(1 for row in comparison_rows if row["llm_top_friction"])
    recipes_with_fixes = sum(1 for row in comparison_rows if row["llm_top_fix"])
    recipes_with_no_clear_evidence = sum(
        1
        for row in comparison_rows
        if not row["llm_top_friction"] and not row["llm_top_fix"]
    )

    print(f"Saved comparison file: {args.output}")
    print(f"Recipes processed: {recipes_processed:,}")
    print(f"Recipes with friction found: {recipes_with_friction:,}")
    print(f"Recipes with fixes found: {recipes_with_fixes:,}")
    print(f"Recipes with no clear evidence: {recipes_with_no_clear_evidence:,}")

    if comparison_rows and editorial_rows:
        matches = sum(int(row["rough_match_flag"]) for row in comparison_rows)
        match_rate = matches / len(comparison_rows)
        print(f"Rough match rate vs deterministic layer: {match_rate:.1%}")


if __name__ == "__main__":
    main()
