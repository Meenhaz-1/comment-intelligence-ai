import "server-only";

import fs from "node:fs";
import path from "node:path";

import { RagAnswer, RagQueryType, RagSupportingEvidenceItem, RecipeRow } from "@/lib/types";

type RagChunk = {
  chunk_id: string;
  recipe_id: string;
  chunk_type: string;
  evidence_type: string;
  evidence_strength?: string;
  issue_confidence?: string;
  display_issue?: string;
  recommended_edit?: string;
  why_it_matters?: string;
  text: string;
  retrieval_text: string;
};

let ragCorpusCache: RagChunk[] | null = null;

const QUERY_TEXT: Record<RagQueryType, string> = {
  issue: "Why is this recipe not working?",
  fix: "How are users fixing it?",
  mixed: "Is the feedback consistent or mixed?",
  editorial: "What should the editor change first?",
};

const EVIDENCE_LABELS: Record<string, string> = {
  issue: "Issue evidence",
  problem_solving_fix: "Fix evidence",
  mixed: "Mixed evidence",
  adaptation: "Adaptation",
  recommended_edit: "Editorial recommendation",
  why_it_matters: "Why it matters",
  summary: "Summary context",
};

function getRagCorpusPath() {
  return path.resolve(process.cwd(), "../outputs/rag_corpus.jsonl");
}

function loadRagCorpus(): RagChunk[] {
  if (ragCorpusCache) {
    return ragCorpusCache;
  }

  const filePath = getRagCorpusPath();

  if (!fs.existsSync(filePath)) {
    ragCorpusCache = [];
    return ragCorpusCache;
  }

  ragCorpusCache = fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as RagChunk];
      } catch {
        return [];
      }
    });

  return ragCorpusCache;
}

function normalizeText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function tokenize(value: string) {
  return normalizeText(value)
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length > 1);
}

function scoreChunk(chunk: RagChunk, queryText: string, queryType: RagQueryType) {
  const queryTokens = tokenize(queryText);
  const retrievalTokens = tokenize(chunk.retrieval_text || chunk.text || "");
  const textTokens = tokenize(chunk.text || "");
  const queryTokenSet = new Set(queryTokens);

  const overlap = retrievalTokens.filter((token) => queryTokenSet.has(token)).length;
  const textOverlap = textTokens.filter((token) => queryTokenSet.has(token)).length;

  let score = overlap * 2 + textOverlap * 3;

  if (queryType === "issue") {
    if (chunk.evidence_type === "issue") score += 6;
    if (chunk.evidence_type === "mixed") score += 2;
  }

  if (queryType === "fix") {
    if (chunk.evidence_type === "problem_solving_fix") score += 6;
    if (chunk.evidence_type === "adaptation") score += 3;
    if (chunk.evidence_type === "recommended_edit") score += 2;
  }

  if (queryType === "mixed" && chunk.evidence_type === "mixed") {
    score += 7;
  }

  if (queryType === "editorial") {
    if (chunk.chunk_type === "decision") score += 7;
    if (chunk.evidence_type === "recommended_edit") score += 6;
    if (chunk.evidence_type === "why_it_matters") score += 4;
    if (chunk.evidence_type === "issue") score += 3;
  }

  if (chunk.evidence_strength === "high") score += 2;
  if (chunk.evidence_strength === "medium") score += 1;
  if (chunk.issue_confidence === "high") score += 1.5;
  if (chunk.issue_confidence === "medium") score += 0.75;

  return score;
}

function retrieveChunks(recipeId: string, queryText: string, queryType: RagQueryType) {
  return loadRagCorpus()
    .filter((chunk) => chunk.recipe_id === recipeId)
    .map((chunk) => ({ chunk, score: scoreChunk(chunk, queryText, queryType) }))
    .sort((left, right) => right.score - left.score)
    .map((entry) => entry.chunk);
}

function compactSnippet(text: string, maxLength = 220) {
  const normalized = text.trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}

