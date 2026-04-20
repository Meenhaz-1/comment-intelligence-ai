# generate_llm_editor_summaries_batch.py
#
# Purpose:
# Submit recipe-summary requests through the OpenAI Batch API and fetch results.
#
# Inputs:
#   outputs/llm_summary_batch.jsonl
#
# Outputs:
#   outputs/llm_summary_batch_api_input.jsonl
#   outputs/llm_editor_summaries_batch_raw.jsonl
#   outputs/llm_editor_summaries.jsonl
#
# Usage:
#   python generate_llm_editor_summaries_batch.py prepare
#   python generate_llm_editor_summaries_batch.py submit
#   python generate_llm_editor_summaries_batch.py status --batch-id batch_abc123
#   python generate_llm_editor_summaries_batch.py fetch --batch-id batch_abc123
#
# Requirements:
#   pip install openai
#   export OPENAI_API_KEY=...

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


INPUT_PATH = Path("outputs/llm_summary_batch.jsonl")
BATCH_INPUT_PATH = Path("outputs/llm_summary_batch_api_input.jsonl")
RAW_OUTPUT_PATH = Path("outputs/llm_editor_summaries_batch_raw.jsonl")
FINAL_OUTPUT_PATH = Path("outputs/llm_editor_summaries.jsonl")

DEFAULT_MODEL = "gpt-5.4"


