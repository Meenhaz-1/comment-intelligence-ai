import { RagAnswer } from "@/lib/types";

import { ConfidencePill } from "./confidence-pill";
import { EvidenceSnippetList } from "./evidence-snippet-list";

export function RagAnswerPanel({
  answer,
}: {
  answer: RagAnswer;
}) {
  return (
    <div className="rag-answer-panel">
      <div className="rag-answer-head">
        <div>
          <div className="label">Question</div>
          <div className="rag-question">{answer.question}</div>
        </div>
        <div className="rag-answer-meta">
          {answer.confidence ? (
            <ConfidencePill
              label={`${answer.confidence.charAt(0).toUpperCase()}${answer.confidence.slice(1)} confidence`}
              tone={answer.confidence}
            />
          ) : null}
          {answer.evidenceStrength && answer.evidenceStrength !== "none" ? (
            <span className="insight-helper-chip">
              {answer.evidenceStrength.charAt(0).toUpperCase()}
              {answer.evidenceStrength.slice(1)} evidence
            </span>
          ) : null}
        </div>
      </div>

      <p className="rag-answer-copy">{answer.answer}</p>

      <div className="label">Supporting evidence</div>
      <EvidenceSnippetList items={answer.supportingEvidence} />
    </div>
  );
}