function collectEvidence(chunks: RagChunk[], queryType: RagQueryType): RagSupportingEvidenceItem[] {
  const preferredTypes =
    queryType === "issue"
      ? ["issue", "mixed"]
      : queryType === "fix"
        ? ["problem_solving_fix", "adaptation", "recommended_edit"]
        : queryType === "mixed"
          ? ["mixed", "issue", "problem_solving_fix"]
          : ["recommended_edit", "why_it_matters", "issue", "problem_solving_fix"];

  const ranked = chunks
    .filter((chunk) => preferredTypes.includes(chunk.evidence_type) || chunk.chunk_type === "evidence")
    .slice(0, 4);

  return ranked.map((chunk) => ({
    id: chunk.chunk_id,
    text: compactSnippet(chunk.text),
    label: EVIDENCE_LABELS[chunk.evidence_type] ?? "Supporting evidence",
    chunkType: chunk.chunk_type === "decision" ? "Decision layer" : "Comment evidence",
  }));
}

function deriveConfidence(recipe: RecipeRow, queryType: RagQueryType): "high" | "medium" | "low" {
  const relevantConfidence =
    queryType === "fix" ? recipe.fixConfidence : recipe.issueConfidence;

  if (relevantConfidence === "high") {
    return "high";
  }

  if (
    relevantConfidence === "medium" ||
    recipe.llmReadiness?.evidenceStrength === "high"
  ) {
    return "medium";
  }

  return "low";
}

function buildAnswerText(
  recipe: RecipeRow,
  queryType: RagQueryType,
  supportingEvidence: RagSupportingEvidenceItem[],
): string {
  const issue = recipe.displayIssue || "the main recurring problem";
  const recommendedEdit = recipe.recommendedEditV2 || recipe.recommendedEdit || "";
  const whyItMatters = recipe.whyItMatters || "";
  const fixSignalSummary = recipe.fixSignalSummary || "";
  const evidenceLead = supportingEvidence[0]?.text
    ? `"${compactSnippet(supportingEvidence[0].text, 120)}"`
    : null;

  if (queryType === "issue") {
    const lines = [
      `The clearest recurring issue is ${issue}.`,
      evidenceLead ? `The strongest supporting comments point to ${evidenceLead}.` : null,
      recipe.llmReadiness?.evidenceStrength === "low" || recipe.issueConfidence === "low"
        ? "The evidence is still limited, so this should be reviewed against the broader comment set."
        : null,
    ];
    return lines.filter(Boolean).join(" ");
  }

  if (queryType === "fix") {
    const lines = [
      fixSignalSummary || "Readers are trying a few recurring fixes, but the pattern is not perfectly consistent.",
      recommendedEdit
        ? `The safest editorial change is still ${recommendedEdit.charAt(0).toLowerCase()}${recommendedEdit.slice(1)}`
        : null,
      recipe.fixConfidence === "low"
        ? "Fix evidence is weak, so treat user workarounds as hints rather than a definitive rewrite."
        : null,
    ];
    return lines.filter(Boolean).join(" ");
  }

  if (queryType === "mixed") {
    const lines = [
      "Feedback is not fully consistent.",
      supportingEvidence.length > 1
        ? `Some comments reinforce ${issue}, while others show workaround behavior or mixed outcomes.`
        : `There is not enough evidence yet to separate a single dominant issue from general user adaptation.`,
      recipe.llmReadiness?.evidenceStrength !== "high"
        ? "Treat this as a review aid, not a final call."
        : null,
    ];
    return lines.filter(Boolean).join(" ");
  }

  const lines = [
    recommendedEdit
      ? `Start with ${recommendedEdit.charAt(0).toLowerCase()}${recommendedEdit.slice(1)}`
      : "Start by reviewing the strongest supporting comments before changing the base recipe.",
    whyItMatters,
    fixSignalSummary || null,
  ];
  return lines.filter(Boolean).join(" ");
}

export function buildRagAnswer(
  recipe: RecipeRow,
  queryType: RagQueryType,
  questionOverride?: string,
): RagAnswer | null {
  const question = questionOverride?.trim() || QUERY_TEXT[queryType];
  const chunks = retrieveChunks(recipe.contentId, question, queryType);
  const supportingEvidence = collectEvidence(chunks, queryType);

  if (supportingEvidence.length === 0) {
    return null;
  }

  return {
    question,
    queryType,
    answer: buildAnswerText(recipe, queryType, supportingEvidence),
    confidence: deriveConfidence(recipe, queryType),
    evidenceStrength: recipe.llmReadiness?.evidenceStrength ?? "none",
    supportingEvidence,
  };
}
