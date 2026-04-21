import { DashboardRecipeRow, RecipeComment } from "@/lib/types";
import {
  formatOpportunityScore,
  getDisplayIssueText,
  getEditorialConfidenceNote,
  getEditorialConfidenceTier,
  getFixConfidenceLabel,
  getFixSignalSummaryText,
  getIssueConfidenceLabel,
  getRecommendedEditText,
  getWhyItMattersText,
  isInferredState,
  isLowSignal,
  isManualReviewState,
} from "@/lib/utils/editorial";

import { TagChip } from "../dashboard/tag-chip";
import { ConfidencePill } from "./confidence-pill";

export function EditorialInsightCard({
  recipe,
  comments,
}: {
  recipe: DashboardRecipeRow;
  comments: RecipeComment[];
}) {
  const lowSignal = isLowSignal(recipe.priority);
  const manualReview = isManualReviewState(recipe.displayIssueActionState);
  const inferred = isInferredState(recipe.displayIssueActionState);
  const evidenceTexts = [
    ...(recipe.evidence?.fixEvidenceComments ?? []),
    ...comments.map((comment) => comment.text),
  ];
  const recommendedEdit = getRecommendedEditText(recipe, { evidenceTexts });
  const displayIssue = getDisplayIssueText(recipe);
  const whyItMatters = getWhyItMattersText(recipe);
  const issueConfidenceLabel = getIssueConfidenceLabel(recipe);
  const fixConfidenceLabel = getFixConfidenceLabel(recipe);
  const fixSignalSummary = getFixSignalSummaryText(recipe, { evidenceTexts });
  const confidenceNote = getEditorialConfidenceNote(recipe);
  const confidenceTier = getEditorialConfidenceTier(recipe);

  return (
    <section
      className={`card card-pad detail-section insight-card confidence-${confidenceTier} ${manualReview ? "manual-review-card" : ""}`}
    >
      <div className="detail-section-head">
        <div>
          <h2 className="section-title">Editorial Insight</h2>
          <div className="section-kicker">Deterministic source of truth</div>
        </div>
        <div className="insight-chip-row">
          <TagChip label={recipe.priority} tone={lowSignal ? "default" : "insight"} />
          <ConfidencePill
            label={`${confidenceTier.charAt(0).toUpperCase()}${confidenceTier.slice(1)} confidence`}
            tone={confidenceTier}
          />
          {inferred ? <span className="insight-helper-chip">Inferred</span> : null}
          {manualReview ? <span className="insight-helper-chip caution">Manual review</span> : null}
        </div>
      </div>

      <div className="insight-hero">
        <div className="label">Recommended Edit</div>
        <div className="insight-lead-copy">
          {recommendedEdit || "Review the supporting evidence directly before revising this recipe."}
        </div>
      </div>

      <div className="insight-grid detail">
        <div className="insight-panel">
          <div className="label">Main Issue</div>
          <div className="insight-copy">{displayIssue || "Needs manual review"}</div>
          {issueConfidenceLabel ? <div className="insight-subcopy">{issueConfidenceLabel}</div> : null}
        </div>

        <div className="insight-panel">
          <div className="label">Why It Matters</div>
          <p className="insight-summary compact">{whyItMatters}</p>
        </div>

        <div className="insight-panel">
          <div className="label">Fix Signal Summary</div>
          <p className="insight-summary compact">
            {fixSignalSummary ?? "Fix evidence is limited, so workaround patterns are still tentative."}
          </p>
          {fixConfidenceLabel ? <div className="insight-subcopy muted">{fixConfidenceLabel}</div> : null}
        </div>

        <div className="insight-panel">
          <div className="label">Confidence Note</div>
          <p className="insight-summary compact">{confidenceNote}</p>
          <div className="insight-subcopy muted">
            Opportunity score: {formatOpportunityScore(recipe.opportunityScore)}
          </div>
        </div>
      </div>
    </section>
  );
}
