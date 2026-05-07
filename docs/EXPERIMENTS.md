# Experiments

## Purpose
This document describes the experimental scripts in `src/experiments/`.

These experiments are intentionally separate from the production editorial pipeline. Their purpose is to help compare alternative approaches, inspect failure modes, and learn whether a simpler or more model-driven workflow is worth deeper investment.

They should not be treated as production decision logic.

## Current Experiments
### 1. Naive LLM-Only Comment Analysis
Script:
- `src/experiments/naive_llm_comment_analysis.py`

Goal:
- Test a simple recipe-level LLM workflow where all comments for a recipe are sent directly to the OpenAI API.
- Ask the model to identify friction points, suggested fixes, supporting snippets, confidence, and uncertainty.

This is meant to answer:
- What happens if we skip the deterministic editorial pipeline and ask a model to reason directly over recipe comments?
- Does the model find similar issues?
- Does it produce grounded supporting evidence?
- Where does it hallucinate or overgeneralize?

### 2. Naive LLM vs Deterministic Comparison
Script:
- `src/experiments/compare_naive_llm_to_editorial_intelligence.py`

Goal:
- Compare the top naive LLM friction/fix output to the deterministic editorial layer.
- Produce a simple side-by-side file for quick inspection.

This is meant to answer:
- How often does the naive LLM roughly agree with the deterministic issue label?
- Where does it diverge?
- Are divergences useful or mostly noisy?

## Experiment 1: Naive LLM-Only Comment Analysis
### Inputs
- `outputs/cleaned_comments.csv`
- optional: `data/recipe_master.csv`

### Output
- `outputs/experiments/naive_llm_comment_analysis.jsonl`

### Model
- `gpt-4.1-mini`

### API Key
Required environment variable:

```bash
OPENAI_API_KEY=...
```

### What the script does
For each selected recipe, the script:
1. groups comments by `recipe_id`
2. skips recipes with fewer than 5 comments
3. processes only a small sample by default
4. keeps only the most recent comments up to a configured cap
5. builds a single prompt containing recipe metadata and comment payload
6. asks the model for strict JSON output
7. saves both the raw response and parsed JSON
8. retries once on failure
9. continues processing other recipes even if one recipe fails

### Default behavior
- sample size: `10` recipes
- minimum comments per recipe: `5`
- maximum comments per recipe: `50`
- retry count: `1`

### Prompt behavior
The prompt asks the model to return:
- main friction points
- suggested fixes
- exact supporting snippets
- confidence
- uncertainty notes

Important constraints in the prompt:
- supporting snippets must be exact substrings from provided comments
- fixes must be explicitly supported by at least one comment
- app/site/product issues should be excluded
- neutral adaptations should be separated from problem-solving fixes
- precision is preferred over recall
- empty arrays are valid when evidence is weak

### Output row structure
Each JSONL row includes:
- `recipe_id`
- `recipe_title`
- `status`
- `attempt_count`
- `raw_model_response`
- `parsed_json`
- `error`
- `comment_count_total`
- `comment_count_used`
- `model`
- `prompt_text`

### Example command
```bash
./.venv/bin/python src/experiments/naive_llm_comment_analysis.py
```

### Useful optional arguments
```bash
./.venv/bin/python src/experiments/naive_llm_comment_analysis.py \
  --sample-size 5 \
  --max-comments-per-recipe 30
```

Run specific recipes only:

```bash
./.venv/bin/python src/experiments/naive_llm_comment_analysis.py \
  --recipe-ids 12345 67890
```

## Experiment 2: Compare Naive LLM to Editorial Intelligence
### Inputs
- `outputs/experiments/naive_llm_comment_analysis.jsonl`
- `outputs/editorial_intelligence.jsonl` if available

### Output
- `outputs/experiments/naive_llm_comparison.csv`

### What the script does
For each naive LLM output row, the script extracts:
- top LLM friction
- top LLM fix
- top LLM confidence
- uncertainty notes
- total supporting snippet count

Then, when deterministic editorial output is available, it compares those fields to:
- `decision.issue.display_issue`
- `decision.recommended_edit`
- `decision.issue.issue_confidence`

### Comparison columns
- `recipe_id`
- `recipe_title`
- `llm_top_friction`
- `deterministic_display_issue`
- `llm_top_fix`
- `deterministic_recommended_edit`
- `llm_confidence`
- `deterministic_issue_confidence`
- `snippet_count`
- `uncertainty_notes`
- `rough_match_flag`

### Rough match logic
`rough_match_flag` is intentionally simple.

It uses normalized token overlap between:
- LLM top friction
- deterministic display issue

This is not semantic matching. It is only a lightweight first-pass comparison.

### Example command
```bash
./.venv/bin/python src/experiments/compare_naive_llm_to_editorial_intelligence.py
```

## How to Interpret the Experiment
### What success would look like
This experiment is useful if it helps answer questions like:
- Does the naive LLM find similar friction patterns to the deterministic layer?
- Does it identify workable supporting snippets?
- Does it express uncertainty when evidence is weak?
- Does it surface useful issues the deterministic layer misses?

### What failure would look like
Common failure modes to watch for:
- invented or non-exact snippets
- overconfident issue labels from vague complaints
- unsupported fixes inferred from weak evidence
- mixing recipe issues with app/site complaints
- treating neutral adaptations as proof of recipe flaws
- overly broad or generic summary language

### Why this experiment matters
The production system is deterministic-first by design. This experiment helps test whether a naive model-only approach is:
- surprisingly competitive
- obviously weaker
- useful as a secondary signal
- useful only for idea generation

The value is not just whether the model agrees. The value is understanding where it is strong and where it becomes unreliable.

## Important Caveats
- This experiment does not replace the deterministic pipeline.
- It is intentionally naive and should be treated as a baseline.
- The script uses synthetic comment IDs when a stable source comment ID is not available in `cleaned_comments.csv`.
- Strict JSON output reduces parsing risk but does not guarantee high-quality reasoning.
- The comparison helper uses rough string overlap only; it is not a formal evaluation framework.

## Recommended Review Workflow
1. Run the naive experiment on 10 recipes.
2. Open the JSONL output and inspect:
   - whether snippets are truly exact
   - whether fixes are explicitly supported
   - whether uncertainty is handled honestly
3. Run the comparison helper.
4. Review recipes where:
   - rough match is false
   - LLM found a friction but deterministic did not
   - deterministic found a friction but LLM returned no clear evidence
5. Decide whether the naive model-only approach is:
   - not useful
   - useful only as a diagnostic baseline
   - useful as a supplemental signal for later experiments

## Future Experiment Ideas
- Compare naive full-comment prompting against curated-evidence prompting.
- Measure snippet exactness and support quality on a hand-labeled sample.
- Compare lexical RAG against direct whole-comment prompting for the same recipe.
- Test whether a model can reliably distinguish adaptation from repair behavior.
- Add a lightweight human review sheet for disagreement analysis.
