from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from tqdm import tqdm


INPUT_PATH = Path("outputs/cleaned_comments.csv")
OUTPUT_PATH = Path("outputs/recipe_insights.csv")


class RecipeInsights(BaseModel):
    sentiment: str = Field(description="One of: positive, mixed, negative")
    complaints: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    substitutions: list[str] = Field(default_factory=list)
    would_make_again_signal: str = Field(
        description="One of: high, medium, low, unknown"
    )


def group_comments_by_recipe(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("recipe_id", as_index=False)
        .agg(
            comments=("comment_text", list),
            comment_count=("comment_text", "count"),
        )
    )
    return grouped


return f"""
Analyze these user comments for a single recipe and extract structured insights.

Recipe ID: {recipe_id}

Comments:
{comment_block}

Instructions:
- Focus only on repeated or meaningful patterns
- Do not include one-off opinions unless they are very strong and clearly actionable
- Do not invent details
- Keep outputs short and specific
- If there is not enough evidence, return empty lists
- If fewer than 2 comments support a complaint, improvement, or substitution, prefer excluding it
- If sentiment is unclear, use "unknown"
- If willingness to make again is unclear, use "unknown"

Field definitions:
- sentiment: one of ["positive", "mixed", "negative", "unknown"]
- complaints: repeated issues users mention
- improvements: practical suggestions, fixes, or tips from users
- substitutions: ingredient swaps explicitly mentioned by users
- would_make_again_signal:
- "high" = strong positive signal or explicit repeat intent
- "medium" = mixed but generally acceptable
- "low" = clearly negative experience
- "unknown" = not enough signal
""".strip()


def extract_insights_for_recipe(
    client: OpenAI, recipe_id: str, comments: list[str]
) -> dict:
    prompt = build_prompt(recipe_id, comments)

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": "You are a strict JSON generator. Always return valid JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "recipe_insights",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "sentiment": {"type": "string"},
                            "complaints": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "improvements": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "substitutions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "would_make_again_signal": {"type": "string"},
                        },
                        "required": [
                            "sentiment",
                            "complaints",
                            "improvements",
                            "substitutions",
                            "would_make_again_signal",
                        ],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        )
    except Exception as e:
        print(f"API request failed for recipe {recipe_id}: {e}")
        return {
            "sentiment": "unknown",
            "complaints": [],
            "improvements": [],
            "substitutions": [],
            "would_make_again_signal": "unknown",
        }

    try:
        parsed = json.loads(response.output_text)
        validated = RecipeInsights(**parsed)
        return validated.model_dump()
    except Exception as e:
        print(f"Failed parsing for recipe {recipe_id}: {e}")
        return {
            "sentiment": "unknown",
            "complaints": [],
            "improvements": [],
            "substitutions": [],
            "would_make_again_signal": "unknown",
        }


def main() -> None:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from .env")

    client = OpenAI(api_key=api_key)

    df = pd.read_csv(INPUT_PATH)
    grouped = group_comments_by_recipe(df)

    results = []

    sample_grouped = grouped[grouped["comment_count"] >= 3].head(20).copy()

    for _, row in tqdm(sample_grouped.iterrows(), total=len(sample_grouped)):
        recipe_id = row["recipe_id"]
        comments = row["comments"]

        insights = extract_insights_for_recipe(client, recipe_id, comments)

        results.append(
            {
                "recipe_id": recipe_id,
                "comment_count": row["comment_count"],
                **insights,
            }
        )

    result_df = pd.DataFrame(results)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Processed recipes: {len(result_df)}")
    print(f"Output written to: {OUTPUT_PATH}")
    print(result_df.head().to_string(index=False))


if __name__ == "__main__":
    main()
