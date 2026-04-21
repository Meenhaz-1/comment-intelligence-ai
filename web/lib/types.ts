export type Editor = {
  id: string;
  name: string;
  recipeCount: number;
};

export type EvidenceStrength = "none" | "low" | "medium" | "high";

export type RecipeMetadata = {
  title: string | null;
  author: string | null;
  brand: string | null;
  tags: string[];
  url: string | null;
};

export type RecipeDecisionIssue = {
  displayIssue: string | null;
  issueFamily: string | null;
  topIssuePhrase: string | null;
  secondaryIssuePhrase: string | null;
  issueSource: string | null;
  issueConfidence: string | null;
  displayIssueReason: string | null;
  displayIssueActionState: string | null;
};

export type RecipeDecision = {
  classification: string | null;
  opportunityScore: number | null;
  issue: RecipeDecisionIssue;
  recommendedEdit: string | null;
  recommendedEditV2: string | null;
  recommendedEditSource: string | null;
  whyItMatters: string | null;
  fixConfidence: string | null;
  fixSignalSummary: string | null;
  topCanonicalFix1: string | null;
  topCanonicalFix2: string | null;
  topFixFamily1: string | null;
  topFixFamily2: string | null;
};

export type RecipeSignals = {
  totalComments: number;
  eligibleComments: number | null;
  pctFriction: number | null;
  pctModification: number | null;
  pctRepeatIntent: number | null;
  engagementLevel: string | null;
};

export type RecipeEvidence = {
  issueEvidenceComments: string[];
  fixEvidenceComments: string[];
  mixedEvidenceComments: string[];
  adaptationComments: string[];
  hasIssueEvidence: boolean;
  hasFixEvidence: boolean;
  hasMixedEvidence: boolean;
  totalSelectedEvidenceComments: number;
};

export type RecipeLlmReadiness = {
  llmReadyForSummary: boolean | null;
  llmReadyForRag: boolean | null;
  evidenceStrength: EvidenceStrength | null;
};

export type RecipeLlmEval = {
  overallScore: number | null;
  groundedness: number | null;
  correctness: number | null;
  actionability: number | null;
  specificity: number | null;
  flag: string | null;
};

export type RecipeRow = {
  contentId: string;
  editorId: string;
  title: string;
  tags: string[];
  topKeywords: string[];
  topPhrases: string[];
  keywordBuckets: string[];
  priority: string;
  opportunityScore: number | null;
  displayIssue: string | null;
  displayIssueReason: string | null;
  displayIssueActionState: string | null;
  whyItMatters: string | null;
  recommendedEdit: string | null;
  topIssuePhrase: string | null;
  issueSource: string | null;
  issueConfidence: string | null;
  topModificationPhrase: string | null;
  topNormalizedIssue: string | null;
  totalComments: number;
  pctFriction: number | null;
  pctModification: number | null;
  pageviews: number;
  saves: number | null;
  commentsCount: number;
  url: string | null;
  brand: string | null;
  authorName: string;
  authorId: string | null;
  hasSaveFeature: boolean;
  metadata: RecipeMetadata;
  decision: RecipeDecision;
  signals: RecipeSignals;
  evidence: RecipeEvidence | null;
  llmReadiness: RecipeLlmReadiness | null;
  llmEditorSummary: string | null;
  llmEval: RecipeLlmEval | null;
  showLlmSummary: boolean | null;
  recommendedEditV2: string | null;
  recommendedEditSource: string | null;
  fixConfidence: string | null;
  fixSignalSummary: string | null;
  topCanonicalFix1: string | null;
  topCanonicalFix2: string | null;
  topFixFamily1: string | null;
  topFixFamily2: string | null;
};

export type DashboardRecipeRow = RecipeRow & {
  saveRate: number | null;
  saveRateTier: "high" | "medium" | "low" | "na";
  interpretationLabel: "Low Conversion" | "High Performer" | "Highly Discussed" | "Low Visibility";
};

export type RecipeComment = {
  id: string;
  contentId: string;
  text: string;
  createdAt: string | null;
  displayName: string;
  location: string | null;
  authorId: string | null;
  willPrepareAgain: string | null;
};

export type EditorDashboardData = {
  editor: Editor;
  totalRecipes: number;
  totalPageviews: number;
  totalSaves: number;
  totalPageviewsFormatted: string;
  totalSavesFormatted: string;
  topRecipesToFix: DashboardRecipeRow[];
  highestReach: DashboardRecipeRow[];
  highestIntent: DashboardRecipeRow[];
  highReachLowConversion: DashboardRecipeRow[];
  topByPageviews: DashboardRecipeRow[];
  topBySaves: DashboardRecipeRow[];
  recipes: DashboardRecipeRow[];
};

export type RecipeDetailData = {
  recipe: DashboardRecipeRow;
  comments: RecipeComment[];
};

export type RagQueryType = "issue" | "fix" | "mixed" | "editorial";

export type RagSupportingEvidenceItem = {
  id: string;
  text: string;
  label?: string;
  chunkType?: string;
};

export type RagAnswer = {
  question: string;
  answer: string;
  queryType: RagQueryType;
  confidence?: "high" | "medium" | "low";
  evidenceStrength?: EvidenceStrength;
  supportingEvidence: RagSupportingEvidenceItem[];
};

export type EditorialSummary = {
  mostCommonComplaint: string | null;
  mostCommonWorkaround: string | null;
  feedbackConsistency: string | null;
  strongestComments: RagSupportingEvidenceItem[];
};
