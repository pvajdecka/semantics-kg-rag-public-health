#!/usr/bin/env python3
"""Create vector-ready retrieval documents from the complete datasets.

The standard RAG corpus contains schema, code-list, distinct-value, and
aggregate-slice documents computed from the full raw CSV files. The KG-RAG
corpus contains graph node documents generated from ``artifacts/kg`` so a
backend can retrieve typed nodes and then expand through edges.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from build_kg import DATASETS, EXCLUDED_DATASET_COLUMNS, ROOT, block_for_code, file_sha256, stable_id


METADATA_DIR = ROOT / "data" / "metadata"
RETRIEVAL_DIR = ROOT / "artifacts" / "retrieval"
KG_DIR = ROOT / "artifacts" / "kg"
QUIET = False


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(message: str) -> None:
    if not QUIET:
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] {message}", flush=True)


def progress(label: str, current: int, total: int, *, every: int = 1_000) -> None:
    if QUIET or total <= 0:
        return
    if current < total and current % every != 0:
        return
    width = 28
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    percent = 100 * current / total
    end = "\n" if current >= total else "\r"
    print(f"{label} [{bar}] {current}/{total} ({percent:5.1f}%)", end=end, file=sys.stderr, flush=True)


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        if value.is_integer():
            return int(value)
    return value


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            cleaned = clean_json(item)
            if cleaned is not None:
                result[str(key)] = cleaned
        return result
    if isinstance(value, (list, tuple, set)):
        return [clean_json(item) for item in value if clean_json(item) is not None]
    return clean_scalar(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(clean_json(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(clean_json(record), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def read_metadata(dataset_key: str) -> dict[str, Any]:
    path = METADATA_DIR / f"{dataset_key}.metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def make_doc(
    doc_id: str,
    approach: str,
    doc_type: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": doc_id,
        "approach": approach,
        "doc_type": doc_type,
        "text": " ".join(str(text).split()),
        "metadata": metadata,
    }


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def load_dataframes() -> dict[str, pd.DataFrame]:
    return {key: pd.read_csv(path, encoding="utf-8-sig", low_memory=False) for key, path in DATASETS.items()}


def metadata_docs(datasets: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    log("Building dataset and column metadata documents")
    for dataset_key, df in datasets.items():
        metadata = read_metadata(dataset_key)
        schema = metadata.get("tableSchema") or {}
        fields = schema.get("columns") or schema.get("fields") or []
        title = metadata.get("dc:title") or dataset_key
        description = metadata.get("dc:description") or ""
        excluded_columns = EXCLUDED_DATASET_COLUMNS.get(dataset_key, set())
        visible_columns = [column for column in df.columns if column not in excluded_columns]
        column_list = ", ".join(str(column) for column in visible_columns)
        docs.append(
            make_doc(
                stable_id("standard_doc", dataset_key, "dataset"),
                "standard_rag",
                "dataset_overview",
                (
                    f"Dataset {dataset_key}. Title: {title}. Description: {description}. "
                    f"Complete raw table has {len(df)} rows and {len(visible_columns)} columns: {column_list}."
                ),
                {
                    "dataset_key": dataset_key,
                    "row_count": int(len(df)),
                    "column_count": int(len(visible_columns)),
                    "local_path": str(DATASETS[dataset_key].relative_to(ROOT)),
                },
            )
        )
        field_by_name = {field.get("name"): field for field in fields if isinstance(field, dict)}
        for column in visible_columns:
            field = field_by_name.get(column, {})
            docs.append(
                make_doc(
                    stable_id("standard_doc", dataset_key, "column", column),
                    "standard_rag",
                    "column",
                    (
                        f"Dataset {dataset_key} column {column}. "
                        f"Datatype: {field.get('datatype')}. Description: {field.get('dc:description')}."
                    ),
                    {
                        "dataset_key": dataset_key,
                        "column": column,
                        "datatype": field.get("datatype"),
                        "description": field.get("dc:description"),
                    },
                )
            )
    return docs


def mkn_code_docs(mkn: pd.DataFrame) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    rows = list(mkn.drop_duplicates("kod").iterrows())
    log(f"Building MKN code documents for {len(rows)} codes")
    for index, (_, row) in enumerate(rows, start=1):
        code = str(row["kod"]).strip()
        if not code:
            continue
        label = str(row.get("nazev", "")).strip()
        block = block_for_code(code)
        block_text = f" Derived block: {block[0]} {block[1]}." if block else ""
        docs.append(
            make_doc(
                stable_id("standard_doc", "mkn10_cz", "code", code),
                "standard_rag",
                "mkn_code",
                (
                    f"MKN-10-CZ code {code}. Dotted code {row.get('kod_tecka')}. Czech label: {label}. "
                    f"Chapter {row.get('kod_kapitola_cislo')} {row.get('nazev_kapitola')} "
                    f"range {row.get('kod_kapitola_rozsah')}.{block_text} "
                    f"Validity from {row.get('platnost_od')} to {row.get('platnost_do')}."
                ),
                {
                    "dataset_key": "mkn10_cz",
                    "code": code,
                    "label_cs": label,
                    "chapter_range": row.get("kod_kapitola_rozsah"),
                    "block_code": block[0] if block else None,
                    "block_label_cs": block[1] if block else None,
                },
            )
        )
        progress("MKN code docs", index, len(rows), every=2_000)
    return docs

def add_value_summary_docs(
    docs: list[dict[str, Any]],
    df: pd.DataFrame,
    *,
    dataset_key: str,
    columns: list[str],
    measure_col: str,
    doc_type: str,
    value_name: str,
) -> None:
    work = df.copy()
    work["_measure"] = numeric_series(work, measure_col)
    grouped = (
        work.groupby(columns, dropna=False)
        .agg(total=("_measure", "sum"), row_count=(columns[0], "size"))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    rows = list(grouped.iterrows())
    log(f"Building {doc_type} documents: {len(rows)} aggregates")
    for index, (_, row) in enumerate(rows, start=1):
        labels = [f"{column}={row[column]}" for column in columns]
        text = (
            f"Dataset {dataset_key} {value_name} summary. "
            f"{'; '.join(labels)}. Sum of {measure_col}: {int(row['total'])}. "
            f"Rows contributing to this aggregate: {int(row['row_count'])}."
        )
        docs.append(
            make_doc(
                stable_id("standard_doc", dataset_key, doc_type, *[row[column] for column in columns]),
                "standard_rag",
                doc_type,
                text,
                {
                    "dataset_key": dataset_key,
                    "columns": columns,
                    "values": {column: row[column] for column in columns},
                    "measure": measure_col,
                    "total": int(row["total"]),
                    "row_count": int(row["row_count"]),
                },
            )
        )
        progress(doc_type, index, len(rows), every=2_000)


def add_groupby_slice_docs(
    docs: list[dict[str, Any]],
    df: pd.DataFrame,
    *,
    dataset_key: str,
    group_cols: list[str],
    measure_col: str,
    doc_type: str,
) -> None:
    work = df.copy()
    work["_measure"] = numeric_series(work, measure_col)
    grouped = (
        work.groupby(group_cols, dropna=False)
        .agg(total=("_measure", "sum"), row_count=(group_cols[0], "size"))
        .reset_index()
    )
    rows = list(grouped.iterrows())
    log(f"Building {doc_type} documents: {len(rows)} aggregate slices")
    for index, (_, row) in enumerate(rows, start=1):
        values = {column: row[column] for column in group_cols}
        labels = [f"{column}={row[column]}" for column in group_cols]
        docs.append(
            make_doc(
                stable_id("standard_doc", dataset_key, doc_type, *[row[column] for column in group_cols]),
                "standard_rag",
                doc_type,
                (
                    f"Aggregate slice from complete dataset {dataset_key}. "
                    f"{'; '.join(labels)}. Sum of {measure_col}: {int(row['total'])}. "
                    f"Rows: {int(row['row_count'])}."
                ),
                {
                    "dataset_key": dataset_key,
                    "group_columns": group_cols,
                    "values": values,
                    "measure": measure_col,
                    "total": int(row["total"]),
                    "row_count": int(row["row_count"]),
                },
            )
        )
        progress(doc_type, index, len(rows), every=5_000)


def top_aggregate_text(
    df: pd.DataFrame,
    *,
    code_col: str,
    filter_value: Any,
    group_col: str,
    label_col: str | None,
    measure_col: str,
    limit: int = 5,
) -> str:
    subset = df[df[code_col].astype(str) == str(filter_value)].copy()
    subset["_measure"] = numeric_series(subset, measure_col)
    group_cols = [group_col] + ([label_col] if label_col and label_col != group_col else [])
    grouped = subset.groupby(group_cols, dropna=False)["_measure"].sum().sort_values(ascending=False).head(limit)
    parts = []
    for index, value in grouped.items():
        if isinstance(index, tuple):
            label = " ".join(str(item) for item in index)
        else:
            label = str(index)
        parts.append(f"{label}: {int(value)}")
    return ", ".join(parts)


def infectious_docs(infectious: pd.DataFrame) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    log("Building infectious-disease retrieval documents")
    infectious = infectious.copy()
    infectious["diagnoza"] = infectious["diagnoza"].astype(str).str.strip()
    infectious["pocet_pripadu_num"] = numeric_series(infectious, "pocet_pripadu")

    diagnosis_summary = (
        infectious.groupby(["diagnoza", "diagnoza_nazev"], dropna=False)
        .agg(
            reported_cases=("pocet_pripadu_num", "sum"),
            row_count=("diagnoza", "size"),
            year_min=("rok", "min"),
            year_max=("rok", "max"),
        )
        .reset_index()
        .sort_values("reported_cases", ascending=False)
    )
    rows = list(diagnosis_summary.iterrows())
    for index, (_, row) in enumerate(rows, start=1):
        code = str(row["diagnoza"]).strip()
        label = str(row["diagnoza_nazev"]).strip()
        docs.append(
            make_doc(
                stable_id("standard_doc", "infectious_diseases", "diagnosis_summary", code),
                "standard_rag",
                "infectious_diagnosis_summary",
                (
                    f"Infectious-disease diagnosis {code} {label}. "
                    f"Reported case count sum {int(row['reported_cases'])} across {int(row['row_count'])} rows. "
                    f"Years {int(row['year_min'])}-{int(row['year_max'])}."
                ),
                {
                    "dataset_key": "infectious_diseases",
                    "diagnosis_code": code,
                    "diagnosis_label": label,
                    "reported_cases": int(row["reported_cases"]),
                    "row_count": int(row["row_count"]),
                },
            )
        )
        progress("Infectious diagnosis summaries", index, len(rows), every=25)
    return docs


def hospitalization_docs(hospitalization: pd.DataFrame, mkn: pd.DataFrame, include_slices: bool) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    log("Building hospitalization retrieval documents")
    hospitalization = hospitalization.copy()
    hospitalization["ZDG"] = hospitalization["ZDG"].astype(str).str.strip()
    hospitalization["pocet_hosp_num"] = numeric_series(hospitalization, "pocet_hosp")
    mkn_label_by_code = {
        str(row["kod"]).strip(): str(row.get("nazev", "")).strip()
        for _, row in mkn.drop_duplicates("kod").iterrows()
    }

    diagnosis_summary = (
        hospitalization.groupby("ZDG", dropna=False)
        .agg(
            hospitalizations=("pocet_hosp_num", "sum"),
            row_count=("ZDG", "size"),
            year_min=("rok", "min"),
            year_max=("rok", "max"),
        )
        .reset_index()
        .sort_values("hospitalizations", ascending=False)
    )
    rows = list(diagnosis_summary.iterrows())
    log(f"Building hospitalization diagnosis summaries: {len(rows)} diagnosis values")
    for index, (_, row) in enumerate(rows, start=1):
        code = str(row["ZDG"]).strip()
        label = mkn_label_by_code.get(code, "")
        docs.append(
            make_doc(
                stable_id("standard_doc", "hospitalization", "diagnosis_summary", code),
                "standard_rag",
                "hospitalization_diagnosis_summary",
                (
                    f"Hospitalization principal diagnosis value {code}. "
                    f"MKN label: {label or 'not exactly matched to MKN code list'}. "
                    f"Hospitalization count sum {int(row['hospitalizations'])} across {int(row['row_count'])} rows. "
                    f"Years {int(row['year_min'])}-{int(row['year_max'])}."
                ),
                {
                    "dataset_key": "hospitalization",
                    "diagnosis_code": code,
                    "mkn_label_cs": label or None,
                    "hospitalizations": int(row["hospitalizations"]),
                    "row_count": int(row["row_count"]),
                },
            )
        )
        progress("Hospitalization diagnosis summaries", index, len(rows), every=250)

    for group_cols, doc_type, value_name in [
        (["rok"], "hospitalization_year_summary", "year"),
        (["operace"], "hospitalization_operation_summary", "operation flag"),
        (["umrti"], "hospitalization_death_summary", "death flag"),
    ]:
        add_value_summary_docs(
            docs,
            hospitalization,
            dataset_key="hospitalization",
            columns=group_cols,
            measure_col="pocet_hosp",
            doc_type=doc_type,
            value_name=value_name,
        )

    if include_slices:
        for group_cols, doc_type in [
            (["ZDG", "rok"], "hospitalization_diagnosis_year_slice"),
            (["ZDG", "operace"], "hospitalization_diagnosis_operation_slice"),
            (["ZDG", "umrti"], "hospitalization_diagnosis_death_slice"),
        ]:
            add_groupby_slice_docs(
                docs,
                hospitalization,
                dataset_key="hospitalization",
                group_cols=group_cols,
                measure_col="pocet_hosp",
                doc_type=doc_type,
            )
    return docs


def build_standard_corpus(
    datasets: dict[str, pd.DataFrame],
    *,
    include_hospitalization_slices: bool,
    include_deep_infectious_slices: bool,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    log("Building standard RAG corpus")
    docs.extend(infectious_docs(datasets["infectious_diseases"]))
    return docs


def relation_summary(
    node_id: str,
    outgoing_by_node: dict[str, list[dict[str, Any]]],
    incoming_by_node: dict[str, list[dict[str, Any]]],
    node_labels: dict[str, str],
    *,
    max_edges: int,
) -> str:
    outgoing = outgoing_by_node.get(node_id, [])
    incoming = incoming_by_node.get(node_id, [])

    def render(items: list[dict[str, Any]], direction: str) -> str:
        shown = items[:max_edges]
        parts = []
        for edge in shown:
            other_id = edge["target"] if direction == "outgoing" else edge["source"]
            props = edge.get("properties") or {}
            score_text = ""
            if edge["type"] == "SIMILAR_CASE_PROFILE":
                score_text = f" profile_similarity={props.get('profile_similarity')}"
            elif edge["type"] == "WEIGHTED_COOCCURS_WITH":
                score_text = (
                    f" support={props.get('weighted_support')}"
                    f" cosine={props.get('cosine_similarity')}"
                    f" lift={props.get('lift')}"
                )
            parts.append(f"{edge['type']} {node_labels.get(other_id, other_id)}{score_text}")
        if len(items) > max_edges:
            parts.append(f"{len(items) - max_edges} more")
        return "; ".join(parts)

    outgoing_text = render(outgoing, "outgoing")
    incoming_text = render(incoming, "incoming")
    return f"Outgoing relations: {outgoing_text or 'none'}. Incoming relations: {incoming_text or 'none'}."


def build_kg_corpus(kg_dir: Path) -> list[dict[str, Any]]:
    nodes_path = kg_dir / "nodes.jsonl"
    edges_path = kg_dir / "edges.jsonl"
    if not nodes_path.exists() or not edges_path.exists():
        raise FileNotFoundError("KG artifacts not found; run scripts/build_kg.py first.")
    nodes = read_jsonl(nodes_path)
    edges = read_jsonl(edges_path)
    log(f"Building KG-RAG node documents from {len(nodes)} nodes and {len(edges)} edges")
    node_labels = {node["id"]: node.get("label", node["id"]) for node in nodes}
    outgoing_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing_by_node[edge["source"]].append(edge)
        incoming_by_node[edge["target"]].append(edge)

    def edge_rank(edge: dict[str, Any]) -> tuple[float, float, str]:
        props = edge.get("properties") or {}
        primary = (
            props.get("profile_similarity")
            or props.get("cosine_similarity")
            or props.get("weighted_support")
            or 0
        )
        support = props.get("weighted_support") or props.get("source_reported_cases") or 0
        return (float(primary), float(support), edge.get("type", ""))

    for adjacency in [outgoing_by_node, incoming_by_node]:
        for node_id, node_edges in adjacency.items():
            adjacency[node_id] = sorted(node_edges, key=edge_rank, reverse=True)

    docs: list[dict[str, Any]] = []
    for index, node in enumerate(nodes, start=1):
        node_id = node["id"]
        props = node.get("properties") or {}
        aliases = ", ".join(str(alias) for alias in node.get("aliases", [])[:20])
        prop_text = ", ".join(f"{key}: {value}" for key, value in props.items())
        max_edges = 80 if node.get("type") in {"mkn_block", "diagnosis_value"} else 40
        text = (
            f"KG node {node.get('label')} with id {node_id}. Type: {node.get('type')}. "
            f"Aliases: {aliases}. Properties: {prop_text}. "
            f"{relation_summary(node_id, outgoing_by_node, incoming_by_node, node_labels, max_edges=max_edges)}"
        )
        docs.append(
            make_doc(
                stable_id("kg_doc", node_id),
                "kg_rag",
                f"kg_node_{node.get('type')}",
                text,
                {
                    "kg_node_id": node_id,
                    "kg_node_type": node.get("type"),
                    "kg_label": node.get("label"),
                    "properties": props,
                },
            )
        )
        progress("KG node docs", index, len(nodes), every=2_000)
    return docs


def corpus_sha(path: Path) -> str:
    return file_sha256(path)


def build_corpora(
    *,
    output_dir: Path,
    kg_dir: Path,
    include_hospitalization_slices: bool,
    include_deep_infectious_slices: bool,
) -> dict[str, Any]:
    log("Loading complete raw CSV files")
    datasets = load_dataframes()
    standard_docs = build_standard_corpus(
        datasets,
        include_hospitalization_slices=include_hospitalization_slices,
        include_deep_infectious_slices=include_deep_infectious_slices,
    )
    kg_docs = build_kg_corpus(kg_dir)

    standard_path = output_dir / "standard_rag_documents.jsonl"
    kg_path = output_dir / "kg_rag_documents.jsonl"
    log(f"Writing standard RAG corpus to {standard_path.relative_to(ROOT)}")
    standard_count = write_jsonl(standard_path, standard_docs)
    log(f"Writing KG-RAG corpus to {kg_path.relative_to(ROOT)}")
    kg_count = write_jsonl(kg_path, kg_docs)

    standard_type_counts: dict[str, int] = defaultdict(int)
    kg_type_counts: dict[str, int] = defaultdict(int)
    for doc in standard_docs:
        standard_type_counts[doc["doc_type"]] += 1
    for doc in kg_docs:
        kg_type_counts[doc["doc_type"]] += 1

    manifest_path = output_dir / "manifest.json"
    manifest = {
        "generated_at": now_iso(),
        "outputs": {
            "standard_rag_documents": str(standard_path.relative_to(ROOT)),
            "kg_rag_documents": str(kg_path.relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
        },
        "document_counts": {"standard_rag": standard_count, "kg_rag": kg_count},
        "document_type_counts": {
            "standard_rag": dict(sorted(standard_type_counts.items())),
            "kg_rag": dict(sorted(kg_type_counts.items())),
        },
        "source_files": {
            key: {
                "path": str(path.relative_to(ROOT)),
                "sha256": file_sha256(path),
                "rows": int(len(datasets[key])),
                "columns": int(len([column for column in datasets[key].columns if column not in EXCLUDED_DATASET_COLUMNS.get(key, set())])),
            }
            for key, path in DATASETS.items()
        },
        "corpus_sha256": {
            "standard_rag": corpus_sha(standard_path),
            "kg_rag": corpus_sha(kg_path),
        },
        "settings": {
            "include_hospitalization_slices": include_hospitalization_slices,
            "include_deep_infectious_slices": include_deep_infectious_slices,
        },
        "notes": [
            "Documents are built from complete raw CSVs, not samples.",
            "Standard RAG documents intentionally contain flat infectious diagnosis code/name evidence only.",
            "KG-RAG documents are node-centric; graph expansion should use artifacts/kg/edges.jsonl after initial node retrieval.",
        ],
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    global QUIET
    parser = argparse.ArgumentParser(description="Build vector-ready corpora for standard RAG and KG-RAG.")
    parser.add_argument("--output-dir", type=Path, default=RETRIEVAL_DIR)
    parser.add_argument("--kg-dir", type=Path, default=KG_DIR)
    parser.add_argument(
        "--include-hospitalization-slices",
        action="store_true",
        help="Include ZDG-by-dimension aggregate slices for hospitalization.",
    )
    parser.add_argument(
        "--include-deep-infectious-slices",
        action="store_true",
        help="Deprecated; standard RAG is kept flat for the RAG-vs-KG-RAG comparison.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    args = parser.parse_args()
    QUIET = args.quiet

    manifest = build_corpora(
        output_dir=args.output_dir,
        kg_dir=args.kg_dir,
        include_hospitalization_slices=args.include_hospitalization_slices,
        include_deep_infectious_slices=args.include_deep_infectious_slices,
    )
    print(
        "Wrote retrieval corpora: "
        f"standard_rag={manifest['document_counts']['standard_rag']} docs, "
        f"kg_rag={manifest['document_counts']['kg_rag']} docs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
