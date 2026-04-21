const MANUAL_REVIEW_ISSUE = "Needs manual review";
const MANUAL_REVIEW_EDIT = "Review comment evidence manually";
const NEGATIVE_FIX_SUMMARY = "No consistent user fixes identified.";

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
  issueConfidence?: string | null;
  fixConfidence?: string | null;
  fixSignalSummary?: string | null;
  recommendedEditV2?: string | null;
  recommendedEditSource?: string | null;
  llmEditorSummary?: string | null;
  showLlmSummary?: boolean | null;
  llmReadiness?: {
    evidenceStrength?: string | null;
    llmReadyForSummary?: boolean | null;
    llmReadyForRag?: boolean | null;
  } | null;
  llmEval?: {
    flag?: string | null;
  } | null;
  decision?: {
    classification?: string | null;
    opportunityScore?: number | null;
    recommendedEdit?: string | null;
    recommendedEditV2?: string | null;
    recommendedEditSource?: string | null;
    whyItMatters?: string | null;
    fixConfidence?: string | null;
    fixSignalSummary?: string | null;
    topCanonicalFix1?: string | null;
    topCanonicalFix2?: string | null;
    topFixFamily1?: string | null;
    topFixFamily2?: string | null;
    issue?: {
      displayIssue?: string | null;
      displayIssueReason?: string | null;
      displayIssueActionState?: string | null;
      issueSource?: string | null;
      issueConfidence?: string | null;
      topIssuePhrase?: string | null;
    } | null;
  } | null;
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

function toSentenceCase(value: string): string {
  return value ? `${value.charAt(0).toUpperCase()}${value.slice(1)}` : value;
}

function joinList(values: string[]): string {
  if (values.length === 0) {
    return "";
  }

  if (values.length === 1) {
    return values[0];
  }

  if (values.length === 2) {
    return `${values[0]} or ${values[1]}`;
  }

  return `${values.slice(0, -1).join(", ")}, or ${values.at(-1)}`;
}

function getCanonicalFixes(recipe: EditorialDecisionLike): string[] {
  const values = [
    cleanText((recipe as { topCanonicalFix1?: string | null }).topCanonicalFix1),
    cleanText((recipe as { topCanonicalFix2?: string | null }).topCanonicalFix2),
    cleanText(recipe.decision?.topCanonicalFix1),
    cleanText(recipe.decision?.topCanonicalFix2),
  ].filter((value): value is string => Boolean(value));

  return [...new Set(values.map((value) => value.toLowerCase()))];
}

function getFixConfidence(recipe: EditorialDecisionLike): string | null {
  return cleanText(recipe.fixConfidence) ?? cleanText(recipe.decision?.fixConfidence);
}

function getEvidenceIngredientTargets(
  evidenceTexts: string[] | undefined,
  groups: string[][],
): string[] {
  if (!evidenceTexts?.length) {
    return [];
  }

  const haystack = evidenceTexts.join(" ").toLowerCase();
  const matches: string[] = [];

  groups.forEach((group) => {
    const hit = group.find((candidate) => haystack.includes(candidate));
    if (hit) {
      matches.push(hit);
    }
  });

  return [...new Set(matches)].slice(0, 3);
}

function buildSpecificFixEdit(
  canonicalFix: string | null,
  evidenceTexts: string[] | undefined,
): string | null {
  const fix = canonicalFix?.toLowerCase();

  if (!fix) {
    return null;
  }

  if (fix === "reduce salt") {
    const ingredients = getEvidenceIngredientTargets(evidenceTexts, [
      ["bouillon", "broth", "stock"],
      ["parmesan", "pecorino"],
      ["soy sauce", "miso", "fish sauce"],
      ["added salt", "kosher salt", "salt"],
    ]);

    if (ingredients.length > 0) {
      return `Reduce ${joinList(ingredients)} in the base recipe.`;
    }

    return "Reduce added salt in the base recipe.";
  }

  if (fix === "reduce sugar") {
    const ingredients = getEvidenceIngredientTargets(evidenceTexts, [
      ["brown sugar", "white sugar", "granulated sugar", "sugar"],
      ["maple syrup", "honey"],
      ["sweetened coconut", "sweetener"],
    ]);

    if (ingredients.length > 0) {
      return `Reduce ${joinList(ingredients)} in the base recipe.`;
    }

    return "Reduce sugar in the base recipe.";
  }

  if (fix === "add acidity") {
    const acids = getEvidenceIngredientTargets(evidenceTexts, [
      ["lemon juice", "lemon"],
      ["lime juice", "lime"],
      ["vinegar", "rice vinegar", "apple cider vinegar"],
      ["acid", "citrus"],
    ]);

    if (acids.length > 0) {
      return `Add ${joinList(acids)} to brighten and rebalance the base recipe.`;
    }

    return "Add acidity to brighten and rebalance the base recipe.";
  }

  if (fix === "boost umami") {
    return "Deepen savory flavor in the base recipe with more umami-building ingredients or technique.";
  }

  if (fix === "boost flavor" || fix === "increase seasoning") {
    return "Strengthen seasoning and flavor development in the base recipe.";
  }

  if (fix === "increase moisture") {
    return "Increase moisture in the base recipe so the finished dish does not eat dry.";
  }

  return null;
}

