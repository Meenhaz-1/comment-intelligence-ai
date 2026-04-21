"use client";

import { useState } from "react";

import { DashboardRecipeRow, RagAnswer, RagQueryType } from "@/lib/types";
import { isRagReady } from "@/lib/utils/editorial";

import { RagAnswerPanel } from "./rag-answer-panel";
import { RagEmptyState } from "./rag-empty-state";
import { RagQuestionChips } from "./rag-question-chips";

type RagState =
  | { status: "idle" }
  | { status: "loading"; queryType: RagQueryType; question: string }
  | { status: "success"; queryType: RagQueryType; question: string; answer: RagAnswer }
  | { status: "error"; queryType: RagQueryType; question: string; message: string };

export function RagExploration({ recipe }: { recipe: DashboardRecipeRow }) {
  const [state, setState] = useState<RagState>({ status: "idle" });

  async function handleSelect(selection: { label: string; queryType: RagQueryType }) {
    const { label, queryType } = selection;
    setState({ status: "loading", queryType, question: label });

    try {
      const response = await fetch(`/api/recipe/${recipe.contentId}/rag`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ queryType, question: label }),
      });

      const payload = (await response.json().catch(() => ({}))) as
        | RagAnswer
        | { error?: string };

      if (!response.ok || !("answer" in payload)) {
        throw new Error(
          payload && "error" in payload && payload.error
            ? payload.error
            : "Unable to retrieve evidence-backed analysis right now.",
        );
      }

      setState({ status: "success", queryType, question: label, answer: payload });
    } catch (error) {
      setState({
        status: "error",
        queryType,
        question: label,
        message:
          error instanceof Error
            ? error.message
            : "Unable to retrieve evidence-backed analysis right now.",
      });
    }
  }

  if (!recipe.llmReadiness) {
    return null;
  }

  return (
    <section className="card card-pad detail-section rag-section">
      <div className="detail-section-head">
        <div>
          <h2 className="section-title">Ask the evidence</h2>
          <div className="section-kicker">Focused follow-up, grounded in comments</div>
        </div>
      </div>

      {isRagReady(recipe) ? (
        <>
          <p className="section-copy rag-intro">
            Use one of these focused questions to inspect what the evidence supports before making a final editorial call.
          </p>
          <RagQuestionChips
            activeQueryType={state.status === "idle" ? null : state.queryType}
            disabled={state.status === "loading"}
            onSelect={handleSelect}
          />

          {state.status === "idle" ? (
            <RagEmptyState
              title="Choose a question"
              description="Start with a focused prompt to inspect grounded evidence without replacing the main editorial recommendation."
            />
          ) : null}

          {state.status === "loading" ? (
            <div className="rag-loading-state">
              <div className="rag-loading-bar" />
              <div className="detail-muted">
                Pulling the most relevant evidence for: {state.question}
              </div>
            </div>
          ) : null}

          {state.status === "success" ? <RagAnswerPanel answer={state.answer} /> : null}

          {state.status === "error" ? (
            <div className="rag-error-state">
              <p className="detail-muted">{state.message}</p>
              <button
                className="button secondary-button"
                onClick={() => handleSelect({ label: state.question, queryType: state.queryType })}
                type="button"
              >
                Retry question
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <RagEmptyState
          title="Limited mode"
          description="Limited evidence available for deeper analysis. Review the supporting comments directly."
        />
      )}
    </section>
  );
}
