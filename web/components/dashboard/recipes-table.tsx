"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { DashboardRecipeRow } from "@/lib/types";
import {
  formatOpportunityScore,
  getDisplayIssueText,
  getInferredBadgeLabel,
  getRecommendedEditText,
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
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [minComments, setMinComments] = useState("0");
  const [sortKey, setSortKey] = useState<SortKey>("opportunityScore");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  const filteredAndSortedRecipes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const minCommentsValue = Number(minComments);
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
      const matchesMinComments = recipe.totalComments >= minCommentsValue;

      return matchesQuery && matchesPriority && matchesMinComments;
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
  }, [minComments, priorityFilter, query, recipes, sortDirection, sortKey]);

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
          onChange={(event) => setMinComments(event.target.value)}
          value={minComments}
        >
          <option value="0">Min comments: 0</option>
          <option value="3">Min comments: 3</option>
          <option value="5">Min comments: 5</option>
          <option value="10">Min comments: 10</option>
        </select>
      </div>

      <div className="table-scroll">
        <table className="recipes-table">
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
            {filteredAndSortedRecipes.map((recipe) => {
              const displayIssue = getDisplayIssueText(recipe);
              const recommendedEdit = getRecommendedEditText(recipe);
              const inferredBadge = getInferredBadgeLabel(recipe);

              return (
                <tr
                  className={isLowSignal(recipe.priority) ? "low-signal-row" : ""}
                  key={recipe.contentId}
                >
                  <td>
                    <Link className="recipe-title recipe-link" href={`/recipe/${recipe.contentId}`}>
                      {recipe.title}
                    </Link>
                    <div className="recipe-insight-chip">
                      <span className="table-secondary">
                        {isLowSignal(recipe.priority)
                          ? "Low signal"
                          : `${recipe.pageviews.toLocaleString()} views · ${
                              recipe.saves === null ? "N/A saves" : `${recipe.saves.toLocaleString()} saves`
                            }`}
                      </span>
                    </div>
                  </td>
                  <td>
                    <TagChip
                      label={recipe.priority}
                      tone={isLowSignal(recipe.priority) ? "default" : "insight"}
                    />
                  </td>
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
                  <td className="metric-cell">{formatOpportunityScore(recipe.opportunityScore)}</td>
                  <td className="metric-cell">{recipe.totalComments}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
