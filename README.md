# Comment Intelligence

This project turns recipe comments into structured product and editorial signals.

It combines rule-based text processing, recipe-level aggregation, evidence selection, and optional OpenAI-generated summaries to help identify recipes that are performing well, need improvement, or need a closer editorial review. The repo also includes a Next.js dashboard for browsing recipe and editor-level outputs.

## What the project does

- Cleans and analyzes recipe comments
- Extracts friction, modification, substitution, and repeat-intent signals
- Builds recipe-level intelligence tables
- Selects representative evidence comments for each recipe
- Packages editorial-ready JSON for downstream review
- Optionally generates short editor summaries with the OpenAI Batch API
- Serves a web UI for exploring recipe intelligence outputs

## Repo structure

- `src/`: Python data pipeline and evaluation scripts
- `data/`: input datasets such as recipe metadata
- `outputs/`: generated CSV and JSONL artifacts
- `web/`: Next.js app for the dashboard and recipe detail views

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

## Core pipeline

The repo has a few parallel analysis paths, but this is the most useful end-to-end sequence for the current editorial workflow.

### 1. Load and clean comments

```bash
./.venv/bin/python src/load_data.py
./.venv/bin/python src/clean_comments.py
./.venv/bin/python src/extract_insights.py
./.venv/bin/python src/analyze_insights.py
./.venv/bin/python src/cluster_insights.py
./.venv/bin/python src/tag_comment_signals.py
```

### 2. Build recipe-level intelligence inputs

```bash
./.venv/bin/python src/build_recipe_comment_features.py
./.venv/bin/python src/build_recipe_top_phrases.py
./.venv/bin/python src/build_recipe_top_phrases_wide.py
./.venv/bin/python src/aggregate_global_friction_phrases.py
./.venv/bin/python src/build_recipe_intelligence.py
```

Key output:

- `outputs/recipe_intelligence.csv`

### 3. Build evidence for editorial review

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

## Optional LLM summary workflow

This flow prepares batch-ready prompts, submits them to OpenAI, fetches results, and evaluates summary quality.

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

## Web app

The dashboard lives in `web/` and reads from mock data plus recipe/editorial utility layers.

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

- `src/build_recipe_intelligence.py`: merges recipe metadata, comment features, behavioral phrases, and normalized issue labels into the main recipe-level table
- `src/build_evidence_candidates.py`: filters and scores candidate comments that can support an editorial diagnosis
- `src/build_recipe_evidence.py`: selects top issue, fix, mixed, and adaptation comments per recipe
- `src/build_editorial_intelligence.py`: packages recipe intelligence plus evidence into a nested CSV and JSONL schema
- `src/build_llm_summary_batch.py`: gates and compacts editorial records for LLM summarization
- `src/generate_llm_editor_summaries_batch.py`: submits and retrieves OpenAI Batch API jobs
- `src/evaluate_llm_summaries.py`: runs heuristic checks for groundedness, correctness, actionability, and specificity

## Notes

- Most scripts read from `outputs/` artifacts produced by earlier steps, so running them out of order will usually fail on missing files.
- The LLM summary flow is optional. You can stop at `editorial_intelligence.jsonl` if you only need structured editorial inputs.
- Some older scripts remain in `src/` for experiments and earlier iterations; the workflow above reflects the current editorial pipeline in this repo.