function deriveFixSummary(
  recipe: EditorialDecisionLike,
  evidenceTexts: string[] | undefined,
): string | null {
  const fixes = getCanonicalFixes(recipe);
  const confidence = getFixConfidence(recipe)?.toLowerCase();

  if (fixes.length === 0) {
    if (evidenceTexts?.length) {
      return "Readers are making a few recurring adjustments, but the workaround pattern is still limited.";
    }

    return null;
  }

  if (confidence === "high") {
    if (fixes.length > 1) {
      return `Readers consistently correct this by ${fixes[0]}, with ${fixes[1]} as a secondary pattern.`;
    }

    return `Readers consistently correct this by ${fixes[0]}.`;
  }

  if (confidence === "medium") {
    if (fixes.length > 1) {
      return `Readers often compensate by ${fixes[0]} or ${fixes[1]}.`;
    }

    return `Readers often compensate by ${fixes[0]}.`;
  }

  if (confidence === "low") {
    return fixes.length > 1
      ? `Some readers try fixes like ${fixes[0]} or ${fixes[1]}, but the pattern is still mixed.`
      : `Some readers try ${fixes[0]}, but the pattern is still mixed.`;
  }

  return `Some readers try ${fixes[0]}, but the evidence is still limited.`;
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
  const actionState =
    cleanText(recipe.displayIssueActionState) ??
    cleanText(recipe.decision?.issue?.displayIssueActionState);

  if (isManualReviewState(actionState)) {
    return MANUAL_REVIEW_ISSUE;
  }

  return (
    cleanText(recipe.displayIssue) ??
    cleanText(recipe.decision?.issue?.displayIssue) ??
    cleanText(recipe.topNormalizedIssue) ??
    ""
  );
}

export function getRecommendedEditText(
  recipe: EditorialDecisionLike,
  options?: { evidenceTexts?: string[] },
): string {
  const actionState =
    cleanText(recipe.displayIssueActionState) ??
    cleanText(recipe.decision?.issue?.displayIssueActionState);

  if (isManualReviewState(actionState)) {
    return cleanText(recipe.recommendedEdit) ?? cleanText(recipe.decision?.recommendedEdit) ?? MANUAL_REVIEW_EDIT;
  }

  const confidence = getFixConfidence(recipe)?.toLowerCase();
  const canonicalFix = getCanonicalFixes(recipe)[0] ?? null;
  const evidenceBackedSpecificEdit =
    confidence && (confidence === "high" || confidence === "medium")
      ? buildSpecificFixEdit(canonicalFix, options?.evidenceTexts)
      : null;

  return (
    evidenceBackedSpecificEdit ??
    cleanText(recipe.recommendedEditV2) ??
    cleanText(recipe.decision?.recommendedEditV2) ??
    cleanText(recipe.recommendedEdit) ??
    cleanText(recipe.decision?.recommendedEdit) ??
    normalizeLegacyRecommendedEdit(recipe.topModificationPhrase) ??
    ""
  );
}

export function getWhyItMattersText(recipe: EditorialDecisionLike): string {
  const priority = cleanText(recipe.priority) ?? cleanText(recipe.decision?.classification);
  return cleanText(recipe.whyItMatters) ?? cleanText(recipe.decision?.whyItMatters) ?? getDefaultWhyItMatters(priority);
}

export function getConfidenceNote(recipe: EditorialDecisionLike): string | null {
  return cleanText(recipe.displayIssueReason) ?? cleanText(recipe.decision?.issue?.displayIssueReason);
}

