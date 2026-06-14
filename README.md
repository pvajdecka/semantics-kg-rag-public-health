# SEMANTiCS KG-RAG Public Health Demo

This repository contains a local analytics demo for comparing standard RAG and KG-RAG when answering Czech infectious-disease questions against a shared SQL layer.

The system builds a typed analytical scope from retrieved evidence, generates SQL over a DuckDB fact table, and renders comparable tabular results in a small FastAPI demo app.

## Repository Layout

- `demo_app/` - FastAPI backend and static frontend for manual SQL and AI-assisted querying.
- `sql_database/` - DuckDB build scripts, table documentation, and evaluation SQL.
- `scripts/` - data acquisition, profiling, KG construction, retrieval corpus, and embedding builders.
- `dg_evaluation/` - evaluation runner plus current diagnosis/filter metrics.
- `outputs/` - generated evaluation questions, mappings, and summaries small enough to track.
- `reports/` - data profile and evaluation notes.
- `paper/` - paper sources and supporting publication files.

Large generated files are intentionally not committed, including raw data, vector artifacts, and the local DuckDB database.

## Setup

Use Python 3.10 or newer.

```bash
python3 -m pip install -r requirements.txt
```

Create a local `.env` file when using OpenAI-backed features:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_BATCH_SIZE=128
```

The `.env` file is ignored by Git.

## Build Local Artifacts

Raw data and generated artifacts are excluded from the repository. Rebuild them locally from the repository root:

```bash
python3 scripts/build_all_artifacts.py
python3 sql_database/scripts/create_duckdb_database.py --overwrite
```

The demo expects these local outputs:

- `sql_database/db/semantics.duckdb`
- `artifacts/kg/nodes.jsonl`
- `artifacts/kg/edges.jsonl`
- vector artifacts under `artifacts/vectors/`

## Run Demo App

```bash
HOST=0.0.0.0 PORT=8765 python3 demo_app/backend/run.py
```

Open:

```text
http://localhost:8765
```

See `demo_app/README.md` for API examples and operational details.
