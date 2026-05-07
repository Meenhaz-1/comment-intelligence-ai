from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


BASE_DIR = Path(__file__).resolve().parents[2]

COMMENTS_PATH = BASE_DIR / "outputs" / "cleaned_comments.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "experiments" / "llm_repeatability"
RAW_OUTPUT_PATH = OUTPUT_DIR / "llm_comment_classification_repeatability_raw.jsonl"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "llm_comment_classification_repeatability_summary.csv"
DISAGREEMENTS_OUTPUT_PATH = OUTPUT_DIR / "llm_comment_classification_disagreements.csv"

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_COMMENTS = 50
DEFAULT_RUNS = 3
DEFAULT_SLEEP_SECONDS = 0.2
DEFAULT_MAX_RETRIES = 1


JSON_SCHEMA: dict[str, Any] = {
    "name": "llm_comment_classification_repeatability",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "comment_id": {"type": "string"},
            "recipe_id": {"type": "string"},
            "friction_flag": {"type": "boolean"},
            "fix_flag": {"type": "boolean"},
            "adaptation_flag": {"type": "boolean"},
            "positive_flag": {"type": "boolean"},
            "issue_type": {
                "type": "string",
                "enum": [
                    "cooking_failure",
                    "instruction_clarity",
                    "measurement_confusion",
                    "taste_preference",
                    "product_or_site_issue",
                    "none",
                ],
            },
            "fix_type": {
                "type": "string",
                "enum": ["problem_solving_fix", "neutral_adaptation", "none"],
            },
            "friction_label": {
                "type": ["string", "null"],
            },
            "fix_label": {
                "type": ["string", "null"],
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "evidence_quote": {
                "type": ["string", "null"],
            },
        },
        "required": [
            "comment_id",
            "recipe_id",
            "friction_flag",
            "fix_flag",
            "adaptation_flag",
            "positive_flag",
            "issue_type",
            "fix_type",
            "friction_label",
            "fix_label",
            "confidence",
            "evidence_quote",
        ],
    },
}


