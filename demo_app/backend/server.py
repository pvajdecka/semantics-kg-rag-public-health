from __future__ import annotations

import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = ROOT / ".python_packages"
if PROJECT_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_PACKAGES))

import duckdb  # type: ignore  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from openai import OpenAI  # type: ignore  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402


APP_ROOT = ROOT / "demo_app"
FRONTEND_DIR = APP_ROOT / "frontend"
DB_PATH = ROOT / "sql_database" / "db" / "semantics.duckdb"
VECTOR_DIR = ROOT / "artifacts" / "vectors"
RETRIEVAL_DIR = ROOT / "artifacts" / "retrieval"
KG_DIR = ROOT / "artifacts" / "kg"
EVALUATION_PATH = ROOT / "outputs" / "kg_rag_evaluation_queries.json"
FINAL_TABLE = "fact_infectious_disease_cases_enriched"
EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
PAGE_SIZE_MAX = 500
DEFAULT_PAGE_SIZE = 100
SQL_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|copy|attach|detach|pragma|call|execute)\b",
    re.IGNORECASE,
)
KG_METHODS = {"full_kg_rag"}
AI_METHODS = {"rag", *KG_METHODS}
FULL_KG_WEIGHTS = {"seed_support": 0.55, "case_support": 0.25, "lexical": 0.20}
WHOLE_BLOCK_LEXICAL_THRESHOLD = 0.65
METHOD_LABELS = {
    "rag": "RAG",
    "full_kg_rag": "KG-RAG",
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ROOT / ".env")


FINAL_COLUMNS = [
    "report_year",
    "report_month",
    "region_name_cs",
    "diagnosis_code",
    "diagnosis_name_cs",
    "mkn_block_code",
    "mkn_block_name_cs",
    "mkn_chapter_number",
    "mkn_chapter_name_cs",
    "age_group_name_cs",
    "sex_name_cs",
    "reported_case_count",
    "fact_id",
]

ORDER_COLUMNS = [
    "report_year",
    "report_month",
    "diagnosis_code",
    "fact_id",
]

FILTERABLE_COLUMNS = [
    "report_year",
    "report_month",
    "region_name_cs",
    "diagnosis_code",
    "diagnosis_name_cs",
    "mkn_block_code",
    "mkn_block_name_cs",
    "mkn_chapter_number",
    "mkn_chapter_name_cs",
    "age_group_name_cs",
    "sex_name_cs",
]

MANUAL_FILTERABLE_COLUMNS = [
    "report_year",
    "report_month",
    "region_name_cs",
    "diagnosis_code",
    "mkn_block_code",
    "mkn_chapter_number",
    "age_group_name_cs",
    "sex_name_cs",
]

CODE_LABEL_VALUE_COLUMNS = {
    "diagnosis_code": ("diagnosis_code", "diagnosis_name_cs"),
    "diagnosis_name_cs": ("diagnosis_code", "diagnosis_name_cs"),
    "mkn_block_code": ("mkn_block_code", "mkn_block_name_cs"),
    "mkn_block_name_cs": ("mkn_block_code", "mkn_block_name_cs"),
    "mkn_chapter_number": ("mkn_chapter_number", "mkn_chapter_name_cs"),
    "mkn_chapter_name_cs": ("mkn_chapter_number", "mkn_chapter_name_cs"),
}

MANUAL_RESULT_COLUMN_SPECS = [
    "report_year",
    "report_month",
    "region_name_cs",
    ("diagnosis_code", "diagnosis_name_cs", "diagnosis"),
    ("mkn_block_code", "mkn_block_name_cs", "mkn_block"),
    ("mkn_chapter_number", "mkn_chapter_name_cs", "mkn_chapter"),
    "age_group_name_cs",
    "sex_name_cs",
]

MANUAL_RESULT_COLUMN_LABELS = {
    "report_year": "Report year",
    "report_month": "Report month",
    "region_name_cs": "Region",
    "diagnosis": "Diagnosis",
    "mkn_block": "MKN block",
    "mkn_chapter": "MKN chapter",
    "age_group_name_cs": "Age group",
    "sex_name_cs": "Sex",
}

MANUAL_DEFAULT_RESULT_COLUMNS = ["diagnosis"]
MANUAL_RESULT_MEASURE_ALIAS = "reported_cases"

MKN_HIERARCHY_COLUMNS = {
    "mkn_block_code",
    "mkn_block_name_cs",
    "mkn_chapter_number",
    "mkn_chapter_name_cs",
}

RAG_ALLOWED_COLUMNS = [column for column in FINAL_COLUMNS if column not in MKN_HIERARCHY_COLUMNS]
RAG_FILTERABLE_COLUMNS = [column for column in FILTERABLE_COLUMNS if column not in MKN_HIERARCHY_COLUMNS]
AI_RETRIEVAL_COLUMNS = RAG_FILTERABLE_COLUMNS
MIN_DATABASE_CANDIDATE_VECTOR_SIMILARITY = 0.20
DIAGNOSIS_PROMOTION_MAX_PER_SPAN = 5
DIAGNOSIS_PROMOTION_MIN_SCORE = 0.28
DIAGNOSIS_PROMOTION_SCORE_DROP = 0.14
AGE_PROMOTION_MAX_PER_SPAN = 5
AGE_PROMOTION_MIN_SCORE = 0.20
AGE_PROMOTION_SCORE_DROP = 0.02

COLUMN_LABELS = {
    "report_year": "Report year",
    "report_month": "Report month",
    "region_name_cs": "Region",
    "diagnosis_code": "Diagnosis code",
    "diagnosis_name_cs": "Diagnosis",
    "mkn_code": "MKN code",
    "mkn_block_code": "MKN block",
    "mkn_block_name_cs": "MKN block label",
    "mkn_chapter_number": "MKN chapter",
    "mkn_chapter_name_cs": "MKN chapter label",
    "age_group_name_cs": "Age group",
    "sex_name_cs": "Sex",
    "reported_case_count": "Reported cases",
}

MANUAL_COLUMN_LABELS = {
    **COLUMN_LABELS,
    "diagnosis_code": "Diagnosis",
}

COLUMN_SEARCH_ALIASES = {
    "report_year": ["rok", "roky", "podle roku", "year", "by year"],
    "report_month": ["měsíc", "mesic", "měsíce", "month", "by month"],
    "region_name_cs": ["kraj", "kraje", "podle kraje", "region", "by region"],
    "diagnosis_code": ["diagnóza", "diagnoza", "diagnózy", "podle diagnózy", "diagnosis", "by diagnosis"],
    "diagnosis_name_cs": ["název diagnózy", "nazev diagnozy", "diagnosis label", "diagnosis name"],
    "age_group_name_cs": ["věk", "vek", "věková skupina", "věkové skupiny", "age group", "by age"],
    "sex_name_cs": ["pohlaví", "pohlavi", "sex", "gender", "by sex"],
}


def manual_column_label(column: str) -> str:
    return MANUAL_COLUMN_LABELS.get(column, column)


def db() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise HTTPException(500, f"DuckDB file not found: {DB_PATH}")
    return duckdb.connect(str(DB_PATH), read_only=True)


def q(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def norm_text(value: str) -> str:
    return value.lower().strip()


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip()


def text_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold_text(value))


def text_has_any(text: str, needles: list[str]) -> bool:
    lowered = norm_text(text)
    return any(needle.lower() in lowered for needle in needles)


