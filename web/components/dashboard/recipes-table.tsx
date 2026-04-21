"use client";
import { useEffect, useMemo, useState } from "react";

import { AppLink } from "@/components/navigation/navigation-progress";
import { DashboardRecipeRow } from "@/lib/types";
import {
  formatOpportunityScore,
  getAiSummaryPreview,
  getDisplayIssueText,
  getEvidenceStrengthBadge,
  getInferredBadgeLabel,
  getIssueConfidenceLabel,
  getRecommendedEditText,
  shouldShowLlmSummary,
  isLowSignal,
  truncateText,
} from "@/lib/utils/editorial";

import { TagChip } from "./tag-chip";

type SortKey = "opportunityScore" | "commentsCount" | "priority";

function SortIcon({
  isActive,
  direction,
}: {
  isActive: boolean;
  direction: "asc" | "desc";
}) {
  return (
    <span
      aria-hidden="true"
      className={`sort-icon ${isActive ? "active" : ""}`}
    >
      {isActive ? (direction === "desc" ? "↓" : "↑") : "↕"}
    </span>
  );
}

export function RecipesTable({ recipes }: { recipes: DashboardRecipeRow[] }) {
  const PAGE_SIZE = 40;
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [evidenceStrengthFilter, setEvidenceStrengthFilter] = useState("all");
  const [aiSummaryFilter, setAiSummaryFilter] = useState("all");
  const [issueConfidenceFilter, setIssueConfidenceFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("opportunityScore");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const filteredAndSortedRecipes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const priorityRank: Record<string, number> = {
      "High Opportunity": 4,
      "Needs Improvement": 3,
      "Needs Fix": 2,
      "Performing Well": 1,
      "Low Signal": 0,
    };

    const filteredRecipes = recipes.filter((recipe) => {
      const matchesQuery = !normalizedQuery || recipe.title.toLowerCase().includes(normalizedQuery);
      const matchesPriority = priorityFilter === "all" || recipe.priority === priorityFilter;
      const strength = recipe.llmReadiness?.evidenceStrength ?? "none";
      const matchesEvidenceStrength =
        evidenceStrengthFilter === "all" || strength === evidenceStrengthFilter;
      const aiReady = shouldShowLlmSummary(recipe);
      const matchesAiSummary =
        aiSummaryFilter === "all" ||
        (aiSummaryFilter === "ready" && aiReady) ||
        (aiSummaryFilter === "not-ready" && !aiReady);
      const confidence = (recipe.issueConfidence ?? "").toLowerCase() || "unknown";
      const matchesIssueConfidence =
        issueConfidenceFilter === "all" || confidence === issueConfidenceFilter;

      return (
        matchesQuery &&
        matchesPriority &&
        matchesEvidenceStrength &&
        matchesAiSummary &&
        matchesIssueConfidence
      );
    });

    const sortedRecipes = [...filteredRecipes].sort((left, right) => {
      const leftValue =
        sortKey === "priority"
          ? priorityRank[left.priority] ?? 0
          : sortKey === "commentsCount"
            ? left.totalComments
            : left.opportunityScore ?? -Infinity;
      const rightValue =
        sortKey === "priority"
          ? priorityRank[right.priority] ?? 0
          : sortKey === "commentsCount"
            ? right.totalComments
            : right.opportunityScore ?? -Infinity;

      if (leftValue === rightValue) {
        return left.title.localeCompare(right.title);
      }

      return sortDirection === "desc"
        ? rightValue - leftValue
        : leftValue - rightValue;
    });

    return sortedRecipes;
  }, [
    aiSummaryFilter,
    evidenceStrengthFilter,
    issueConfidenceFilter,
    priorityFilter,
    query,
    recipes,
    sortDirection,
    sortKey,
  ]);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [
    PAGE_SIZE,
    aiSummaryFilter,
    evidenceStrengthFilter,
    issueConfidenceFilter,
    priorityFilter,
    query,
    sortDirection,
    sortKey,
  ]);

  const visibleRecipes = filteredAndSortedRecipes.slice(0, visibleCount);
  const hasMoreRecipes = visibleCount < filteredAndSortedRecipes.length;

  function toggleSort(nextSortKey: SortKey) {
    if (sortKey === nextSortKey) {
      setSortDirection((currentDirection) =>
        currentDirection === "desc" ? "asc" : "desc",
      );
      return;
    }

    setSortKey(nextSortKey);
    setSortDirection("desc");
  }

  return (
    <section className="card table-card">
      <div className="card-pad table-head">
        <div>
          <h2 className="section-title">All Recipes</h2>
          <p className="section-copy">
            Work through the full creator backlog with priority, issue, and fix context up front.
          </p>
        </div>
        <div className="recipes-count">{filteredAndSortedRecipes.length} recipes</div>
      </div>

      <div className="search-row table-filter-row">
        <input
          className="text-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by recipe title..."
          type="text"
          value={query}
        />
        <select
          className="select-input"
          onChange={(event) => setPriorityFilter(event.target.value)}
          value={priorityFilter}
        >
          <option value="all">All priorities</option>
          <option value="High Opportunity">High Opportunity</option>
          <option value="Needs Improvement">Needs Improvement</option>
          <option value="Needs Fix">Needs Fix</option>
          <option value="Performing Well">Performing Well</option>
          <option value="Low Signal">Low Signal</option>
        </select>
        <select
          className="select-input"
          onChange={(event) => setEvidenceStrengthFilter(event.target.value)}
          value={evidenceStrengthFilter}
        >
          <option value="all">All evidence strengths</option>
          <option value="high">High evidence</option>
          <option value="medium">Medium evidence</option>
          <option value="low">Low evidence</option>
          <option value="none">No evidence label</option>
        </select>
        <select
          className="select-input"
          onChange={(event) => setAiSummaryFilter(event.target.value)}
          value={aiSummaryFilter}
        >
          <option value="all">AI summary: all</option>
          <option value="ready">AI summary ready</option>
          <option value="not-ready">AI summary hidden</option>
        </select>
        <select
          className="select-input"
          onChange={(event) => setIssueConfidenceFilter(event.target.value)}
          value={issueConfidenceFilter}
        >
          <option value="all">All issue confidence</option>
          <option value="high">High confidence</option>
          <option value="medium">Medium confidence</option>
          <option value="low">Low confidence</option>
          <option value="unknown">Unknown confidence</option>
        </select>
      </div>

      <div className="table-scroll">
        <table className="recipes-table">
          <colgroup>
            <col className="recipes-col-title" />
            <col className="recipes-col-priority" />
            <col className="recipes-col-issue" />
            <col className="recipes-col-edit" />
            <col className="recipes-col-ai" />
            <col className="recipes-col-score" />
            <col className="recipes-col-comments" />
          </colgroup>
          <thead>
            <tr>
              <th>Recipe Title</th>
              <th>
                <button
                  className="sort-button"
                  onClick={() => toggleSort("priority")}
                  type="button"
                >
                  Priority
                  <SortIcon
                    direction={sortDirection}
                    isActive={sortKey === "priority"}
                  />
                </button>
              </th>
              <th>Main Issue</th>
              <th>Recommended Edit</th>
              <th>AI</th>
              <th>
                <button
                  className="sort-button"
                  onClick={() => toggleSort("opportunityScore")}
                  type="button"
                >
                  Opportunity Score
                  <SortIcon
                    direction={sortDirection}
                    isActive={sortKey === "opportunityScore"}
                  />
                </button>
              </th>
              <th>
                <button
                  className="sort-button"
                  onClick={() => toggleSort("commentsCount")}
                  type="button"
                >
                  Comments
                  <SortIcon
                    direction={sortDirection}
                    isActive={sortKey === "commentsCount"}
                  />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {visibleRecipes.map((recipe) => {
              const displayIssue = getDisplayIssueText(recipe);
              const recommendedEdit = getRecommendedEditText(recipe);
              const inferredBadge = getInferredBadgeLabel(recipe);
              const aiReady = shouldShowLlmSummary(recipe);
              const aiPreview = getAiSummaryPreview(recipe.llmEditorSummary);
              const evidenceBadge = getEvidenceStrengthBadge(recipe);
              const confidenceLabel = getIssueConfidenceLabel(recipe);

              return (
                <tr
                  className={isLowSignal(recipe.priority) ? "low-signal-row" : ""}
                  key={recipe.contentId}
                >
                  <td>
                    <AppLink className="recipe-title recipe-link dashboard-recipe-title" href={`/recipe/${recipe.contentId}`}>
                      {recipe.title}
                    </AppLink>
                    <div className="recipe-insight-chip">
                      <span className="table-secondary">
                        {isLowSignal(recipe.priority)
                          ? "Low signal"
                          : `${recipe.pageviews.toLocaleString()} views · ${
                              recipe.saves === null ? "N/A saves" : `${recipe.saves.toLocaleString()} saves`
                            }`}
                      </span>
                    </div>
                    {aiReady && aiPreview ? (
                      <div className="table-tertiary clamped-copy clamped-copy-2" title={aiPreview}>
                        {aiPreview}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <TagChip
                      label={recipe.priority}
                      tone={isLowSignal(recipe.priority) ? "default" : "insight"}
                    />
                  </td>
                  <td>
                    <div className="decision-cell-copy clamped-copy clamped-copy-3">
                      {displayIssue || "Needs manual review"}
                    </div>
                    {[inferredBadge, confidenceLabel].filter((note): note is string => Boolean(note)).map((note) => (
                      <div className="decision-inline-note clamped-copy clamped-copy-2" key={note} title={note}>
                        {note}
                      </div>
                    ))}
                  </td>
                  <td title={recommendedEdit || undefined}>
                    <div className="decision-cell-copy clamped-copy clamped-copy-4">
                      {truncateText(recommendedEdit, 88) || "Review comment evidence manually"}
                    </div>
                  </td>
                  <td>
                    {aiReady ? (
                      <div className="ai-status-cell" title={aiPreview || undefined}>
                        <TagChip label="AI Summary Ready" tone="success" />
                        {evidenceBadge ? (
                          <div className="decision-inline-note">{evidenceBadge.label}</div>
                        ) : null}
                      </div>
                    ) : null}
                  </td>
                  <td className="metric-cell">{formatOpportunityScore(recipe.opportunityScore)}</td>
                  <td className="metric-cell">{recipe.totalComments}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hasMoreRecipes ? (
        <div className="table-load-more">
          <button
            className="secondary-button table-load-more-button"
            onClick={() => setVisibleCount((current) => current + PAGE_SIZE)}
            type="button"
          >
            Load {Math.min(PAGE_SIZE, filteredAndSortedRecipes.length - visibleCount)} more recipes
          </button>
          <div className="detail-muted">
            Showing {visibleRecipes.length} of {filteredAndSortedRecipes.length}
          </div>
        </div>
      ) : filteredAndSortedRecipes.length > PAGE_SIZE ? (
        <div className="table-load-more">
          <div className="detail-muted">
            Showing all {filteredAndSortedRecipes.length} recipes
          </div>
        </div>
      ) : null}
    </section>
  );
}
