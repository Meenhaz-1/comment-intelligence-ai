# Technical Implementation Document

## Purpose
This document explains how Epicurious Comment Intelligence is implemented today, why the system is structured this way, and what trade-offs the current architecture makes.

It is intended to complement [PRD.md](./PRD.md) by focusing less on product requirements and more on engineering decisions, implementation boundaries, and operational implications.

## Executive Summary
The system is built as a deterministic-first analytics pipeline with optional AI augmentation layered on top. The implementation favors:
- inspectability over abstraction
- file-based artifacts over service orchestration
- rule-based editorial diagnosis over model-first classification
- bounded evidence selection over raw comment dumps
- local read-time composition in the web app over a separate backend service

These choices make the system relatively easy to audit, iterate on, and debug for an MVP or internal tool. The trade-off is that some parts of the system are less scalable, less automated, and less flexible than a productionized service architecture.

## Implementation Goals
The current implementation appears optimized for five engineering goals:

1. Make editorial decisions explainable.
2. Preserve a visible chain from raw comment to recommendation.
3. Keep optional AI outputs subordinate to deterministic outputs.
4. Let the team iterate quickly with CSV/JSONL artifacts.
5. Support an internal review workflow without requiring a full platform rewrite.

## System Overview
The project has two main runtime layers:

1. Python data pipeline in `src/`
2. Next.js presentation layer in `web/`

The pipeline reads raw inputs, materializes intermediate artifacts, and produces product-facing outputs. The web app reads those artifacts directly from disk and builds a recipe-level read model for dashboard and detail experiences.

This is not a service-oriented architecture. It is a batch-oriented artifact pipeline plus a thin application layer.

## Core Architectural Choice: Deterministic-First
### Choice
The main editorial diagnosis is computed with deterministic heuristics and aggregations rather than delegated to an LLM.

Key implementation points:
- `src/build_recipe_intelligence.py` computes recipe classification, issue inference, and recommendation fields.
- Phrase lookups from `outputs/global_friction_phrases_labeled.csv` are used to map comment language to normalized issues.
- Heuristic fallbacks infer issues from modification patterns when phrase-backed evidence is weak or absent.

### Why this choice is strong
- Easier to debug than model outputs.
- Safer for editorial decision-making.
- Produces stable outputs across runs.
- Makes reasoning traceable to phrases, scores, and thresholds.

### Trade-offs
- Lower recall on novel or paraphrased user language.
- More manual upkeep for mappings and thresholds.
- Harder to generalize across new content styles without expanding rules.

### Alternative considered implicitly
A model-first classifier could infer issues directly from comments.

Why it was not chosen as the primary layer:
- Lower trust for editorial decisions.
- Harder to guarantee consistency.
- More expensive and harder to evaluate at scale.

## Core Architectural Choice: Evidence as a First-Class Layer
### Choice
The system does not stop at classification. It separately constructs an evidence layer through:
- `src/build_evidence_candidates.py`
- `src/build_recipe_evidence.py`
- `src/build_editorial_intelligence.py`

The product-facing object includes selected comment evidence, not just a diagnosis.

### Why this choice is strong
- Supports editorial trust and reviewability.
- Reduces black-box behavior.
- Creates a bridge between structured signals and raw community language.
- Enables downstream AI prompts to be grounded in curated evidence rather than full comment dumps.

### Trade-offs
- Evidence selection can accidentally hide useful edge-case comments.
- A small cap on surfaced comments improves usability but reduces completeness.
- Scoring logic can overfit to known issue phrasing patterns.

### Notable implementation detail
The evidence layer is intentionally bounded. Current per-recipe caps are:
- 2 issue comments
- 2 fix comments
- 1 mixed comment
- 1 adaptation comment

This is a clear usability-over-completeness choice.

## Core Architectural Choice: Artifact-Driven Pipeline
### Choice
The system writes many intermediate CSV and JSONL artifacts rather than passing everything through a database or a long-running service.

Examples:
- `data/recipe_master.csv`
- `outputs/comment_signals.csv`
- `outputs/recipe_intelligence.csv`
- `outputs/editorial_intelligence.jsonl`
- `outputs/rag_corpus.jsonl`

### Why this choice is strong
- Easy to inspect outputs by hand.
- Easy to run stages independently.
- Low infrastructure overhead.
- Good fit for exploratory analytics and editorial prototyping.

### Trade-offs
- Run order matters and can fail silently when artifacts are stale.
- Schema drift is easy unless explicitly tested.
- Concurrency, lineage tracking, and reproducibility are weaker than in orchestrated systems.
- Large datasets will eventually become cumbersome in flat files.

