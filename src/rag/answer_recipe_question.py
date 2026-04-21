#!/usr/bin/env python3
"""
Answer a recipe-specific question using retrieved RAG chunks.

Flow
- Load rag_corpus.jsonl
- Retrieve top-k chunks for a recipe/question
- Send compact grounded context to an LLM
- Return a structured answer with supporting chunk IDs

This script assumes retrieval quality is already decent enough to surface the
right evidence. The LLM is used for synthesis, not search.

Typical usage
python src/rag/answer_recipe_question.py \
  --recipe-id 669a6694ce501f7231beb7a9 \
  --query "what are users doing to fix the salt issue?" \
  --top-k 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


DEFAULT_CORPUS_PATH = "outputs/rag_corpus.jsonl"
DEFAULT_TOP_K = 3
DEFAULT_MODEL = "gpt-5.4"


SYSTEM_PROMPT = """
You are generating structured, grounded answers about recipe issues.

STRICT RULES:

1. main_issue
- You MUST use the canonical issue label from recipe_context.display_issue for main_issue when it exists.
- Do NOT paraphrase it.
- Do NOT expand it.
- Output it exactly.

2. user_fixes_seen
- Must be SHORT normalized actions.
- Examples:
  - "reduce salt"
  - "add acidity"
  - "add more sauce"
  - "boost flavor"
  - "adjust filling amount"
- Do NOT include long sentences.
- Do NOT copy full comments.
- Only include fixes directly supported by retrieved_chunks.

3. recommended_edit
- Use recipe_context.recommended_edit if it is supported by the retrieved evidence.
- If it is not supported, keep it short and grounded in retrieved_chunks.
- Must be a short editorial action, not a paragraph.

4. why_it_matters
- Briefly explain why this issue matters for the recipe.
- Keep it to one sentence.
- Ground it in retrieved evidence and recipe_context.

5. priority
- Output one of: "high", "medium", "low"
- For editorial queries:
  - use "high" when the issue is clearly supported and there are meaningful fix signals
  - use "medium" when there is some evidence but it is incomplete
  - use "low" when evidence is weak

6. answer
- Explain the issue briefly
- Summarize user fixes clearly
- For editorial queries, state what the editor should change first
- Be concise: 2 to 3 sentences max

7. grounding
- Do NOT introduce new issues or fixes not present in retrieved_chunks.
- supporting_chunk_ids must reference only chunks actually used in the answer.

OUTPUT FORMAT (STRICT JSON ONLY):

