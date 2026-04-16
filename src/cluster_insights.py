from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT_DIR / "outputs" / "recipe_insights.csv"
OUTPUT_DIR = ROOT_DIR / "outputs"


def parse_list(value):
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        return []
    return []


def get_all_items(df: pd.DataFrame, column: str) -> list[str]:
    items = []
    for val in df[column]:
        items.extend(parse_list(val))
    return clean_items([item for item in items if item])


def cluster_items(client: OpenAI, items: list[str], label: str) -> list[dict]:
    unique_items = list(set(items))

    if len(unique_items) == 0:
        return []

    prompt = f"""
Group these {label} into a small set of normalized themes.

Items:
{chr(10).join(unique_items)}

Rules:
- Merge semantically similar items into one theme
- Theme names must be short, concrete, and reusable
- Avoid vague labels like "recipe issues", "flavor adjustments", or "other"
- Prefer labels like:
- too salty
- unclear instructions
- ingredient confusion
- long cook time
- texture too dense
- substitution: protein
- Do not create duplicate or overlapping themes
- Do not include "none mentioned"
- Return valid JSON only in this format:
[
{{
    "theme": "too salty",
    "items": ["too salty", "olives stewed in the dish can make it too salty"]
}}
]
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
    except Exception as e:
        print(f"API request failed while clustering {label}: {e}")
        return []

    try:
        parsed = json.loads(response.output_text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def clean_items(items: list[str]) -> list[str]:
    bad_exact = {"none mentioned", "none", "n/a", "na"}
    cleaned = []

    for item in items:
        text = str(item).strip()
        lower = text.lower()

        if not text:
            continue
        if lower in bad_exact:
            continue
        if "not repeated" in lower:
            continue

        cleaned.append(text)

    return cleaned

def main():
    load_dotenv()
    client = OpenAI()

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Could not find input file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    for column in ["complaints", "improvements", "substitutions"]:
        items = get_all_items(df, column)

        print(f"\n--- Clustering {column} ---")

        clusters = cluster_items(client, items, column)

        rows = []
        for cluster in clusters:
            theme = cluster.get("theme", "").strip()
            cluster_items_list = cluster.get("items", [])

            if not theme or not isinstance(cluster_items_list, list):
                continue

            rows.append(
                {
                    "category": column,
                    "theme": theme,
                    "count": len(cluster_items_list),
                    "items": " | ".join(cluster_items_list),
                }
            )

        cluster_df = pd.DataFrame(rows, columns=["category", "theme", "count", "items"])
        if not cluster_df.empty:
            cluster_df = cluster_df.sort_values(by="count", ascending=False)

        print(cluster_df.to_string(index=False))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"{column}_themes.csv"
        cluster_df.to_csv(output_path, index=False)
        print(f"\nSaved: {output_path}")

if __name__ == "__main__":
    main()