def format_sql_value(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return "NULL"
        return str(int(value)) if float(value).is_integer() else str(value)
    text = str(value)
    if re.fullmatch(r"-?\d+(\.\d+)?", text):
        return text
    return q(text)


def method_label(method: str) -> str:
    return METHOD_LABELS.get(method, method.replace("_", " "))


def clean_display_part(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def code_label_display(code: Any, label: Any) -> str:
    code_text = clean_display_part(code)
    label_text = clean_display_part(label)
    if code_text and label_text:
        return f"{code_text} - {label_text}"
    return code_text or label_text


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_evaluation_question_texts() -> list[dict[str, str]]:
    if not EVALUATION_PATH.exists():
        return []
    raw_items = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    questions: list[dict[str, str]] = []
    for item in raw_items:
        question_id = str(item.get("id") or "").strip()
        query_cs = str(item.get("query_cs") or "").strip()
        query_en = str(item.get("query_en") or "").strip()
        if question_id and (query_cs or query_en):
            questions.append({"id": question_id, "query_cs": query_cs, "query_en": query_en})
    return questions


def add_catalog_item(
    catalog: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    *,
    column: str,
    value: Any,
    label: str,
    embedding_text: str,
    paired_values: dict[str, Any] | None = None,
    row_count: int | None = None,
    entity_type: str = "value",
) -> None:
    if value is None:
        return
    key = (column, str(value))
    if key in seen:
        return
    seen.add(key)
    catalog.append(
        {
            "id": f"{column}:{value}",
            "column": column,
            "column_label": COLUMN_LABELS.get(column, column),
            "value": value,
            "label": label,
            "embedding_text": embedding_text,
            "paired_values": paired_values or {},
            "row_count": row_count,
            "entity_type": entity_type,
        }
    )


def add_column_catalog_items(catalog: list[dict[str, Any]], seen: set[tuple[str, str]]) -> None:
    for column in AI_RETRIEVAL_COLUMNS:
        label = COLUMN_LABELS.get(column, column)
        aliases = COLUMN_SEARCH_ALIASES.get(column, [])
        alias_text = "; ".join(aliases)
        embedding_text = f"{label} column {column}. Query aliases: {alias_text}."
        add_catalog_item(
            catalog,
            seen,
            column=column,
            value=column,
            label=f"{label} column",
            embedding_text=embedding_text,
            paired_values={"column": column},
            entity_type="column",
        )


def load_db_entity_catalog() -> list[dict[str, Any]]:
    con = db()
    catalog: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    add_column_catalog_items(catalog, seen)

    diagnosis_rows = con.execute(
        f"""
        SELECT diagnosis_code, diagnosis_name_cs, COUNT(*) AS row_count
        FROM {FINAL_TABLE}
        WHERE diagnosis_code IS NOT NULL
        GROUP BY diagnosis_code, diagnosis_name_cs
        ORDER BY diagnosis_code
        """
    ).fetchall()
    for code, name, row_count in diagnosis_rows:
        label = f"{code} {name}"
        paired = {"diagnosis_code": code, "diagnosis_name_cs": name}
        text = f"Diagnosis code {code}; diagnosis label {name}."
        add_catalog_item(catalog, seen, column="diagnosis_code", value=code, label=label, embedding_text=text, paired_values=paired, row_count=row_count)
        add_catalog_item(catalog, seen, column="diagnosis_name_cs", value=name, label=label, embedding_text=text, paired_values=paired, row_count=row_count)

    region_rows = con.execute(
        f"""
        SELECT region_name_cs, COUNT(*) AS row_count
        FROM {FINAL_TABLE}
        WHERE region_name_cs IS NOT NULL
        GROUP BY region_name_cs
        ORDER BY region_name_cs
        """
    ).fetchall()
    for name, row_count in region_rows:
        label = str(name)
        paired = {"region_name_cs": name}
        text = f"Czech region name {name}."
        add_catalog_item(catalog, seen, column="region_name_cs", value=name, label=label, embedding_text=text, paired_values=paired, row_count=row_count)

    age_rows = con.execute(
        f"""
        SELECT age_group_name_cs, COUNT(*) AS row_count
        FROM {FINAL_TABLE}
        WHERE age_group_name_cs IS NOT NULL
        GROUP BY age_group_name_cs
        ORDER BY age_group_name_cs
        """
    ).fetchall()
    for name, row_count in age_rows:
        label = str(name)
        paired = {"age_group_name_cs": name}
        text = f"Age group label {name}."
        add_catalog_item(catalog, seen, column="age_group_name_cs", value=name, label=label, embedding_text=text, paired_values=paired, row_count=row_count)

    sex_rows = con.execute(
        f"""
        SELECT sex_name_cs, COUNT(*) AS row_count
        FROM {FINAL_TABLE}
        WHERE sex_name_cs IS NOT NULL
        GROUP BY sex_name_cs
        ORDER BY sex_name_cs
        """
    ).fetchall()
    for name, row_count in sex_rows:
        label = str(name)
        paired = {"sex_name_cs": name}
        text = f"Sex label {name}."
        add_catalog_item(catalog, seen, column="sex_name_cs", value=name, label=label, embedding_text=text, paired_values=paired, row_count=row_count)

    for column in ["report_year", "report_month"]:
        rows = con.execute(
            f"""
            SELECT {column} AS value, COUNT(*) AS row_count
            FROM {FINAL_TABLE}
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY {column}
            """
        ).fetchall()
        for value, row_count in rows:
            label = f"{COLUMN_LABELS.get(column, column)} {value}"
            text = f"{COLUMN_LABELS.get(column, column)} database value {value}."
            add_catalog_item(catalog, seen, column=column, value=value, label=label, embedding_text=text, row_count=row_count)

    con.close()
    return catalog


def openai_client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(500, "OPENAI_API_KEY is missing in .env")
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


class VectorIndex:
    def __init__(self, approach: Literal["standard_rag", "kg_rag"]):
        self.approach = approach
        self.embedding_path = VECTOR_DIR / approach / "embeddings.npy"
        self.metadata_path = VECTOR_DIR / approach / "metadata.jsonl"
        if not self.embedding_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError(f"Missing vector artifacts for {approach}")
        self.embeddings = np.load(self.embedding_path, mmap_mode="r")
        self.metadata = load_jsonl(self.metadata_path)

    def search(self, query_vector: list[float], top_k: int = 16) -> list[dict[str, Any]]:
        query_arr = np.asarray(query_vector, dtype=np.float32)
        query_norm = float(np.linalg.norm(query_arr))
        if query_norm == 0:
            return []
        top_scores: list[tuple[float, int]] = []
        chunk = 4096
        for start in range(0, self.embeddings.shape[0], chunk):
            matrix = np.asarray(self.embeddings[start : start + chunk], dtype=np.float32)
            dots = matrix @ query_arr
            norms = np.linalg.norm(matrix, axis=1) * query_norm
            scores = np.divide(dots, norms, out=np.zeros_like(dots), where=norms != 0)
            local_count = min(top_k, len(scores))
            if local_count == 0:
                continue
            local_idx = np.argpartition(scores, -local_count)[-local_count:]
            for offset in local_idx:
                top_scores.append((float(scores[offset]), start + int(offset)))
            top_scores = sorted(top_scores, reverse=True)[:top_k]
        return [
            {
                "score": round(score, 4),
                "document": self.metadata[index],
            }
            for score, index in top_scores
        ]


@dataclass
class Scope:
    method: str
    group_by: list[str]
    where_clauses: list[str]
    entities: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    normalized_question: str
    kg_subgraph: dict[str, Any]


class ManualQueryRequest(BaseModel):
    filters: dict[str, list[Any]] = Field(default_factory=dict)
    display_columns: list[str] = Field(default_factory=list)
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = "asc"


class AIQueryRequest(BaseModel):
    question: str
    method: Literal["rag", "full_kg_rag", "kg_rag"] = "rag"
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = "asc"


app = FastAPI(title="SEMANTiCS RAG vs KG-RAG SQL Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    app.state.standard_index = VectorIndex("standard_rag")
    app.state.kg_index = VectorIndex("kg_rag")
    app.state.db_catalog = load_db_entity_catalog()
    app.state.db_catalog_embeddings = None
    app.state.kg_nodes = {node["id"]: node for node in load_jsonl(KG_DIR / "nodes.jsonl")}
    app.state.kg_edges = load_jsonl(KG_DIR / "edges.jsonl")
    app.state.out_edges = {}
    app.state.in_edges = {}
    for edge in app.state.kg_edges:
        app.state.out_edges.setdefault(edge["source"], []).append(edge)
        app.state.in_edges.setdefault(edge["target"], []).append(edge)
    app.state.client = None


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "database": str(DB_PATH.relative_to(ROOT)),
        "standard_vectors": list(app.state.standard_index.embeddings.shape),
        "kg_vectors": list(app.state.kg_index.embeddings.shape),
    }


def describe_final_table(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in con.execute(f"DESCRIBE {FINAL_TABLE}").fetchall()}


def scrub_hidden_column_mentions(row: dict[str, Any], hidden_columns: set[str]) -> dict[str, Any]:
    scrubbed: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str):
            text = value
            for column in sorted(hidden_columns, key=len, reverse=True):
                text = re.sub(rf"\b{re.escape(column)}\b", "non-public source field", text, flags=re.IGNORECASE)
            scrubbed[key] = text
        else:
            scrubbed[key] = value
    return scrubbed


@app.get("/api/schema")
def schema() -> dict[str, Any]:
    con = db()
    hidden_columns = describe_final_table(con).difference(FINAL_COLUMNS)
    dictionary_rows = con.execute("SELECT * FROM column_dictionary").fetchdf().to_dict("records")
    dictionary = [
        scrub_hidden_column_mentions(row, hidden_columns)
        for row in dictionary_rows
        if row.get("column") in FINAL_COLUMNS
    ]
    values: dict[str, list[Any]] = {}
    for column in MANUAL_FILTERABLE_COLUMNS:
        values[column] = schema_values_for_column(con, column)
    con.close()
    return {
        "final_table": FINAL_TABLE,
        "columns": [
            {
                "name": column,
                "label": manual_column_label(column),
                "values": values.get(column, []),
            }
            for column in MANUAL_FILTERABLE_COLUMNS
        ],
        "result_columns": manual_result_columns_payload(),
        "default_result_columns": MANUAL_DEFAULT_RESULT_COLUMNS,
        "result_measure_column": {"name": MANUAL_RESULT_MEASURE_ALIAS, "label": "Reported cases"},
        "dictionary": dictionary,
    }


@app.get("/api/evaluation-questions")
def evaluation_questions() -> dict[str, Any]:
    return {"questions": load_evaluation_question_texts()}


def page_bounds(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = max(1, min(PAGE_SIZE_MAX, int(page_size or DEFAULT_PAGE_SIZE)))
    return page, page_size


def stable_page_sql(base_sql: str, page: int, page_size: int, order_clause: str) -> str:
    offset = (page - 1) * page_size
    return f"""
SELECT *
FROM (
{base_sql.strip().rstrip(';')}
) AS page_source
ORDER BY {order_clause}
LIMIT {page_size} OFFSET {offset}
""".strip()


def quote_ident(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def nullable_text_sql(column: str) -> str:
    return f"NULLIF(CAST({quote_ident(column)} AS VARCHAR), '')"


def code_label_sql_expression(code_column: str, label_column: str, alias: str) -> str:
    code_value = nullable_text_sql(code_column)
    label_value = nullable_text_sql(label_column)
    return f"""CASE
    WHEN {code_value} IS NULL THEN {label_value}
    WHEN {label_value} IS NULL THEN {code_value}
    ELSE {code_value} || ' - ' || {label_value}
  END AS {quote_ident(alias)}"""


def manual_select_expression(spec: str | tuple[str, str, str]) -> str:
    if isinstance(spec, str):
        return quote_ident(spec)
    code_column, label_column, alias = spec
    return code_label_sql_expression(code_column, label_column, alias)


def manual_result_column_key(spec: str | tuple[str, str, str]) -> str:
    return spec if isinstance(spec, str) else spec[2]


def manual_result_columns_payload() -> list[dict[str, str]]:
    return [
        {
            "name": manual_result_column_key(spec),
            "label": MANUAL_RESULT_COLUMN_LABELS.get(manual_result_column_key(spec), manual_result_column_key(spec)),
        }
        for spec in MANUAL_RESULT_COLUMN_SPECS
    ]


def selected_manual_result_specs(display_columns: list[str]) -> list[str | tuple[str, str, str]]:
    requested = {str(column) for column in display_columns if str(column).strip()}
    if not requested:
        requested = set(MANUAL_DEFAULT_RESULT_COLUMNS)
    selected = [spec for spec in MANUAL_RESULT_COLUMN_SPECS if manual_result_column_key(spec) in requested]
    return selected or [spec for spec in MANUAL_RESULT_COLUMN_SPECS if manual_result_column_key(spec) in MANUAL_DEFAULT_RESULT_COLUMNS]


def schema_values_for_column(con: duckdb.DuckDBPyConnection, column: str) -> list[Any]:
    if column in CODE_LABEL_VALUE_COLUMNS:
        code_column, label_column = CODE_LABEL_VALUE_COLUMNS[column]
        rows = con.execute(
            f"""
            SELECT DISTINCT
              {quote_ident(column)} AS value,
              {quote_ident(code_column)} AS code_value,
              {quote_ident(label_column)} AS label_value
            FROM {FINAL_TABLE}
            WHERE {quote_ident(column)} IS NOT NULL
            ORDER BY code_value, label_value
            LIMIT 600
            """
        ).fetchall()
        return [
            {"value": row[0], "label": code_label_display(row[1], row[2])}
            for row in rows
        ]
    rows = con.execute(
        f"""
        SELECT DISTINCT {quote_ident(column)} AS value
        FROM {FINAL_TABLE}
        WHERE {quote_ident(column)} IS NOT NULL
        ORDER BY {quote_ident(column)}
        LIMIT 600
        """
    ).fetchall()
    return [row[0] for row in rows]


def page_order_clause(shape: list[Any], sort_by: str | None, sort_dir: str) -> tuple[str, str | None, str | None]:
    columns = [str(item[0]) for item in shape]
    if sort_by and sort_by in columns:
        direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
        return f"{quote_ident(sort_by)} {direction}", sort_by, direction.lower()
    return ", ".join(str(index) for index in range(1, len(shape) + 1)) or "1", None, None


def execute_paged(base_sql: str, page: int, page_size: int, sort_by: str | None = None, sort_dir: str = "asc") -> dict[str, Any]:
    page, page_size = page_bounds(page, page_size)
    normalized_sql = base_sql.strip().rstrip(";")
    count_sql = f"SELECT COUNT(*) AS total_rows FROM ({normalized_sql}) AS count_source"
    con = db()
    total = int(con.execute(count_sql).fetchone()[0])
    shape = con.execute(f"SELECT * FROM ({normalized_sql}) AS shape_source LIMIT 0").description or []
    order_clause, applied_sort_by, applied_sort_dir = page_order_clause(shape, sort_by, sort_dir)
    page_sql = stable_page_sql(normalized_sql, page, page_size, order_clause)
    result = con.execute(page_sql).fetchdf()
    con.close()
    return {
        "sql": page_sql,
        "base_sql": normalized_sql,
        "page": page,
        "page_size": page_size,
        "total_rows": total,
        "total_pages": max(1, math.ceil(total / page_size)),
        "sort_by": applied_sort_by,
        "sort_dir": applied_sort_dir,
        "columns": list(result.columns),
        "rows": json.loads(result.to_json(orient="records", force_ascii=False)),
    }


@app.post("/api/manual/query")
def manual_query(request: ManualQueryRequest) -> dict[str, Any]:
    clauses = []
    artifacts = []
    for column, raw_values in request.filters.items():
        if column not in MANUAL_FILTERABLE_COLUMNS:
            continue
        values = [value for value in raw_values if value not in {None, ""}]
        if not values:
            continue
        artifacts.append({"column": column, "label": manual_column_label(column), "values": values})
        sql_values = ", ".join(format_sql_value(value) for value in values)
        clauses.append(f"{column} IN ({sql_values})")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    result_specs = selected_manual_result_specs(request.display_columns)
    dimension_select_cols = [manual_select_expression(spec) for spec in result_specs]
    select_cols = ",\n  ".join(
        [
            *dimension_select_cols,
            f"CAST(SUM({quote_ident('reported_case_count')}) AS BIGINT) AS {quote_ident(MANUAL_RESULT_MEASURE_ALIAS)}",
        ]
    )
    group_by_sql = f"GROUP BY {', '.join(str(index) for index in range(1, len(dimension_select_cols) + 1))}"
    order_by_sql = f"ORDER BY {', '.join(str(index) for index in range(1, len(dimension_select_cols) + 1))}"
    base_sql = f"""
SELECT
  {select_cols}
FROM {FINAL_TABLE}
{where_sql}
{group_by_sql}
{order_by_sql}
"""
    result = execute_paged(base_sql, request.page, request.page_size, request.sort_by, request.sort_dir)
    result["artifacts"] = artifacts
    return result


def chat_json(system_prompt: str, payload: dict[str, Any], max_tokens: int = 1800) -> dict[str, Any]:
    if app.state.client is None:
        app.state.client = openai_client()
    response = app.state.client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(502, f"OpenAI returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(502, "OpenAI returned JSON that was not an object.")
    return parsed


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    if app.state.client is None:
        app.state.client = openai_client()
    vectors: list[list[float]] = []
    batch_size = 96
    for start in range(0, len(texts), batch_size):
        response = app.state.client.embeddings.create(model=EMBED_MODEL, input=texts[start : start + batch_size])
        vectors.extend(list(item.embedding) for item in response.data)
    return np.asarray(vectors, dtype=np.float32)


def db_catalog_embeddings() -> np.ndarray:
    if app.state.db_catalog_embeddings is None:
        app.state.db_catalog_embeddings = embed_texts([item["embedding_text"] for item in app.state.db_catalog])
    return app.state.db_catalog_embeddings


def normalize_openai_span(question: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    text = str(raw.get("text") or raw.get("span") or "").strip()
    if not text:
        return None
    start = raw.get("start")
    end = raw.get("end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(question):
        if question[start:end] != text:
            start = None
            end = None
    else:
        start = None
        end = None
    if start is None or end is None:
        exact = question.find(text)
        if exact < 0:
            exact = question.lower().find(text.lower())
        if exact >= 0:
            start = exact
            end = exact + len(text)
            text = question[start:end]
    return {
        "text": text,
        "kind": str(raw.get("kind") or "entity").strip() or "entity",
        "start": start,
        "end": end,
        "reason": str(raw.get("reason") or "").strip(),
        "source": "openai_query_span_extraction",
    }


def extract_query_spans(question: str) -> list[dict[str, Any]]:
    system_prompt = """
You extract candidate entity and constraint spans from public-health table questions.
Return only JSON with key "spans".
Each span must be an exact substring from the original question when possible.
Extract disease names or disease groups, diagnosis codes or code ranges, places, age/sex groups,
time expressions, reported measures, and grouping dimensions such as "by region" or "podle kraje".
Do not map spans to database values and do not invent synonyms.
JSON shape: {"spans":[{"text":"...","kind":"disease|code|place|age|time|sex|measure|grouping|other","start":0,"end":5,"reason":"..."}]}.
""".strip()
    data = chat_json(system_prompt, {"question": question}, max_tokens=1200)
    raw_spans = data.get("spans") if isinstance(data.get("spans"), list) else []
    spans: list[dict[str, Any]] = []
    seen: set[tuple[int | None, int | None, str]] = set()
    for raw in raw_spans:
        if not isinstance(raw, dict):
            continue
        span = normalize_openai_span(question, raw)
        if not span:
            continue
        key = (span["start"], span["end"], fold_text(span["text"]))
        if key in seen:
            continue
        seen.add(key)
        span["id"] = f"S{len(spans) + 1:02d}"
        spans.append(span)
    return spans[:12]


def lexical_similarity(needle: str, haystack: str) -> float:
    needle_folded = fold_text(needle)
    haystack_folded = fold_text(haystack)
    if not needle_folded or not haystack_folded:
        return 0.0
    score = 0.0
    if needle_folded == haystack_folded:
        score += 1.0
    elif needle_folded in haystack_folded or haystack_folded in needle_folded:
        score += 0.45
    needle_tokens = set(text_tokens(needle_folded))
    haystack_tokens = set(text_tokens(haystack_folded))
    if needle_tokens and haystack_tokens:
        score += 0.45 * (len(needle_tokens & haystack_tokens) / len(needle_tokens | haystack_tokens))
    code_match = re.search(r"\b[A-Z][0-9]{2}(?:\s*[-–]\s*[A-Z][0-9]{2})?\b", needle.upper())
    if code_match and code_match.group(0).replace(" ", "") in str(haystack).upper().replace(" ", ""):
        score += 0.6
    return min(score, 1.0)


def top_database_candidates(
    spans: list[dict[str, Any]],
    *,
    candidate_columns: list[str] | None = None,
    per_column: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not spans:
        return [], {}
    candidate_columns = candidate_columns or AI_RETRIEVAL_COLUMNS
    catalog = app.state.db_catalog
    catalog_vectors = db_catalog_embeddings()
    span_vectors = embed_texts([span["text"] for span in spans])
    catalog_norms = np.linalg.norm(catalog_vectors, axis=1)
    span_norms = np.linalg.norm(span_vectors, axis=1)
    by_column: dict[str, list[int]] = {}
    for index, item in enumerate(catalog):
        by_column.setdefault(item["column"], []).append(index)

    candidate_groups: list[dict[str, Any]] = []
    candidate_map: dict[str, dict[str, Any]] = {}
    serial = 1
    for span_index, span in enumerate(spans):
        span_candidates: list[dict[str, Any]] = []
        span_vector = span_vectors[span_index]
        span_norm = span_norms[span_index]
        for column in candidate_columns:
            scored: list[tuple[float, float, int]] = []
            for catalog_index in by_column.get(column, []):
                denom = float(span_norm * catalog_norms[catalog_index])
                cosine = float((catalog_vectors[catalog_index] @ span_vector) / denom) if denom else 0.0
                if cosine < MIN_DATABASE_CANDIDATE_VECTOR_SIMILARITY:
                    continue
                lex = lexical_similarity(span["text"], catalog[catalog_index]["embedding_text"])
                score = (0.86 * cosine) + (0.14 * lex)
                scored.append((score, cosine, catalog_index))
            for score, cosine, catalog_index in sorted(scored, reverse=True)[:per_column]:
                item = catalog[catalog_index]
                candidate_id = f"C{serial:04d}"
                serial += 1
                candidate = {
                    "id": candidate_id,
                    "span_id": span["id"],
                    "span_text": span["text"],
                    "span_kind": span["kind"],
                    "column": item["column"],
                    "column_label": item["column_label"],
                    "value": item["value"],
                    "label": item["label"],
                    "score": round(float(score), 4),
                    "vector_similarity": round(float(cosine), 4),
                    "paired_values": item.get("paired_values") or {},
                    "row_count": item.get("row_count"),
                    "entity_type": item.get("entity_type") or "value",
                }
                if item["column"] == "age_group_name_cs":
                    bounds = parse_age_group_bounds(str(item["value"]))
                    if bounds:
                        candidate["value_metadata"] = {"age_from": bounds[0], "age_to": bounds[1]}
                candidate_map[candidate_id] = candidate
                span_candidates.append(candidate)
        candidate_groups.append({"span": span, "candidates": span_candidates})
    return candidate_groups, candidate_map


def compact_candidate_for_prompt(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate["id"],
        "span_id": candidate["span_id"],
        "span_text": candidate["span_text"],
        "span_kind": candidate["span_kind"],
        "column": candidate["column"],
        "value": candidate["value"],
        "label": candidate["label"],
        "score": candidate["score"],
        "vector_similarity": candidate.get("vector_similarity"),
        "paired_values": candidate.get("paired_values") or {},
        "entity_type": candidate.get("entity_type") or "value",
        "value_metadata": candidate.get("value_metadata") or {},
    }


def preferred_filter_pair(candidate: dict[str, Any]) -> tuple[str, Any]:
    paired = candidate.get("paired_values") or {}
    preferred = {
        "diagnosis_name_cs": "diagnosis_code",
        "mkn_block_name_cs": "mkn_block_code",
        "mkn_chapter_name_cs": "mkn_chapter_number",
    }
    target_column = preferred.get(candidate["column"], candidate["column"])
    return target_column, paired.get(target_column, candidate["value"])


def coalesce_selected_entities(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_blocks = {
        str(entity.get("filter_value"))
        for entity in selected
        if entity.get("role") == "filter" and entity.get("filter_column") == "mkn_block_code"
    }
    if not selected_blocks:
        return selected
    coalesced: list[dict[str, Any]] = []
    for entity in selected:
        if entity.get("filter_column") == "diagnosis_code":
            paired_block = str((entity.get("paired_values") or {}).get("mkn_block_code") or "")
            if paired_block in selected_blocks:
                continue
        coalesced.append(entity)
    return coalesced


def dedupe_selected_entities(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_rank = {"filter": 0, "group_by": 1, "context": 2}
    best: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for entity in selected:
        column = str(entity.get("filter_column") or entity.get("column") or "")
        value = str(entity.get("filter_value") if entity.get("filter_value") is not None else entity.get("value"))
        key = (column, value)
        if key not in best:
            best[key] = entity
            order.append(key)
            continue
        current_rank = role_rank.get(str(best[key].get("role") or ""), 9)
        next_rank = role_rank.get(str(entity.get("role") or ""), 9)
        if next_rank < current_rank:
            best[key] = entity
    return [best[key] for key in order]


def parse_age_group_bounds(label: str) -> tuple[int, int | None] | None:
    text = str(label).replace("–", "-").replace("—", "-")
    range_match = re.search(r"\b([0-9]{1,3})\s*-\s*([0-9]{1,3})\b", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    plus_match = re.search(r"\b([0-9]{1,3})\s*\+", text)
    if plus_match:
        return int(plus_match.group(1)), None
    exact_match = re.search(r"\b([0-9]{1,3})\b", text)
    if exact_match:
        age = int(exact_match.group(1))
        return age, age
    return None


def numeric_age_constraint_from_text(text: str) -> dict[str, Any] | None:
    folded = fold_text(text)
    range_match = re.search(r"\b([0-9]{1,3})\s*[-–]\s*([0-9]{1,3})\b", folded)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return {"min_age": min(low, high), "max_age": max(low, high), "source": range_match.group(0)}
    plus_match = re.search(r"\b([0-9]{1,3})\s*\+", folded)
    if plus_match:
        min_age = int(plus_match.group(1))
        return {"min_age": min_age, "max_age": None, "source": plus_match.group(0)}
    from_match = re.search(r"\b(?:od|nad|from|older than)\s+([0-9]{1,3})\b", folded)
    if from_match:
        min_age = int(from_match.group(1))
        return {"min_age": min_age, "max_age": None, "source": from_match.group(0)}
    under_match = re.search(r"\b(?:do|pod|under|younger than)\s+([0-9]{1,3})\b", folded)
    if under_match:
        max_age = int(under_match.group(1))
        return {"min_age": 0, "max_age": max_age, "source": under_match.group(0)}
    return None


def numeric_age_constraints(question: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    seen: set[tuple[int, int | None]] = set()
    for span in spans:
        constraint = numeric_age_constraint_from_text(str(span.get("text") or ""))
        if not constraint:
            continue
        constraint = {**constraint, "source_span_id": span.get("id"), "source_span": span.get("text")}
        key = (int(constraint["min_age"]), constraint["max_age"])
        if key not in seen:
            seen.add(key)
            constraints.append(constraint)
    question_constraint = numeric_age_constraint_from_text(question)
    if question_constraint:
        key = (int(question_constraint["min_age"]), question_constraint["max_age"])
        if key not in seen:
            constraints.append({**question_constraint, "source_span_id": None, "source_span": None})
    return constraints


def age_interval_matches_constraint(age_bounds: tuple[int, int | None], constraint: dict[str, Any]) -> bool:
    start_age, end_age = age_bounds
    min_age = int(constraint["min_age"])
    max_age = constraint.get("max_age")
    if max_age is None:
        return start_age >= min_age
    if end_age is None:
        return False
    return start_age >= min_age and end_age <= int(max_age)


def generic_numeric_age_filter_entities(
    question: str,
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    constraints = numeric_age_constraints(question, spans)
    if not constraints:
        return []
    catalog = getattr(app.state, "db_catalog", None) or load_db_entity_catalog()
    entities: list[dict[str, Any]] = []
    seen_values: set[str] = set()
    for constraint in constraints:
        for item in catalog:
            if item.get("column") != "age_group_name_cs" or item.get("entity_type") == "column":
                continue
            parsed = parse_age_group_bounds(str(item.get("value") or item.get("label") or ""))
            if not parsed or not age_interval_matches_constraint(parsed, constraint):
                continue
            value = str(item.get("value"))
            if value in seen_values:
                continue
            seen_values.add(value)
            entities.append(
                {
                    "kind": "age_group_name_cs",
                    "column": "age_group_name_cs",
                    "value": item.get("value"),
                    "label": item.get("label") or item.get("value"),
                    "source_span_id": constraint.get("source_span_id"),
                    "source_span": constraint.get("source_span"),
                    "source": "Generic numeric age interval constraint",
                    "score": 1.0,
                    "role": "filter",
                    "filter_column": "age_group_name_cs",
                    "filter_value": item.get("value"),
                    "paired_values": {"age_group_name_cs": item.get("value")},
                    "entity_type": "value",
                    "reason": f"Age group interval satisfies numeric query constraint {constraint.get('source')}.",
                }
            )
    return sorted(entities, key=lambda entity: parse_age_group_bounds(str(entity.get("filter_value"))) or (999, 999))


def age_entity_from_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    filter_column, filter_value = preferred_filter_pair(candidate)
    if filter_column != "age_group_name_cs" or candidate.get("entity_type") == "column" or not filter_value:
        return None
    if not parse_age_group_bounds(str(filter_value)):
        return None
    return {
        "kind": "age_group_name_cs",
        "column": candidate["column"],
        "value": candidate["value"],
        "label": candidate["label"],
        "source_span_id": candidate.get("span_id"),
        "source_span": candidate.get("span_text"),
        "source": "Deterministic age span value promotion",
        "score": candidate["score"],
        "role": "filter",
        "filter_column": "age_group_name_cs",
        "filter_value": filter_value,
        "paired_values": candidate.get("paired_values") or {"age_group_name_cs": filter_value},
        "entity_type": candidate.get("entity_type") or "value",
        "reason": "Age value candidate belongs to an age span and constrains rows.",
    }


def deterministic_age_filter_entities(
    spans: list[dict[str, Any]],
    candidate_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen_values: set[str] = set()
    span_counts: dict[str, int] = {}
    for group in candidate_groups:
        span = group.get("span") or {}
        span_id = str(span.get("id") or "")
        if str(span.get("kind") or "").lower() != "age":
            continue
        candidates = [
            candidate
            for candidate in group.get("candidates") or []
            if candidate.get("column") == "age_group_name_cs"
            and candidate.get("entity_type") != "column"
            and age_entity_from_candidate(candidate)
        ]
        if not candidates:
            continue
        top_score = max(float(candidate.get("score") or 0.0) for candidate in candidates)
        cutoff = max(AGE_PROMOTION_MIN_SCORE, top_score - AGE_PROMOTION_SCORE_DROP)
        for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
            if float(candidate.get("score") or 0.0) < cutoff:
                continue
            entity = age_entity_from_candidate(candidate)
            if not entity:
                continue
            value = str(entity.get("filter_value"))
            if value in seen_values:
                continue
            seen_values.add(value)
            span_counts[span_id] = span_counts.get(span_id, 0) + 1
            entities.append(entity)
            if span_counts[span_id] >= AGE_PROMOTION_MAX_PER_SPAN:
                break
    return entities


def span_allows_diagnosis_promotion(span: dict[str, Any], top_diagnosis_score: float, top_other_score: float) -> bool:
    kind = str(span.get("kind") or "").lower()
    text = str(span.get("text") or "")
    if re.search(r"\b[A-Z][0-9]{2}\b", text.upper()):
        return True
    if kind in {"disease", "code"}:
        return top_diagnosis_score >= DIAGNOSIS_PROMOTION_MIN_SCORE
    if kind in {"age", "sex", "place", "time", "measure", "grouping"}:
        return False
    return top_diagnosis_score >= DIAGNOSIS_PROMOTION_MIN_SCORE and top_diagnosis_score >= (top_other_score - 0.02)


def diagnosis_entity_from_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    filter_column, filter_value = preferred_filter_pair(candidate)
    code = str(filter_value or "")
    if filter_column != "diagnosis_code" or not re.fullmatch(r"[A-Z][0-9]{2}", code):
        return None
    return {
        "kind": "diagnosis_code",
        "column": candidate["column"],
        "value": candidate["value"],
        "label": candidate["label"],
        "source_span_id": candidate.get("span_id"),
        "source_span": candidate.get("span_text"),
        "source": "Deterministic diagnosis score promotion",
        "score": candidate["score"],
        "role": "filter",
        "filter_column": "diagnosis_code",
        "filter_value": code,
        "paired_values": candidate.get("paired_values") or {},
        "entity_type": candidate.get("entity_type") or "value",
        "reason": "High-scoring diagnosis candidate for disease/code span.",
    }


def deterministic_diagnosis_filter_entities(
    spans: list[dict[str, Any]],
    candidate_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    span_by_id = {span.get("id"): span for span in spans}
    for group in candidate_groups:
        span = group.get("span") or span_by_id.get((group.get("span") or {}).get("id")) or {}
        candidates = group.get("candidates") or []
        diagnosis_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("column") in {"diagnosis_code", "diagnosis_name_cs"}
            and candidate.get("entity_type") != "column"
            and diagnosis_entity_from_candidate(candidate)
        ]
        if not diagnosis_candidates:
            continue
        top_diagnosis_score = max(float(candidate.get("score") or 0.0) for candidate in diagnosis_candidates)
        top_other_score = max(
            [float(candidate.get("score") or 0.0) for candidate in candidates if candidate.get("column") not in {"diagnosis_code", "diagnosis_name_cs"}]
            or [0.0]
        )
        if not span_allows_diagnosis_promotion(span, top_diagnosis_score, top_other_score):
            continue
        cutoff = max(DIAGNOSIS_PROMOTION_MIN_SCORE, top_diagnosis_score - DIAGNOSIS_PROMOTION_SCORE_DROP)
        by_code: dict[str, dict[str, Any]] = {}
        for candidate in sorted(diagnosis_candidates, key=lambda item: item["score"], reverse=True):
            entity = diagnosis_entity_from_candidate(candidate)
            if not entity:
                continue
            code = str(entity["filter_value"])
            if float(candidate.get("score") or 0.0) < cutoff:
                continue
            current = by_code.get(code)
            if current is None or float(entity.get("score") or 0.0) > float(current.get("score") or 0.0):
                by_code[code] = entity
            if len(by_code) >= DIAGNOSIS_PROMOTION_MAX_PER_SPAN:
                break
        for code, entity in by_code.items():
            if code in seen_codes:
                continue
            seen_codes.add(code)
            entities.append(entity)
    return entities


def prune_blocked_span_diagnosis_filters(
    spans: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    promoted_diagnosis_codes: set[str],
) -> list[dict[str, Any]]:
    span_kind_by_id = {span.get("id"): str(span.get("kind") or "").lower() for span in spans}
    blocked_kinds = {"age", "sex", "place", "time", "measure", "grouping"}
    pruned: list[dict[str, Any]] = []
    for entity in selected:
        if entity.get("role") == "filter" and entity.get("filter_column") == "diagnosis_code":
            code = str(entity.get("filter_value") or "")
            span_kind = span_kind_by_id.get(entity.get("source_span_id"), "")
            if span_kind in blocked_kinds and code not in promoted_diagnosis_codes:
                continue
        pruned.append(entity)
    return pruned


def apply_deterministic_diagnosis_entities(
    spans: list[dict[str, Any]],
    candidate_groups: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    promoted = deterministic_diagnosis_filter_entities(spans, candidate_groups)
    promoted_codes = {str(entity.get("filter_value")) for entity in promoted}
    selected = prune_blocked_span_diagnosis_filters(spans, selected, promoted_codes)
    if not promoted:
        return selected
    return [*selected, *promoted]


def apply_deterministic_scope_entities(
    question: str,
    spans: list[dict[str, Any]],
    candidate_groups: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = apply_deterministic_diagnosis_entities(spans, candidate_groups, selected)
    age_entities = generic_numeric_age_filter_entities(question, spans)
    if not age_entities:
        age_entities = deterministic_age_filter_entities(spans, candidate_groups)
    if not age_entities:
        return selected
    kept = [
        entity
        for entity in selected
        if entity.get("filter_column") != "age_group_name_cs"
    ]
    return [*kept, *age_entities]


def select_database_entities(
    question: str,
    spans: list[dict[str, Any]],
    candidate_groups: list[dict[str, Any]],
    candidate_map: dict[str, dict[str, Any]],
    available_columns: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    prompt_groups = [
        {
            "span": group["span"],
            "candidates_by_column": [
                {
                    "column": column,
                    "label": COLUMN_LABELS.get(column, column),
                    "candidates": [
                        compact_candidate_for_prompt(candidate)
                        for candidate in sorted(
                            [item for item in group["candidates"] if item["column"] == column],
                            key=lambda item: item["score"],
                            reverse=True,
                        )
                    ],
                }
                for column in available_columns
                if any(item["column"] == column for item in group["candidates"])
            ],
        }
        for group in candidate_groups
    ]
    system_prompt = """
You select database entities that are relevant for answering a question.
You are given extracted text spans and top database value or column candidates for the flat RAG retrieval columns.
The original question is the primary source of truth. Use candidate scores only as retrieval hints; do not choose a value that contradicts explicit text or numbers in the question.
Choose only candidate IDs that are actually relevant. Do not invent values.
Prefer stable code columns via paired_values when they identify the same database entity.
Candidates with entity_type="column" represent a column/grouping concept, not a row value; use role "group_by" or "context" for them, never "filter".
For age_group_name_cs candidates, use value_metadata.age_from and value_metadata.age_to to compare against numeric age constraints in the query. For example, 65+ means age_from must be at least 65; do not choose a child age group for 65+ even if it appears among candidates.
For disease or diagnosis-code spans, select relevant high-scoring diagnosis_code candidates even when other columns also have candidates.
Use role "filter" for values that constrain rows, "group_by" for values or columns that define grouping,
and "context" for helpful but non-filtering matches.
Return only JSON with keys "selected_entities" and "unresolved_spans".
JSON shape: {"selected_entities":[{"candidate_id":"C0001","role":"filter","reason":"..."}],"unresolved_spans":["..."]}.
""".strip()
    data = chat_json(
        system_prompt,
        {
            "question": question,
            "numeric_age_constraints": numeric_age_constraints(question, spans),
            "available_columns": [{"name": column, "label": COLUMN_LABELS.get(column, column)} for column in available_columns],
            "extracted_spans": spans,
            "candidate_groups": prompt_groups,
        },
        max_tokens=3000,
    )
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in data.get("selected_entities", []):
        if not isinstance(raw, dict):
            continue
        candidate = candidate_map.get(str(raw.get("candidate_id") or ""))
        if not candidate:
            continue
        role = str(raw.get("role") or "filter").strip() or "filter"
        is_column_entity = candidate.get("entity_type") == "column"
        filter_column, filter_value = preferred_filter_pair(candidate)
        if is_column_entity:
            role = "context" if role == "context" else "group_by"
            filter_value = None
        key = (role, filter_column, str(filter_value))
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                "kind": filter_column,
                "column": candidate["column"],
                "value": candidate["value"],
                "label": candidate["label"],
                "source_span_id": candidate["span_id"],
                "source_span": candidate["span_text"],
                "source": "OpenAI selection from per-column database candidates",
                "score": candidate["score"],
                "role": role,
                "filter_column": filter_column,
                "filter_value": filter_value,
                "paired_values": candidate.get("paired_values") or {},
                "entity_type": candidate.get("entity_type") or "value",
                "reason": str(raw.get("reason") or "").strip(),
            }
        )
    unresolved = [str(item) for item in data.get("unresolved_spans", []) if str(item).strip()]
    selected = apply_deterministic_scope_entities(question, spans, candidate_groups, selected)
    return dedupe_selected_entities(coalesce_selected_entities(selected)), unresolved


def seed_node_for_entity(entity: dict[str, Any]) -> str | None:
    column = entity.get("filter_column") or entity.get("column")
    value = entity.get("filter_value")
    if value in {None, ""}:
        return None
    if column == "diagnosis_code" and re.fullmatch(r"[A-Z][0-9]{2}", str(value)):
        return f"infectious_diagnosis:{value}"
    if column == "mkn_block_code":
        return f"mkn_block:{value}"
    if column == "report_year":
        return f"year:{value}"
    if column == "report_month":
        return f"month:{value}"
    return None


def selected_entity_seed_nodes(selected_entities: list[dict[str, Any]]) -> list[str]:
    seed_nodes = [node_id for entity in selected_entities if (node_id := seed_node_for_entity(entity))]
    return [node_id for node_id in dict.fromkeys(seed_nodes) if node_id in app.state.kg_nodes]


def selected_diagnosis_seed_entities(selected_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    seeds: list[dict[str, Any]] = []
    for entity in selected_entities:
        code = str(entity.get("filter_value") or "")
        if entity.get("filter_column") != "diagnosis_code" or not re.fullmatch(r"[A-Z][0-9]{2}", code):
            continue
        if code in seen:
            continue
        seen.add(code)
        seeds.append(entity)
    return seeds


def diagnosis_reported_cases(code: str) -> float:
    node = app.state.kg_nodes.get(f"infectious_diagnosis:{code}") or {}
    props = node.get("properties") or {}
    try:
        return float(props.get("reported_cases") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def hierarchy_candidate_score(
    *,
    query: str,
    label: str,
    seed_codes: set[str],
    all_seed_codes: set[str],
    weights: dict[str, float],
) -> float:
    total_seed_cases = sum(diagnosis_reported_cases(code) for code in all_seed_codes) or 1.0
    seed_cases = sum(diagnosis_reported_cases(code) for code in seed_codes)
    seed_support = len(seed_codes) / max(1, len(all_seed_codes))
    case_support = seed_cases / total_seed_cases
    lexical = lexical_similarity(query, label)
    return round(
        weights["seed_support"] * seed_support
        + weights["case_support"] * case_support
        + weights["lexical"] * lexical,
        6,
    )


def chapter_nodes_for_diagnosis(code: str) -> list[str]:
    diagnosis_id = f"infectious_diagnosis:{code}"
    mkn_nodes = [
        edge["target"]
        for edge in app.state.out_edges.get(diagnosis_id, [])
        if edge.get("type") == "SAME_AS_MKN_CODE"
    ]
    chapter_ids: list[str] = []
    for mkn_node in mkn_nodes:
        for edge in app.state.in_edges.get(mkn_node, []):
            if edge.get("type") == "CONTAINS_MKN_CODE" and str(edge.get("source", "")).startswith("mkn_chapter:"):
                chapter_ids.append(str(edge["source"]))
    return list(dict.fromkeys(chapter_ids))


def kg_node_to_external_entity(node_id: str, *, source_seed: str, edge_type: str, score: float) -> dict[str, Any] | None:
    node = app.state.kg_nodes.get(node_id)
    if not node:
        return None
    props = node.get("properties") or {}
    node_type = node.get("type")
    label = node.get("label") or node_id
    column = None
    value = None
    if node_type == "diagnosis_value":
        column = "diagnosis_code"
        value = props.get("code")
    elif node_type == "mkn_block":
        column = "mkn_block_code"
        value = props.get("block_code")
    elif node_type == "mkn_chapter":
        column = "mkn_chapter_number"
        value = props.get("chapter_number")
    elif node_type == "year":
        column = "report_year"
        value = props.get("year")
    elif node_type == "month":
        column = "report_month"
        value = props.get("month")
    if column is None or value is None:
        return None
    return {
        "kind": column,
        "column": column,
        "value": value,
        "label": label,
        "source": f"KG {edge_type} expansion",
        "source_seed": source_seed,
        "score": round(score, 4),
        "role": "kg_external_candidate",
        "filter_column": column,
        "filter_value": value,
        "kg_node_id": node_id,
        "edge_type": edge_type,
    }


def kg_external_entities(selected_entities: list[dict[str, Any]], limit: int = 18) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_nodes = selected_entity_seed_nodes(selected_entities)
    seed_span_ids = {
        node_id: entity.get("source_span_id")
        for entity in selected_entities
        if (node_id := seed_node_for_entity(entity)) and entity.get("source_span_id")
    }
    selected_keys = {(str(entity.get("filter_column")), str(entity.get("filter_value"))) for entity in selected_entities}
    external: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set(selected_keys)

    selected_diagnosis_codes = [
        str(entity.get("filter_value"))
        for entity in selected_entities
        if entity.get("filter_column") == "diagnosis_code" and re.fullmatch(r"[A-Z][0-9]{2}", str(entity.get("filter_value")))
    ]
    selected_block = next((str(entity.get("filter_value")) for entity in selected_entities if entity.get("filter_column") == "mkn_block_code"), None)
    selected_block_span_id = next(
        (entity.get("source_span_id") for entity in selected_entities if entity.get("filter_column") == "mkn_block_code"),
        None,
    )
    block_support: dict[str, set[str]] = {}
    for code in selected_diagnosis_codes:
        node = app.state.kg_nodes.get(f"infectious_diagnosis:{code}") or {}
        block_code = (node.get("properties") or {}).get("mkn_block_code")
        if block_code:
            block_support.setdefault(str(block_code), set()).add(code)

    def first_span_for_codes(codes: set[str]) -> str | None:
        for code in sorted(codes):
            span_id = seed_span_ids.get(f"infectious_diagnosis:{code}")
            if span_id:
                return span_id
        return None

    for block_code, codes in sorted(block_support.items(), key=lambda item: (len(item[1]), item[0]), reverse=True)[:4]:
        block_id = f"mkn_block:{block_code}"
        span_id = first_span_for_codes(codes)
        block_entity = kg_node_to_external_entity(
            block_id,
            source_seed=", ".join(f"infectious_diagnosis:{code}" for code in sorted(codes)),
            edge_type="MKN_HIERARCHY",
            score=len(codes) / max(1, len(selected_diagnosis_codes)),
        )
        if block_entity:
            block_entity["source"] = "KG MKN hierarchy expansion"
            block_entity["supporting_diagnosis_codes"] = sorted(codes)
            if span_id:
                block_entity["source_span_id"] = span_id
            key = (str(block_entity["filter_column"]), str(block_entity["filter_value"]))
            if key not in seen:
                seen.add(key)
                external.append(block_entity)
            seed_nodes.append(block_id)
            if not selected_block and len(codes) >= 2:
                selected_block = block_code
                selected_block_span_id = span_id

        for edge in app.state.in_edges.get(block_id, []):
            if edge.get("type") != "CONTAINS_MKN_BLOCK":
                continue
            chapter_id = edge.get("source")
            chapter_entity = kg_node_to_external_entity(
                chapter_id,
                source_seed=block_id,
                edge_type="MKN_HIERARCHY",
                score=len(codes) / max(1, len(selected_diagnosis_codes)),
            )
            if not chapter_entity:
                continue
            chapter_entity["source"] = "KG MKN hierarchy expansion"
            chapter_entity["supporting_mkn_block_code"] = block_code
            if span_id:
                chapter_entity["source_span_id"] = span_id
            key = (str(chapter_entity["filter_column"]), str(chapter_entity["filter_value"]))
            if key not in seen:
                seen.add(key)
                external.append(chapter_entity)
            seed_nodes.append(str(chapter_id))

    if selected_block:
        block_diagnoses = table_diagnoses_for_block(selected_block)
        selected_diagnosis_codes.extend(item["code"] for item in block_diagnoses)
        seed_nodes.extend(f"infectious_diagnosis:{item['code']}" for item in block_diagnoses[:8])
        if selected_block_span_id:
            for item in block_diagnoses[:8]:
                seed_span_ids[f"infectious_diagnosis:{item['code']}"] = selected_block_span_id
    if selected_diagnosis_codes:
        for item in profile_similar_diagnoses(list(dict.fromkeys(selected_diagnosis_codes)), selected_block=selected_block, limit=10):
            key = ("diagnosis_code", item["code"])
            if key in seen:
                continue
            seen.add(key)
            node_id = f"infectious_diagnosis:{item['code']}"
            external.append(
                {
                    "kind": "diagnosis_code",
                    "column": "diagnosis_code",
                    "value": item["code"],
                    "label": item["label"],
                    "source": "KG diagnosis profile similarity",
                    "source_seed": item["source_seed_code"],
                    "source_span_id": seed_span_ids.get(f"infectious_diagnosis:{item['source_seed_code']}") or selected_block_span_id,
                    "score": item["score"],
                    "role": "kg_external_candidate",
                    "filter_column": "diagnosis_code",
                    "filter_value": item["code"],
                    "kg_node_id": node_id,
                    "edge_type": "SIMILAR_CASE_PROFILE",
                    "external_to_selected_block": item["external_to_selected_block"],
                    "mkn_block_code": item.get("mkn_block_code"),
                }
            )

    for seed in list(dict.fromkeys(seed_nodes))[:20]:
        related = app.state.out_edges.get(seed, []) + app.state.in_edges.get(seed, [])
        related = [edge for edge in related if edge.get("type") in {"WEIGHTED_COOCCURS_WITH", "SIMILAR_CASE_PROFILE"}]
        for edge in sorted(related, key=edge_strength, reverse=True)[:6]:
            other_id = edge["target"] if edge["source"] == seed else edge["source"]
            entity = kg_node_to_external_entity(other_id, source_seed=seed, edge_type=edge["type"], score=edge_strength(edge))
            if not entity:
                continue
            if seed_span_ids.get(seed):
                entity["source_span_id"] = seed_span_ids[seed]
            key = (str(entity["filter_column"]), str(entity["filter_value"]))
            if key in seen:
                continue
            seen.add(key)
            external.append(entity)
            seed_nodes.append(other_id)
            if len(external) >= limit:
                break
        if len(external) >= limit:
            break
    graph = build_kg_graph(list(dict.fromkeys(seed_nodes + [str(item.get("kg_node_id")) for item in external if item.get("kg_node_id")])))
    return external[:limit], graph


def diagnosis_external_entity(
    diagnosis: dict[str, str],
    *,
    source: str,
    source_seed: str,
    source_span_id: str | None,
    score: float,
    edge_type: str,
) -> dict[str, Any]:
    node_id = f"infectious_diagnosis:{diagnosis['code']}"
    return {
        "kind": "diagnosis_code",
        "column": "diagnosis_code",
        "value": diagnosis["code"],
        "label": f"{diagnosis['code']} {diagnosis['label']}",
        "source": source,
        "source_seed": source_seed,
        "source_span_id": source_span_id,
        "score": round(float(score), 4),
        "role": "kg_external_candidate",
        "filter_column": "diagnosis_code",
        "filter_value": diagnosis["code"],
        "kg_node_id": node_id,
        "edge_type": edge_type,
    }


def expanded_filter_entities(expanded: list[dict[str, str]], *, source: str, score: float) -> list[dict[str, Any]]:
    entities = []
    for diagnosis in expanded:
        entities.append(
            {
                "kind": "diagnosis_code",
                "column": "diagnosis_code",
                "value": diagnosis["code"],
                "label": f"{diagnosis['code']} {diagnosis['label']}",
                "source": source,
                "score": round(float(score), 4),
                "role": "filter",
                "filter_column": "diagnosis_code",
                "filter_value": diagnosis["code"],
                "paired_values": {"diagnosis_code": diagnosis["code"], "diagnosis_name_cs": diagnosis["label"]},
                "reason": source,
            }
        )
    return entities


def seed_source_spans(selected_entities: list[dict[str, Any]], seed_codes: set[str]) -> list[str]:
    spans: list[str] = []
    seen: set[str] = set()
    for entity in selected_entities:
        code = str(entity.get("filter_value") or "")
        span = str(entity.get("source_span") or "").strip()
        if code in seed_codes and span and span not in seen:
            seen.add(span)
            spans.append(span)
    return spans


def code_range_bounds(codes: list[str]) -> tuple[str, str] | None:
    parsed: list[tuple[str, int, str]] = []
    for code in codes:
        match = re.fullmatch(r"([A-Z])([0-9]{2})", code)
        if not match:
            return None
        parsed.append((match.group(1), int(match.group(2)), code))
    if not parsed:
        return None
    letters = {item[0] for item in parsed}
    if len(letters) != 1:
        return None
    low = min(parsed, key=lambda item: item[1])
    high = max(parsed, key=lambda item: item[1])
    return low[2], high[2]


def diagnoses_in_code_range(diagnoses: list[dict[str, str]], start_code: str, end_code: str) -> list[dict[str, str]]:
    return [diagnosis for diagnosis in diagnoses if start_code <= diagnosis["code"] <= end_code]


def scoped_diagnoses_for_block(
    *,
    question: str,
    block_code: str,
    block_label: str,
    seed_codes: set[str],
    selected_entities: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], str, float]:
    block_diagnoses = table_diagnoses_for_block(block_code)
    block_code_set = {diagnosis["code"] for diagnosis in block_diagnoses}
    block_seed_codes = sorted(seed_codes & block_code_set)
    spans = seed_source_spans(selected_entities, set(block_seed_codes))
    lexical_scores = [lexical_similarity(span, block_label) for span in spans]
    lexical_scores.append(lexical_similarity(question, block_label))
    block_lexical = max(lexical_scores or [0.0])

    if block_lexical >= WHOLE_BLOCK_LEXICAL_THRESHOLD or not block_seed_codes:
        return block_diagnoses, f"MKN block expansion {block_code}", block_lexical

    bounds = code_range_bounds(block_seed_codes)
    if bounds:
        start_code, end_code = bounds
        ranged = diagnoses_in_code_range(block_diagnoses, start_code, end_code)
        if len(ranged) >= len(block_seed_codes):
            return ranged, f"MKN block seed-range expansion {start_code}-{end_code}", block_lexical

    seeded = [diagnosis for diagnosis in block_diagnoses if diagnosis["code"] in block_seed_codes]
    return seeded or block_diagnoses, f"MKN block seed-only expansion {block_code}", block_lexical


def kg_method_expansion(
    question: str,
    selected_entities: list[dict[str, Any]],
    *,
    max_external: int = 28,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    seeds = selected_diagnosis_seed_entities(selected_entities)
    seed_codes = {str(entity.get("filter_value")) for entity in seeds}
    seed_span_by_code = {str(entity.get("filter_value")): entity.get("source_span_id") for entity in seeds}
    if not seed_codes:
        return [], {"nodes": [], "edges": []}, [], {"chosen": [], "weights": {}}

    external: list[dict[str, Any]] = []
    graph_nodes = [f"infectious_diagnosis:{code}" for code in sorted(seed_codes)]
    priority_entities: list[dict[str, Any]] = []
    chosen_records: list[dict[str, Any]] = []

    grouped: dict[str, set[str]] = {}
    for code in seed_codes:
        node = app.state.kg_nodes.get(f"infectious_diagnosis:{code}") or {}
        block_code = (node.get("properties") or {}).get("mkn_block_code")
        if block_code:
            grouped.setdefault(str(block_code), set()).add(code)
    candidates = []
    for block_code, codes in grouped.items():
        block_id = f"mkn_block:{block_code}"
        block_node = app.state.kg_nodes.get(block_id) or {}
        block_label = str(block_node.get("label") or block_code)
        score = hierarchy_candidate_score(
            query=question,
            label=block_label,
            seed_codes=codes,
            all_seed_codes=seed_codes,
            weights=FULL_KG_WEIGHTS,
        )
        candidates.append((score, block_code, block_label, codes, block_id))
    candidates.sort(reverse=True, key=lambda item: (item[0], len(item[3]), item[1]))
    chosen = candidates[:1]
    for score, block_code, block_label, codes, block_id in chosen:
        span_id = next((seed_span_by_code.get(code) for code in sorted(codes) if seed_span_by_code.get(code)), None)
        block_entity = kg_node_to_external_entity(
            block_id,
            source_seed=", ".join(f"infectious_diagnosis:{code}" for code in sorted(codes)),
            edge_type="FULL_HIERARCHY_BLOCK",
            score=score,
        )
        if block_entity:
            block_entity["source"] = "KG-RAG block path"
            block_entity["supporting_diagnosis_codes"] = sorted(codes)
            block_entity["source_span_id"] = span_id
            external.append(block_entity)
        graph_nodes.append(block_id)
        for edge in app.state.in_edges.get(block_id, []):
            if edge.get("type") == "CONTAINS_MKN_BLOCK":
                graph_nodes.append(str(edge["source"]))
                chapter_entity = kg_node_to_external_entity(
                    str(edge["source"]),
                    source_seed=block_id,
                    edge_type="FULL_HIERARCHY_CHAPTER",
                    score=score,
                )
                if chapter_entity:
                    chapter_entity["source"] = "KG-RAG chapter context"
                    chapter_entity["source_span_id"] = span_id
                    external.append(chapter_entity)
        expanded, scope_source, scope_lexical = scoped_diagnoses_for_block(
            question=question,
            block_code=block_code,
            block_label=block_label,
            seed_codes=seed_codes,
            selected_entities=selected_entities,
        )
        priority_entities.extend(expanded_filter_entities(expanded, source=f"KG-RAG {scope_source}", score=score))
        for diagnosis in expanded[:max_external]:
            external.append(
                diagnosis_external_entity(
                    diagnosis,
                    source="KG-RAG diagnosis expansion",
                    source_seed=block_id,
                    source_span_id=span_id,
                    score=score,
                    edge_type="FULL_HIERARCHY_DIAGNOSIS",
                )
            )
            graph_nodes.append(f"infectious_diagnosis:{diagnosis['code']}")
        chosen_records.append(
            {
                "kind": "mkn_block",
                "value": block_code,
                "label": block_label,
                "score": score,
                "seed_codes": sorted(codes),
                "scope": scope_source,
                "scope_lexical": round(scope_lexical, 4),
                "expanded_count": len(expanded),
            }
        )
    weights = FULL_KG_WEIGHTS

    seen_priority: set[str] = set()
    deduped_priority = []
    for entity in priority_entities:
        code = str(entity.get("filter_value"))
        if code in seen_priority:
            continue
        seen_priority.add(code)
        deduped_priority.append(entity)

    seen_external: set[tuple[str, str, str]] = set()
    deduped_external = []
    for entity in external:
        key = (str(entity.get("kind")), str(entity.get("value")), str(entity.get("source")))
        if key in seen_external:
            continue
        seen_external.add(key)
        deduped_external.append(entity)
        if len(deduped_external) >= max_external:
            break

    graph = build_kg_graph(list(dict.fromkeys(graph_nodes)))
    return deduped_external, graph, deduped_priority, {"chosen": chosen_records, "weights": weights}


def schema_prompt_payload(method: str) -> dict[str, Any]:
    data_years = sorted(
        int(item["value"])
        for item in app.state.db_catalog
        if item["column"] == "report_year" and str(item["value"]).isdigit()
    )
    allowed_columns = RAG_ALLOWED_COLUMNS
    filterable_columns = RAG_FILTERABLE_COLUMNS
    return {
        "table": FINAL_TABLE,
        "measure": "reported_case_count",
        "allowed_columns": allowed_columns,
        "filterable_columns": filterable_columns,
        "column_labels": {column: COLUMN_LABELS.get(column, column) for column in allowed_columns},
        "available_years": data_years,
    }


def validate_generated_sql(sql: str, method: str) -> str:
    sql = sql.strip().rstrip(";")
    if not sql:
        raise HTTPException(502, "OpenAI returned empty SQL.")
    lowered = sql.lower()
    if not lowered.startswith("select"):
        raise HTTPException(502, "OpenAI SQL must start with SELECT.")
    if SQL_FORBIDDEN_RE.search(sql):
        raise HTTPException(502, "OpenAI SQL contained a forbidden statement.")
    if FINAL_TABLE.lower() not in lowered:
        raise HTTPException(502, f"OpenAI SQL must query {FINAL_TABLE}.")
    con = db()
    table_columns = describe_final_table(con)
    con.close()
    hidden_columns = table_columns.difference(FINAL_COLUMNS)
    for column in hidden_columns:
        if re.search(rf"\b{re.escape(column)}\b", sql, re.IGNORECASE):
            raise HTTPException(502, f"OpenAI SQL used a non-public column: {column}.")
    if method in AI_METHODS:
        for column in MKN_HIERARCHY_COLUMNS:
            if re.search(rf"\b{re.escape(column)}\b", sql, re.IGNORECASE):
                raise HTTPException(502, f"AI SQL used a KG-only hierarchy column: {column}.")
    return sql


def display_group_columns(columns: list[str]) -> list[str]:
    expanded: list[str] = []
    for column in columns:
        if column == "diagnosis_code":
            expanded.extend(["diagnosis_code", "diagnosis_name_cs"])
        elif column == "diagnosis_name_cs":
            expanded.extend(["diagnosis_code", "diagnosis_name_cs"])
        else:
            expanded.append(column)
    return [column for column in dict.fromkeys(expanded) if column in RAG_ALLOWED_COLUMNS]


def deterministic_priority_sql(
    question: str,
    priority_entities: list[dict[str, Any]],
    selected_entities: list[dict[str, Any]],
) -> str | None:
    diagnosis_codes = sorted(
        dict.fromkeys(
            str(entity.get("filter_value"))
            for entity in priority_entities
            if entity.get("filter_column") == "diagnosis_code"
            and re.fullmatch(r"[A-Z][0-9]{2}", str(entity.get("filter_value") or ""))
        )
    )
    if not diagnosis_codes:
        return None

    filters: dict[str, list[Any]] = {"diagnosis_code": diagnosis_codes}
    for year in sorted(set(int(item) for item in re.findall(r"\b(20[0-9]{2})\b", question))):
        filters.setdefault("report_year", []).append(year)
    for entity in selected_entities:
        if entity.get("role") != "filter":
            continue
        column = str(entity.get("filter_column") or "")
        value = entity.get("filter_value")
        if column == "diagnosis_code" or column not in RAG_FILTERABLE_COLUMNS or value in {None, ""}:
            continue
        filters.setdefault(column, []).append(value)

    clauses = []
    for column, values in filters.items():
        unique_values = list(dict.fromkeys(values))
        sql_values = ", ".join(format_sql_value(value) for value in unique_values)
        clauses.append(f"{column} IN ({sql_values})")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    selected_group_by = [
        str(entity.get("filter_column") or entity.get("column"))
        for entity in selected_entities
        if entity.get("role") == "group_by"
        and str(entity.get("filter_column") or entity.get("column")) in RAG_ALLOWED_COLUMNS
    ]
    filter_group_by = [column for column in filters if column in RAG_ALLOWED_COLUMNS]
    group_by = display_group_columns(
        selected_group_by
        + [column for column in infer_group_by(question) if column in RAG_ALLOWED_COLUMNS]
        + filter_group_by
    )
    if group_by:
        select_dims = ",\n  ".join(group_by)
        group_dims = ", ".join(group_by)
        return f"""
SELECT
  {select_dims},
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_cases
FROM {FINAL_TABLE}
{where_sql}
GROUP BY {group_dims}
ORDER BY {group_dims}
""".strip()
    return f"""
SELECT
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_cases
FROM {FINAL_TABLE}
{where_sql}
""".strip()


def generate_sql_with_openai(
    question: str,
    method: str,
    spans: list[dict[str, Any]],
    selected_entities: list[dict[str, Any]],
    external_entities: list[dict[str, Any]],
    unresolved_spans: list[str],
    priority_entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    system_prompt = """
You generate read-only DuckDB SQL for one public-health fact table.
Return only JSON with keys "sql", "normalized_question", and "used_entities".
The payload field "question" is the user's original textual query and is the primary instruction. Use retrieved entities only when they are consistent with that text.
Use only the table and columns supplied in the payload. Do not invent tables or columns.
The answer measure is SUM(reported_case_count), cast to BIGINT.
Use selected_database_entities as trusted database grounding. Prefer filter_column/filter_value for WHERE clauses.
For method=rag, use only flat diagnosis/database columns supplied in schema; never use MKN block or MKN chapter hierarchy columns.
For KG-RAG, external_kg_entities are explanatory candidates from KG expansion.
For KG-RAG, kg_priority_entities are the final expanded diagnosis_code filters. If kg_priority_entities is non-empty, use exactly those diagnosis_code filter values in WHERE instead of an incomplete seed diagnosis_code list.
Never use MKN block or MKN chapter hierarchy columns in the final SQL for any AI method.
For grouping requests ("podle kraje", "by region", "podle diagnózy", "by age group", "by year"), include the corresponding code and label columns when available.
Every column used in WHERE must also appear in SELECT and GROUP BY so the returned table shows the exact filtered scope. If diagnosis_code is used in WHERE, include both diagnosis_code and diagnosis_name_cs in SELECT and GROUP BY. The only aggregated numeric output should be SUM(reported_case_count).
For relative time expressions, use current_date and available_years from the payload, and only produce years present in available_years.
Do not add a report_year filter unless the question has a time restriction. Never add all available years as a filter.
Never use DELETE, UPDATE, INSERT, CREATE, DROP, ALTER, PRAGMA, COPY, ATTACH, DETACH, or multiple statements.
JSON shape: {"sql":"SELECT ...","normalized_question":"...","used_entities":[{"column":"...","value":"...","source":"..."}]}.
""".strip()
    kg_priority_entities = priority_entities or []
    selected_for_sql = selected_entities
    if kg_priority_entities:
        priority_span_ids = {entity.get("source_span_id") for entity in kg_priority_entities if entity.get("source_span_id")}
        selected_for_sql = [
            {**entity, "role": "filter", "reason": "KG-expanded diagnosis-code priority scope"}
            for entity in kg_priority_entities
        ]
        for entity in selected_entities:
            if (
                entity.get("filter_column") == "diagnosis_code"
                and entity.get("role") == "filter"
                and entity.get("source_span_id") in priority_span_ids
            ):
                selected_for_sql.append({**entity, "role": "context"})
            else:
                selected_for_sql.append(entity)
    payload = {
        "question": question,
        "method": method,
        "current_date": "2026-06-13",
        "schema": schema_prompt_payload(method),
        "extracted_spans": spans,
        "selected_database_entities": selected_for_sql,
        "external_kg_entities": external_entities,
        "kg_priority_entities": kg_priority_entities,
        "unresolved_spans": unresolved_spans,
    }
    data = chat_json(system_prompt, payload, max_tokens=2200)
    sql = deterministic_priority_sql(question, kg_priority_entities, selected_entities)
    if sql is None:
        sql = str(data.get("sql") or "")
    sql = validate_generated_sql(sql, method)
    used_entities = data.get("used_entities") if isinstance(data.get("used_entities"), list) else []
    if kg_priority_entities:
        used_entities = [
            {"column": "diagnosis_code", "value": entity.get("filter_value"), "source": entity.get("source")}
            for entity in kg_priority_entities
            if entity.get("filter_column") == "diagnosis_code"
        ]
        for entity in selected_entities:
            column = str(entity.get("filter_column") or entity.get("column") or "")
            if column == "diagnosis_code" or column not in RAG_ALLOWED_COLUMNS:
                continue
            if entity.get("role") not in {"filter", "group_by"}:
                continue
            used_entities.append(
                {
                    "column": column,
                    "value": entity.get("filter_value") if entity.get("filter_value") is not None else entity.get("value"),
                    "source": entity.get("source"),
                    "role": entity.get("role"),
                }
            )
    return {
        "sql": sql,
        "normalized_question": str(data.get("normalized_question") or "").strip()
        or normalize_question(question, selected_entities + external_entities, []),
        "used_entities": used_entities,
    }


def candidate_artifact_items(candidate_groups: list[dict[str, Any]], per_column: int = 3, max_items: int = 80) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in candidate_groups:
        for column in AI_RETRIEVAL_COLUMNS:
            column_candidates = sorted(
                [candidate for candidate in group["candidates"] if candidate["column"] == column],
                key=lambda item: item["score"],
                reverse=True,
            )[:per_column]
            for candidate in column_candidates:
                items.append(
                    {
                        "label": candidate["id"],
                        "node_type": candidate["column"],
                        "score": candidate["score"],
                        "source_span_id": candidate.get("span_id"),
                        "text": (
                            f"{candidate['span_text']} -> {candidate['column']} = {candidate['label']} "
                            f"(vector={candidate.get('vector_similarity')})"
                        ),
                    }
                )
    return sorted(items, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:max_items]


def build_ai_scope_with_openai(question: str, method: Literal["rag", "full_kg_rag"]) -> Scope:
    spans = extract_query_spans(question)
    candidate_groups, candidate_map = top_database_candidates(spans, candidate_columns=AI_RETRIEVAL_COLUMNS)
    selected_entities, unresolved_spans = select_database_entities(
        question,
        spans,
        candidate_groups,
        candidate_map,
        AI_RETRIEVAL_COLUMNS,
    )
    external_entities: list[dict[str, Any]] = []
    priority_entities: list[dict[str, Any]] = []
    kg_graph: dict[str, Any] = {"nodes": [], "edges": []}
    expansion_meta: dict[str, Any] = {}
    artifacts = [
        {
            "title": "Top database candidates per extracted span",
            "items": candidate_artifact_items(candidate_groups),
        }
    ]

    if method in KG_METHODS:
        external_entities, kg_graph, priority_entities, expansion_meta = kg_method_expansion(question, selected_entities)
        if expansion_meta.get("chosen"):
            artifacts.append(
                {
                    "title": f"{method_label(method)} expansion setup",
                    "items": [
                        {
                            "label": str(item.get("value")),
                            "node_type": item.get("kind"),
                            "score": item.get("score"),
                            "text": (
                                f"{item.get('label')} · seeds={', '.join(item.get('seed_codes') or [])} · "
                                f"scope={item.get('scope')} · expanded={item.get('expanded_count')} · "
                                f"scope_lexical={item.get('scope_lexical')} · "
                                f"weights={json.dumps(expansion_meta.get('weights') or {}, ensure_ascii=False)}"
                            ),
                        }
                        for item in expansion_meta.get("chosen", [])
                    ],
                }
            )
        if external_entities:
            artifacts.append(
                {
                    "title": "KG external entities from hierarchy expansion",
                    "items": [
                        {
                            "label": str(item.get("value")),
                            "node_type": item.get("kind"),
                            "score": item.get("score"),
                            "source_span_id": item.get("source_span_id"),
                            "text": f"{item.get('label')} · source={item.get('source')} · seed={item.get('source_seed')}",
                        }
                        for item in external_entities
                    ],
                }
            )

    sql_payload = generate_sql_with_openai(
        question,
        method,
        spans,
        selected_entities,
        external_entities,
        unresolved_spans,
        priority_entities,
    )
    if unresolved_spans:
        artifacts.append(
            {
                "title": "Unresolved extracted spans",
                "items": [{"label": span, "node_type": "unresolved", "text": span} for span in unresolved_spans],
            }
        )
    scope = Scope(
        method=method,
        group_by=[],
        where_clauses=[],
        entities=selected_entities,
        artifacts=artifacts,
        normalized_question=sql_payload["normalized_question"],
        kg_subgraph=kg_graph,
    )
    scope.sql = sql_payload["sql"]  # type: ignore[attr-defined]
    scope.extracted_spans = spans  # type: ignore[attr-defined]
    scope.database_entities = selected_entities  # type: ignore[attr-defined]
    scope.external_entities = external_entities  # type: ignore[attr-defined]
    scope.priority_entities = priority_entities  # type: ignore[attr-defined]
    scope.used_entities = sql_payload["used_entities"]  # type: ignore[attr-defined]
    return scope


def ai_query_result_payload(
    request: AIQueryRequest,
    question: str,
    method: str,
    scope: Scope,
) -> dict[str, Any]:
    base_sql = getattr(scope, "sql")
    result = execute_paged(base_sql, request.page, request.page_size, request.sort_by, request.sort_dir)
    result.update(
        {
            "method": method,
            "question": question,
            "entities": scope.entities,
            "extracted_spans": getattr(scope, "extracted_spans", []),
            "database_entities": getattr(scope, "database_entities", scope.entities),
            "external_entities": getattr(scope, "external_entities", []),
            "priority_entities": getattr(scope, "priority_entities", []),
            "used_entities": getattr(scope, "used_entities", []),
            "artifacts": scope.artifacts,
            "normalized_question": scope.normalized_question,
            "kg_subgraph": scope.kg_subgraph,
        }
    )
    return result


def ndjson_event(event: str, **payload: Any) -> str:
    return json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n"


def ai_query_event_stream(request: AIQueryRequest, question: str, method: str):
    yield ndjson_event("status", step_index=0, status="Extracting potential entity spans")
    spans = extract_query_spans(question)
    yield ndjson_event(
        "spans",
        step_index=0,
        status=f"Extracted {len(spans)} potential entity span{'s' if len(spans) != 1 else ''}",
        spans=spans,
    )

    yield ndjson_event("status", step_index=1, status="Embedding spans and finding database candidates")
    candidate_groups, candidate_map = top_database_candidates(spans, candidate_columns=AI_RETRIEVAL_COLUMNS)
    artifacts = [
        {
            "title": "Top database candidates per extracted span",
            "items": candidate_artifact_items(candidate_groups),
        }
    ]
    yield ndjson_event(
        "artifacts",
        step_index=1,
        status="Found database candidates",
        artifacts=artifacts,
    )

    yield ndjson_event("status", step_index=2, status="Selecting extracted database entities")
    selected_entities, unresolved_spans = select_database_entities(
        question,
        spans,
        candidate_groups,
        candidate_map,
        AI_RETRIEVAL_COLUMNS,
    )
    yield ndjson_event(
        "entities",
        step_index=2,
        status=f"Selected {len(selected_entities)} database entit{'y' if len(selected_entities) == 1 else 'ies'}",
        database_entities=selected_entities,
        unresolved_spans=unresolved_spans,
    )

    external_entities: list[dict[str, Any]] = []
    priority_entities: list[dict[str, Any]] = []
    kg_graph: dict[str, Any] = {"nodes": [], "edges": []}
    expansion_meta: dict[str, Any] = {}
    sql_step_index = 3
    if method in KG_METHODS:
        yield ndjson_event("status", step_index=3, status="Expanding related KG entities")
        external_entities, kg_graph, priority_entities, expansion_meta = kg_method_expansion(question, selected_entities)
        if expansion_meta.get("chosen"):
            artifacts.append(
                {
                    "title": f"{method_label(method)} expansion setup",
                    "items": [
                        {
                            "label": str(item.get("value")),
                            "node_type": item.get("kind"),
                            "score": item.get("score"),
                            "text": (
                                f"{item.get('label')} · seeds={', '.join(item.get('seed_codes') or [])} · "
                                f"scope={item.get('scope')} · expanded={item.get('expanded_count')} · "
                                f"scope_lexical={item.get('scope_lexical')} · "
                                f"weights={json.dumps(expansion_meta.get('weights') or {}, ensure_ascii=False)}"
                            ),
                        }
                        for item in expansion_meta.get("chosen", [])
                    ],
                }
            )
        if external_entities:
            artifacts.append(
                {
                    "title": "KG external entities from hierarchy expansion",
                    "items": [
                        {
                            "label": str(item.get("value")),
                            "node_type": item.get("kind"),
                            "score": item.get("score"),
                            "source_span_id": item.get("source_span_id"),
                            "text": f"{item.get('label')} · source={item.get('source')} · seed={item.get('source_seed')}",
                        }
                        for item in external_entities
                    ],
                }
            )
        yield ndjson_event(
            "kg_entities",
            step_index=3,
            status=f"Expanded {len(external_entities)} related KG entities",
            external_entities=external_entities,
            priority_entities=priority_entities,
            artifacts=artifacts,
            kg_subgraph=kg_graph,
        )
        sql_step_index = 4

    yield ndjson_event("status", step_index=sql_step_index, status="Generating SQL from resolved scope")
    sql_payload = generate_sql_with_openai(
        question,
        method,
        spans,
        selected_entities,
        external_entities,
        unresolved_spans,
        priority_entities,
    )
    if unresolved_spans:
        artifacts.append(
            {
                "title": "Unresolved extracted spans",
                "items": [{"label": span, "node_type": "unresolved", "text": span} for span in unresolved_spans],
            }
        )
    scope = Scope(
        method=method,
        group_by=[],
        where_clauses=[],
        entities=selected_entities,
        artifacts=artifacts,
        normalized_question=sql_payload["normalized_question"],
        kg_subgraph=kg_graph,
    )
    scope.sql = sql_payload["sql"]  # type: ignore[attr-defined]
    scope.extracted_spans = spans  # type: ignore[attr-defined]
    scope.database_entities = selected_entities  # type: ignore[attr-defined]
    scope.external_entities = external_entities  # type: ignore[attr-defined]
    scope.priority_entities = priority_entities  # type: ignore[attr-defined]
    scope.used_entities = sql_payload["used_entities"]  # type: ignore[attr-defined]
    yield ndjson_event(
        "scope",
        step_index=sql_step_index,
        status="Generated SQL from resolved scope",
        sql=getattr(scope, "sql"),
        normalized_question=scope.normalized_question,
        used_entities=getattr(scope, "used_entities", []),
        artifacts=artifacts,
    )

    yield ndjson_event("status", step_index=sql_step_index + 1, status="Running SQL and rendering results")
    yield ndjson_event(
        "result",
        step_index=sql_step_index + 1,
        status="Rendered results",
        result=ai_query_result_payload(request, question, method, scope),
    )


def query_embedding(question: str) -> list[float]:
    if app.state.client is None:
        app.state.client = openai_client()
    response = app.state.client.embeddings.create(model=EMBED_MODEL, input=[question])
    return list(response.data[0].embedding)


def relevant_doc_text(doc: dict[str, Any]) -> str:
    return str(doc.get("text") or doc.get("metadata", {}).get("kg_label") or "")


def add_entity(entities: list[dict[str, Any]], kind: str, value: str, label: str, source: str, score: float | None = None) -> None:
    key = (kind, value)
    if any((item["kind"], item["value"]) == key for item in entities):
        return
    entity = {"kind": kind, "value": value, "label": label, "source": source}
    if score is not None:
        entity["score"] = score
    entities.append(entity)


def extract_rag_scope(question: str, hits: list[dict[str, Any]]) -> Scope:
    entities: list[dict[str, Any]] = []
    clauses: list[str] = []
    artifacts: list[dict[str, Any]] = []
    diagnosis_codes: list[str] = []

    for hit in hits[:18]:
        doc = hit["document"]
        meta = doc.get("metadata") or {}
        doc_type = doc.get("doc_type")
        if doc_type in {"infectious_diagnosis_summary", "mkn_code"}:
            code = meta.get("diagnosis_code") or meta.get("code")
            label = meta.get("diagnosis_label") or meta.get("label_cs") or code
            if code and re.fullmatch(r"[A-Z][0-9]{2}", str(code)) and len(diagnosis_codes) < 12:
                diagnosis_codes.append(str(code))
                add_entity(entities, "diagnosis_code", str(code), f"{code} {label}", "standard vector retrieval", hit["score"])

    diagnosis_codes = sorted(dict.fromkeys(diagnosis_codes))
    if diagnosis_codes:
        clauses.append(f"diagnosis_code IN ({', '.join(q(code) for code in diagnosis_codes)})")

    years = re.findall(r"\b(20[0-9]{2})\b", question)
    if years:
        year_values = sorted(set(int(year) for year in years))
        clauses.append(f"report_year IN ({', '.join(str(year) for year in year_values)})")
        for year in year_values:
            add_entity(entities, "year", str(year), str(year), "literal year")

    group_by = infer_group_by(question)
    artifacts.append(
        {
            "title": "Top retrieved standard RAG chunks",
            "items": [
                {
                    "score": hit["score"],
                    "doc_type": hit["document"].get("doc_type"),
                    "text": relevant_doc_text(hit["document"])[:360],
                }
                for hit in hits[:8]
            ],
        }
    )
    normalized = normalize_question(question, entities, group_by)
    return Scope("rag", group_by, clauses, entities, artifacts, normalized, {"nodes": [], "edges": []})


def node_label(node_id: str) -> str:
    node = app.state.kg_nodes.get(node_id) or {}
    return node.get("label") or node_id


def table_diagnoses_for_block(block_code: str) -> list[dict[str, str]]:
    con = db()
    rows = con.execute(
        """
        SELECT DISTINCT diagnosis_code, diagnosis_name_cs
        FROM fact_infectious_disease_cases_enriched
        WHERE mkn_block_code = ?
        ORDER BY diagnosis_code
        """,
        [block_code],
    ).fetchall()
    con.close()
    return [{"code": row[0], "label": row[1]} for row in rows]


def table_diagnoses_for_chapter(chapter_number: str) -> list[dict[str, str]]:
    con = db()
    rows = con.execute(
        """
        SELECT DISTINCT diagnosis_code, diagnosis_name_cs
        FROM fact_infectious_disease_cases_enriched
        WHERE mkn_chapter_number = ?
        ORDER BY diagnosis_code
        """,
        [chapter_number],
    ).fetchall()
    con.close()
    return [{"code": row[0], "label": row[1]} for row in rows]


def table_diagnoses_for_range(start_code: str, end_code: str) -> list[dict[str, str]]:
    con = db()
    rows = con.execute(
        """
        SELECT DISTINCT diagnosis_code, diagnosis_name_cs
        FROM fact_infectious_disease_cases_enriched
        WHERE diagnosis_code BETWEEN ? AND ?
        ORDER BY diagnosis_code
        """,
        [start_code, end_code],
    ).fetchall()
    con.close()
    return [{"code": row[0], "label": row[1]} for row in rows]


def parse_diagnosis_range(question: str) -> tuple[str, str] | None:
    match = re.search(r"\b([A-Z][0-9]{2})\s*[-–]\s*([A-Z][0-9]{2})\b", question.upper())
    if not match:
        return None
    return match.group(1), match.group(2)


def parse_literal_diagnosis_codes(question: str) -> list[str]:
    return sorted(set(re.findall(r"\b[A-Z][0-9]{2}\b", question.upper())))


def region_matches_from_question(question: str, limit: int = 8) -> list[dict[str, str]]:
    return []


def age_scope_from_question(question: str) -> tuple[str, str, list[str]] | None:
    return None


def diagnosis_code_from_node(node_id: str) -> str | None:
    node = app.state.kg_nodes.get(node_id) or {}
    props = node.get("properties") or {}
    code = props.get("code")
    if code and re.fullmatch(r"[A-Z][0-9]{2}", str(code)):
        return str(code)
    return None


def profile_similar_diagnoses(seed_codes: list[str], *, selected_block: str | None, limit: int = 10) -> list[dict[str, Any]]:
    seed_set = set(seed_codes)
    candidates: dict[str, dict[str, Any]] = {}
    for seed_code in seed_codes:
        seed_id = f"infectious_diagnosis:{seed_code}"
        for edge in app.state.out_edges.get(seed_id, []) + app.state.in_edges.get(seed_id, []):
            if edge.get("type") != "SIMILAR_CASE_PROFILE":
                continue
            other_id = edge["target"] if edge["source"] == seed_id else edge["source"]
            other_code = diagnosis_code_from_node(other_id)
            if not other_code or other_code in seed_set:
                continue
            props = edge.get("properties") or {}
            other_node = app.state.kg_nodes.get(other_id) or {}
            other_props = other_node.get("properties") or {}
            other_block = other_props.get("mkn_block_code")
            score = float(props.get("profile_similarity") or 0)
            external = bool(selected_block and other_block != selected_block)
            current = candidates.get(other_code)
            if current is None or score > current["score"]:
                candidates[other_code] = {
                    "code": other_code,
                    "label": other_node.get("label") or other_code,
                    "score": round(score, 4),
                    "external_to_selected_block": external,
                    "mkn_block_code": other_block,
                    "source_seed_code": seed_code,
                    "component_similarity": props.get("component_similarity") or {},
                }
    return sorted(
        candidates.values(),
        key=lambda item: (item["external_to_selected_block"], item["score"]),
        reverse=True,
    )[:limit]


def compact_node(node_id: str, highlight: bool = False, expanded: bool = False) -> dict[str, Any]:
    node = app.state.kg_nodes.get(node_id) or {}
    props = node.get("properties") or {}
    return {
        "id": node_id,
        "label": node.get("label") or node_id,
        "type": node.get("type") or "node",
        "highlight": highlight,
        "expanded": expanded,
        "code": props.get("code")
        or props.get("block_code")
        or props.get("year")
        or props.get("month")
        or props.get("value"),
    }


def edge_strength(edge: dict[str, Any]) -> float:
    props = edge.get("properties") or {}
    for key in ["profile_similarity", "cosine_similarity", "lift", "weighted_support"]:
        value = props.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def build_kg_graph(seed_nodes: list[str], max_expand: int = 80) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    preferred_edges = {
        "CONTAINS_MKN_BLOCK",
        "CONTAINS_MKN_CODE",
        "HAS_TABLE_DIAGNOSIS_VALUE",
        "SAME_AS_MKN_BLOCK",
        "SAME_AS_MKN_CODE",
        "WEIGHTED_COOCCURS_WITH",
        "SIMILAR_CASE_PROFILE",
    }
    queue = list(dict.fromkeys(seed_nodes))
    for seed in queue:
        nodes[seed] = compact_node(seed, highlight=True)
    for seed in queue[:20]:
        all_related = app.state.out_edges.get(seed, []) + app.state.in_edges.get(seed, [])
        related = [edge for edge in all_related if edge["type"] in preferred_edges]
        if not related:
            related = all_related[:12]
        related = sorted(related, key=edge_strength, reverse=True)
        related = related[:max_expand]
        for edge in related:
            source = edge["source"]
            target = edge["target"]
            nodes.setdefault(source, compact_node(source, highlight=source in seed_nodes, expanded=source not in seed_nodes))
            nodes.setdefault(target, compact_node(target, highlight=target in seed_nodes, expanded=target not in seed_nodes))
            if len(edges) < max_expand:
                edges.append({"source": source, "target": target, "type": edge["type"], "properties": edge.get("properties") or {}})
    return {"nodes": list(nodes.values())[:120], "edges": edges[:160]}


def expand_kg_scope(question: str, hits: list[dict[str, Any]]) -> Scope:
    entities: list[dict[str, Any]] = []
    clauses: list[str] = []
    artifacts: list[dict[str, Any]] = []
    seed_nodes: list[str] = []
    diagnosis_codes: dict[str, float] = {}

    block_candidates: list[tuple[float, str, str]] = []
    explicit_range = parse_diagnosis_range(question)
    literal_codes = parse_literal_diagnosis_codes(question)
    for code in literal_codes:
        diagnosis_codes.setdefault(code, 1.0)
        seed_nodes.append(f"infectious_diagnosis:{code}")
        add_entity(entities, "diagnosis_code", code, code, "literal diagnosis code")

    for hit in hits[:16]:
        doc = hit["document"]
        meta = doc.get("metadata") or {}
        node_id = meta.get("kg_node_id")
        node_type = meta.get("kg_node_type")
        props = meta.get("properties") or {}
        if node_type == "mkn_block":
            candidate_block = props.get("block_code")
            if candidate_block:
                block_candidates.append((float(hit["score"]), str(candidate_block), str(meta.get("kg_label") or candidate_block)))
                if node_id:
                    seed_nodes.append(str(node_id))
        if node_type == "diagnosis_value":
            code = props.get("code")
            if code:
                diagnosis_codes[str(code)] = max(float(hit["score"]), diagnosis_codes.get(str(code), 0.0))
                if node_id:
                    seed_nodes.append(str(node_id))
                add_entity(entities, "diagnosis_code", str(code), str(meta.get("kg_label") or code), "KG vector retrieval", hit["score"])
        elif node_type == "mkn_diagnosis":
            code = props.get("code")
            if code and re.fullmatch(r"[A-Z][0-9]{2}", str(code)):
                diagnosis_codes[str(code)] = max(float(hit["score"]), diagnosis_codes.get(str(code), 0.0))
                seed_nodes.append(f"infectious_diagnosis:{code}")
                add_entity(entities, "diagnosis_code", str(code), str(meta.get("kg_label") or code), "KG vector retrieval", hit["score"])

    block_code: str | None = None
    block_label: str | None = None
    if block_candidates:
        _, block_code, block_label = sorted(block_candidates, reverse=True)[0]
        add_entity(entities, "mkn_block_code", block_code, block_label, "KG vector retrieval")

    selected_diagnosis_codes: list[str] = []
    if block_code:
        clauses.append(f"mkn_block_code = {q(block_code)}")
        expanded = table_diagnoses_for_block(block_code)
        selected_diagnosis_codes = [item["code"] for item in expanded]
        if expanded:
            add_entity(
                entities,
                "expanded_diagnosis_scope",
                ", ".join(item["code"] for item in expanded),
                f"{len(expanded)} table-present diagnosis codes from {block_code}",
                "KG block expansion from source-derived MKN block",
            )
            seed_nodes.extend([f"infectious_diagnosis:{item['code']}" for item in expanded])
            artifacts.append(
                {
                    "title": f"KG block expansion for {block_code}",
                    "items": [
                        {
                            "label": item["code"],
                            "node_type": "diagnosis_value",
                            "text": f"{item['code']} {item['label']}",
                        }
                        for item in expanded
                    ],
                }
            )
    elif explicit_range:
        start_code, end_code = explicit_range
        clauses.append(f"diagnosis_code BETWEEN {q(start_code)} AND {q(end_code)}")
        expanded = table_diagnoses_for_range(start_code, end_code)
        selected_diagnosis_codes = [item["code"] for item in expanded]
        add_entity(entities, "diagnosis_range", f"{start_code}-{end_code}", f"{start_code}-{end_code}", "literal diagnosis range")
        seed_nodes.extend([f"infectious_diagnosis:{item['code']}" for item in expanded])
        if expanded:
            artifacts.append(
                {
                    "title": f"Table-present diagnosis values in literal range {start_code}-{end_code}",
                    "items": [
                        {
                            "label": item["code"],
                            "node_type": "diagnosis_value",
                            "text": f"{item['code']} {item['label']}",
                        }
                        for item in expanded
                    ],
                }
            )
    elif diagnosis_codes:
        selected_diagnosis_codes = sorted(diagnosis_codes, key=diagnosis_codes.get, reverse=True)[:16]
        clauses.append(f"diagnosis_code IN ({', '.join(q(code) for code in selected_diagnosis_codes)})")

    years = re.findall(r"\b(20[0-9]{2})\b", question)
    if years:
        year_values = sorted(set(int(year) for year in years))
        clauses.append(f"report_year IN ({', '.join(str(year) for year in year_values)})")
        for year in year_values:
            add_entity(entities, "year", str(year), str(year), "literal year")

    if selected_diagnosis_codes:
        similar = profile_similar_diagnoses(selected_diagnosis_codes, selected_block=block_code)
        if similar:
            artifacts.append(
                {
                    "title": "Top diagnoses with similar weighted case profiles",
                    "items": [
                        {
                            "label": item["code"],
                            "node_type": "similar_diagnosis",
                            "score": item["score"],
                            "text": (
                                f"{item['label']} · block={item.get('mkn_block_code')} · "
                                f"external_to_selected_block={item['external_to_selected_block']} · "
                                f"source={item['source_seed_code']}"
                            ),
                        }
                        for item in similar
                    ],
                }
            )
            for item in similar[:6]:
                add_entity(
                    entities,
                    "similar_diagnosis",
                    item["code"],
                    f"{item['label']} (profile similarity {item['score']})",
                    "weighted case-profile similarity",
                    item["score"],
                )
                seed_nodes.append(f"infectious_diagnosis:{item['code']}")

    group_by = infer_group_by(question)
    artifacts.append(
        {
            "title": "Top retrieved KG nodes",
            "items": [
                {
                    "score": hit["score"],
                    "node_type": hit["document"].get("metadata", {}).get("kg_node_type"),
                    "label": hit["document"].get("metadata", {}).get("kg_label"),
                    "text": relevant_doc_text(hit["document"])[:300],
                }
                for hit in hits[:8]
            ],
        }
    )
    normalized = normalize_question(question, entities, group_by)
    return Scope("kg_rag", group_by, clauses, entities, artifacts, normalized, build_kg_graph(seed_nodes))


def infer_group_by(question: str) -> list[str]:
    lowered = norm_text(question)
    if "podle roku" in lowered or "by year" in lowered:
        return ["report_year"]
    if "podle měsí" in lowered or "podle mesi" in lowered or "by month" in lowered:
        return ["report_month"]
    if "věkové" in lowered or "věkov" in lowered or "age group" in lowered:
        return ["age_group_name_cs"]
    if "podle pohlav" in lowered or "by sex" in lowered or "by gender" in lowered:
        return ["sex_name_cs"]
    if "podle kraje" in lowered or "by region" in lowered or "region" in lowered:
        return ["region_name_cs"]
    if "podle diagn" in lowered or "by diagnosis" in lowered:
        return ["diagnosis_code", "diagnosis_name_cs"]
    if "kolik" in lowered or "how many" in lowered:
        if "pra" in lowered:
            return ["region_name_cs"]
        return []
    return []


def normalize_question(question: str, entities: list[dict[str, Any]], group_by: list[str]) -> str:
    entity_text = "; ".join(f"{item['kind']}={item['value']}" for item in entities[:10]) or "no linked entities"
    group_text = ", ".join(group_by) if group_by else "overall total"
    return f"Scope resolved from query: {entity_text}. SQL grouping: {group_text}. Measure: SUM(reported_case_count)."


def sql_for_scope(scope: Scope) -> str:
    where = f"WHERE {' AND '.join(scope.where_clauses)}" if scope.where_clauses else ""
    if scope.group_by:
        select_dims = ",\n  ".join(scope.group_by)
        group_dims = ", ".join(scope.group_by)
        return f"""
SELECT
  {select_dims},
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM {FINAL_TABLE}
{where}
GROUP BY {group_dims}
ORDER BY {group_dims}
"""
    return f"""
SELECT
  CAST(SUM(reported_case_count) AS BIGINT) AS reported_case_count
FROM {FINAL_TABLE}
{where}
"""


@app.post("/api/ai/query")
def ai_query(request: AIQueryRequest) -> dict[str, Any]:
    question = request.question.strip()
    if not question:
        raise HTTPException(400, "Question is required.")
    method = "full_kg_rag" if request.method == "kg_rag" else request.method
    scope = build_ai_scope_with_openai(question, method)
    return ai_query_result_payload(request, question, method, scope)


@app.post("/api/ai/query/stream")
def ai_query_stream(request: AIQueryRequest) -> StreamingResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(400, "Question is required.")
    method = "full_kg_rag" if request.method == "kg_rag" else request.method

    def events():
        try:
            yield from ai_query_event_stream(request, question, method)
        except Exception as exc:  # pragma: no cover - exercised through browser/network failures
            yield ndjson_event("error", status="AI query failed", message=str(exc))

    return StreamingResponse(events(), media_type="application/x-ndjson")
