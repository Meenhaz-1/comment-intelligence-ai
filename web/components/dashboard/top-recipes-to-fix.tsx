"use client";

import { useNavigationProgress } from "@/components/navigation/navigation-progress";
import { DashboardRecipeRow } from "@/lib/types";
import {
  formatOpportunityScore,
  getDisplayIssueText,
  getInferredBadgeLabel,
  getRecommendedEditText,
  truncateText,
} from "@/lib/utils/editorial";

import { TagChip } from "./tag-chip";

export function TopRecipesToFix({ recipes }: { recipes: DashboardRecipeRow[] }) {
  const { navigate } = useNavigationProgress();

  return (
    <section className="card table-card decision-card">
      <div className="card-pad table-head">
        <div>
          <h2 className="section-title">Top Recipes to Fix</h2>
          <p className="section-copy">
            Start with the recipes that show the clearest editorial opportunity.
          </p>
        </div>
        <div className="recipes-count">{recipes.length} recipes</div>
      </div>

      <div className="table-scroll">
        {recipes.length === 0 ? (
          <div className="card-pad detail-muted">
            No clear fix-priority recipes for this creator yet.
          </div>
        ) : (
          <table className="recipes-table decision-table">
            <colgroup>
              <col className="decision-col-title" />
              <col className="decision-col-priority" />
              <col className="decision-col-score" />
              <col className="decision-col-issue" />
              <col className="decision-col-edit" />
              <col className="decision-col-comments" />
            </colgroup>
            <thead>
              <tr>
                <th>Recipe</th>
                <th>Priority</th>
                <th>Opportunity Score</th>
                <th>Main Issue</th>
                <th>Recommended Edit</th>
                <th>Comments</th>
              </tr>
            </thead>
            <tbody>
              {recipes.map((recipe, index) => {
                const displayIssue = getDisplayIssueText(recipe);
                const recommendedEdit = getRecommendedEditText(recipe);
                const inferredBadge = getInferredBadgeLabel(recipe);

                return (
                  <tr
                    className="decision-row"
                    key={recipe.contentId}
                    onClick={() => navigate(`/recipe/${recipe.contentId}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/recipe/${recipe.contentId}`);
                      }
                    }}
                    tabIndex={0}
                  >
                    <td>
                      <div className="decision-title-wrap">
                        <div className="top-rank">{index + 1}</div>
                        <div>
                          <div className="recipe-title clamped-copy clamped-copy-2">{recipe.title}</div>
                          <div className="decision-meta">
                            {recipe.brand ?? "Recipe creator portfolio"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <TagChip label={recipe.priority} tone="insight" />
                    </td>
                    <td className="metric-cell">{formatOpportunityScore(recipe.opportunityScore)}</td>
                    <td>
                      <div className="decision-cell-copy clamped-copy clamped-copy-3">{displayIssue || "Needs manual review"}</div>
                      {inferredBadge ? (
                        <div className="decision-inline-note clamped-copy clamped-copy-2">{inferredBadge}</div>
                      ) : null}
                    </td>
                    <td title={recommendedEdit || undefined}>
                      <div className="decision-cell-copy clamped-copy clamped-copy-4">
                        {truncateText(recommendedEdit, 88) || "Review comment evidence manually"}
                      </div>
                    </td>
                    <td className="metric-cell">{recipe.totalComments}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