SYSTEM_PROMPT = """
You are classifying exactly one recipe comment.

Return JSON only and follow the schema exactly.

Rules:
- Classify only the provided comment.
- Do not use outside knowledge.
- Do not infer a fix unless the comment explicitly describes a change meant to solve a problem.
- Separate neutral adaptations from problem-solving fixes.
- Separate cooking failures from instruction clarity or measurement confusion.
- Product/app/site complaints should not count as recipe friction.
- If unclear, prefer false and low confidence.
- evidence_quote must be an exact substring from the provided comment or null.
- If issue_type is "none", friction_flag should usually be false.
- If fix_type is "none", fix_flag should usually be false.
- adaptation_flag should be true only for neutral adaptations rather than explicit problem-solving fixes.
- positive_flag should be true only when the comment clearly expresses positive satisfaction.
- friction_label and fix_label should be short normalized labels or null.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repeatability test for per-comment LLM classification.")
    parser.add_argument("--comments", type=Path, default=COMMENTS_PATH)
    parser.add_argument("--recipe-id", type=str, required=True)
    parser.add_argument("--max-comments", type=int, default=DEFAULT_MAX_COMMENTS)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    return parser.parse_args()


def require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)


def load_comments(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing comments input: {path}")

    df = pd.read_csv(path, low_memory=False)
    required = {"comment_id", "recipe_id", "comment_text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    work = df.copy()
    work["comment_id"] = work["comment_id"].astype(str).str.strip()
    work["recipe_id"] = work["recipe_id"].astype(str).str.strip()
    work["comment_text"] = work["comment_text"].fillna("").astype(str).str.strip()

    if "created_at" in work.columns:
        work["created_at"] = pd.to_datetime(work["created_at"], errors="coerce")
    else:
        work["created_at"] = pd.NaT

    work = work[
        (work["comment_id"] != "") &
        (work["recipe_id"] != "") &
        (work["comment_text"] != "")
    ].copy()
    return work


def select_recipe_comments(
    comments_df: pd.DataFrame,
    recipe_id: str,
    max_comments: int,
) -> pd.DataFrame:
    work = comments_df[comments_df["recipe_id"] == recipe_id].copy()
    if work.empty:
        raise ValueError(f"No comments found for recipe_id={recipe_id}")

    work = work.sort_values(
        by=["created_at", "comment_id"],
        ascending=[True, True],
        na_position="last",
    )
    return work.head(max_comments).reset_index(drop=True)


def build_comment_prompt(row: pd.Series) -> str:
    payload = {
        "comment_id": str(row["comment_id"]),
        "recipe_id": str(row["recipe_id"]),
        "comment_text": str(row["comment_text"]),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def extract_response_text(response: Any) -> str:
    output = getattr(response, "output", None)
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for part in content:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        if chunks:
            return "\n".join(chunks)

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    return ""


def classify_comment_once(
    client: OpenAI,
    prompt_text: str,
    model: str,
) -> tuple[dict[str, Any], str]:
    response = client.responses.create(
        model=model,
        temperature=0,
        instructions=SYSTEM_PROMPT,
        input=prompt_text,
        text={
            "format": {
                "type": "json_schema",
                "name": JSON_SCHEMA["name"],
                "schema": JSON_SCHEMA["schema"],
                "strict": True,
            }
        },
    )

    raw_text = extract_response_text(response)
    if not raw_text:
        raise ValueError("No output text returned from model")

    parsed = json.loads(raw_text)
    return parsed, raw_text


def classify_comment_with_retry(
    client: OpenAI,
    prompt_text: str,
    model: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> tuple[dict[str, Any] | None, str | None, str | None, int]:
    attempt = 0
    last_error = None

    while attempt <= max_retries:
        attempt += 1
        try:
            parsed, raw_text = classify_comment_once(
                client=client,
                prompt_text=prompt_text,
                model=model,
            )
            return parsed, raw_text, None, attempt
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt > max_retries:
                break

    return None, None, last_error, attempt


def append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def to_bool(value: Any) -> bool:
    return bool(value)


def aggregate_run(rows: list[dict[str, Any]], run_number: int) -> dict[str, Any]:
    run_rows = [row for row in rows if row["run_number"] == run_number and row["status"] == "ok"]
    total_comments = len(run_rows)

    def count_where(key: str, expected: Any = True) -> int:
        return sum(1 for row in run_rows if row["parsed_json"].get(key) == expected)

    friction_count = count_where("friction_flag", True)
    fix_count = count_where("fix_flag", True)
    adaptation_count = count_where("adaptation_flag", True)
    positive_count = count_where("positive_flag", True)

    def issue_count(issue_type: str) -> int:
        return sum(1 for row in run_rows if row["parsed_json"].get("issue_type") == issue_type)

    summary = {
        "run_number": run_number,
        "total_comments": total_comments,
        "friction_count": friction_count,
        "fix_count": fix_count,
        "adaptation_count": adaptation_count,
        "positive_count": positive_count,
        "cooking_failure_count": issue_count("cooking_failure"),
        "instruction_clarity_count": issue_count("instruction_clarity"),
        "measurement_confusion_count": issue_count("measurement_confusion"),
        "taste_preference_count": issue_count("taste_preference"),
        "product_or_site_issue_count": issue_count("product_or_site_issue"),
        "no_issue_count": issue_count("none"),
        "friction_rate_pct": round((friction_count / total_comments) * 100, 2) if total_comments else 0.0,
        "fix_rate_pct": round((fix_count / total_comments) * 100, 2) if total_comments else 0.0,
        "adaptation_rate_pct": round((adaptation_count / total_comments) * 100, 2) if total_comments else 0.0,
    }
    return summary


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "run_number",
        "total_comments",
        "friction_count",
        "fix_count",
        "adaptation_count",
        "positive_count",
        "cooking_failure_count",
        "instruction_clarity_count",
        "measurement_confusion_count",
        "taste_preference_count",
        "product_or_site_issue_count",
        "no_issue_count",
        "friction_rate_pct",
        "fix_rate_pct",
        "adaptation_rate_pct",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_disagreement_rows(
    comments_df: pd.DataFrame,
    raw_rows: list[dict[str, Any]],
    runs: int,
) -> list[dict[str, Any]]:
    by_comment: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        if row["status"] != "ok":
            continue
        by_comment.setdefault(row["comment_id"], []).append(row)

    comment_text_lookup = {
        str(row["comment_id"]): str(row["comment_text"])
        for _, row in comments_df.iterrows()
    }

    disagreement_rows: list[dict[str, Any]] = []

    for comment_id, rows in by_comment.items():
        runs_present = {row["run_number"] for row in rows}
        if len(runs_present) != runs:
            continue

        rows_by_run = {row["run_number"]: row for row in rows}
        friction_values = [rows_by_run[run]["parsed_json"]["friction_flag"] for run in range(1, runs + 1)]
        fix_values = [rows_by_run[run]["parsed_json"]["fix_flag"] for run in range(1, runs + 1)]
        issue_values = [rows_by_run[run]["parsed_json"]["issue_type"] for run in range(1, runs + 1)]
        fix_type_values = [rows_by_run[run]["parsed_json"]["fix_type"] for run in range(1, runs + 1)]

        if (
            len(set(friction_values)) == 1 and
            len(set(fix_values)) == 1 and
            len(set(issue_values)) == 1 and
            len(set(fix_type_values)) == 1
        ):
            continue

        row: dict[str, Any] = {
            "comment_id": comment_id,
            "comment_text": comment_text_lookup.get(comment_id, ""),
        }
        for run in range(1, runs + 1):
            parsed = rows_by_run[run]["parsed_json"]
            row[f"run_{run}_friction_flag"] = parsed["friction_flag"]
            row[f"run_{run}_fix_flag"] = parsed["fix_flag"]
            row[f"run_{run}_issue_type"] = parsed["issue_type"]
            row[f"run_{run}_fix_type"] = parsed["fix_type"]
        disagreement_rows.append(row)

    return disagreement_rows


def write_disagreements_csv(path: Path, rows: list[dict[str, Any]], runs: int) -> None:
    fieldnames = ["comment_id", "comment_text"]
    for run in range(1, runs + 1):
        fieldnames.extend(
            [
                f"run_{run}_friction_flag",
                f"run_{run}_fix_flag",
                f"run_{run}_issue_type",
                f"run_{run}_fix_type",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    require_api_key()

    comments_df = load_comments(args.comments)
    selected_comments = select_recipe_comments(
        comments_df=comments_df,
        recipe_id=args.recipe_id.strip(),
        max_comments=args.max_comments,
    )

    client = OpenAI()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_OUTPUT_PATH.open("w", encoding="utf-8"):
        pass

    raw_rows: list[dict[str, Any]] = []

    print(
        f"Running repeatability experiment for recipe_id={args.recipe_id} "
        f"on {len(selected_comments)} comments across {args.runs} runs.",
        flush=True,
    )

    for run_number in range(1, args.runs + 1):
        print(f"\nStarting run {run_number}/{args.runs}", flush=True)

        for index, (_, row) in enumerate(selected_comments.iterrows(), start=1):
            prompt_text = build_comment_prompt(row)
            parsed, raw_response, error, attempt_count = classify_comment_with_retry(
                client=client,
                prompt_text=prompt_text,
                model=args.model,
            )

            output_row = {
                "run_number": run_number,
                "comment_id": str(row["comment_id"]),
                "recipe_id": str(row["recipe_id"]),
                "comment_text": str(row["comment_text"]),
                "status": "ok" if parsed is not None else "error",
                "attempt_count": attempt_count,
                "model": args.model,
                "temperature": 0,
                "raw_model_response": raw_response,
                "parsed_json": parsed,
                "error": error,
            }
            raw_rows.append(output_row)
            append_jsonl_row(RAW_OUTPUT_PATH, output_row)

            print(
                f"  run={run_number} comment={index}/{len(selected_comments)} "
                f"comment_id={row['comment_id']} status={output_row['status']}",
                flush=True,
            )

            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    summary_rows = [aggregate_run(raw_rows, run_number) for run_number in range(1, args.runs + 1)]
    write_summary_csv(SUMMARY_OUTPUT_PATH, summary_rows)

    disagreement_rows = build_disagreement_rows(
        comments_df=selected_comments,
        raw_rows=raw_rows,
        runs=args.runs,
    )
    write_disagreements_csv(DISAGREEMENTS_OUTPUT_PATH, disagreement_rows, runs=args.runs)

    friction_counts = [row["friction_count"] for row in summary_rows]
    fix_counts = [row["fix_count"] for row in summary_rows]
    adaptation_counts = [row["adaptation_count"] for row in summary_rows]

    print("\nSaved outputs:")
    print(f"- Raw JSONL: {RAW_OUTPUT_PATH}")
    print(f"- Summary CSV: {SUMMARY_OUTPUT_PATH}")
    print(f"- Disagreements CSV: {DISAGREEMENTS_OUTPUT_PATH}")
    print("\nPer-run summary:")
    for row in summary_rows:
        print(
            f"  run={row['run_number']} total={row['total_comments']} "
            f"friction={row['friction_count']} fix={row['fix_count']} "
            f"adaptation={row['adaptation_count']} positive={row['positive_count']}",
            flush=True,
        )

    print("\nCross-run comparison:")
    print(f"- min friction_count: {min(friction_counts)}")
    print(f"- max friction_count: {max(friction_counts)}")
    print(f"- min fix_count: {min(fix_counts)}")
    print(f"- max fix_count: {max(fix_counts)}")
    print(f"- min adaptation_count: {min(adaptation_counts)}")
    print(f"- max adaptation_count: {max(adaptation_counts)}")
    print(f"- friction_count spread: {max(friction_counts) - min(friction_counts)}")
    print(f"- fix_count spread: {max(fix_counts) - min(fix_counts)}")
    print(f"- comment-level disagreement count: {len(disagreement_rows)}")


if __name__ == "__main__":
    main()
