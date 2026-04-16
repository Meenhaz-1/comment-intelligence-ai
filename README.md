# Recipe Comment Intelligence

This project extracts structured insights from recipe comments using LLMs.

## Features
- Comment cleaning + normalization
- Structured extraction (sentiment, complaints, improvements, substitutions)
- Theme clustering
- Recipe scoring (high friction + high intent)

## Stack
- Python
- OpenAI API
- Pandas

## How to run

```bash
python3 src/load_data.py
python3 src/extract_insights.py
python3 src/analyze_insights.py
python3 src/cluster_insights.py
python3 src/score_recipes.py
