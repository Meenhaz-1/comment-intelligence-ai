# Recipe Comment Intelligence

This project extracts structured insights from recipe comments using LLMs and rule-based text analysis.

## Features
- Comment cleaning and normalization
- Structured extraction for sentiment, complaints, improvements, and substitutions
- Theme clustering
- Recipe scoring for high-friction and high-intent recipes
- Phrase extraction and recipe-level comment features

## Stack
- Python
- OpenAI API
- Pandas
- spaCy
- RapidFuzz
- Sentence Transformers

## Python setup

This repo uses the local virtual environment at `.venv`.

Install dependencies with:

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m spacy download en_core_web_sm
```

## How to run

Core data pipeline:

```bash
./.venv/bin/python src/load_data.py
./.venv/bin/python src/extract_insights.py
./.venv/bin/python src/analyze_insights.py
./.venv/bin/python src/cluster_insights.py
```

Phrase and comment-feature pipeline:

```bash
./.venv/bin/python src/extract_recipe_phrases.py
./.venv/bin/python src/build_recipe_top_phrases.py
./.venv/bin/python src/build_recipe_top_phrases_wide.py
./.venv/bin/python src/build_recipe_comment_features.py
```
