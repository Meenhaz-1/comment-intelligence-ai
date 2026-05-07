from __future__ import annotations

import argparse
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


COMMENTS_PATH = Path("outputs/cleaned_comments.csv")
RECIPE_MASTER_PATH = Path("data/recipe_master.csv")
OUTPUT_PATH = Path("outputs/experiments/naive_llm_comment_analysis.jsonl")

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_SAMPLE_SIZE = 10
DEFAULT_MIN_COMMENTS = 5
DEFAULT_MAX_COMMENTS_PER_RECIPE = 50
DEFAULT_MAX_RETRIES = 1
DEFAULT_SLEEP_SECONDS = 0.75


JSON_SCHEMA: dict[str, Any] = {
    "name": "naive_llm_comment_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recipe_id": {"type": "string"},
            "recipe_title": {"type": "string"},
            "main_friction_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "friction": {"type": "string"},
                        "description": {"type": "string"},
                        "supporting_snippets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "comment_id": {"type": "string"},
                                    "snippet": {"type": "string"},
                                    "why_this_supports_the_friction": {"type": "string"},
                                },
                                "required": [
                                    "comment_id",
                                    "snippet",
                                    "why_this_supports_the_friction",
                                ],
                            },
                        },
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": [
                        "friction",
                        "description",
                        "supporting_snippets",
                        "confidence",
                    ],
                },
            },
            "suggested_fixes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "fix": {"type": "string"},
                        "linked_friction": {"type": "string"},
                        "supporting_snippets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "comment_id": {"type": "string"},
                                    "snippet": {"type": "string"},
                                    "why_this_supports_the_fix": {"type": "string"},
                                },
                                "required": [
                                    "comment_id",
                                    "snippet",
                                    "why_this_supports_the_fix",
                                ],
                            },
                        },
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": [
                        "fix",
                        "linked_friction",
                        "supporting_snippets",
                        "confidence",
                    ],
                },
            },
            "overall_summary": {"type": "string"},
            "uncertainty_notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "recipe_id",
            "recipe_title",
            "main_friction_points",
            "suggested_fixes",
            "overall_summary",
            "uncertainty_notes",
        ],
    },
}


