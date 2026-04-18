"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Editor } from "@/lib/types";

type EditorSelectCardProps = {
  editors: Editor[];
  ctaLabel: string;
};

export function EditorSelectCard({
  editors,
  ctaLabel,
}: EditorSelectCardProps) {
  const router = useRouter();
  const [selectedEditorId, setSelectedEditorId] = useState("");
  const [query, setQuery] = useState("");

  function handleContinue() {
    if (!selectedEditorId) {
      return;
    }

    router.push(`/editor/${selectedEditorId}`);
  }

  const normalizedQuery = query.trim().toLowerCase();
  const filteredEditors = editors
    .filter((editor) => {
      if (!normalizedQuery) {
        return true;
      }

      return editor.name.toLowerCase().includes(normalizedQuery);
    })
    .slice(0, 8);

  function handleSelectEditor(editor: Editor) {
    setSelectedEditorId(editor.id);
    setQuery(editor.name);
  }

  return (
    <section className="card card-pad editor-select-card">
      <div className="editor-select-grid">
        <div>
          <h2 className="section-title">Select a Recipe Creator</h2>
          <p className="section-copy">
            Start with one creator and jump straight into recipe performance.
          </p>
        </div>

        <div className="input-wrap">
          <label className="label" htmlFor="editor-search">
            Recipe Creator
          </label>
          <div className="combobox">
            <input
              className="text-input"
              id="editor-search"
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedEditorId("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && filteredEditors[0]) {
                  handleSelectEditor(filteredEditors[0]);
                }
              }}
              placeholder="Search by name..."
              type="text"
              value={query}
            />
            <div className="combobox-list" role="listbox" aria-label="Recipe creators">
              {filteredEditors.length === 0 ? (
                <div className="combobox-empty">No recipe creators found.</div>
              ) : (
                filteredEditors.map((editor) => (
                  <button
                    key={editor.id}
                    className={`combobox-option ${
                      selectedEditorId === editor.id ? "active" : ""
                    }`}
                    onClick={() => handleSelectEditor(editor)}
                    type="button"
                  >
                    <span>{editor.name}</span>
                    <span className="combobox-meta">
                      {editor.recipeCount} recipes
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        <button
          className="button"
          disabled={!selectedEditorId}
          onClick={handleContinue}
          type="button"
        >
          {selectedEditorId ? ctaLabel : "Select a recipe creator to continue"}
        </button>
      </div>
    </section>
  );
}
