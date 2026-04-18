import { DashboardRecipeRow } from "@/lib/types";
import { formatOpportunityScore, isLowSignal } from "@/lib/utils/editorial";

import { TagChip } from "../dashboard/tag-chip";

export function EditorialInsightCard({ recipe }: { recipe: DashboardRecipeRow }) {
  const lowSignal = isLowSignal(recipe.priority);

  return (
    <section className="card card-pad detail-section insight-card">
      <div className="detail-section-head">
        <h2 className="section-title">Editorial Insight</h2>
        <div className="section-kicker">Lead with the fix</div>
      </div>

      <div className="insight-grid">
        <div>
          <div className="label">Priority</div>
          <div className="detail-tag-row">
            <TagChip label={recipe.priority} tone={lowSignal ? "default" : "insight"} />
          </div>
        </div>

        <div>
          <div className="label">Opportunity Score</div>
          <div className="insight-value">{formatOpportunityScore(recipe.opportunityScore)}</div>
        </div>

        <div>
          <div className="label">Main Issue</div>
          <div className="insight-copy">{recipe.mainIssue}</div>
        </div>

        <div>
          <div className="label">Common Fix</div>
          <div className="insight-copy">{recipe.commonFix}</div>
        </div>
      </div>

      <div className="insight-summary-block">
        <div className="label">Summary</div>
        <p className="insight-summary">
          {recipe.editorialSummary ?? "Editorial signal is still forming for this recipe."}
        </p>
      </div>
    </section>
  );
}
