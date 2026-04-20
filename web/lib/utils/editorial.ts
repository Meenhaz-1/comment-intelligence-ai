const MANUAL_REVIEW_ISSUE = "Needs manual review";
const MANUAL_REVIEW_EDIT = "Review comment evidence manually";

type EditorialDecisionLike = {
  priority?: string | null;
  displayIssue?: string | null;
  displayIssueReason?: string | null;
  displayIssueActionState?: string | null;
  whyItMatters?: string | null;
  recommendedEdit?: string | null;
  topModificationPhrase?: string | null;
  topNormalizedIssue?: string | null;
  issueSource?: string | null;
};

function cleanText(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function normalizeLegacyRecommendedEdit(value: string | null | undefined): string | null {
  const normalized = cleanText(value);

  if (!normalized) {
    return null;
  }

  const edit = normalized.toLowerCase();

  if (
    edit === "double recipe" ||
    edit === "doubled spices" ||
    edit === "double spices" ||
    edit === "increase spices" ||
    edit === "added more spices"
  ) {
    return "Increase seasoning.";
  }

  if (
    edit === "added lemon" ||
    edit === "add lemon" ||
    edit === "added lime" ||
    edit === "add lime"
  ) {
    return "Add acidity.";
  }

  if (
    edit === "used less salt" ||
    edit === "less salt" ||
    edit === "reduce salt" ||
    edit === "used less kosher salt"
  ) {
    return "Reduce salt.";
  }

  return null;
}

export function formatOpportunityScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "N/A";
}

export function isLowSignal(priority: string | null | undefined): boolean {
  return (priority ?? "").trim().toLowerCase() === "low signal";
}

export function isManualReviewState(value: string | null | undefined): boolean {
  return (value ?? "").trim() === "show_manual_review";
}

export function isInferredState(value: string | null | undefined): boolean {
  return (value ?? "").trim() === "show_inferred";
}

export function getDefaultWhyItMatters(priority: string | null | undefined): string {
  const normalized = (priority ?? "").trim().toLowerCase();

  if (normalized === "high opportunity") {
    return "High friction and strong engagement suggest this recipe is worth fixing.";
  }

  if (normalized === "needs improvement") {
    return "Users report consistent issues but are actively adapting the recipe.";
  }

  if (normalized === "needs fix") {
    return "Users report consistent issues without a clear workaround.";
  }

  if (normalized === "performing well") {
    return "Reader feedback suggests the recipe is landing well without a clear editorial issue.";
  }

  if (normalized === "low signal") {
    return "There is not enough reliable feedback yet to point to a clear editorial action.";
  }

  return "Reader feedback suggests this recipe may benefit from closer editorial review.";
}

export function getDisplayIssueText(recipe: EditorialDecisionLike): string {
  if (isManualReviewState(recipe.displayIssueActionState)) {
    return MANUAL_REVIEW_ISSUE;
  }

  return cleanText(recipe.displayIssue) ?? cleanText(recipe.topNormalizedIssue) ?? "";
}

export function getRecommendedEditText(recipe: EditorialDecisionLike): string {
  if (isManualReviewState(recipe.displayIssueActionState)) {
    return cleanText(recipe.recommendedEdit) ?? MANUAL_REVIEW_EDIT;
  }

  return (
    cleanText(recipe.recommendedEdit) ??
    normalizeLegacyRecommendedEdit(recipe.topModificationPhrase) ??
    ""
  );
}

export function getWhyItMattersText(recipe: EditorialDecisionLike): string {
  return cleanText(recipe.whyItMatters) ?? getDefaultWhyItMatters(recipe.priority);
}

export function getConfidenceNote(recipe: EditorialDecisionLike): string | null {
  return cleanText(recipe.displayIssueReason);
}

export function getInferredBadgeLabel(recipe: EditorialDecisionLike): string | null {
  if (!isInferredState(recipe.displayIssueActionState)) {
    return null;
  }

  const reason = cleanText(recipe.displayIssueReason);
  return reason ?? "Inferred";
}

export function getIssueEvidenceEmptyState(recipe: EditorialDecisionLike): string {
  if (isManualReviewState(recipe.displayIssueActionState) || cleanText(recipe.issueSource) === "friction_inference") {
    return "No clear recurring issue phrase was extracted. Manual review recommended.";
  }

  if (cleanText(recipe.issueSource) === "modification_inference") {
    return "Issue inferred from recurring user modifications. Direct issue phrase matches are limited.";
  }

  return "No directly matched comments found for this issue yet.";
}

export function getFixEvidenceEmptyState(recipe: EditorialDecisionLike): string {
  if (isManualReviewState(recipe.displayIssueActionState)) {
    return "Recommended edit is based on manual review guidance rather than a recurring workaround phrase.";
  }

  if (cleanText(recipe.issueSource) === "modification_inference") {
    return "Users are adapting this recipe in recurring ways, but direct workaround matches are limited in the visible comments.";
  }

  return "No directly matched comments found for this recommendation yet.";
}

export function truncateText(value: string | null | undefined, maxLength = 84): string {
  const normalized = cleanText(value);

  if (!normalized || normalized.length <= maxLength) {
    return normalized ?? "";
  }

  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}
