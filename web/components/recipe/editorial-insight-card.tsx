import { DashboardRecipeRow } from "@/lib/types";
import {
  formatOpportunityScore,
  getConfidenceNote,
  getDisplayIssueText,
  getRecommendedEditText,
  getWhyItMattersText,
  isInferredState,
  isLowSignal,
  isManualReviewState,
} from "@/lib/utils/editorial";

import { TagChip } from "../dashboard/tag-chip";

export function EditorialInsightCard({ recipe }: { recipe: DashboardRecipeRow }) {
  const lowSignal = isLowSignal(recipe.priority);
  const manualReview = isManualReviewState(recipe.displayIssueActionState);
  const inferred = isInferredState(recipe.displayIssueActionState);
  const recommendedEdit = getRecommendedEditText(recipe);
  const displayIssue = getDisplayIssueText(recipe);
  const whyItMatters = getWhyItMattersText(recipe);
  const confidenceNote = getConfidenceNote(recipe);

  return (
    <section className={`card card-pad detail-section insight-card ${manualReview ? "manual-review-card" : ""}`}>
      <div className="detail-section-head">
        <h2 className="section-title">Editorial Insight</h2>
        <div className="section-kicker">Lead with the fix</div>
      </div>

      <div className="insight-grid">
        <div>
          <div className="label">Priority</div>
          <div className="detail-tag-row insight-priority-row">
            <TagChip label={recipe.priority} tone={lowSignal ? "default" : "insight"} />
            {inferred ? <span className="insight-helper-chip">Inferred</span> : null}
            {manualReview ? <span className="insight-helper-chip caution">Manual review</span> : null}
          </div>
        </div>

        <div>
          <div className="label">Opportunity Score</div>
          <div className="insight-value">{formatOpportunityScore(recipe.opportunityScore)}</div>
        </div>

        <div className="insight-lead-block">
          <div className="label">Recommended Edit</div>
          <div className="insight-copy">{recommendedEdit || "Review comment evidence manually"}</div>
        </div>

        <div>
          <div className="label">Main Issue</div>
          <div className="insight-copy">{displayIssue || "Needs manual review"}</div>
          {confidenceNote ? <div className="insight-subcopy muted">{confidenceNote}</div> : null}
        </div>
      </div>

      <div className="insight-summary-block">
        <div className="label">Why It Matters</div>
        <p className="insight-summary">{whyItMatters}</p>
      </div>
    </section>
  );
}
