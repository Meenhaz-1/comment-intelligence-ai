export type Editor = {
  id: string;
  name: string;
  recipeCount: number;
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
