"use client";

import { useState } from "react";

import { RagSupportingEvidenceItem } from "@/lib/types";

function truncateSnippet(text: string, maxLength = 220) {
  const normalized = text.trim();

  if (normalized.length <= maxLength) {
    return { text: normalized, truncated: false };
  }

  return {
    text: `${normalized.slice(0, maxLength - 1).trimEnd()}…`,
    truncated: true,
  };
}

export function EvidenceSnippetList({
  items,
  highlight,
  emptyLabel,
}: {
  items: RagSupportingEvidenceItem[];
  highlight?: string | null;
  emptyLabel?: string;
}) {
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  if (items.length === 0) {
    return <div className="detail-muted evidence-empty">{emptyLabel ?? "No supporting evidence available."}</div>;
  }

  return (
    <div className="evidence-list">
      {items.map((item) => {
        const isExpanded = Boolean(expandedIds[item.id]);
        const { text, truncated } = truncateSnippet(item.text);
        const content = isExpanded || !truncated ? item.text : text;
        const highlighted = highlight?.trim().toLowerCase();
        const highlightIndex =
          highlighted && content.toLowerCase().includes(highlighted)
            ? content.toLowerCase().indexOf(highlighted)
            : -1;

        return (
          <article className="evidence-card" key={item.id}>
            {item.label || item.chunkType ? (
              <div className="evidence-topline">
                <div className="evidence-author">{item.label ?? "Supporting evidence"}</div>
                {item.chunkType ? (
                  <div className="comment-date">{item.chunkType}</div>
                ) : null}
              </div>
            ) : null}
            <p className="evidence-body">
              {highlightIndex >= 0 ? (
                <>
                  <span>{content.slice(0, highlightIndex)}</span>
                  <mark className="evidence-mark">
                    {content.slice(highlightIndex, highlightIndex + highlighted!.length)}
                  </mark>
                  <span>{content.slice(highlightIndex + highlighted!.length)}</span>
                </>
              ) : (
                content
              )}
            </p>
            {truncated ? (
              <button
                className="evidence-toggle"
                onClick={() =>
                  setExpandedIds((current) => ({ ...current, [item.id]: !current[item.id] }))
                }
                type="button"
              >
                {isExpanded ? "Show less" : "Read more"}
              </button>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