export function getInferredBadgeLabel(recipe: EditorialDecisionLike): string | null {
  if (!isInferredState(recipe.displayIssueActionState)) {
    return null;
  }

  const reason = cleanText(recipe.displayIssueReason);
  return reason ?? "Inferred";
}

export function getIssueEvidenceEmptyState(recipe: EditorialDecisionLike): string {
  const actionState =
    cleanText(recipe.displayIssueActionState) ??
    cleanText(recipe.decision?.issue?.displayIssueActionState);
  const issueSource =
    cleanText(recipe.issueSource) ??
    cleanText(recipe.decision?.issue?.issueSource);

  if (isManualReviewState(actionState) || issueSource === "friction_inference") {
    return "No clear recurring issue phrase was extracted. Manual review recommended.";
  }

  if (issueSource === "modification_inference") {
    return "Issue inferred from recurring user modifications. Direct issue phrase matches are limited.";
  }

  return "No directly matched comments found for this issue yet.";
}

export function getFixEvidenceEmptyState(recipe: EditorialDecisionLike): string {
  const actionState =
    cleanText(recipe.displayIssueActionState) ??
    cleanText(recipe.decision?.issue?.displayIssueActionState);
  const issueSource =
    cleanText(recipe.issueSource) ??
    cleanText(recipe.decision?.issue?.issueSource);

  if (isManualReviewState(actionState)) {
    return "Recommended edit is based on manual review guidance rather than a recurring workaround phrase.";
  }

  if (issueSource === "modification_inference") {
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

export function shouldShowLlmSummary(recipe: EditorialDecisionLike): boolean {
  if (typeof recipe.showLlmSummary === "boolean") {
    return recipe.showLlmSummary;
  }

  const strength = cleanText(recipe.llmReadiness?.evidenceStrength)?.toLowerCase();
  const summary = cleanText(recipe.llmEditorSummary);
  const flag = cleanText(recipe.llmEval?.flag)?.toLowerCase();

  return (
    (strength === "medium" || strength === "high") &&
    typeof summary === "string" &&
    summary.length > 0 &&
    flag === "pass"
  );
}

export function getEvidenceStrengthBadge(recipe: EditorialDecisionLike): {
  label: string;
  tone: "default" | "insight" | "success";
} | null {
  const strength = cleanText(recipe.llmReadiness?.evidenceStrength)?.toLowerCase();

  if (!strength) {
    return null;
  }

  if (strength === "high") {
    return { label: "High evidence", tone: "success" };
  }

  if (strength === "medium") {
    return { label: "Medium evidence", tone: "insight" };
  }

  if (strength === "low") {
    return { label: "Low evidence", tone: "default" };
  }

  return { label: "Evidence limited", tone: "default" };
}

export function getAiSummaryPreview(summary: string | null | undefined): string {
  const normalized = cleanText(summary);

  if (!normalized) {
    return "";
  }

  const sentenceMatch = normalized.match(/.+?[.!?](?:\s|$)/);
  const firstSentence = sentenceMatch?.[0]?.trim() ?? normalized;

  return truncateText(firstSentence, 140);
}

export function getIssueConfidenceLabel(recipe: EditorialDecisionLike): string | null {
  const confidence =
    cleanText(recipe.issueConfidence) ??
    cleanText(recipe.decision?.issue?.issueConfidence);
  const issueSource =
    cleanText(recipe.issueSource) ??
    cleanText(recipe.decision?.issue?.issueSource);

  if (!confidence && !issueSource) {
    return null;
  }

  const confidenceLabel = confidence
    ? `${confidence.charAt(0).toUpperCase()}${confidence.slice(1)} confidence`
    : null;

  const sourceLabel =
    issueSource === "phrase"
      ? "Phrase-backed"
      : issueSource === "modification_inference"
        ? "Inferred from modifications"
        : issueSource === "friction_inference"
          ? "Derived from friction signal"
          : issueSource
            ? issueSource.replace(/_/g, " ")
            : null;

  return [confidenceLabel, sourceLabel].filter(Boolean).join(" · ") || null;
}

export function getFixConfidenceLabel(recipe: EditorialDecisionLike): string | null {
  const confidence =
    cleanText(recipe.fixConfidence) ??
    cleanText(recipe.decision?.fixConfidence);

  if (!confidence) {
    return null;
  }

  return `${confidence.charAt(0).toUpperCase()}${confidence.slice(1)} fix confidence`;
}

export function getFixSignalSummaryText(
  recipe: EditorialDecisionLike,
  options?: { evidenceTexts?: string[] },
): string | null {
  const explicit = cleanText(recipe.fixSignalSummary) ?? cleanText(recipe.decision?.fixSignalSummary);
  const derived = deriveFixSummary(recipe, options?.evidenceTexts);

  if (explicit && explicit !== NEGATIVE_FIX_SUMMARY) {
    return explicit;
  }

  if (explicit === NEGATIVE_FIX_SUMMARY && !derived) {
    return "Visible fix evidence is limited, so any workaround pattern is still tentative.";
  }

  return derived ?? (explicit === NEGATIVE_FIX_SUMMARY ? "Visible fix evidence is limited, so any workaround pattern is still tentative." : explicit);
}

export function getEditorialConfidenceTier(
  recipe: EditorialDecisionLike,
): "high" | "medium" | "low" {
  const issueConfidence =
    cleanText(recipe.issueConfidence) ??
    cleanText(recipe.decision?.issue?.issueConfidence);
  const fixConfidence =
    cleanText(recipe.fixConfidence) ??
    cleanText(recipe.decision?.fixConfidence);

  if (issueConfidence === "high" || fixConfidence === "high") {
    return "high";
  }

  if (issueConfidence === "medium" || fixConfidence === "medium") {
    return "medium";
  }

  return "low";
}

export function getEditorialConfidenceNote(recipe: EditorialDecisionLike): string | null {
  const explicitNote = getConfidenceNote(recipe);
  const fixConfidenceLabel = getFixConfidenceLabel(recipe);
  const tier = getEditorialConfidenceTier(recipe);

  if (tier === "high") {
    return explicitNote ?? fixConfidenceLabel ?? "Evidence is consistent enough to support a direct recommendation.";
  }

  if (tier === "medium") {
    return (
      explicitNote ??
      "Evidence points in a clear direction, but some editor judgment is still helpful before revising the base recipe."
    );
  }

  return (
    explicitNote ??
    "Evidence is limited or mixed. Use the issue and supporting comments to guide manual review before making a stronger fix claim."
  );
}

export function getMostCommonComplaintText(recipe: EditorialDecisionLike): string | null {
  const displayIssue = getDisplayIssueText(recipe);
  const issuePhrase =
    cleanText((recipe as { topIssuePhrase?: string | null }).topIssuePhrase) ??
    cleanText(recipe.decision?.issue?.topIssuePhrase);

  if (displayIssue && issuePhrase && issuePhrase.toLowerCase() !== displayIssue.toLowerCase()) {
    return `${toSentenceCase(displayIssue)}. Readers most often describe it as "${issuePhrase}".`;
  }

  return displayIssue ? toSentenceCase(displayIssue) : issuePhrase;
}

export function getMostCommonWorkaroundText(
  recipe: EditorialDecisionLike,
  options?: { evidenceTexts?: string[] },
): string | null {
  const recommendation = getRecommendedEditText(recipe, options);
  const confidence = getFixConfidence(recipe)?.toLowerCase();

  if (!recommendation) {
    return null;
  }

  if (confidence === "low" || !confidence) {
    return `${recommendation} Evidence for this workaround is still limited.`;
  }

  return recommendation;
}

export function getFeedbackConsistencyLabel(
  recipe: EditorialDecisionLike,
  issueEvidenceCount = 0,
  fixEvidenceCount = 0,
): string {
  const confidenceTier = getEditorialConfidenceTier(recipe);
  const evidenceStrength = cleanText(recipe.llmReadiness?.evidenceStrength)?.toLowerCase();

  if (confidenceTier === "high" || evidenceStrength === "high") {
    return "Feedback is highly consistent across the selected comments.";
  }

  if (confidenceTier === "medium" || issueEvidenceCount + fixEvidenceCount >= 4) {
    return "Feedback mostly points in one direction, with a few variations in how readers describe or fix it.";
  }

  if (fixEvidenceCount > 0 || issueEvidenceCount > 0) {
    return "Feedback is mixed or limited, so the evidence supports a cautious editorial read.";
  }

  return "Feedback is sparse, so manual review of the comments matters more than pattern strength.";
}

export function shouldShowRagSection(recipe: EditorialDecisionLike): boolean {
  return recipe.llmReadiness !== undefined && recipe.llmReadiness !== null;
}

export function isRagReady(recipe: EditorialDecisionLike): boolean {
  return Boolean(recipe.llmReadiness?.llmReadyForRag);
}