### Alternative considered implicitly
Use a relational database, data warehouse, or object-store-backed processing stack.

Why the current approach still makes sense
- Faster to build.
- Easier for local development.
- Better aligned with a team still exploring logic and thresholds.

## Core Architectural Choice: Local Read Model in the Web App
### Choice
The Next.js app reads local artifacts directly from disk via `web/lib/data/recipe-master.ts` instead of calling a backend API for most data access.

### Why this choice is strong
- Minimal moving parts.
- No separate backend deployment needed for MVP.
- Read model can flexibly merge multiple artifact types at request time.
- Easy to recover from missing optional layers by falling back to deterministic fields.

### Trade-offs
- Tight coupling between web app and artifact file layout.
- Harder to scale to remote deployment or multi-user access patterns.
- Caching, invalidation, and freshness are manual concerns.
- The web layer becomes responsible for schema normalization that might belong in a backend.

### Consequence
`web/lib/data/recipe-master.ts` is effectively both:
- a file loader
- a schema adapter
- a composition layer
- part of the business logic surface

That is convenient for speed, but it centralizes a lot of responsibility into one file.

## Core Architectural Choice: Optional AI as Controlled Enhancement
### Choice
AI is present in two places:
- summary generation via batch workflow
- RAG-style evidence exploration in the detail experience

It is not the source of truth for main editorial decisions.

### Why this choice is strong
- Keeps AI in high-value, lower-risk roles.
- Makes AI output easier to gate based on evidence strength.
- Avoids replacing structured logic with difficult-to-audit generation.

### Trade-offs
- AI may feel underpowered compared to a full conversational assistant.
- The separation between deterministic and AI layers increases implementation complexity.
- There is some duplication between deterministic recommendation copy and AI-generated explanatory text.

## LLM Summary Design
### Choice
Summaries are built from pre-structured editorial records and run through the OpenAI Batch API.

Relevant scripts:
- `src/build_llm_summary_batch.py`
- `src/generate_llm_editor_summaries_batch.py`
- `src/evaluate_llm_summaries.py`

### Why this choice is strong
- Batch mode reduces cost and operational overhead versus interactive generation.
- Compact structured prompts are easier to control.
- Evaluation scripts reinforce groundedness expectations.

### Trade-offs
- Summaries are not real-time.
- Batch workflows add asynchronous operational steps.
- Evaluation is heuristic and may not catch all quality failures.

### Important product/engineering choice
Low-evidence rows are not meant to show AI by default. This protects trust, but it also reduces coverage.

## RAG Design
### Choice
The RAG implementation is lightweight and recipe-scoped:
- `src/rag/build_rag_corpus.py` builds retrieval chunks.
- `web/lib/server/rag.ts` performs lexical retrieval and synthesizes answer text.
- `web/app/api/recipe/[contentId]/rag/route.ts` enforces readiness and response behavior.

### Why this choice is strong
- Keeps retrieval grounded in known artifacts.
- Fast to implement.
- Works well for constrained question types.
- Easier to understand than a full semantic retrieval stack.

### Trade-offs
- Lexical retrieval is weaker on paraphrase and semantic similarity.
- Retrieval quality depends heavily on chunk wording.
- Answer generation is partly template-based, which improves consistency but limits nuance.

### Alternative considered implicitly
Embedding-based semantic search using `sentence-transformers` or OpenAI embeddings.

Why lexical retrieval may have been preferred initially
- Lower implementation overhead.
- No embedding pipeline to maintain.
- Easier debugging and deterministic scoring behavior.

## Signal Extraction Design
### Choice
Comment understanding is heavily driven by regex patterns and rule libraries.

Examples appear in:
- `src/tag_comment_signals.py`
- `src/build_evidence_candidates.py`

### Why this choice is strong
- Transparent and editable by engineers and analysts.
- Fast to run locally.
- Easy to target specific known issue families.

### Trade-offs
- Brittle against language drift.
- Hard to scale elegantly as taxonomy grows.
- Precision and recall depend on constant rule maintenance.

### Key implementation implication
Rule sets are not just helpers; they are part of the product logic. That means they should eventually be treated as versioned configuration, not merely inline script constants.

## Recommendation Layer Design
### Choice
Recommendations are generated in two stages:

1. Deterministic issue-driven recommendation
2. Optional fix-aware rewrite when canonical fix evidence is strong enough

Relevant script:
- `src/build_recommended_edit_with_fixes.py`

