import { DashboardRecipeRow, RecipeComment } from "@/lib/types";
import {
  getDisplayIssueText,
  getFixEvidenceEmptyState,
  getIssueEvidenceEmptyState,
  getRecommendedEditText,
} from "@/lib/utils/editorial";
import {
  buildEvidenceExcerpt,
  getEvidenceCommentsForFix,
  getEvidenceCommentsForIssue,
} from "@/lib/utils/recipe-evidence";
import { formatDate } from "@/lib/utils/format-date";

type SupportingEvidenceProps = {
  recipe: DashboardRecipeRow;
  comments: RecipeComment[];
};

function highlightExcerpt(text: string, matchedTerms: string[]) {
  if (matchedTerms.length === 0) {
    return text;
  }

  const uniqueTerms = [...new Set(matchedTerms)]
    .filter(Boolean)
    .sort((left, right) => right.length - left.length);

  if (uniqueTerms.length === 0) {
    return text;
  }

  const pattern = new RegExp(`(${uniqueTerms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  const parts = text.split(pattern);

  return parts.map((part, index) =>
    uniqueTerms.some((term) => term.toLowerCase() === part.toLowerCase()) ? (
      <mark className="evidence-mark" key={`${part}-${index}`}>
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  );
}

function EvidenceBlock({
  title,
  emptyLabel,
  helperLabel,
  matches,
}: {
  title: string;
  emptyLabel: string;
  helperLabel?: string | null;
  matches: ReturnType<typeof getEvidenceCommentsForIssue>;
}) {
  return (
    <div className="evidence-block">
      <div className="label">{title}</div>
      {helperLabel ? <div className="detail-muted evidence-helper">{helperLabel}</div> : null}
      {matches.length === 0 ? (
        <div className="detail-muted evidence-empty">{emptyLabel}</div>
      ) : (
        <div className="evidence-list">
          {matches.map((match) => {
            const excerpt = buildEvidenceExcerpt(match.comment.text, match.matchedTerms);

            return (
              <article className="evidence-card" key={match.comment.id}>
                <div className="evidence-topline">
                  <div className="evidence-author">{match.comment.displayName}</div>
                  <div className="comment-date">{formatDate(match.comment.createdAt)}</div>
                </div>
                <p className="evidence-body">
                  {highlightExcerpt(excerpt, match.matchedTerms)}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SupportingEvidence({ recipe, comments }: SupportingEvidenceProps) {
  const displayIssue = getDisplayIssueText(recipe);
  const recommendedEdit = getRecommendedEditText(recipe);
  const issueMatches = getEvidenceCommentsForIssue(recipe, comments);
  const fixMatches = getEvidenceCommentsForFix(
    recipe,
    comments,
    new Set(issueMatches.map((match) => match.comment.id)),
  );
  const showIssueSourceNote = recipe.issueSource === "modification_inference";
  const issueHelper =
    showIssueSourceNote ? "Issue inferred from recurring user modifications" : null;

  return (
    <section className="card card-pad detail-section evidence-section">
      <div className="detail-section-head">
        <h2 className="section-title">Supporting Evidence</h2>
        <div className="section-kicker">Matched comment excerpts</div>
      </div>

      <div className="evidence-grid">
        <EvidenceBlock
          emptyLabel={getIssueEvidenceEmptyState(recipe)}
          helperLabel={issueHelper}
          matches={issueMatches}
          title="Evidence for Main Issue"
        />
        <EvidenceBlock
          emptyLabel={getFixEvidenceEmptyState(recipe)}
          matches={fixMatches}
          title={`Evidence for ${recommendedEdit ? "Recommended Edit" : "Workaround"}`}
        />
      </div>
    </section>
  );
}
