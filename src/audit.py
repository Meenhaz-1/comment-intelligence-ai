import pandas as pd

df = pd.read_csv("outputs/recipe_intelligence.csv", low_memory=False)

# -------------------------
# Filter rankable set
# -------------------------
rankable = df[
    (df["total_comments"] >= 5)
    & (df["has_behavioral_signal"] == 1)
].copy()

rankable = rankable.sort_values(
    by=["opportunity_score", "total_comments"],
    ascending=[False, False]
)

# -------------------------
# Take balanced sample
# -------------------------
top_high_opportunity = rankable[rankable["classification"] == "High Opportunity"].head(10)
top_needs_improvement = rankable[rankable["classification"] == "Needs Improvement"].head(10)
top_needs_fix = rankable[rankable["classification"] == "Needs Fix"].head(10)

audit_df = pd.concat(
    [top_high_opportunity, top_needs_improvement, top_needs_fix],
    ignore_index=True
)

# -------------------------
# Add audit columns
# -------------------------
audit_df["issue_feels_real"] = ""
audit_df["editorially_actionable"] = ""
audit_df["classification_feels_right"] = ""
audit_df["explanation_is_clear"] = ""
audit_df["needs_phrase_coverage_improvement"] = ""
audit_df["notes"] = ""

# -------------------------
# Select useful columns
# -------------------------
audit_df = audit_df[
    [
        "recipe_id",
        "title",
        "total_comments",
        "classification",
        "opportunity_score",
        "friction_score",
        "recoverability_score",
        "top_friction_phrase_1",
        "top_modification_phrase_1",

        # audit fields
        "issue_feels_real",
        "editorially_actionable",
        "classification_feels_right",
        "explanation_is_clear",
        "needs_phrase_coverage_improvement",
        "notes",
    ]
]

# -------------------------
# Save
# -------------------------
output_path = "outputs/recipe_audit_sample.csv"
audit_df.to_csv(output_path, index=False)

print(f"Saved audit file to: {output_path}")
print(audit_df.head(30).to_string(index=False))