### Why this choice is strong
- Preserves a stable baseline recommendation.
- Allows user workaround patterns to improve wording and specificity.
- Avoids letting noisy fixes overtake the primary diagnosis.

### Trade-offs
- Dual recommendation fields add some complexity to the web read model.
- Alignment checks between issue and fix patterns need maintenance.
- The recommendation system can feel templated unless expanded carefully.

## Schema Strategy
### Choice
The implementation uses explicit flattened CSV outputs plus richer nested JSONL outputs.

Examples:
- CSV for analysis, inspection, and joins
- JSONL for nested product objects and downstream AI use

### Why this choice is strong
- CSV remains easy for analysts and quick inspection.
- JSONL supports nested structures needed for evidence and prompts.
- The dual format reduces friction for different consumers.

### Trade-offs
- Two formats can drift if not generated from the same source of truth.
- The web app must normalize multiple shapes.
- Changes to field names can create cascading breakage.

## Error Handling and Failure Modes
### Current strength
The codebase includes several useful defensive behaviors:
- missing input checks
- duplicate recipe id assertions
- schema requirement validation in some scripts
- graceful handling of missing optional artifacts in the web app

### Current weakness
There is still no comprehensive contract enforcement across the full pipeline:
- no single end-to-end validation pass
- no centralized schema registry
- no strong stale-artifact detection

### Trade-off
The current balance favors iteration speed over operational rigor.

## Operational Model
### Choice
The project is designed for local execution with an expected `.venv`, local files, and manual command sequencing.

### Why this choice is strong
- Very low operational complexity.
- Good for prototyping and small-team iteration.
- Easy for a technical editor or analyst to inspect outputs.

### Trade-offs
- Manual orchestration is fragile.
- Hard to guarantee reproducibility across environments.
- Not ideal for scheduled or collaborative production workflows.

## Major Technical Trade-offs Summary
### 1. Determinism vs flexibility
- Chosen: determinism
- Benefit: trust, explainability, stability
- Cost: lower adaptability to new language patterns

### 2. Files vs services
- Chosen: files
- Benefit: simplicity, inspectability, low overhead
- Cost: weak orchestration, scaling, and freshness management

### 3. Local read model vs backend API
- Chosen: local read model
- Benefit: faster MVP implementation
- Cost: tighter coupling and less deployment flexibility

### 4. Regex/rules vs model inference
- Chosen: regex/rules for core classification
- Benefit: control and auditability
- Cost: maintenance burden and lower semantic coverage

### 5. Lexical retrieval vs semantic retrieval
- Chosen: lexical retrieval
- Benefit: low complexity and debuggability
- Cost: weaker performance on paraphrased questions

### 6. Bounded evidence vs exhaustive evidence
- Chosen: bounded evidence
- Benefit: better editor usability
- Cost: loss of breadth and edge-case context

### 7. Optional AI vs AI-first workflow
- Chosen: optional AI
- Benefit: preserves trust and safety
- Cost: less generative breadth and lower perceived intelligence

## Where the Current Design Is Well-Calibrated
The current implementation is well suited for:
- an internal editorial tool
- a team still discovering the right taxonomy and thresholds
- workflows where trust and inspectability matter more than automation
- medium-scale datasets that still fit comfortably in local artifact workflows

## Where the Current Design Will Strain
The current design will start to strain when:
- data volume grows substantially
- multiple users need synchronized fresh data
- schemas change frequently across teams
- the team wants real-time or near-real-time updates
- retrieval quality expectations increase
- governance and audit requirements become more formal

## Recommended Next Technical Investments
### Near-term
- Add a single orchestrated entry point for full pipeline execution.
- Add schema validation and artifact freshness checks.
- Move major thresholds and regex libraries into versioned config files.
- Add test fixtures for representative issue classes and evidence outputs.

### Mid-term
- Split read-model normalization from UI concerns in `web/lib/data/recipe-master.ts`.
- Add stronger evaluation datasets for issue precision and recommendation quality.
- Introduce a more formal artifact manifest or lineage file.

### Longer-term
- Consider a backend service or persisted store for recipe objects.
- Consider embedding-based retrieval if RAG quality becomes a priority.
- Consider lightweight workflow orchestration if scheduled refresh becomes necessary.

## Conclusion
The key engineering decision in this project is not “use AI” but “constrain AI.” The implementation is organized around the belief that editorial intelligence should be:
- deterministic first
- evidence-backed second
- AI-enhanced only where helpful and safe

That is a strong and coherent design choice for the current stage of the product. The main trade-off is that the system accepts more manual structure, more rules, and more artifact plumbing in exchange for trust, control, and explainability.
