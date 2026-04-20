import json
from pathlib import Path
from typing import Optional, List, Dict

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "outputs" / "evidence_candidates.csv"
OUTPUT_CSV_PATH = BASE_DIR / "outputs" / "recipe_evidence.csv"
OUTPUT_JSONL_PATH = BASE_DIR / "outputs" / "recipe_evidence.jsonl"

MAX_ISSUE = 2
MAX_FIX = 2
MAX_MIXED = 1
MAX_ADAPTATION = 1


def clean_text(value: str) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def select_top(df: pd.DataFrame, evidence_type: str, max_n: int) -> pd.DataFrame:
    subset = df[df["evidence_type"] == evidence_type].copy()
    if subset.empty:
        return subset

    subset = subset.sort_values(
        by=["evidence_score", "rank_within_recipe_type"],
        ascending=[False, True],
    )
    return subset.head(max_n).copy()


def build_comment_records(df_subset: pd.DataFrame) -> List[Dict]:
    records = []
    seen = set()

    for _, row in df_subset.iterrows():
        comment_text = clean_text(row.get("trimmed_comment"))
        if not comment_text:
            continue

        dedupe_key = comment_text.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        record = {
            "comment_text": comment_text,
            "evidence_score": float(row["evidence_score"]) if pd.notna(row["evidence_score"]) else None,
        }

        if "comment_id" in df_subset.columns:
            comment_id = clean_text(row.get("comment_id"))
            if comment_id:
                record["comment_id"] = comment_id

        records.append(record)

    return records


def build_text_list(comment_records: List[Dict]) -> List[str]:
    return [record["comment_text"] for record in comment_records if record.get("comment_text")]


def serialize_list_for_csv(values: List) -> str:
    return json.dumps(values, ensure_ascii=False)


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)

    required_cols = {"recipe_id", "evidence_type", "evidence_score", "trimmed_comment"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {INPUT_PATH}: {sorted(missing)}")

    rows = []

    for recipe_id, group in df.groupby("recipe_id", dropna=True):
        issue_df = select_top(group, "issue", MAX_ISSUE)
        fix_df = select_top(group, "problem_solving_fix", MAX_FIX)
        mixed_df = select_top(group, "mixed", MAX_MIXED)
        adaptation_df = select_top(group, "adaptation", MAX_ADAPTATION)

        issue_records = build_comment_records(issue_df)
        fix_records = build_comment_records(fix_df)
        mixed_records = build_comment_records(mixed_df)
        adaptation_records = build_comment_records(adaptation_df)

        row = {
            "recipe_id": recipe_id,

            # Text-only lists (for easy use)
            "issue_evidence_comments": serialize_list_for_csv(build_text_list(issue_records)),
            "fix_evidence_comments": serialize_list_for_csv(build_text_list(fix_records)),
            "mixed_evidence_comments": serialize_list_for_csv(build_text_list(mixed_records)),
            "adaptation_comments": serialize_list_for_csv(build_text_list(adaptation_records)),

            # Rich records (for later LLM / debugging)
            "issue_evidence_records": serialize_list_for_csv(issue_records),
            "fix_evidence_records": serialize_list_for_csv(fix_records),
            "mixed_evidence_records": serialize_list_for_csv(mixed_records),
            "adaptation_records": serialize_list_for_csv(adaptation_records),

            # Counts
            "num_issue_comments": len(issue_records),
            "num_fix_comments": len(fix_records),
            "num_mixed_comments": len(mixed_records),
            "num_adaptation_comments": len(adaptation_records),

            # Flags
            "has_issue_evidence": int(len(issue_records) > 0),
            "has_fix_evidence": int(len(fix_records) > 0),
            "has_mixed_evidence": int(len(mixed_records) > 0),

            # Total
            "total_selected_evidence_comments": (
                len(issue_records)
                + len(fix_records)
                + len(mixed_records)
                + len(adaptation_records)
            ),
        }

        rows.append(row)

    out_df = pd.DataFrame(rows).sort_values("recipe_id").reset_index(drop=True)
    out_df.to_csv(OUTPUT_CSV_PATH, index=False)

    # JSONL output (clean + ready for LLM)
    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as f:
        for _, row in out_df.iterrows():
            obj = {
                "recipe_id": row["recipe_id"],
                "issue_evidence_comments": json.loads(row["issue_evidence_comments"]),
                "fix_evidence_comments": json.loads(row["fix_evidence_comments"]),
                "mixed_evidence_comments": json.loads(row["mixed_evidence_comments"]),
                "adaptation_comments": json.loads(row["adaptation_comments"]),
                "issue_evidence_records": json.loads(row["issue_evidence_records"]),
                "fix_evidence_records": json.loads(row["fix_evidence_records"]),
                "mixed_evidence_records": json.loads(row["mixed_evidence_records"]),
                "adaptation_records": json.loads(row["adaptation_records"]),
                "num_issue_comments": int(row["num_issue_comments"]),
                "num_fix_comments": int(row["num_fix_comments"]),
                "num_mixed_comments": int(row["num_mixed_comments"]),
                "num_adaptation_comments": int(row["num_adaptation_comments"]),
                "has_issue_evidence": bool(row["has_issue_evidence"]),
                "has_fix_evidence": bool(row["has_fix_evidence"]),
                "has_mixed_evidence": bool(row["has_mixed_evidence"]),
                "total_selected_evidence_comments": int(row["total_selected_evidence_comments"]),
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(out_df):,} recipes to {OUTPUT_CSV_PATH}")
    print(f"Saved JSONL to {OUTPUT_JSONL_PATH}")

    print("\nEvidence coverage summary:")
    print(f"Recipes with issue evidence: {out_df['has_issue_evidence'].sum():,}")
    print(f"Recipes with fix evidence: {out_df['has_fix_evidence'].sum():,}")
    print(f"Recipes with mixed evidence: {out_df['has_mixed_evidence'].sum():,}")

    print("\nSelected evidence per recipe summary:")
    print(out_df["total_selected_evidence_comments"].describe())


if __name__ == "__main__":
    main()