"use client";

import { useMemo, useState } from "react";

import { DashboardRecipeRow, EditorialSummary, RecipeComment } from "@/lib/types";
import {
  getFeedbackConsistencyLabel,
  getMostCommonComplaintText,
  getMostCommonWorkaroundText,
} from "@/lib/utils/editorial";
import { getStrongestEvidenceItems, getSupportingEvidenceCollections } from "@/lib/utils/recipe-evidence";
import { formatDate } from "@/lib/utils/format-date";

import { EvidenceSnippetList } from "./evidence-snippet-list";

type CommentsPanelProps = {
  recipe: DashboardRecipeRow;
  comments: RecipeComment[];
};

function buildEditorialSummary(
  recipe: DashboardRecipeRow,
  comments: RecipeComment[],
): EditorialSummary {
  const { issueEvidenceItems, fixEvidenceItems } = getSupportingEvidenceCollections(recipe, comments);
  const evidenceTexts = fixEvidenceItems.map((item) => item.text);

  return {
    mostCommonComplaint: getMostCommonComplaintText(recipe),
    mostCommonWorkaround: getMostCommonWorkaroundText(recipe, { evidenceTexts }),
    feedbackConsistency: getFeedbackConsistencyLabel(
      recipe,
      issueEvidenceItems.length,
      fixEvidenceItems.length,
    ),
    strongestComments: getStrongestEvidenceItems(recipe, comments, 3),
  };
}

export function CommentsPanel({ recipe, comments }: CommentsPanelProps) {
  const [query, setQuery] = useState("");
  const [expandedCommentIds, setExpandedCommentIds] = useState<Record<string, boolean>>({});
  const editorialSummary = useMemo(() => buildEditorialSummary(recipe, comments), [comments, recipe]);

  const filteredComments = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return comments;
    }

    return comments.filter((comment) =>
      [
        comment.text,
        comment.displayName,
        comment.location ?? "",
      ].some((value) => value.toLowerCase().includes(normalizedQuery)),
    );
  }, [comments, query]);

  return (
    <>
      <section className="card card-pad detail-section editorial-summary-section">
        <div className="detail-section-head">
          <div>
            <h2 className="section-title">Editorial Summary</h2>
            <div className="section-kicker">Quick read on the comment set</div>
          </div>
        </div>

        <div className="editorial-summary-grid">
          <div className="insight-panel">
            <div className="label">Most Common Complaint</div>
            <p className="insight-summary compact">
              {editorialSummary.mostCommonComplaint ?? "No single complaint rises above the rest yet."}
            </p>
          </div>

          <div className="insight-panel">
            <div className="label">Most Common Workaround</div>
            <p className="insight-summary compact">
              {editorialSummary.mostCommonWorkaround ?? "No strong workaround pattern is visible in the current evidence."}
            </p>
          </div>

          <div className="insight-panel editorial-summary-wide">
            <div className="label">Feedback Consistency</div>
            <p className="insight-summary compact">
              {editorialSummary.feedbackConsistency ?? "Feedback consistency is still unclear."}
            </p>
          </div>
        </div>

        <div className="editorial-strongest-comments">
          <div className="label">Strongest Comments</div>
          {editorialSummary.strongestComments.length > 0 ? (
            <EvidenceSnippetList
              items={editorialSummary.strongestComments}
              emptyLabel="No standout evidence comments were selected for this recipe."
            />
          ) : (
            <div className="detail-muted evidence-empty">
              Strong evidence comments are limited for this recipe. Review the raw comments below.
            </div>
          )}
        </div>
      </section>

      <section className="card card-pad detail-section">
        <div className="detail-section-head">
          <h2 className="section-title">Comments</h2>
          <div className="recipes-count">{filteredComments.length} comments</div>
        </div>

        <div className="comments-search-row">
          <input
            className="text-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search comments by text, reader, or location..."
            type="text"
            value={query}
          />
        </div>

        <div className="comments-list">
          {filteredComments.length === 0 ? (
            <div className="detail-muted">No comments match this search.</div>
          ) : (
            filteredComments.map((comment) => (
              <article className="comment-card" key={comment.id}>
                <div className="comment-topline">
                  <div className="comment-author">
                    {comment.displayName}
                    {comment.location ? (
                      <span className="comment-location"> · {comment.location}</span>
                    ) : null}
                  </div>
                  <div className="comment-date">{formatDate(comment.createdAt)}</div>
                </div>
                <p className={`comment-body${expandedCommentIds[comment.id] ? " expanded" : " collapsed"}`}>
                  {comment.text}
                </p>
                {comment.text.trim().length > 280 ? (
                  <button
                    className="evidence-toggle comment-expand-toggle"
                    onClick={() =>
                      setExpandedCommentIds((current) => ({
                        ...current,
                        [comment.id]: !current[comment.id],
                      }))
                    }
                    type="button"
                  >
                    {expandedCommentIds[comment.id] ? "Show less" : "Read full comment"}
                  </button>
                ) : null}
                {comment.willPrepareAgain ? (
                  <div className="comment-chip-row">
                    <span className="tag-chip">
                      Would prepare again: {comment.willPrepareAgain}
                    </span>
                  </div>
                ) : null}
              </article>
            ))
          )}
        </div>
      </section>
    </>
  );
}
