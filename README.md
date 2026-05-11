# Comment Intelligence

Recipe website editors often have thousands of user comments, but those comments are hard to act on at scale. The real signal is buried in free text:

- Which recipes are actually failing for readers?
- What kind of problem is happening?
- Are people finding workarounds?
- What should an editor fix first?

This project solves that problem by turning messy recipe comments into structured editorial intelligence for recipe review.

Instead of asking editors to manually read hundreds of comments per recipe, the system:

- detects recurring friction and workaround signals in comments
- rolls those signals up to the recipe level
- keeps representative evidence attached to each recommendation
- suggests what kind of editorial change may be needed
- optionally adds AI summaries and an evidence-backed Q&A layer

The final product is a Next.js interface where the deterministic editorial decision remains the source of truth, supporting evidence remains visible, and AI is only used as a controlled enhancement.

## Problem this project solves

Recipe comments are valuable, but raw comment streams are noisy and difficult to use operationally. A single recipe may have:

- praise mixed with complaints
- vague descriptions of failures
- user modifications that hide the original issue
- workaround suggestions scattered across many comments
- too much volume for an editor to review quickly

Without structure, it is hard to tell whether a recipe has a real quality problem, what the likely issue is, and whether readers have already discovered a fix pattern.

This repo is designed to make that review process faster, more consistent, and easier to trust.

## What the project does

- Cleans and analyzes recipe comments
- Extracts friction, modification, substitution, and repeat-intent signals
- Builds deterministic recipe-level intelligence tables
- Selects representative evidence comments for each recipe
- Packages editorial-ready CSV and JSONL outputs
- Enriches recommendations with canonical user-fix patterns when confidence is sufficient
- Optionally generates short editor summaries with the OpenAI Batch API
- Builds a recipe-level RAG corpus for evidence-backed follow-up questions
- Serves a web UI for dashboard triage and recipe detail review

## Repo structure

- `src/`: Python data pipeline and evaluation scripts
- `data/`: input datasets such as recipe metadata
- `outputs/`: generated CSV and JSONL artifacts
- `web/`: Next.js app for the dashboard and recipe detail views

## Product model

The feature is built as four layers:

1. Raw data layer
2. Deterministic editorial intelligence layer
3. Controlled AI enrichment layer
4. Frontend presentation layer

The core product rule is:

- deterministic decision is the source of truth
- evidence is the trust layer
- LLM summary is optional and gated
- RAG is an evidence explorer, not the decision-maker

## Stack

- Python
- Pandas
- NumPy
- OpenAI API
- spaCy
- RapidFuzz
- Sentence Transformers
- Next.js
- React
- TypeScript

## Setup

This repo expects a local virtual environment at `.venv`.

Install Python dependencies:

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m spacy download en_core_web_sm
```

If you want to run the LLM summary flow, add your API key to `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

Install the web app dependencies:

```bash
cd web
npm install
```

## End-to-end information flow

This is the current feature flow from raw files to the final frontend.

### 1. Build the raw recipe and comment foundations

Primary inputs:

- `data/comments_sample.csv`
- raw recipe metadata and save/session inputs loaded by `src/load_data.py`

Key scripts:

```bash
./.venv/bin/python src/load_data.py
./.venv/bin/python src/clean_comments.py
./.venv/bin/python src/build_recipe_master.py
```

Key outputs:

- `outputs/cleaned_comments.csv`
- `data/recipe_master.csv`

What this stage does:

- cleans raw comment data
- consolidates recipe metadata, pageviews, saves, tags, and optional keyword summaries
- creates the base one-row-per-recipe table used by the frontend

### 2. Extract comment-level behavioral signals

Key script:

```bash
./.venv/bin/python src/tag_comment_signals.py
```

Key output:

- `outputs/comment_signals.csv`

What this stage does:

- tags comment-level friction
- tags modification / workaround behavior
- tags repeat-intent and related signals

### 3. Build recipe-level deterministic intelligence inputs

Key scripts:

```bash
./.venv/bin/python src/build_recipe_comment_features.py
./.venv/bin/python src/build_recipe_top_phrases.py
./.venv/bin/python src/build_recipe_top_phrases_wide.py
./.venv/bin/python src/aggregate_global_friction_phrases.py
./.venv/bin/python src/build_recipe_intelligence.py
```

Key output:

- `outputs/recipe_intelligence.csv`

What this stage does:

- aggregates comment-level signals into recipe-level features
- identifies top issue phrases and behavioral phrases
- maps recipe phrases to normalized issue labels
- computes deterministic fields such as:
  - `classification`
  - `opportunity_score`
  - `display_issue`
  - `issue_confidence`
  - `recommended_edit`
  - `why_it_matters`

This is the backbone deterministic editorial layer.

### 4. Build supporting evidence for editorial review

Key scripts:

```bash
./.venv/bin/python src/build_evidence_candidates.py
./.venv/bin/python src/build_recipe_evidence.py
./.venv/bin/python src/build_editorial_intelligence.py
```

Key outputs:

- `outputs/evidence_candidates.csv`
- `outputs/recipe_evidence.csv`
- `outputs/recipe_evidence.jsonl`
- `outputs/editorial_intelligence.csv`
- `outputs/editorial_intelligence.jsonl`

What this stage does:

- filters and scores candidate evidence comments
- selects top issue, fix, mixed, and adaptation comments per recipe
- merges deterministic intelligence plus evidence into the main editorial object

`editorial_intelligence.jsonl` is the key product-facing structured artifact. It contains:

- `metadata`
- `decision`
- `signals`
- `evidence`
- `llm_readiness`
- `llm_input`

### 5. Build the fix-aware recommendation layer

Key scripts:

```bash
./.venv/bin/python src/export_fix_comments.py
./.venv/bin/python src/extract_raw_fix_phrases.py
./.venv/bin/python src/build_fix_phrase_mapping_template.py
./.venv/bin/python src/apply_fix_phrase_mapping.py
./.venv/bin/python src/apply_fix_phrase_rules.py
./.venv/bin/python src/aggregate_recipe_canonical_fixes.py
./.venv/bin/python src/merge_recipe_canonical_fixes.py
./.venv/bin/python src/build_recommended_edit_with_fixes.py
```

Key outputs:

- `outputs/recipe_canonical_fixes.csv`
- `outputs/editorial_intelligence_with_fixes.csv`
- `outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv`

What this stage does:

- extracts raw workaround/fix language from comments
- maps raw fix phrases to canonical fix families
- aggregates canonical fixes at the recipe level
- enriches deterministic editorial recommendations with:
  - `recommended_edit_v2`
  - `recommended_edit_source`
  - `fix_confidence`
  - `fix_signal_summary`
  - canonical fix fields

This layer sharpens the recommendation, but it does not replace the deterministic issue diagnosis.

## Optional LLM summary workflow

This flow prepares gated recipe records for summarization, submits them to OpenAI, fetches results, and evaluates summary quality.

### 1. Build the batch payload

```bash
./.venv/bin/python src/build_llm_summary_batch.py
```

Outputs:

- `outputs/llm_summary_batch.jsonl`
- `outputs/llm_summary_eval_sample.csv`

### 2. Prepare and submit the batch

```bash
./.venv/bin/python src/generate_llm_editor_summaries_batch.py prepare
./.venv/bin/python src/generate_llm_editor_summaries_batch.py submit
```

### 3. Check status and fetch results

```bash
./.venv/bin/python src/generate_llm_editor_summaries_batch.py status --batch-id <batch_id>
./.venv/bin/python src/generate_llm_editor_summaries_batch.py fetch --batch-id <batch_id>
```

Outputs:

- `outputs/llm_summary_batch_api_input.jsonl`
- `outputs/llm_editor_summaries_batch_raw.jsonl`
- `outputs/llm_editor_summaries.jsonl`

### 4. Evaluate generated summaries

```bash
./.venv/bin/python src/evaluate_llm_summaries.py
```

Outputs:

- `outputs/llm_summary_eval_auto.csv`
- `outputs/llm_summary_eval_flagged.csv`

What this stage does:

- generates optional editor-friendly summaries
- evaluates groundedness, correctness, actionability, and specificity
- supports frontend gating so low-evidence rows do not show AI by default

## Optional RAG workflow

This flow builds an evidence-backed retrieval corpus for focused follow-up questions on the recipe detail page.

### 1. Build the RAG corpus

```bash
./.venv/bin/python src/rag/build_rag_corpus.py
```

Inputs:

