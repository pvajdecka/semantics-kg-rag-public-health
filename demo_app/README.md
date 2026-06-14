# SEMANTiCS Demo App

Professional demo app for comparing two routes to tabular answers:

1. **Manual SQL**: select table columns and values manually. No AI is used.
2. **AI Scope Builder**: type a question and choose **RAG** or **RAG + KG**. The app retrieves artifacts, resolves entities, generates SQL against the same DuckDB fact table, and renders a paginated result table.

The app uses:

- FastAPI backend
- OpenAI API access via `OPENAI_API_KEY` in the environment or repository-root `.env`
- DuckDB database: `sql_database/db/semantics.duckdb`
- vector artifacts: `artifacts/vectors/*`
- KG artifacts: `artifacts/kg/*`
- KIZI/VSE-inspired institutional color system in a static frontend served by FastAPI

## Prerequisites

Run commands from the repository root, not from `demo_app/`.

Use Python 3.10+ and install the Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

The app also expects these generated local assets to already exist:

- `sql_database/db/semantics.duckdb`
- `artifacts/vectors/standard_rag/embeddings.npy`
- `artifacts/vectors/standard_rag/metadata.jsonl`
- `artifacts/vectors/kg_rag/embeddings.npy`
- `artifacts/vectors/kg_rag/metadata.jsonl`
- `artifacts/kg/nodes.jsonl`
- `artifacts/kg/edges.jsonl`

AI Scope Builder calls OpenAI for span extraction, entity selection, SQL generation, and embeddings. Set an API key either in your shell:

```bash
export OPENAI_API_KEY="your-api-key"
```

or in a repository-root `.env` file:

```text
OPENAI_API_KEY=your-api-key
```

Optional model overrides:

```bash
export OPENAI_CHAT_MODEL="gpt-4o-mini"
export OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
```

## Run the App

From the repository root:

```bash
python3 demo_app/backend/run.py
```

By default this binds to `0.0.0.0:8000`.

To choose the host and port explicitly:

```bash
HOST=0.0.0.0 PORT=8765 python3 demo_app/backend/run.py
```

Then open locally:

```text
http://localhost:8765
```

On EC2, use the instance hostname/IP with port `8765` if the security group allows it.

The frontend is static HTML/CSS/JS served by FastAPI. There is no separate Node or frontend build step.

## Quick Checks

The following checks assume you started the server with `PORT=8765`. Verify the backend and artifacts loaded:

```bash
curl http://127.0.0.1:8765/api/health
```

Run a Manual SQL query without AI:

```bash
curl -X POST http://127.0.0.1:8765/api/manual/query \
  -H "Content-Type: application/json" \
  -d '{"filters":{"diagnosis_code":["A01","A02"]},"page":1,"page_size":5}'
```

Run the streaming AI Scope Builder endpoint:

```bash
curl -N -X POST http://127.0.0.1:8765/api/ai/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"Porovnej střevní infekční nemoci dle diagnózy.","method":"full_kg_rag","page":1,"page_size":5}'
```

Use `Ctrl+C` in the server terminal to stop the app.

## API Endpoints

- `GET /api/health`
- `GET /api/schema`
- `GET /api/evaluation-questions`
- `POST /api/manual/query`
- `POST /api/ai/query`
- `POST /api/ai/query/stream`

## Important Demo Semantics

Both RAG and KG-RAG query the same SQL table:

`fact_infectious_disease_cases_enriched`

The evaluation-question endpoint is only a frontend convenience for selecting sample text. It returns question wording only and does not create KG nodes, retrieval documents, aliases, scope rules, or query-specific backend behavior.

The KG-RAG advantage is not a different table. It is better entity/scope construction before SQL, for example:

- map retrieved MKN labels or explicit code ranges to MKN blocks
- ground region mentions in official region codes and labels from the table
- resolve explicit numeric age constraints to SQL predicates over official age interval columns
- show a KG subgraph explaining the expansion

The output measure is `reported_case_count`. It is a reported table count, not unique patients, prevalence, incidence, or clinical evidence.
