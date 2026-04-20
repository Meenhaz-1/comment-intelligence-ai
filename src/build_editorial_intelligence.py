import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

# Update this if your canonical recipe-level table has a different name.
MAIN_INPUT_PATH = BASE_DIR / "outputs" / "recipe_intelligence.csv"
EVIDENCE_INPUT_PATH = BASE_DIR / "outputs" / "recipe_evidence.csv"

OUTPUT_CSV_PATH = BASE_DIR / "outputs" / "editorial_intelligence.csv"
OUTPUT_JSONL_PATH = BASE_DIR / "outputs" / "editorial_intelligence.jsonl"


def safe_get(row: pd.Series, col: str, default: Any = None) -> Any:
    return row[col] if col in row.index and pd.notna(row[col]) else default


def parse_json_list(value: Any) -> List[Any]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def clean_scalar(value: Any) -> Optional[Any]:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return value


def normalize_tags(value: Any) -> List[str]:
    if pd.isna(value):
        return []

    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    text = str(value).strip()
    if not text:
        return []

    # Handle pipe-delimited tags first, then comma fallback
    if "|" in text:
        parts = text.split("|")
    elif "," in text:
        parts = text.split(",")
    else:
        parts = [text]

    return [part.strip() for part in parts if part.strip()]


def to_float(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def to_int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(value)
    except Exception:
        return default


def bucket_level(
    value: Optional[float],
    low_cutoff: float,
    high_cutoff: float,
) -> str:
    if value is None:
        return "unknown"
    if value < low_cutoff:
        return "low"
    if value < high_cutoff:
        return "medium"
    return "high"


def compute_engagement_value(row: pd.Series) -> Optional[float]:
    total_comments = to_float(safe_get(row, "total_comments"))
    total_save_sessions = to_float(safe_get(row, "total_save_sessions"))
    save_sessions_app = to_float(safe_get(row, "save_sessions_app"))
    save_sessions_web = to_float(safe_get(row, "save_sessions_web"))

    if total_save_sessions is not None:
        return total_save_sessions
    if save_sessions_app is not None or save_sessions_web is not None:
        return (save_sessions_app or 0.0) + (save_sessions_web or 0.0)
    if total_comments is not None:
        return total_comments
    return None


def compute_engagement_type(row: pd.Series) -> str:
    if pd.notna(safe_get(row, "total_save_sessions")):
        return "saves"
    if pd.notna(safe_get(row, "save_sessions_app")) or pd.notna(safe_get(row, "save_sessions_web")):
        return "blended"
    if pd.notna(safe_get(row, "total_comments")):
        return "comments"
    return "none"


def compute_engagement_level(value: Optional[float], engagement_type: str) -> str:
    if value is None:
        return "unknown"

    # Slightly different cutoffs depending on proxy type
    if engagement_type in {"saves", "blended"}:
        return bucket_level(value, low_cutoff=5, high_cutoff=20)

    # comments
    return bucket_level(value, low_cutoff=5, high_cutoff=20)


def compute_friction_level(value: Optional[float]) -> str:
    return bucket_level(value, low_cutoff=0.10, high_cutoff=0.25)


def compute_recoverability_level(value: Optional[float]) -> str:
    return bucket_level(value, low_cutoff=0.05, high_cutoff=0.15)


def compute_repeat_intent_level(value: Optional[float]) -> str:
    return bucket_level(value, low_cutoff=0.10, high_cutoff=0.30)


def compute_evidence_strength(total_selected_evidence_comments: int) -> str:
    if total_selected_evidence_comments <= 0:
        return "none"
    if total_selected_evidence_comments == 1:
        return "low"
    if total_selected_evidence_comments <= 3:
        return "medium"
    return "high"


def build_llm_readiness(
    has_issue_evidence: bool,
    has_fix_evidence: bool,
    has_mixed_evidence: bool,
    total_selected_evidence_comments: int,
) -> Dict[str, Any]:
    llm_ready_for_summary = has_issue_evidence or has_fix_evidence or has_mixed_evidence
    llm_ready_for_rag = total_selected_evidence_comments >= 2
    evidence_strength = compute_evidence_strength(total_selected_evidence_comments)

    return {
        "llm_ready_for_summary": llm_ready_for_summary,
        "llm_ready_for_rag": llm_ready_for_rag,
        "evidence_strength": evidence_strength,
    }


def build_metadata(row: pd.Series) -> Dict[str, Any]:
    return {
        "title": clean_scalar(safe_get(row, "title")),
        "author": clean_scalar(safe_get(row, "author_name", safe_get(row, "author"))),
        "brand": clean_scalar(safe_get(row, "brand")),
        "tags": normalize_tags(safe_get(row, "tags")),
        "url": clean_scalar(safe_get(row, "url")),
    }


def build_decision(row: pd.Series) -> Dict[str, Any]:
    return {
        "classification": clean_scalar(
            safe_get(row, "classification", safe_get(row, "priority"))
        ),
        "opportunity_score": to_float(safe_get(row, "opportunity_score")),
        "issue": {
            "display_issue": clean_scalar(
                safe_get(row, "display_issue", safe_get(row, "top_normalized_issue"))
            ),
            "issue_family": clean_scalar(
                safe_get(row, "top_issue_family", safe_get(row, "issue_family"))
            ),
            "top_issue_phrase": clean_scalar(
                safe_get(row, "top_issue_phrase", safe_get(row, "top_friction_phrase"))
            ),
            "secondary_issue_phrase": clean_scalar(
                safe_get(row, "secondary_issue_phrase")
            ),
            "issue_source": clean_scalar(
                safe_get(row, "issue_source", "none")
            ),
            "issue_confidence": clean_scalar(
                safe_get(row, "issue_confidence", "none")
            ),
            "display_issue_reason": clean_scalar(
                safe_get(row, "display_issue_reason")
            ),
            "display_issue_action_state": clean_scalar(
                safe_get(row, "display_issue_action_state", "no_issue")
            ),
        },
        "recommended_edit": clean_scalar(safe_get(row, "recommended_edit")),
        "why_it_matters": clean_scalar(safe_get(row, "why_it_matters")),
    }


def build_signals(row: pd.Series) -> Dict[str, Any]:
    total_comments = to_int(safe_get(row, "total_comments"), default=0)
    eligible_comments = to_int(safe_get(row, "eligible_comments"), default=0)

    pct_friction = to_float(safe_get(row, "pct_friction"))
    if pct_friction is None:
        pct_friction = to_float(safe_get(row, "friction_score"))

    pct_modification = to_float(safe_get(row, "pct_modification"))
    if pct_modification is None:
        pct_modification = to_float(safe_get(row, "recoverability_score"))

    pct_repeat_intent = to_float(safe_get(row, "pct_repeat_intent"))

    engagement_proxy_value = compute_engagement_value(row)
    engagement_proxy_type = compute_engagement_type(row)
    engagement_level = compute_engagement_level(engagement_proxy_value, engagement_proxy_type)

    return {
        "total_comments": total_comments,
        "eligible_comments": eligible_comments,
        "pct_friction": pct_friction,
        "friction_level": compute_friction_level(pct_friction),
        "pct_modification": pct_modification,
        "recoverability_level": compute_recoverability_level(pct_modification),
        "pct_repeat_intent": pct_repeat_intent,
        "repeat_intent_level": compute_repeat_intent_level(pct_repeat_intent),
        "engagement_proxy_value": engagement_proxy_value,
        "engagement_proxy_type": engagement_proxy_type,
        "engagement_level": engagement_level,
    }


def build_evidence(row: pd.Series) -> Dict[str, Any]:
    issue_evidence_comments = parse_json_list(safe_get(row, "issue_evidence_comments", "[]"))
    fix_evidence_comments = parse_json_list(safe_get(row, "fix_evidence_comments", "[]"))
    mixed_evidence_comments = parse_json_list(safe_get(row, "mixed_evidence_comments", "[]"))
    adaptation_comments = parse_json_list(safe_get(row, "adaptation_comments", "[]"))

    has_issue_evidence = bool(to_int(safe_get(row, "has_issue_evidence"), default=0))
    has_fix_evidence = bool(to_int(safe_get(row, "has_fix_evidence"), default=0))
    has_mixed_evidence = bool(to_int(safe_get(row, "has_mixed_evidence"), default=0))
    total_selected_evidence_comments = to_int(
        safe_get(row, "total_selected_evidence_comments"),
        default=len(issue_evidence_comments)
        + len(fix_evidence_comments)
        + len(mixed_evidence_comments)
        + len(adaptation_comments),
    )

    return {
        "issue_evidence_comments": issue_evidence_comments,
        "fix_evidence_comments": fix_evidence_comments,
        "mixed_evidence_comments": mixed_evidence_comments,
        "adaptation_comments": adaptation_comments,
        "has_issue_evidence": has_issue_evidence,
        "has_fix_evidence": has_fix_evidence,
        "has_mixed_evidence": has_mixed_evidence,
        "total_selected_evidence_comments": total_selected_evidence_comments,
    }


def build_llm_input(metadata: Dict[str, Any], decision: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, str]:
    title = metadata.get("title") or "Unknown recipe"
    brand = metadata.get("brand") or "unknown brand"
    classification = decision.get("classification") or "Unknown"
    issue = decision.get("issue", {}).get("display_issue") or "Unclear issue"
    recommended_edit = decision.get("recommended_edit") or "No recommended edit available"
    why_it_matters = decision.get("why_it_matters") or "No explanation available"

    friction_level = signals.get("friction_level", "unknown")
    recoverability_level = signals.get("recoverability_level", "unknown")
    engagement_level = signals.get("engagement_level", "unknown")

    return {
        "editorial_context": (
            f"{title} ({brand}) is classified as {classification}. "
            f"Main issue: {issue}. Recommended edit: {recommended_edit}."
        ),
        "reasoning_summary": (
            f"Why it matters: {why_it_matters} "
            f"Friction is {friction_level}, recoverability is {recoverability_level}, "
            f"and engagement is {engagement_level}."
        ),
    }


def flatten_for_csv(
    recipe_id: str,
    metadata: Dict[str, Any],
    decision: Dict[str, Any],
    signals: Dict[str, Any],
    evidence: Dict[str, Any],
    llm_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    issue_block = decision.get("issue", {})

    return {
        "recipe_id": recipe_id,
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "brand": metadata.get("brand"),
        "tags": json.dumps(metadata.get("tags", []), ensure_ascii=False),
        "url": metadata.get("url"),
        "classification": decision.get("classification"),
        "opportunity_score": decision.get("opportunity_score"),
        "display_issue": issue_block.get("display_issue"),
        "issue_family": issue_block.get("issue_family"),
        "top_issue_phrase": issue_block.get("top_issue_phrase"),
        "secondary_issue_phrase": issue_block.get("secondary_issue_phrase"),
        "issue_source": issue_block.get("issue_source"),
        "issue_confidence": issue_block.get("issue_confidence"),
        "display_issue_reason": issue_block.get("display_issue_reason"),
        "display_issue_action_state": issue_block.get("display_issue_action_state"),
        "recommended_edit": decision.get("recommended_edit"),
        "why_it_matters": decision.get("why_it_matters"),
        "total_comments": signals.get("total_comments"),
        "eligible_comments": signals.get("eligible_comments"),
        "pct_friction": signals.get("pct_friction"),
        "friction_level": signals.get("friction_level"),
        "pct_modification": signals.get("pct_modification"),
        "recoverability_level": signals.get("recoverability_level"),
        "pct_repeat_intent": signals.get("pct_repeat_intent"),
        "repeat_intent_level": signals.get("repeat_intent_level"),
        "engagement_proxy_value": signals.get("engagement_proxy_value"),
        "engagement_proxy_type": signals.get("engagement_proxy_type"),
        "engagement_level": signals.get("engagement_level"),
        "issue_evidence_comments": json.dumps(evidence.get("issue_evidence_comments", []), ensure_ascii=False),
        "fix_evidence_comments": json.dumps(evidence.get("fix_evidence_comments", []), ensure_ascii=False),
        "mixed_evidence_comments": json.dumps(evidence.get("mixed_evidence_comments", []), ensure_ascii=False),
        "adaptation_comments": json.dumps(evidence.get("adaptation_comments", []), ensure_ascii=False),
        "has_issue_evidence": int(evidence.get("has_issue_evidence", False)),
        "has_fix_evidence": int(evidence.get("has_fix_evidence", False)),
        "has_mixed_evidence": int(evidence.get("has_mixed_evidence", False)),
        "total_selected_evidence_comments": evidence.get("total_selected_evidence_comments", 0),
        "llm_ready_for_summary": int(llm_readiness.get("llm_ready_for_summary", False)),
        "llm_ready_for_rag": int(llm_readiness.get("llm_ready_for_rag", False)),
        "evidence_strength": llm_readiness.get("evidence_strength"),
    }


def main():
    main_df = pd.read_csv(MAIN_INPUT_PATH, low_memory=False)
    evidence_df = pd.read_csv(EVIDENCE_INPUT_PATH, low_memory=False)

    if "recipe_id" not in main_df.columns:
        if "content_id" in main_df.columns:
            main_df = main_df.rename(columns={"content_id": "recipe_id"})
        else:
            raise ValueError(f"{MAIN_INPUT_PATH} must contain either 'recipe_id' or 'content_id'.")

    if "recipe_id" not in evidence_df.columns:
        raise ValueError(f"{EVIDENCE_INPUT_PATH} must contain 'recipe_id'.")

    merged = main_df.merge(evidence_df, on="recipe_id", how="left")

    csv_rows: List[Dict[str, Any]] = []

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as f:
        for _, row in merged.iterrows():
            recipe_id = clean_scalar(safe_get(row, "recipe_id"))
            if recipe_id is None:
                continue

            metadata = build_metadata(row)
            decision = build_decision(row)
            signals = build_signals(row)
            evidence = build_evidence(row)

            llm_readiness = build_llm_readiness(
                has_issue_evidence=evidence["has_issue_evidence"],
                has_fix_evidence=evidence["has_fix_evidence"],
                has_mixed_evidence=evidence["has_mixed_evidence"],
                total_selected_evidence_comments=evidence["total_selected_evidence_comments"],
            )

            llm_input = build_llm_input(metadata, decision, signals)

            obj = {
                "recipe_id": recipe_id,
                "version": "editorial_intelligence_v1",
                "metadata": metadata,
                "decision": decision,
                "signals": signals,
                "evidence": evidence,
                "llm_readiness": llm_readiness,
                "llm_input": llm_input,
            }

            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

            csv_rows.append(
                flatten_for_csv(
                    recipe_id=recipe_id,
                    metadata=metadata,
                    decision=decision,
                    signals=signals,
                    evidence=evidence,
                    llm_readiness=llm_readiness,
                )
            )

    out_df = pd.DataFrame(csv_rows).sort_values("recipe_id").reset_index(drop=True)
    out_df.to_csv(OUTPUT_CSV_PATH, index=False)

    print(f"Saved {len(out_df):,} rows to {OUTPUT_CSV_PATH}")
    print(f"Saved JSONL to {OUTPUT_JSONL_PATH}")

    print("\nLLM readiness summary:")
    print(f"Ready for summary: {int(out_df['llm_ready_for_summary'].sum()):,}")
    print(f"Ready for RAG: {int(out_df['llm_ready_for_rag'].sum()):,}")

    print("\nEvidence strength distribution:")
    print(out_df["evidence_strength"].value_counts(dropna=False))


if __name__ == "__main__":
    main()