SYSTEM_INSTRUCTIONS = """
You write concise editorial summaries for an internal recipe-quality tool.

Your job is to turn structured recipe evidence into a short, useful summary for an editor.

Rules:
- Write a maximum of 2 sentences.
- Prefer 1 sentence when possible.
- Use only the information provided.
- Do not speculate.
- Do not invent issues, fixes, or user behavior.
- Do not use internal model language such as "friction", "engagement", "recoverability", "classification", or "opportunity".
- Do not say "this recipe shows" or "this recipe is a high-opportunity candidate".
- Write in plain cooking/editorial language such as "too salty", "too sweet", "dry", "bland", "curdled", "crumbly", "confusing", or "over-seasoned".
- If users describe a clear issue, lead with that issue.
- If users also suggest or imply a fix, include it briefly.
- If the issue is unclear, summarize the most common evidence theme and say manual review may be needed.
- Avoid weak phrasing like "may need" or "likely deserves attention"; be direct when evidence is clear.
- Be concrete, specific, and restrained.
- Avoid filler, hype, and vague phrasing.
- Return valid JSON only.

Return this schema exactly:
{
  "llm_editor_summary": "..."
}
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-generate editorial summaries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--input", type=Path, default=INPUT_PATH)
    prepare.add_argument("--output", type=Path, default=BATCH_INPUT_PATH)
    prepare.add_argument("--model", type=str, default=DEFAULT_MODEL)
    prepare.add_argument("--limit", type=int, default=None)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--input", type=Path, default=BATCH_INPUT_PATH)
    submit.add_argument("--model", type=str, default=DEFAULT_MODEL)
    submit.add_argument("--metadata-tag", type=str, default="recipe_llm_summary_batch")

    status = subparsers.add_parser("status")
    status.add_argument("--batch-id", type=str, required=True)

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--batch-id", type=str, required=True)
    fetch.add_argument("--raw-output", type=Path, default=RAW_OUTPUT_PATH)
    fetch.add_argument("--final-output", type=Path, default=FINAL_OUTPUT_PATH)

    return parser.parse_args()


def require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def build_batch_request_row(batch_row: dict[str, Any], model: str) -> dict[str, Any]:
    recipe_id = batch_row.get("recipe_id")
    if not recipe_id:
        raise ValueError("Missing recipe_id in batch row")

    return {
        "custom_id": str(recipe_id),
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "instructions": SYSTEM_INSTRUCTIONS,
            "input": build_user_input(batch_row),
            "max_output_tokens": 120,
        },
    }


def prepare_batch_input(input_path: Path, output_path: Path, model: str, limit: int | None) -> None:
    rows = read_jsonl(input_path)
    if limit is not None:
        rows = rows[:limit]

    batch_rows = [build_batch_request_row(row, model=model) for row in rows]
    write_jsonl(output_path, batch_rows)

    print(f"Read {len(rows):,} rows from {input_path}")
    print(f"Wrote batch input file: {output_path}")


def submit_batch(input_path: Path, model: str, metadata_tag: str) -> None:
    require_api_key()

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()

    uploaded = client.files.create(
        file=input_path,
        purpose="batch",
    )

    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={
            "job_type": metadata_tag,
            "model": model,
        },
    )

    print("Uploaded batch input file.")
    print(f"  file_id: {uploaded.id}")
    print()
    print("Created batch job.")
    print(f"  batch_id: {batch.id}")
    print(f"  status: {batch.status}")
    print(f"  input_file_id: {batch.input_file_id}")
    print()
    print("Save this batch_id. You will need it to check status and fetch results.")


def check_status(batch_id: str) -> None:
    require_api_key()
    client = OpenAI()

    batch = client.batches.retrieve(batch_id)

    print(f"batch_id: {batch.id}")
    print(f"status: {batch.status}")
    print(f"input_file_id: {batch.input_file_id}")
    print(f"output_file_id: {batch.output_file_id}")
    print(f"error_file_id: {batch.error_file_id}")

    counts = getattr(batch, "request_counts", None)
    if counts:
        print("request_counts:")
        print(f"  total: {counts.total}")
        print(f"  completed: {counts.completed}")
        print(f"  failed: {counts.failed}")


def save_file_content(client: OpenAI, file_id: str, output_path: Path) -> None:
    content = client.files.content(file_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = content.read()
    with output_path.open("wb") as f:
        f.write(data)


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

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
    return text[:500]


def parse_batch_raw_results(raw_output_path: Path, final_output_path: Path) -> None:
    raw_rows = read_jsonl(raw_output_path)
    final_rows: list[dict[str, Any]] = []

    for row in raw_rows:
        recipe_id = row.get("custom_id")

        # Error case
        if row.get("error"):
            final_rows.append({
                "recipe_id": recipe_id,
                "evidence_strength": None,
                "llm_editor_summary": None,
                "model": None,
                "status": "error",
                "error": row.get("error"),
            })
            continue

        response = row.get("response", {})
        body = response.get("body", {}) if isinstance(response, dict) else {}

        model = body.get("model")
        output_text = body.get("output_text", "")

        try:
            parsed = extract_json_from_text(output_text)
            summary = normalize_summary(parsed.get("llm_editor_summary"))
            status = "ok" if summary else "error"

            final_rows.append({
                "recipe_id": recipe_id,
                "evidence_strength": None,
                "llm_editor_summary": summary if summary else None,
                "model": model,
                "status": status,
                "error": None if summary else "Missing llm_editor_summary",
            })
        except Exception as exc:
            final_rows.append({
                "recipe_id": recipe_id,
                "evidence_strength": None,
                "llm_editor_summary": None,
                "model": model,
                "status": "error",
                "error": str(exc),
            })

    write_jsonl(final_output_path, final_rows)

    ok_count = sum(1 for row in final_rows if row.get("status") == "ok")
    error_count = len(final_rows) - ok_count

    print(f"Read raw batch output: {raw_output_path}")
    print(f"Wrote parsed summaries: {final_output_path}")
    print(f"OK: {ok_count:,}")
    print(f"Errors: {error_count:,}")


def fetch_results(batch_id: str, raw_output_path: Path, final_output_path: Path) -> None:
    require_api_key()
    client = OpenAI()

    batch = client.batches.retrieve(batch_id)

    print(f"batch_id: {batch.id}")
    print(f"status: {batch.status}")

    if batch.status != "completed":
        print("Batch is not completed yet. Check again later.")
        return

    if not batch.output_file_id:
        print("Batch completed but no output_file_id was found.", file=sys.stderr)
        sys.exit(1)

    save_file_content(client, batch.output_file_id, raw_output_path)
    print(f"Downloaded raw batch output to: {raw_output_path}")

    parse_batch_raw_results(raw_output_path, final_output_path)


def main() -> None:
    args = parse_args()

    if args.command == "prepare":
        prepare_batch_input(
            input_path=args.input,
            output_path=args.output,
            model=args.model,
            limit=args.limit,
        )
    elif args.command == "submit":
        submit_batch(
            input_path=args.input,
            model=args.model,
            metadata_tag=args.metadata_tag,
        )
    elif args.command == "status":
        check_status(args.batch_id)
    elif args.command == "fetch":
        fetch_results(
            batch_id=args.batch_id,
            raw_output_path=args.raw_output,
            final_output_path=args.final_output,
        )
    else:
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()