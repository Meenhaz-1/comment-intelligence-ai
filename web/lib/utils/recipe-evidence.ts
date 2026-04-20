import { DashboardRecipeRow, RecipeComment } from "@/lib/types";
import {
  getDisplayIssueText,
  getRecommendedEditText,
  isManualReviewState,
} from "@/lib/utils/editorial";

const STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "but",
  "by",
  "for",
  "from",
  "how",
  "if",
  "in",
  "into",
  "is",
  "it",
  "its",
  "of",
  "on",
  "or",
  "that",
  "the",
  "this",
  "to",
  "too",
  "very",
  "was",
  "with",
]);

export type EvidenceMatch = {
  comment: RecipeComment;
  matchedTerms: string[];
  score: number;
};

function normalizeText(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function tokenize(value: string): string[] {
  return normalizeText(value)
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token));
}

function scoreComment(comment: RecipeComment, phrase: string): EvidenceMatch | null {
  const normalizedPhrase = normalizeText(phrase);

  if (!normalizedPhrase) {
    return null;
  }

  const normalizedComment = normalizeText(comment.text);
  const phraseTokens = [...new Set(tokenize(phrase))];
  const matchedTerms = phraseTokens.filter((token) => normalizedComment.includes(token));
  const hasExactPhrase = normalizedComment.includes(normalizedPhrase);
  const score = (hasExactPhrase ? 100 : 0) + matchedTerms.length * 10;

  if (score === 0) {
    return null;
  }

  return {
    comment,
    matchedTerms: hasExactPhrase ? [phrase, ...matchedTerms] : matchedTerms,
    score,
  };
}

function getEvidenceMatches(
  phrase: string,
  comments: RecipeComment[],
  excludedIds: Set<string> = new Set(),
): EvidenceMatch[] {
  return comments
    .filter((comment) => !excludedIds.has(comment.id))
    .map((comment) => scoreComment(comment, phrase))
    .filter((match): match is EvidenceMatch => match !== null)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      const leftTime = left.comment.createdAt ? Date.parse(left.comment.createdAt) : 0;
      const rightTime = right.comment.createdAt ? Date.parse(right.comment.createdAt) : 0;
      return rightTime - leftTime;
    })
    .slice(0, 4);
}

export function getEvidenceCommentsForIssue(
  recipe: Pick<DashboardRecipeRow, "displayIssue" | "displayIssueActionState" | "topIssuePhrase" | "topNormalizedIssue" | "issueSource">,
  comments: RecipeComment[],
): EvidenceMatch[] {
  if (
    isManualReviewState(recipe.displayIssueActionState) ||
    recipe.issueSource === "friction_inference"
  ) {
    return [];
  }

  const phrases = [recipe.topIssuePhrase, getDisplayIssueText(recipe)]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));

  if (phrases.length === 0) {
    return [];
  }

  const seen = new Map<string, EvidenceMatch>();

  for (const phrase of phrases) {
    for (const match of getEvidenceMatches(phrase, comments)) {
      const existing = seen.get(match.comment.id);
      if (!existing || match.score > existing.score) {
        seen.set(match.comment.id, match);
      }
    }
  }

  return [...seen.values()]
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      const leftTime = left.comment.createdAt ? Date.parse(left.comment.createdAt) : 0;
      const rightTime = right.comment.createdAt ? Date.parse(right.comment.createdAt) : 0;
      return rightTime - leftTime;
    })
    .slice(0, 4);
}

export function getEvidenceCommentsForFix(
  recipe: Pick<DashboardRecipeRow, "displayIssueActionState" | "recommendedEdit" | "topModificationPhrase">,
  comments: RecipeComment[],
  excludedIds: Set<string> = new Set(),
): EvidenceMatch[] {
  if (isManualReviewState(recipe.displayIssueActionState)) {
    return [];
  }

  const phrases = [recipe.topModificationPhrase, getRecommendedEditText(recipe)]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));

  if (phrases.length === 0) {
    return [];
  }

  const seen = new Map<string, EvidenceMatch>();

  for (const phrase of phrases) {
    for (const match of getEvidenceMatches(phrase, comments, excludedIds)) {
      const existing = seen.get(match.comment.id);
      if (!existing || match.score > existing.score) {
        seen.set(match.comment.id, match);
      }
    }
  }

  return [...seen.values()]
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      const leftTime = left.comment.createdAt ? Date.parse(left.comment.createdAt) : 0;
      const rightTime = right.comment.createdAt ? Date.parse(right.comment.createdAt) : 0;
      return rightTime - leftTime;
    })
    .slice(0, 4);
}

export function buildEvidenceExcerpt(text: string, matchedTerms: string[]): string {
  const trimmed = text.trim();

  if (trimmed.length <= 220) {
    return trimmed;
  }

  const normalizedText = trimmed.toLowerCase();
  const firstMatch = matchedTerms
    .map((term) => term.toLowerCase())
    .find((term) => normalizedText.includes(term));

  if (!firstMatch) {
    return `${trimmed.slice(0, 217).trimEnd()}...`;
  }

  const matchIndex = normalizedText.indexOf(firstMatch);
  const start = Math.max(0, matchIndex - 80);
  const end = Math.min(trimmed.length, matchIndex + 140);
  const excerpt = trimmed.slice(start, end).trim();

  return `${start > 0 ? "... " : ""}${excerpt}${end < trimmed.length ? " ..." : ""}`;
}