- `outputs/editorial_intelligence.jsonl`
- `outputs/recipe_evidence.jsonl`
- `outputs/llm_editor_summaries.jsonl` (optional)

Output:

- `outputs/rag_corpus.jsonl`

### 2. Retrieve or answer against the corpus

```bash
./.venv/bin/python src/rag/retrieve_recipe_evidence.py
./.venv/bin/python src/rag/answer_recipe_question.py
```

### 3. Build and evaluate RAG cases

```bash
./.venv/bin/python src/rag/build_rag_eval_cases.py
./.venv/bin/python src/rag/evaluate_rag_answers.py
```

What this stage does:

- builds retrieval chunks from deterministic fields plus curated evidence
- preserves provenance and recipe context for grounded answers
- supports follow-up questions such as:
  - why is this recipe not working?
  - how are users fixing it?
  - is the feedback mixed?
  - what should the editor change first?

RAG is an exploration layer only. It does not determine the main issue or recommendation.

## Web app

The dashboard lives in `web/` and reads directly from the generated CSV/JSONL artifacts through a local merge layer in `web/lib/data/recipe-master.ts`.

### Frontend input files

- `data/recipe_master.csv`
- `data/comments_sample.csv`
- `outputs/recipe_intelligence.csv`
- `outputs/editorial_intelligence.jsonl`
- `outputs/llm_editor_summaries.jsonl`
- `outputs/llm_summary_eval_auto.csv`
- `outputs/editorial_intelligence_with_fix_aware_recommended_edit.csv`
- `outputs/rag_corpus.jsonl`

### Frontend behavior

The Next.js app merges those files into a unified recipe model and exposes:

- homepage creator selection
- creator dashboard for prioritization
- recipe detail page for deep review

The recipe detail page is intentionally ordered as:

1. Deterministic editorial insight
2. Supporting evidence
3. Ask the evidence (RAG)
4. Editorial summary and raw comments

The frontend preserves the following rules:

- deterministic fields are always primary
- evidence remains visible below the decision layer
- fix-aware text can sharpen recommendations
- AI summary is gated and optional
- RAG is on-demand and evidence-backed

Run it locally:

```bash
cd web
npm run dev
```

Useful commands:

```bash
npm run build
npm run start
npm run lint
```

## Notable scripts

- `src/build_recipe_master.py`: builds the base recipe catalog used by the frontend
- `src/build_recipe_intelligence.py`: merges recipe metadata, comment features, behavioral phrases, and normalized issue labels into the main recipe-level table
- `src/build_evidence_candidates.py`: filters and scores candidate comments that can support an editorial diagnosis
- `src/build_recipe_evidence.py`: selects top issue, fix, mixed, and adaptation comments per recipe
- `src/build_editorial_intelligence.py`: packages recipe intelligence plus evidence into a nested CSV and JSONL schema
- `src/build_recommended_edit_with_fixes.py`: upgrades deterministic recommendations with canonical fix signals when evidence is strong enough
- `src/build_llm_summary_batch.py`: gates and compacts editorial records for LLM summarization
- `src/generate_llm_editor_summaries_batch.py`: submits and retrieves OpenAI Batch API jobs
- `src/evaluate_llm_summaries.py`: runs heuristic checks for groundedness, correctness, actionability, and specificity
- `src/rag/build_rag_corpus.py`: turns editorial intelligence plus evidence into a retrieval corpus
- `web/lib/data/recipe-master.ts`: merges all generated artifacts into the frontend recipe model

## Current end-state

The final user-facing system works like this:

- raw recipe metadata and comments are cleaned and aggregated
- deterministic recipe intelligence is built first
- supporting evidence is selected and attached
- fix-aware recommendation language is added when confidence is sufficient
- optional LLM summaries are generated and evaluated
- optional RAG corpus is built for evidence-backed follow-up questions
- the frontend merges all of these artifacts into a deterministic-first editorial dashboard and recipe detail workflow

## Notes

- Most scripts read from `outputs/` artifacts produced by earlier steps, so running them out of order will usually fail on missing files.
- The LLM summary flow is optional. You can stop at `editorial_intelligence.jsonl` if you only need structured editorial inputs.
- The RAG flow is optional. You can stop before corpus generation if you only need deterministic review plus evidence.
- Some older scripts remain in `src/` for experiments and earlier iterations; the workflow above reflects the current editorial pipeline in this repo.
