#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import duckdb  # type: ignore  # noqa: E402


DB_PATH = ROOT / "sql_database" / "db" / "semantics.duckdb"
EVAL_PATH = ROOT / "outputs" / "kg_rag_evaluation_queries.json"
OUT_DIR = ROOT / "dg_evaluation"
FACT_TABLE = "fact_infectious_disease_cases_enriched"

METHODS = [
    ("rag", "RAG"),
    ("kg_rag", "KG-RAG"),
]

PUBLIC_FILTER_COLUMNS = {
    "diagnosis_code",
    "diagnosis_name_cs",
    "report_year",
    "report_month",
    "region_name_cs",
    "region_code",
    "age_group_name_cs",
    "age_group_code",
    "sex_name_cs",
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def db() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def sql_literal(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def code_range_values(range_text: str) -> list[str]:
    match = re.fullmatch(r"([A-Z])(\d{2})-([A-Z])(\d{2})", str(range_text).strip())
    if not match or match.group(1) != match.group(3):
        return []
    letter = match.group(1)
    start = int(match.group(2))
    end = int(match.group(4))
    if start > end:
        start, end = end, start
    return [f"{letter}{number:02d}" for number in range(start, end + 1)]


def distinct_fact_codes(con: duckdb.DuckDBPyConnection, codes: list[str]) -> list[str]:
    if not codes:
        return []
    values = ", ".join(sql_literal(code) for code in codes)
    rows = con.execute(
        f"""
        SELECT DISTINCT diagnosis_code
        FROM {FACT_TABLE}
        WHERE diagnosis_code IN ({values})
        ORDER BY diagnosis_code
        """
    ).fetchall()
    return [str(row[0]) for row in rows if row[0] is not None]


def gold_diagnosis_codes(question: dict[str, Any], con: duckdb.DuckDBPyConnection) -> tuple[list[str], str]:
    scope = question.get("gold_scope") or {}
    if scope.get("mkn_group"):
        range_codes = code_range_values(str(scope["mkn_group"]))
        table_codes = distinct_fact_codes(con, range_codes)
        if table_codes:
            return table_codes, f"DuckDB table-present diagnosis codes in range {scope['mkn_group']}"
    raw_codes = [str(code) for code in scope.get("diagnosis_codes") or []]
    table_codes = distinct_fact_codes(con, raw_codes)
    if table_codes:
        return table_codes, "Gold diagnosis codes intersected with DuckDB fact table"
    return sorted(set(raw_codes)), "Gold diagnosis codes from JSON"


def lookup_age_labels(con: duckdb.DuckDBPyConnection, codes: list[str]) -> list[str]:
    if not codes:
        return []
    values = ", ".join(sql_literal(code) for code in codes)
    rows = con.execute(
        f"""
        SELECT DISTINCT age_group_name_cs
        FROM {FACT_TABLE}
        WHERE age_group_code IN ({values}) AND age_group_name_cs IS NOT NULL
        ORDER BY age_group_name_cs
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def lookup_region_labels(con: duckdb.DuckDBPyConnection, codes: list[str]) -> list[str]:
    if not codes:
        return []
    values = ", ".join(sql_literal(code) for code in codes)
    rows = con.execute(
        f"""
        SELECT DISTINCT region_name_cs
        FROM {FACT_TABLE}
        WHERE region_code IN ({values}) AND region_name_cs IS NOT NULL
        ORDER BY region_name_cs
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def expected_filters(question: dict[str, Any], con: duckdb.DuckDBPyConnection) -> tuple[dict[str, list[Any]], str]:
    scope = question.get("gold_scope") or {}
    filters: dict[str, list[Any]] = {}
    diagnosis_codes, diagnosis_source = gold_diagnosis_codes(question, con)
    filters["diagnosis_code"] = diagnosis_codes

    if scope.get("years"):
        filters["report_year"] = sorted({int(year) for year in scope["years"]})

    if scope.get("age_labels"):
        filters["age_group_name_cs"] = sorted({str(label) for label in scope["age_labels"]})
    elif scope.get("age_groups"):
        filters["age_group_name_cs"] = lookup_age_labels(con, [str(code) for code in scope["age_groups"]])

    if scope.get("regions"):
        filters["region_name_cs"] = sorted({str(region) for region in scope["regions"]})
    elif scope.get("region_code"):
        labels = lookup_region_labels(con, [str(scope["region_code"])])
        if labels:
            filters["region_name_cs"] = labels
        elif scope.get("region_label"):
            filters["region_name_cs"] = [str(scope["region_label"])]

    return {key: sorted(set(value), key=lambda item: str(item)) for key, value in filters.items()}, diagnosis_source


def post_json(api_base: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/ai/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_api(api_base: str, questions: list[dict[str, Any]], timeout: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for question in questions:
        for method, label in METHODS:
            started = time.time()
            record = {
                "id": question["id"],
                "question": question["query_cs"],
                "method": method,
                "method_label": label,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                response = post_json(
                    api_base,
                    {
                        "question": question["query_cs"],
                        "method": method,
                        "page": 1,
                        "page_size": 500,
                    },
                    timeout,
                )
                record["ok"] = True
                record["response"] = response
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                record["ok"] = False
                record["error"] = str(exc)
            record["elapsed_seconds"] = round(time.time() - started, 3)
            print(f"{record['id']} {label}: {'ok' if record['ok'] else 'failed'} ({record['elapsed_seconds']}s)")
            results.append(record)
    return results


def records_from_response_dir(response_dir: Path, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response_dir = response_dir.resolve()
    results: list[dict[str, Any]] = []
    for question in questions:
        for method, label in METHODS:
            path = response_dir / f"{question['id']}_{method}.json"
            record = {
                "id": question["id"],
                "question": question["query_cs"],
                "method": method,
                "method_label": label,
                "started_at": None,
                "elapsed_seconds": None,
                "source_file": str(path.relative_to(ROOT)) if path.exists() else str(path),
            }
            if not path.exists():
                record["ok"] = False
                record["error"] = f"Missing response file: {path}"
            else:
                try:
                    response = read_json(path)
                    if isinstance(response, dict) and response.get("detail") and not response.get("base_sql"):
                        record["ok"] = False
                        record["error"] = str(response.get("detail"))
                        record["response"] = response
                    else:
                        record["ok"] = True
                        record["response"] = response
                except (OSError, json.JSONDecodeError) as exc:
                    record["ok"] = False
                    record["error"] = str(exc)
            results.append(record)
    return results


def parse_sql_value(raw: str) -> Any:
    value = raw.strip().rstrip(";")
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('""', '"')
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def split_sql_list(raw: str) -> list[Any]:
    values: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(raw):
        char = raw[index]
        if quote:
            current.append(char)
            if char == quote:
                doubled = index + 1 < len(raw) and raw[index + 1] == quote
                if doubled:
                    current.append(raw[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char == ",":
            values.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    if current:
        values.append("".join(current).strip())
    return [parse_sql_value(value) for value in values if value]


def where_clause(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", sql or "").strip()
    match = re.search(
        r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bOFFSET\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def parse_filters_from_sql(sql: str) -> dict[str, set[Any]]:
    where = where_clause(sql)
    filters: dict[str, set[Any]] = defaultdict(set)
    for column in PUBLIC_FILTER_COLUMNS:
        escaped = re.escape(column)
        for match in re.finditer(rf"\b{escaped}\b\s+IN\s*\((.*?)\)", where, flags=re.IGNORECASE):
            for value in split_sql_list(match.group(1)):
                filters[column].add(value)
        for match in re.finditer(
            rf"\b{escaped}\b\s*=\s*('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|-?\d+)",
            where,
            flags=re.IGNORECASE,
        ):
            filters[column].add(parse_sql_value(match.group(1)))
        for match in re.finditer(
            rf"\b{escaped}\b\s+BETWEEN\s+(-?\d+)\s+AND\s+(-?\d+)",
            where,
            flags=re.IGNORECASE,
        ):
            start = int(match.group(1))
            end = int(match.group(2))
            for value in range(min(start, end), max(start, end) + 1):
                filters[column].add(value)
    return filters


def entity_filters(response: dict[str, Any]) -> dict[str, set[Any]]:
    filters: dict[str, set[Any]] = defaultdict(set)
    for key in ("used_entities", "priority_entities", "database_entities"):
        for entity in response.get(key) or []:
            if not isinstance(entity, dict):
                continue
            if entity.get("role") == "group_by" or entity.get("entity_type") == "column":
                continue
            column = str(entity.get("filter_column") or entity.get("column") or "")
            if column not in PUBLIC_FILTER_COLUMNS:
                continue
            value = entity.get("filter_value") if "filter_value" in entity else entity.get("value")
            if value is None or value == "":
                continue
            filters[column].add(value)
    return filters


def map_diagnosis_names(con: duckdb.DuckDBPyConnection, values: set[Any]) -> set[str]:
    mapped: set[str] = set()
    for value in values:
        text = str(value)
        code_match = re.match(r"^([A-Z][0-9]{2})\b", text)
        if code_match:
            mapped.add(code_match.group(1))
            continue
        rows = con.execute(
            f"""
            SELECT DISTINCT diagnosis_code
            FROM {FACT_TABLE}
            WHERE diagnosis_name_cs = ?
            ORDER BY diagnosis_code
            """,
            [text],
        ).fetchall()
        mapped.update(str(row[0]) for row in rows)
    return mapped


def normalize_predicted_filters(
    raw_filters: dict[str, set[Any]],
    con: duckdb.DuckDBPyConnection,
) -> dict[str, list[Any]]:
    normalized: dict[str, set[Any]] = defaultdict(set)
    for column, values in raw_filters.items():
        if column == "diagnosis_code":
            for value in values:
                text = str(value)
                if re.fullmatch(r"[A-Z][0-9]{2}", text):
                    normalized["diagnosis_code"].add(text)
        elif column == "diagnosis_name_cs":
            normalized["diagnosis_code"].update(map_diagnosis_names(con, values))
        elif column == "report_year":
            for value in values:
                try:
                    normalized["report_year"].add(int(value))
                except (TypeError, ValueError):
                    normalized["report_year"].add(str(value))
        elif column == "age_group_name_cs":
            normalized["age_group_name_cs"].update(str(value) for value in values)
        elif column == "age_group_code":
            normalized["age_group_name_cs"].update(lookup_age_labels(con, [str(value) for value in values]))
        elif column == "region_name_cs":
            normalized["region_name_cs"].update(str(value) for value in values)
        elif column == "region_code":
            normalized["region_name_cs"].update(lookup_region_labels(con, [str(value) for value in values]))
        elif column == "report_month":
            for value in values:
                try:
                    normalized["report_month"].add(int(value))
                except (TypeError, ValueError):
                    normalized["report_month"].add(str(value))
        elif column == "sex_name_cs":
            normalized["sex_name_cs"].update(str(value) for value in values)
    return {key: sorted(value, key=lambda item: str(item)) for key, value in normalized.items() if value}


def row_filter_values(
    response: dict[str, Any],
    expected_columns: set[str],
    con: duckdb.DuckDBPyConnection,
) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = defaultdict(set)
    for row in response.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if "diagnosis_code" in expected_columns:
            if row.get("diagnosis_code") not in {None, ""}:
                values["diagnosis_code"].add(str(row["diagnosis_code"]))
            if row.get("diagnosis_name_cs") not in {None, ""}:
                values["diagnosis_code"].update(map_diagnosis_names(con, {row["diagnosis_name_cs"]}))
        if "report_year" in expected_columns and row.get("report_year") not in {None, ""}:
            try:
                values["report_year"].add(int(row["report_year"]))
            except (TypeError, ValueError):
                values["report_year"].add(str(row["report_year"]))
        if "age_group_name_cs" in expected_columns:
            if row.get("age_group_name_cs") not in {None, ""}:
                values["age_group_name_cs"].add(str(row["age_group_name_cs"]))
            if row.get("age_group_code") not in {None, ""}:
                values["age_group_name_cs"].update(lookup_age_labels(con, [str(row["age_group_code"])]))
        if "region_name_cs" in expected_columns:
            if row.get("region_name_cs") not in {None, ""}:
                values["region_name_cs"].add(str(row["region_name_cs"]))
            if row.get("region_code") not in {None, ""}:
                values["region_name_cs"].update(lookup_region_labels(con, [str(row["region_code"])]))
        if "report_month" in expected_columns and row.get("report_month") not in {None, ""}:
            try:
                values["report_month"].add(int(row["report_month"]))
            except (TypeError, ValueError):
                values["report_month"].add(str(row["report_month"]))
        if "sex_name_cs" in expected_columns and row.get("sex_name_cs") not in {None, ""}:
            values["sex_name_cs"].add(str(row["sex_name_cs"]))
    return values


def predicted_filters(
    record: dict[str, Any],
    con: duckdb.DuckDBPyConnection,
    expected_columns: set[str],
) -> dict[str, list[Any]]:
    if not record.get("ok"):
        return {}
    response = record.get("response") or {}
    raw = parse_filters_from_sql(str(response.get("base_sql") or response.get("sql") or ""))
    sql_filters = normalize_predicted_filters(raw, con)
    row_values = row_filter_values(response, expected_columns, con)
    for column, values in row_values.items():
        if column not in sql_filters:
            sql_filters[column] = sorted(values, key=lambda item: str(item))
    return sql_filters


def precision_recall_f1(gold: set[str], predicted: set[str]) -> dict[str, Any]:
    tp = len(gold & predicted)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold) if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact": int(fp == 0 and fn == 0),
    }


def filter_differences(expected: dict[str, list[Any]], predicted: dict[str, list[Any]]) -> dict[str, Any]:
    expected_columns = set(expected)
    predicted_columns = set(predicted)
    missing_columns = sorted(expected_columns - predicted_columns)
    unexpected_columns = sorted(predicted_columns - expected_columns)
    mismatched: dict[str, dict[str, list[Any]]] = {}
    for column in sorted(expected_columns & predicted_columns):
        expected_values = {str(value) for value in expected[column]}
        predicted_values = {str(value) for value in predicted[column]}
        if expected_values != predicted_values:
            mismatched[column] = {
                "missing": sorted(expected_values - predicted_values),
                "unexpected": sorted(predicted_values - expected_values),
            }
    correct = not missing_columns and not unexpected_columns and not mismatched
    return {
        "all_filters_correct": int(correct),
        "missing_columns": missing_columns,
        "unexpected_columns": unexpected_columns,
        "mismatched_columns": mismatched,
    }


def evaluate(
    questions: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    records_by_key = {(item["id"], item["method"]): item for item in raw_results}
    diagnosis_rows: list[dict[str, Any]] = []
    filter_rows: list[dict[str, Any]] = []
    ground_truth: dict[str, Any] = {}

    con = db()
    try:
        for question in questions:
            filters, diagnosis_source = expected_filters(question, con)
            ground_truth[question["id"]] = {
                "question": question["query_cs"],
                "filters": filters,
                "diagnosis_source": diagnosis_source,
            }
            gold_codes = set(str(code) for code in filters.get("diagnosis_code") or [])
            for method, label in METHODS:
                record = records_by_key.get((question["id"], method), {})
                predicted = predicted_filters(record, con, set(filters))
                predicted_codes = set(str(code) for code in predicted.get("diagnosis_code") or [])
                diagnosis = precision_recall_f1(gold_codes, predicted_codes)
                diagnosis_rows.append(
                    {
                        "id": question["id"],
                        "method": label,
                        "question": question["query_cs"],
                        "gold_diagnosis_codes": " ".join(sorted(gold_codes)),
                        "predicted_diagnosis_codes": " ".join(sorted(predicted_codes)),
                        **diagnosis,
                    }
                )
                diff = filter_differences(filters, predicted)
                filter_rows.append(
                    {
                        "id": question["id"],
                        "method": label,
                        "question": question["query_cs"],
                        "expected_filters": json.dumps(filters, ensure_ascii=False, sort_keys=True),
                        "predicted_filters": json.dumps(predicted, ensure_ascii=False, sort_keys=True),
                        "all_filters_correct": diff["all_filters_correct"],
                        "missing_columns": ", ".join(diff["missing_columns"]),
                        "unexpected_columns": ", ".join(diff["unexpected_columns"]),
                        "mismatched_columns": json.dumps(diff["mismatched_columns"], ensure_ascii=False, sort_keys=True),
                    }
                )
    finally:
        con.close()

    summary = summarize(diagnosis_rows, filter_rows)
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["questions"] = len(questions)
    summary["methods"] = [label for _, label in METHODS]
    summary["ground_truth"] = ground_truth
    return diagnosis_rows, filter_rows, summary


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(diagnosis_rows: list[dict[str, Any]], filter_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"diagnosis_by_method": {}, "all_filters_by_method": {}}
    for _, label in METHODS:
        rows = [row for row in diagnosis_rows if row["method"] == label]
        total_tp = sum(int(row["tp"]) for row in rows)
        total_fp = sum(int(row["fp"]) for row in rows)
        total_fn = sum(int(row["fn"]) for row in rows)
        micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
        micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
        micro_f1 = (
            2 * micro_precision * micro_recall / (micro_precision + micro_recall)
            if micro_precision + micro_recall
            else 0.0
        )
        summary["diagnosis_by_method"][label] = {
            "macro_precision": mean([float(row["precision"]) for row in rows]),
            "macro_recall": mean([float(row["recall"]) for row in rows]),
            "macro_f1": mean([float(row["f1"]) for row in rows]),
            "micro_precision": micro_precision,
            "micro_recall": micro_recall,
            "micro_f1": micro_f1,
            "exact_diagnosis_count": sum(int(row["exact"]) for row in rows),
            "total_questions": len(rows),
            "exact_diagnosis_rate": mean([float(row["exact"]) for row in rows]),
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
        }

        frows = [row for row in filter_rows if row["method"] == label]
        correct = sum(int(row["all_filters_correct"]) for row in frows)
        summary["all_filters_by_method"][label] = {
            "correct": correct,
            "total_questions": len(frows),
            "accuracy": correct / len(frows) if frows else 0.0,
        }
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(item).replace("\n", " ") for item in row) + " |")
    return "\n".join(lines)


def write_readme(
    path: Path,
    api_base: str,
    diagnosis_rows: list[dict[str, Any]],
    filter_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    diagnosis_summary_rows = []
    for label, data in summary["diagnosis_by_method"].items():
        diagnosis_summary_rows.append(
            [
                label,
                data["macro_precision"],
                data["macro_recall"],
                data["macro_f1"],
                data["micro_precision"],
                data["micro_recall"],
                data["micro_f1"],
                f"{data['exact_diagnosis_count']}/{data['total_questions']}",
            ]
        )

    filter_summary_rows = []
    for label, data in summary["all_filters_by_method"].items():
        filter_summary_rows.append([label, f"{data['correct']}/{data['total_questions']}", data["accuracy"]])

    per_question_rows = [
        [
            row["id"],
            row["method"],
            row["precision"],
            row["recall"],
            row["f1"],
            row["exact"],
            row["predicted_diagnosis_codes"] or "-",
        ]
        for row in diagnosis_rows
    ]

    filter_rows_md = [
        [
            row["id"],
            row["method"],
            row["all_filters_correct"],
            row["missing_columns"] or "-",
            row["unexpected_columns"] or "-",
            row["mismatched_columns"] if row["mismatched_columns"] != "{}" else "-",
        ]
        for row in filter_rows
    ]

    text = f"""# Diagnosis and Filter Evaluation

Generated: {summary["generated_at"]}

This folder evaluates the current evaluation-question set from `outputs/kg_rag_evaluation_queries.json` against live outputs from `/api/ai/query` at `{api_base}`.

Diagnosis precision/recall/F1 compares predicted `diagnosis_code` filters with the gold diagnosis scope. When an evaluation item defines a diagnosis range such as `A00-A09`, `B00-B09`, `B15-B19`, or `J12-J18`, the gold set is resolved through DuckDB by intersecting that range with diagnosis codes present in `{FACT_TABLE}`. Other filter gold values come from the current JSON gold scope and DuckDB label lookups.

The all-filters score is binary per question and method: `1` means every expected filter column has exactly the expected values and no unexpected filter column is present; `0` means at least one filter column is missing, extra, or has wrong values. This checks filter semantics rather than literal SQL formatting.

Predicted filters are parsed from SQL `WHERE` clauses first. If an expected filter column is not explicit in `WHERE` but appears in the returned result rows, the scorer uses the distinct returned row values for that expected column. Unused retrieval candidates are not counted as applied filters.

## Diagnosis Totals

{markdown_table(
        [
            "Method",
            "Macro P",
            "Macro R",
            "Macro F1",
            "Micro P",
            "Micro R",
            "Micro F1",
            "Exact diagnoses",
        ],
        diagnosis_summary_rows,
    )}

## All Filters Total

{markdown_table(["Method", "Correct / total", "Accuracy"], filter_summary_rows)}

## Diagnosis Metrics by Question

{markdown_table(
        ["ID", "Method", "P", "R", "F1", "Exact", "Predicted diagnosis codes"],
        per_question_rows,
    )}

## All Filters by Question

{markdown_table(
        ["ID", "Method", "Correct", "Missing columns", "Unexpected columns", "Mismatched columns"],
        filter_rows_md,
    )}

## Files

- `raw_results.json`: raw API responses for both methods.
- `diagnosis_metrics.csv`: per-question diagnosis precision, recall, F1, TP/FP/FN.
- `filter_metrics.csv`: per-question binary complete-filter comparison.
- `evaluation_summary.json`: aggregate metrics plus resolved gold filters.
- `run_evaluation.py`: reproducible runner.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG/KG-RAG diagnosis and filter correctness.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8767", help="Running demo API base URL.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout in seconds.")
    parser.add_argument("--refresh", action="store_true", help="Call the API again instead of using raw_results.json.")
    parser.add_argument(
        "--response-dir",
        type=Path,
        help="Read saved API responses named EQ-01_rag.json, EQ-01_kg_rag.json, etc.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = read_json(EVAL_PATH, default=[])
    if not questions:
        raise SystemExit(f"No evaluation questions found at {EVAL_PATH}")

    raw_path = OUT_DIR / "raw_results.json"
    if args.response_dir:
        raw_results = records_from_response_dir(args.response_dir, questions)
        write_json(raw_path, raw_results)
    elif args.refresh or not raw_path.exists():
        raw_results = run_api(args.api_base, questions, args.timeout)
        write_json(raw_path, raw_results)
    else:
        raw_results = read_json(raw_path, default=[])

    diagnosis_rows, filter_rows, summary = evaluate(questions, raw_results)
    write_csv(OUT_DIR / "diagnosis_metrics.csv", diagnosis_rows)
    write_csv(OUT_DIR / "filter_metrics.csv", filter_rows)
    write_json(OUT_DIR / "evaluation_summary.json", summary)
    write_readme(OUT_DIR / "README.md", args.api_base, diagnosis_rows, filter_rows, summary)
    print(f"Wrote evaluation outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
