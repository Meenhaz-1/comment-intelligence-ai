"use client";

import { useRouter } from "next/navigation";

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
  const router = useRouter();

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
                    onClick={() => router.push(`/recipe/${recipe.contentId}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/recipe/${recipe.contentId}`);
                      }
                    }}
                    tabIndex={0}
                  >
                    <td>
                      <div className="decision-title-wrap">
                        <div className="top-rank">{index + 1}</div>
                        <div>
                          <div className="recipe-title">{recipe.title}</div>
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
                      <div className="decision-cell-copy">{displayIssue || "Needs manual review"}</div>
                      {inferredBadge ? (
                        <div className="decision-inline-note">{inferredBadge}</div>
                      ) : null}
                    </td>
                    <td title={recommendedEdit || undefined}>
                      <div className="decision-cell-copy">
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