SYSTEM_PROMPT = """
You are running a narrow recipe-comment analysis experiment.

You are given comments for exactly one recipe. Your job is to identify:
1. Main friction points
2. Suggested fixes explicitly supported by comments
3. Exact supporting comment snippets
4. Confidence level
5. Uncertainty or missing evidence

Critical rules:
- Return JSON only.
- Follow the schema exactly.
- Supporting snippets must be exact substrings copied from the provided comments.
- Do not invent or paraphrase snippets.
- Do not infer a fix unless at least one comment explicitly supports it.
- If evidence is weak, say so in uncertainty_notes and use lower confidence.
- Separate recipe issues from app/site/product issues.
- Separate neutral adaptations from problem-solving fixes.
- Prefer precision over recall.
- Return empty arrays when there is no clear friction or no clear fix.
- Keep friction labels short and normalized.
- Keep fixes short and actionable.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Naive LLM-only recipe comment analysis experiment.")
    parser.add_argument("--comments", type=Path, default=COMMENTS_PATH)
    parser.add_argument("--recipe-master", type=Path, default=RECIPE_MASTER_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--min-comments", type=int, default=DEFAULT_MIN_COMMENTS)
    parser.add_argument("--max-comments-per-recipe", type=int, default=DEFAULT_MAX_COMMENTS_PER_RECIPE)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--recipe-ids", nargs="*", default=None)
    return parser.parse_args()


def require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)


def load_comments(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing comments input: {path}")

    df = pd.read_csv(path, low_memory=False)

    required = {"recipe_id", "comment_text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required comment columns in {path}: {sorted(missing)}")

    df = df.copy()
    df["recipe_id"] = df["recipe_id"].astype(str).str.strip()
    df["comment_text"] = df["comment_text"].fillna("").astype(str).str.strip()
    df = df[(df["recipe_id"] != "") & (df["comment_text"] != "")].copy()

    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    else:
        df["created_at"] = pd.NaT

    # Provide stable comment ids for the experiment even if the source file has none.
    df = df.reset_index(drop=True)
    df["comment_id"] = df.index.map(lambda idx: f"comment_{idx + 1}")
    return df


def load_recipe_titles(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    df = pd.read_csv(path, low_memory=False)
    if "content_id" not in df.columns or "title" not in df.columns:
        return {}

    work = df.copy()
    work["content_id"] = work["content_id"].astype(str).str.strip()
    work["title"] = work["title"].fillna("").astype(str).str.strip()
    work = work[(work["content_id"] != "") & (work["title"] != "")]
    return dict(zip(work["content_id"], work["title"]))


def select_recipe_groups(
    comments_df: pd.DataFrame,
    sample_size: int,
    min_comments: int,
    recipe_ids: list[str] | None,
) -> list[tuple[str, pd.DataFrame]]:
    if recipe_ids:
        wanted = {recipe_id.strip() for recipe_id in recipe_ids if recipe_id.strip()}
        filtered = comments_df[comments_df["recipe_id"].isin(wanted)].copy()
    else:
        filtered = comments_df.copy()

    groups: list[tuple[str, pd.DataFrame]] = []
    for recipe_id, group in filtered.groupby("recipe_id", sort=True):
        if len(group) < min_comments:
            continue
        groups.append((recipe_id, group.copy()))

    return groups[:sample_size]


def build_recipe_prompt(
    recipe_id: str,
    recipe_title: str,
    comments_df: pd.DataFrame,
    max_comments_per_recipe: int,
) -> tuple[str, int]:
    work = comments_df.copy()
    work = work.sort_values(by="created_at", ascending=False, na_position="last")
    selected = work.head(max_comments_per_recipe).copy()

    comment_lines: list[str] = []
    for _, row in selected.iterrows():
        created_at = row["created_at"]
        created_text = ""
        if pd.notna(created_at):
            created_text = pd.Timestamp(created_at).strftime("%Y-%m-%d")

        comment_lines.append(
            json.dumps(
                {
                    "comment_id": str(row["comment_id"]),
                    "created_at": created_text,
                    "comment_text": str(row["comment_text"]),
                },
                ensure_ascii=False,
            )
        )

    user_payload = {
        "recipe_id": recipe_id,
        "recipe_title": recipe_title,
        "instructions": {
            "focus": [
                "main friction points",
                "suggested fixes explicitly supported by comments",
                "exact supporting snippets",
                "confidence",
                "uncertainty",
            ],
            "ignore": [
                "app issues",
                "site issues",
                "subscription issues",
                "product complaints unrelated to the recipe itself",
            ],
        },
        "comments": [json.loads(line) for line in comment_lines],
    }
    return json.dumps(user_payload, ensure_ascii=False, indent=2), len(selected)


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

    try:
        response_dict = response.model_dump()
    except Exception:
        return ""

    body_output = response_dict.get("output", [])
    if isinstance(body_output, list):
        chunks = []
        for item in body_output:
            for part in item.get("content", []):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        if chunks:
            return "\n".join(chunks)

    return ""


def analyze_recipe_once(
    client: OpenAI,
    recipe_id: str,
    recipe_title: str,
    prompt_text: str,
    model: str,
) -> tuple[dict[str, Any], str]:
    response = client.responses.create(
        model=model,
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
        raise ValueError(f"No output text returned for recipe_id={recipe_id}")

    parsed = json.loads(raw_text)
    parsed["recipe_id"] = recipe_id
    if not parsed.get("recipe_title"):
        parsed["recipe_title"] = recipe_title

    return parsed, raw_text


def analyze_recipe_with_retry(
    client: OpenAI,
    recipe_id: str,
    recipe_title: str,
    prompt_text: str,
    model: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    attempt = 0
    last_error = ""

    while attempt <= max_retries:
        attempt += 1
        try:
            parsed, raw_text = analyze_recipe_once(
                client=client,
                recipe_id=recipe_id,
                recipe_title=recipe_title,
                prompt_text=prompt_text,
                model=model,
            )
            return {
                "recipe_id": recipe_id,
                "recipe_title": recipe_title,
                "status": "ok",
                "attempt_count": attempt,
                "raw_model_response": raw_text,
                "parsed_json": parsed,
                "error": None,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt > max_retries:
                break

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe_title,
        "status": "error",
        "attempt_count": attempt,
        "raw_model_response": None,
        "parsed_json": None,
        "error": last_error,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    require_api_key()

    comments_df = load_comments(args.comments)
    recipe_titles = load_recipe_titles(args.recipe_master)
    recipe_groups = select_recipe_groups(
        comments_df=comments_df,
        sample_size=args.sample_size,
        min_comments=args.min_comments,
        recipe_ids=args.recipe_ids,
    )

    if not recipe_groups:
        print("No recipes met the selection criteria.")
        return

    client = OpenAI()
    rows: list[dict[str, Any]] = []

    # Start fresh for each run so partial outputs are still usable if the job stops early.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8"):
        pass

    for index, (recipe_id, group) in enumerate(recipe_groups, start=1):
        recipe_title = recipe_titles.get(recipe_id, "")
        prompt_text, comments_used = build_recipe_prompt(
            recipe_id=recipe_id,
            recipe_title=recipe_title,
            comments_df=group,
            max_comments_per_recipe=args.max_comments_per_recipe,
        )

        result = analyze_recipe_with_retry(
            client=client,
            recipe_id=recipe_id,
            recipe_title=recipe_title,
            prompt_text=prompt_text,
            model=args.model,
        )
        result["comment_count_total"] = int(len(group))
        result["comment_count_used"] = int(comments_used)
        result["model"] = args.model
        result["prompt_text"] = prompt_text
        rows.append(result)
        append_jsonl_row(args.output, result)

        print(
            f"[{index}/{len(recipe_groups)}] recipe_id={recipe_id} "
            f"status={result['status']} comments_used={comments_used}",
            flush=True,
        )
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    processed = len(rows)
    friction_found = sum(
        1
        for row in rows
        if row.get("parsed_json", {}).get("main_friction_points")
    )
    fixes_found = sum(
        1
        for row in rows
        if row.get("parsed_json", {}).get("suggested_fixes")
    )
    no_clear_evidence = sum(
        1
        for row in rows
        if row.get("status") == "ok"
        and not row.get("parsed_json", {}).get("main_friction_points")
        and not row.get("parsed_json", {}).get("suggested_fixes")
    )

    print()
    print(f"Saved {processed:,} rows to {args.output}")
    print(f"Recipes processed: {processed:,}")
    print(f"Recipes with friction found: {friction_found:,}")
    print(f"Recipes with fixes found: {fixes_found:,}")
    print(f"Recipes with no clear evidence: {no_clear_evidence:,}")


if __name__ == "__main__":
    main()
