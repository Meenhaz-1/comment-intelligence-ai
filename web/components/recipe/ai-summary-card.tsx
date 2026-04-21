import { DashboardRecipeRow } from "@/lib/types";
import {
  getEvidenceStrengthBadge,
  shouldShowLlmSummary,
} from "@/lib/utils/editorial";

import { TagChip } from "../dashboard/tag-chip";

export function AiSummaryCard({ recipe }: { recipe: DashboardRecipeRow }) {
  if (!shouldShowLlmSummary(recipe) || !recipe.llmEditorSummary) {
    return null;
  }

  const evidenceBadge = getEvidenceStrengthBadge(recipe);

  return (
    <section className="card card-pad detail-section ai-summary-card">
      <div className="detail-section-head">
        <h2 className="section-title">AI Summary</h2>
        <div className="section-kicker">Additive editor assist</div>
      </div>

      <p className="ai-summary-copy">{recipe.llmEditorSummary}</p>

      <div className="ai-summary-meta">
        <span className="insight-helper-chip">Evidence-backed</span>
        {evidenceBadge ? <TagChip label={evidenceBadge.label} tone={evidenceBadge.tone} /> : null}
      </div>
    </section>
  );
}
