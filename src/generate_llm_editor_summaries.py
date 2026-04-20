# generate_llm_editor_summaries.py
#
# Purpose:
# Generate grounded editorial summaries from the LLM summary batch file.
#
# Input:
#   outputs/llm_summary_batch.jsonl
#
# Output:
#   outputs/llm_editor_summaries.jsonl
#
# Behavior:
#   - Reads one batch row at a time
#   - Calls the OpenAI Responses API
#   - Writes:
#       recipe_id
#       evidence_strength
#       llm_editor_summary
#       model
#       status
#   - Safe to rerun: skips recipe_ids already present in the output file
#
# Requirements:
#   pip install openai
#   export OPENAI_API_KEY=...
#
# Suggested first pass:
#   python generate_llm_editor_summaries.py --limit 50
#
# Then:
#   python generate_llm_editor_summaries.py

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI


INPUT_PATH = Path("outputs/llm_summary_batch.jsonl")
OUTPUT_PATH = Path("outputs/llm_editor_summaries.jsonl")

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_SLEEP_SECONDS = 0.0
DEFAULT_MAX_RETRIES = 3


SYSTEM_INSTRUCTIONS = """
You are writing concise editorial summaries for an internal recipe-quality tool.

Your job is to turn structured recipe evidence into a short editor-facing summary.

Rules:
- Write exactly 1 to 2 sentences.
- Maximum 2 sentences. Never exceed this.
- If unsure, use 1 sentence.
- Use only the provided fields and evidence.
- Do not use terms like "friction", "engagement", "recoverability".
- Always describe the issue in plain cooking language (e.g., too salty, bland, dry).
- If issue is unclear, summarize the most common themes in the evidence.
- Do not infer engagement level or metrics unless explicitly stated.
- Do not speculate.
- Do not invent issues or fixes.
- If evidence is incomplete, be cautious.
- Focus on the main issue, what users suggest or imply, and why the recipe may deserve attention.
- Keep the tone factual, editorial, and useful.
- Avoid hype, filler, and generic praise.
- Do not mention that you are an AI.
- Never mention more than 2 issues in one summary.
- Return valid JSON only.

Return this schema exactly:
{
  "llm_editor_summary": "..."
}
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LLM editor summaries from batch payloads.")
    parser.add_argument("--input", type=Path, default=INPUT_PATH, help="Input JSONL batch file")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output JSONL summaries file")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of rows to process")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS, help="Optional pause between API calls")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retries per failed row")
    return parser.parse_args()


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


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_completed_recipe_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()

    completed: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            recipe_id = row.get("recipe_id")
            if recipe_id:
                completed.add(str(recipe_id))
    return completed


def compact_prompt_payload(batch_row: dict[str, Any]) -> dict[str, Any]:
    """
    Keep the prompt small and stable.
    We use the already-curated prompt_input payload from the batch builder.
    """
    prompt_input = batch_row.get("prompt_input", {})
    return {
        "recipe_id": batch_row.get("recipe_id"),
        "evidence_strength": batch_row.get("evidence_strength"),
        "prompt_input": prompt_input,
    }


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()

    # Best case: pure JSON.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: extract the first JSON object-looking span.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Model output was not valid JSON")


def normalize_summary(value: Any) -> str:
    if value is None:
        return ""

    text = " ".join(str(value).strip().split())

    # Hard guard: keep summaries short
    return text[:500]


def build_user_input(batch_row: dict[str, Any]) -> str:
    payload = {
        "recipe_id": batch_row.get("recipe_id"),
        "evidence_strength": batch_row.get("evidence_strength"),
        "metadata": batch_row.get("prompt_input", {}).get("metadata", {}),
        "issue": batch_row.get("prompt_input", {}).get("decision", {}).get("issue", {}),
        "recommended_edit": batch_row.get("prompt_input", {}).get("decision", {}).get("recommended_edit"),
        "why_it_matters": batch_row.get("prompt_input", {}).get("decision", {}).get("why_it_matters"),
        "evidence": batch_row.get("prompt_input", {}).get("evidence", {}),
        "editorial_context": batch_row.get("prompt_input", {}).get("llm_input", {}).get("editorial_context"),
        "reasoning_summary": batch_row.get("prompt_input", {}).get("llm_input", {}).get("reasoning_summary"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def call_model(
    client: OpenAI,
    model: str,
    batch_row: dict[str, Any],
) -> str:
    user_input = build_user_input(batch_row)

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=user_input,
        max_output_tokens=120

    )

    raw_text = response.output_text
    parsed = extract_json_from_text(raw_text)
    summary = normalize_summary(parsed.get("llm_editor_summary"))

    if not summary:
        raise ValueError("Missing llm_editor_summary in model output")

    return summary


def process_rows(
    client: OpenAI,
    rows: list[dict[str, Any]],
    output_path: Path,
    model: str,
    limit: int | None,
    sleep_seconds: float,
    max_retries: int,
) -> None:
    completed_ids = load_completed_recipe_ids(output_path)

    processed = 0
    skipped = 0
    succeeded = 0
    failed = 0

    for row in rows:
        recipe_id = str(row.get("recipe_id") or "").strip()
        evidence_strength = row.get("evidence_strength")

        if not recipe_id:
            skipped += 1
            continue

        if recipe_id in completed_ids:
            skipped += 1
            continue

        if limit is not None and processed >= limit:
            break

        processed += 1

        last_error = None
        summary = ""

        for attempt in range(1, max_retries + 1):
            try:
                summary = call_model(client=client, model=model, batch_row=row)
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    time.sleep(min(2 * attempt, 5))

        if last_error is not None:
            failed += 1
            append_jsonl(output_path, {
                "recipe_id": recipe_id,
                "evidence_strength": evidence_strength,
                "llm_editor_summary": None,
                "model": model,
                "status": "error",
                "error": last_error,
            })
            print(f"[ERROR] {recipe_id}: {last_error}")
        else:
            succeeded += 1
            append_jsonl(output_path, {
                "recipe_id": recipe_id,
                "evidence_strength": evidence_strength,
                "llm_editor_summary": summary,
                "model": model,
                "status": "ok",
            })
            print(f"[OK] {recipe_id}: {summary}")

        completed_ids.add(recipe_id)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    print()
    print(f"Processed this run: {processed:,}")
    print(f"Skipped existing/malformed: {skipped:,}")
    print(f"Succeeded: {succeeded:,}")
    print(f"Failed: {failed:,}")
    print(f"Output file: {output_path}")


def main() -> None:
    args = parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    rows = read_jsonl(args.input)
    client = OpenAI()

    print(f"Read {len(rows):,} rows from {args.input}")
    print(f"Writing summaries to {args.output}")
    print(f"Model: {args.model}")
    if args.limit is not None:
        print(f"Limit: {args.limit:,}")
    print()

    process_rows(
        client=client,
        rows=rows,
        output_path=args.output,
        model=args.model,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
    )


if __name__ == "__main__":
    main()