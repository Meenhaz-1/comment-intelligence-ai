import { DashboardRecipeRow, RecipeComment } from "@/lib/types";
import {
  getDisplayIssueText,
  getFixEvidenceEmptyState,
  getIssueEvidenceEmptyState,
  getRecommendedEditText,
} from "@/lib/utils/editorial";
import { getSupportingEvidenceCollections } from "@/lib/utils/recipe-evidence";

import { EvidenceSnippetList } from "./evidence-snippet-list";

type SupportingEvidenceProps = {
  recipe: DashboardRecipeRow;
  comments: RecipeComment[];
};

export function SupportingEvidence({ recipe, comments }: SupportingEvidenceProps) {
  const displayIssue = getDisplayIssueText(recipe);
  const { issueEvidenceItems, fixEvidenceItems } = getSupportingEvidenceCollections(recipe, comments);
  const evidenceTexts = fixEvidenceItems.map((item) => item.text);
  const recommendedEdit = getRecommendedEditText(recipe, { evidenceTexts });
  const showEmptyState = issueEvidenceItems.length === 0 && fixEvidenceItems.length === 0;

  return (
    <section className="card card-pad detail-section evidence-section">
      <div className="detail-section-head">
        <h2 className="section-title">Supporting Evidence</h2>
        <div className="section-kicker">Proof before exploration</div>
      </div>

      {showEmptyState ? (
        <div className="detail-muted evidence-empty">
          Comment evidence is limited for this recipe. Review the available comments directly before making a stronger recommendation.
        </div>
      ) : (
        <div className="evidence-grid">
          {issueEvidenceItems.length > 0 ? (
            <div className="evidence-block">
              <div className="label">Evidence for Main Issue</div>
              <div className="detail-muted evidence-helper">
                {displayIssue
                  ? `These comments reinforce the main issue: ${displayIssue}.`
                  : getIssueEvidenceEmptyState(recipe)}
              </div>
              <EvidenceSnippetList
                highlight={displayIssue}
                items={issueEvidenceItems}
                emptyLabel={getIssueEvidenceEmptyState(recipe)}
              />
            </div>
          ) : null}

          {fixEvidenceItems.length > 0 ? (
            <div className="evidence-block">
              <div className="label">Evidence for Fix Signal</div>
              <div className="detail-muted evidence-helper">
                {recommendedEdit
                  ? `These comments show how readers are compensating or what they change first.`
                  : getFixEvidenceEmptyState(recipe)}
              </div>
              <EvidenceSnippetList
                highlight={recipe.topCanonicalFix1 ?? recommendedEdit}
                items={fixEvidenceItems}
                emptyLabel={getFixEvidenceEmptyState(recipe)}
              />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
