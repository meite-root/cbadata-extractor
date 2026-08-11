# Project instructions

This is a minimal FastAPI and vanilla-JavaScript application for auditable CBA text processing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Checks

```bash
pytest -q
python -m compileall app
git diff --check
```

## Rules

- Keep every NLP transformation auditable and expose the rule used.
- Do not claim exact replication of unavailable trained topic centroids.
- Do not commit pasted CBA text, extracted contract data, secrets, databases, or logs.
- Keep the frontend dependency-free unless there is a demonstrated need.
- Update tests and methodology documentation when classification rules change.