{
  "answer": "...",
  "main_issue": "...",
  "user_fixes_seen": ["...", "..."],
  "recommended_edit": "...",
  "why_it_matters": "...",
  "editor_takeaway": "...",
  "priority": "high|medium|low",
  "confidence": "high|medium|low",
  "supporting_chunk_ids": ["...", "..."]
}
"""


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonicalize_fix_text(text: str) -> List[str]:
    text_norm = normalize_text(text)
    themes: List[str] = []

    def add(theme: str) -> None:
        if theme not in themes:
            themes.append(theme)

    if any(
        x in text_norm
        for x in [
            "reduce salt",
            "less salt",
            "cut salt",
            "cut the salt",
            "use less salt",
            "reduce feta",
            "less feta",
            "reduce olives",
            "less olives",
        ]
    ):
        add("reduce salt")

    if any(
        x in text_norm
        for x in [
            "add acidity",
            "acid",
            "add lemon",
            "lemon juice",
            "added lemon",
            "lime juice",
            "vinegar",
            "squeeze of lemon",
        ]
    ):
        add("add acidity")

    if any(
        x in text_norm
        for x in [
            "more sauce",
            "double sauce",
            "double the sauce",
            "add more sauce",
            "double the pumpkin sauce",
            "pumpkin sauce",
        ]
    ):
        add("add more sauce")

    if any(
        x in text_norm
        for x in [
            "add water",
            "extra egg",
            "add egg",
            "reduce flour",
            "less flour",
            "increase moisture",
            "more moisture",
            "hydration",
            "add liquid",
            "more liquid",
            "add broth",
            "add oil",
            "add butter",
        ]
    ):
        add("increase moisture")

    if any(
        x in text_norm
        for x in [
            "adjust cook time",
            "cook less",
            "bake less",
            "shorter bake",
            "reduce baking time",
            "pull it earlier",
            "bake longer",
            "cook longer",
            "adjust bake time",
        ]
    ):
        add("adjust cook time")

    if any(
        x in text_norm
        for x in [
            "add seasoning",
            "more seasoning",
            "more flavor",
            "more flavour",
            "more salt",
            "add spices",
            "boost flavor",
            "increase seasoning",
            "increase spices",
        ]
    ):
        add("boost flavor")

    if any(
        x in text_norm
        for x in [
            "add aromatics",
            "more ginger",
            "increase ginger",
            "more lemongrass",
            "increase lemongrass",
            "more garlic",
            "more onion",
            "shallots",
            "aromatics",
        ]
    ):
        add("add aromatics")

    if any(
        x in text_norm
        for x in [
            "reduce sugar",
            "less sugar",
            "cut sugar",
            "use less sugar",
            "reduce sweetness",
        ]
    ):
        add("reduce sugar")

    if any(
        x in text_norm
        for x in [
            "add bitterness",
            "bitter",
            "dark chocolate",
            "swap chocolate",
            "more chocolate",
            "use chocolate",
            "coffee",
        ]
    ):
        add("add bitterness")

    if any(
        x in text_norm
        for x in [
            "adjust filling",
            "less filling",
            "more filling",
            "not enough filling",
            "too much filling",
            "adjust filling amount",
            "scale filling",
        ]
    ):
        add("adjust filling amount")

    if any(
        x in text_norm
        for x in [
            "different pan size",
            "deep dish",
            "deeper dish",
            "smaller pan",
            "larger pan",
            "match yield to pan",
            "use different pan",
        ]
    ):
        add("use different pan size")

    if any(
        x in text_norm
        for x in [
            "adjust custard",
            "improve setting",
            "not setting",
            "did not set",
            "curdled",
            "curdling",
            "fix filling ratio",
            "custard ratio",
            "adjust custard ratio",
        ]
    ):
        add("fix setting or custard ratio")

    if any(
        x in text_norm
        for x in [
            "adjust temperature",
            "lower oven",
            "higher oven",
            "water bath",
            "change method",
            "temperature",
        ]
    ):
        add("adjust temperature or method")

    return themes


def run_retrieval_script(
    recipe_id: str,
    query: str,
    corpus_path: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    script_path = Path(__file__).with_name("retrieve_recipe_evidence.py")
    cmd = [
        sys.executable,
        str(script_path),
        "--corpus",
        corpus_path,
        "--recipe-id",
        recipe_id,
        "--query",
        query,
        "--top-k",
        str(top_k),
        "--json",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Retrieval failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Retrieval script did not return valid JSON.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        ) from exc


def compact_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "chunk_type": chunk.get("chunk_type"),
        "evidence_type": chunk.get("evidence_type"),
        "score": chunk.get("score"),
        "text": chunk.get("text"),
        "display_issue": chunk.get("display_issue"),
        "recommended_edit": chunk.get("recommended_edit"),
        "why_it_matters": chunk.get("why_it_matters"),
    }


def infer_query_type(query: str) -> str:
    q = normalize_text(query)
    if "what should the editor change first" in q or "editor" in q:
        return "editorial"
    if "how are they adjusting" in q or "and how are they adjusting it" in q:
        return "mixed"
    if "what are users doing to fix" in q or "how are users fixing" in q or "reduce the sweetness" in q:
        return "fix"
    if "why are users saying" in q or "what are users saying about the filling quantity" in q:
        return "issue"
    return "unknown"


def build_prompt_payload(recipe_id: str, query: str, retrieved: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not retrieved:
        return {
            "recipe_id": recipe_id,
            "query": query,
            "query_type": infer_query_type(query),
            "recipe_context": {},
            "retrieved_chunks": [],
        }

    first = retrieved[0]
    recipe_context = {
        "recipe_id": recipe_id,
        "recipe_title": first.get("recipe_title"),
        "brand": first.get("brand"),
        "author": first.get("author"),
        "display_issue": first.get("display_issue"),
        "recommended_edit": first.get("recommended_edit"),
        "why_it_matters": first.get("why_it_matters"),
        "llm_editor_summary": first.get("llm_editor_summary"),
        "evidence_strength": first.get("evidence_strength"),
        "issue_confidence": first.get("issue_confidence"),
    }

    return {
        "recipe_id": recipe_id,
        "query": query,
        "query_type": infer_query_type(query),
        "recipe_context": recipe_context,
        "retrieved_chunks": [compact_chunk(chunk) for chunk in retrieved],
    }


def extract_normalized_fixes_from_chunks(retrieved: List[Dict[str, Any]]) -> List[str]:
    fixes: List[str] = []
    seen: Set[str] = set()

    for chunk in retrieved:
        evidence_type = str(chunk.get("evidence_type") or "")
        if evidence_type not in {"problem_solving_fix", "adaptation", "mixed", "recommended_edit"}:
            continue

        text = str(chunk.get("text") or "")
        recommended_edit = str(chunk.get("recommended_edit") or "")

        for source_text in [text, recommended_edit]:
            for theme in canonicalize_fix_text(source_text):
                if theme not in seen:
                    seen.add(theme)
                    fixes.append(theme)

    return fixes[:5]


def collect_supporting_ids(retrieved: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    ids: List[str] = []
    for chunk in retrieved[:limit]:
        chunk_id = str(chunk.get("chunk_id") or "")
        if chunk_id:
            ids.append(chunk_id)
    return ids


def derive_priority(retrieved: List[Dict[str, Any]], query_type: str) -> str:
    if not retrieved:
        return "low"

    issue_chunks = 0
    fix_chunks = 0
    decision_chunks = 0

    for chunk in retrieved:
        chunk_type = str(chunk.get("chunk_type") or "")
        evidence_type = str(chunk.get("evidence_type") or "")

        if chunk_type == "decision":
            decision_chunks += 1
        if evidence_type in {"issue", "mixed"}:
            issue_chunks += 1
        if evidence_type in {"problem_solving_fix", "adaptation", "mixed", "recommended_edit"}:
            fix_chunks += 1

    if query_type == "editorial":
        if issue_chunks >= 1 and fix_chunks >= 1:
            return "high"
        if issue_chunks >= 1 or decision_chunks >= 1:
            return "medium"
        return "low"

    if issue_chunks >= 1 and fix_chunks >= 1:
        return "high"
    if issue_chunks >= 1 or fix_chunks >= 1:
        return "medium"
    return "low"


def answer_without_llm(recipe_id: str, query: str, retrieved: List[Dict[str, Any]]) -> Dict[str, Any]:
    query_type = infer_query_type(query)

    if not retrieved:
        return {
            "answer": "There is not enough retrieved evidence to answer this question.",
            "main_issue": "unknown",
            "user_fixes_seen": [],
            "recommended_edit": "",
            "why_it_matters": "No grounded answer is available because retrieval returned no evidence.",
            "editor_takeaway": "No grounded answer available because retrieval returned no evidence.",
            "priority": "low",
            "confidence": "low",
            "supporting_chunk_ids": [],
        }

    top = retrieved[:3]
    supporting_ids = collect_supporting_ids(top)
    issue = str(top[0].get("display_issue") or "unknown")
    recommended_edit = str(top[0].get("recommended_edit") or "").strip()
    why_it_matters = str(top[0].get("why_it_matters") or "").strip()

    fixes = extract_normalized_fixes_from_chunks(top)
    priority = derive_priority(top, query_type)

    if query_type == "editorial":
        answer_parts = []
        if issue != "unknown":
            answer_parts.append(f"The main issue is {issue}.")
        if recommended_edit:
            answer_parts.append(f"The editor should change {recommended_edit} first.")
        elif fixes:
            answer_parts.append(f"Users are trying to address it by {', '.join(fixes[:2])}.")
        if why_it_matters:
            answer_parts.append(why_it_matters)
        answer = " ".join(answer_parts[:3]).strip()
    else:
        answer_parts = []
        if issue != "unknown":
            answer_parts.append(f"The main issue is {issue}.")
        if fixes:
            answer_parts.append(f"Users are mainly addressing it by {', '.join(fixes[:3])}.")
        elif recommended_edit:
            answer_parts.append(f"The clearest supported fix is {recommended_edit}.")
        answer = " ".join(answer_parts[:3]).strip()

    if not answer:
        answer = "There is limited evidence to answer this question."

    if not why_it_matters:
        if issue != "unknown":
            why_it_matters = f"This issue affects how successfully users can make the recipe as written."
        else:
            why_it_matters = "Evidence is limited, so the impact is unclear."

    editor_takeaway = recommended_edit or (fixes[0] if fixes else "Review supporting comments before making an edit.")
    confidence = "high" if len(supporting_ids) >= 3 else "medium" if len(supporting_ids) >= 2 else "low"

    return {
        "answer": answer,
        "main_issue": issue,
        "user_fixes_seen": fixes[:3],
        "recommended_edit": recommended_edit,
        "why_it_matters": why_it_matters,
        "editor_takeaway": editor_takeaway,
        "priority": priority,
        "confidence": confidence,
        "supporting_chunk_ids": supporting_ids,
    }


def call_openai_responses_api(model: str, system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses the OpenAI Python SDK if available in the user's environment.

    Expected environment:
    - OPENAI_API_KEY set
    - openai package installed
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed in this environment. Install it with `pip install openai`."
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        text={"format": {"type": "json_object"}},
    )

    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError(f"No output_text returned from model response: {response}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON output:\n{text}") from exc


def sanitize_answer(answer: Dict[str, Any], payload: Dict[str, Any], retrieved: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    recipe_context = payload.get("recipe_context", {}) or {}
    canonical_issue = str(recipe_context.get("display_issue") or "unknown").strip()
    default_recommended_edit = str(recipe_context.get("recommended_edit") or "").strip()
    default_why_it_matters = str(recipe_context.get("why_it_matters") or "").strip()
    default_confidence = str(recipe_context.get("issue_confidence") or "low").strip() or "low"
    query_type = str(payload.get("query_type") or "unknown")

    if not isinstance(answer, dict):
        raise ValueError(f"Expected dict JSON from model, got: {type(answer)}")

    answer_text = str(answer.get("answer") or "").strip()
    main_issue = str(answer.get("main_issue") or "").strip()
    recommended_edit = str(answer.get("recommended_edit") or "").strip()
    why_it_matters = str(answer.get("why_it_matters") or "").strip()
    editor_takeaway = str(answer.get("editor_takeaway") or "").strip()
    priority = str(answer.get("priority") or "").strip().lower()
    confidence = str(answer.get("confidence") or "").strip().lower()
    supporting_chunk_ids = [str(x) for x in (answer.get("supporting_chunk_ids") or []) if x]
    user_fixes_seen_raw = answer.get("user_fixes_seen") or []

    valid_chunk_ids = {str(chunk.get("chunk_id")) for chunk in retrieved[:top_k] if chunk.get("chunk_id")}
    supporting_chunk_ids = [chunk_id for chunk_id in supporting_chunk_ids if chunk_id in valid_chunk_ids]
    if not supporting_chunk_ids:
        supporting_chunk_ids = collect_supporting_ids(retrieved, limit=top_k)

    normalized_fixes: List[str] = []
    seen_fixes: Set[str] = set()

    for item in user_fixes_seen_raw:
        for theme in canonicalize_fix_text(str(item)):
            if theme not in seen_fixes:
                seen_fixes.add(theme)
                normalized_fixes.append(theme)

    if not normalized_fixes:
        normalized_fixes = extract_normalized_fixes_from_chunks(retrieved)

    if canonical_issue:
        main_issue = canonical_issue

    if not recommended_edit:
        recommended_edit = default_recommended_edit

    if not why_it_matters:
        why_it_matters = default_why_it_matters

    if not editor_takeaway:
        editor_takeaway = recommended_edit or (normalized_fixes[0] if normalized_fixes else "")

    if priority not in {"high", "medium", "low"}:
        priority = derive_priority(retrieved, query_type)

    if confidence not in {"high", "medium", "low"}:
        confidence = default_confidence if default_confidence in {"high", "medium", "low"} else "low"

    if not answer_text:
        fallback = answer_without_llm(
            recipe_id=str(payload.get("recipe_id") or ""),
            query=str(payload.get("query") or ""),
            retrieved=retrieved,
        )
        answer_text = str(fallback.get("answer") or "")

    return {
        "answer": answer_text,
        "main_issue": main_issue or "unknown",
        "user_fixes_seen": normalized_fixes[:5],
        "recommended_edit": recommended_edit,
        "why_it_matters": why_it_matters,
        "editor_takeaway": editor_takeaway,
        "priority": priority,
        "confidence": confidence,
        "supporting_chunk_ids": supporting_chunk_ids,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Answer a recipe-specific question using retrieved RAG chunks")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_PATH, help="Path to rag_corpus.jsonl")
    parser.add_argument("--recipe-id", required=True, help="Recipe ID to search within")
    parser.add_argument("--query", required=True, help="Question to answer")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Number of retrieved chunks to use")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model name")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM call and return a deterministic fallback answer",
    )
    parser.add_argument(
        "--show-payload",
        action="store_true",
        help="Print the retrieval payload sent to the LLM",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    retrieved = run_retrieval_script(
        recipe_id=args.recipe_id,
        query=args.query,
        corpus_path=args.corpus,
        top_k=args.top_k,
    )

    payload = build_prompt_payload(
        recipe_id=args.recipe_id,
        query=args.query,
        retrieved=retrieved,
    )

    if args.show_payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.no_llm:
        answer = answer_without_llm(args.recipe_id, args.query, retrieved)
    else:
        raw_answer = call_openai_responses_api(
            model=args.model,
            system_prompt=SYSTEM_PROMPT,
            payload=payload,
        )
        answer = sanitize_answer(
            answer=raw_answer,
            payload=payload,
            retrieved=retrieved,
            top_k=args.top_k,
        )

    output = {
        "recipe_id": args.recipe_id,
        "query": args.query,
        "query_type": payload.get("query_type"),
        "model": None if args.no_llm else args.model,
        "retrieved_count": len(retrieved),
        "answer": answer,
        "retrieved_chunks": [compact_chunk(chunk) for chunk in retrieved],
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()