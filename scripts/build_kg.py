#!/usr/bin/env python3
"""Build the graph artifacts needed for the KG-RAG backend.

The graph is rebuilt from the complete raw CSV files and source code lists.
It avoids graph database assumptions and writes a portable JSONL node/edge
representation that a backend can load into Neo4j, NetworkX, DuckDB, SQLite,
or an in-memory adjacency map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
METADATA_DIR = ROOT / "data" / "metadata"
ARTIFACT_DIR = ROOT / "artifacts" / "kg"


DATASETS = {
    "infectious_diseases": RAW_DIR / "infectious_diseases.csv",
    "mkn10_cz": RAW_DIR / "mkn10_cz.csv",
    "hospitalization": RAW_DIR / "hospitalization.csv",
}

EXCLUDED_DATASET_COLUMNS = {
    "infectious_diseases": {"kraj_kod", "vek_kod", "pohlavi", "EWS"},
    "hospitalization": {"kraj_pacient", "vek_kod", "pohlavi"},
}


DERIVED_MKN_BLOCKS: list[tuple[str, str, str]] = [
    ("A00", "A09", "Střevní infekční nemoci"),
    ("A20", "A28", "Některé bakteriální zoonózy"),
    ("A30", "A49", "Jiné bakteriální nemoci"),
    ("A50", "A64", "Infekce přenášené převážně pohlavním stykem"),
    ("A65", "A69", "Jiné spirochetové nemoci"),
    ("A70", "A74", "Jiné nemoci způsobené chlamydiemi"),
    ("A75", "A79", "Rickettsiózy"),
    ("A80", "A89", "Virové infekce centrální nervové soustavy"),
    ("A92", "A99", "Virové horečky a virové hemoragické horečky přenášené členovci"),
    ("B00", "B09", "Virové infekce charakterizované postižením kůže a sliznice"),
    ("B15", "B19", "Virová hepatitida"),
    ("B25", "B34", "Jiné virové nemoci"),
    ("B35", "B49", "Mykózy"),
    ("B50", "B64", "Protozoární nemoci"),
    ("B65", "B83", "Helmintózy - hlístové nemoci"),
    ("B85", "B89", "Zavšivení, akarióza a jiná napadení"),
    ("B95", "B98", "Bakteriální, virová a jiná infekční agens"),
    ("B99", "B99", "Jiné infekční nemoci"),
    ("G00", "G09", "Zánětlivé nemoci centrální nervové soustavy"),
    ("G50", "G59", "Onemocnění nervů, nervových kořenů a pletení"),
    ("G60", "G64", "Polyneuropatie a jiné nemoci periferní nervové soustavy"),
    ("J00", "J06", "Akutní infekce horních dýchacích cest"),
    ("J09", "J18", "Chřipka a zánět plic (pneumonie)"),
    ("W50", "W64", "Vystavení životným mechanickým silám"),
]

BLOCK_SOURCE = "derived_from_configured_MKN10_block_ranges; source_CSV_has_no_explicit_block_column"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        return {str(k): clean_json(v) for k, v in value.items() if clean_json(v) is not None}
    if isinstance(value, (list, tuple, set)):
        return [clean_json(item) for item in value if clean_json(item) is not None]
    return clean_scalar(value)


def slug_part(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_.:+-]+", "_", text)
    text = text.strip("_")
    return text or "blank"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    slug = ":".join(slug_part(part) for part in parts)
    if len(slug) > 140:
        slug = f"{slug[:100]}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"
    return f"{prefix}:{slug}"


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(clean_json(record), ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(clean_json(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def load_metadata(dataset_key: str) -> dict[str, Any]:
    path = METADATA_DIR / f"{dataset_key}.metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def mkn_code3(value: Any) -> str | None:
    match = re.match(r"^([A-Z][0-9]{2})", str(value).strip().upper())
    return match.group(1) if match else None


def code_rank(code: str) -> int:
    code = code.upper()
    return (ord(code[0]) - ord("A")) * 1000 + int(code[1:3])


def block_for_code(code: Any) -> tuple[str, str, str] | None:
    code3 = mkn_code3(code)
    if not code3:
        return None
    rank = code_rank(code3)
    for start, end, label in DERIVED_MKN_BLOCKS:
        if code_rank(start) <= rank <= code_rank(end):
            return f"{start}-{end}", label, BLOCK_SOURCE
    return None


class GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.edge_keys: set[str] = set()

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        *,
        properties: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
    ) -> str:
        record = self.nodes.get(node_id)
        if record is None:
            record = {
                "id": node_id,
                "type": node_type,
                "label": label,
                "aliases": [],
                "properties": {},
            }
            self.nodes[node_id] = record
        record["type"] = record.get("type") or node_type
        record["label"] = record.get("label") or label
        if aliases:
            merged = set(record.get("aliases", []))
            merged.update(str(alias) for alias in aliases if str(alias).strip())
            record["aliases"] = sorted(merged)
        if properties:
            current = record.setdefault("properties", {})
            for key, value in properties.items():
                cleaned = clean_json(value)
                if cleaned is not None:
                    current[key] = cleaned
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> None:
        payload = clean_json(properties or {})
        key = json.dumps([source, target, edge_type, payload], ensure_ascii=False, sort_keys=True)
        if key in self.edge_keys:
            return
        self.edge_keys.add(key)
        self.edges.append(
            {
                "source": source,
                "target": target,
                "type": edge_type,
                "properties": payload,
            }
        )


def add_dataset_and_column_nodes(graph: GraphBuilder, datasets: dict[str, pd.DataFrame]) -> None:
    for dataset_key, df in datasets.items():
        metadata = load_metadata(dataset_key)
        title = metadata.get("dc:title") or dataset_key
        description = metadata.get("dc:description")
        excluded_columns = EXCLUDED_DATASET_COLUMNS.get(dataset_key, set())
        visible_columns = [column for column in df.columns if column not in excluded_columns]
        graph.add_node(
            stable_id("dataset", dataset_key),
            "dataset",
            str(title),
            properties={
                "dataset_key": dataset_key,
                "row_count": int(len(df)),
                "column_count": int(len(visible_columns)),
                "local_path": str(DATASETS[dataset_key].relative_to(ROOT)),
                "description": description,
            },
            aliases=[dataset_key],
        )
        schema = metadata.get("tableSchema") or {}
        fields = schema.get("columns") or schema.get("fields") or []
        descriptions = {field.get("name"): field for field in fields if isinstance(field, dict)}
        for column in visible_columns:
            field = descriptions.get(column, {})
            column_id = stable_id("column", dataset_key, column)
            graph.add_node(
                column_id,
                "column",
                f"{dataset_key}.{column}",
                properties={
                    "dataset_key": dataset_key,
                    "column": column,
                    "datatype": field.get("datatype"),
                    "description": field.get("dc:description"),
                    "titles": field.get("titles"),
                },
                aliases=[column, f"{dataset_key} {column}"],
            )
            graph.add_edge(stable_id("dataset", dataset_key), column_id, "HAS_COLUMN")


def add_measure_node(graph: GraphBuilder, dataset_key: str, column: str, label: str | None = None) -> str:
    node_id = stable_id("measure", dataset_key, column)
    graph.add_node(
        node_id,
        "measure",
        label or column,
        properties={"dataset_key": dataset_key, "column": column},
        aliases=[column, label or ""],
    )
    graph.add_edge(stable_id("dataset", dataset_key), node_id, "HAS_MEASURE")
    return node_id


def add_mkn_nodes(graph: GraphBuilder, mkn: pd.DataFrame) -> set[str]:
    mkn_codes = set(str(code).strip() for code in mkn["kod"].dropna().astype(str))
    for _, row in mkn[["kod_kapitola_rozsah", "kod_kapitola_cislo", "nazev_kapitola"]].drop_duplicates().iterrows():
        chapter_range = str(row["kod_kapitola_rozsah"]).strip()
        chapter_number = str(row["kod_kapitola_cislo"]).strip()
        chapter_name = str(row["nazev_kapitola"]).strip()
        chapter_id = stable_id("mkn_chapter", chapter_range)
        graph.add_node(
            chapter_id,
            "mkn_chapter",
            f"{chapter_number} {chapter_name}",
            properties={
                "chapter_range": chapter_range,
                "chapter_number": chapter_number,
                "chapter_name": chapter_name,
            },
            aliases=[chapter_range, chapter_number, chapter_name],
        )

    for _, row in mkn.drop_duplicates("kod").iterrows():
        code = str(row["kod"]).strip()
        if not code:
            continue
        label = str(row.get("nazev", "")).strip()
        node_id = stable_id("mkn_code", code)
        chapter_range = str(row.get("kod_kapitola_rozsah", "")).strip()
        chapter_id = stable_id("mkn_chapter", chapter_range)
        block = block_for_code(code)
        graph.add_node(
            node_id,
            "mkn_diagnosis",
            f"{code} {label}".strip(),
            properties={
                "code": code,
                "code_with_dot": row.get("kod_tecka"),
                "label_cs": label,
                "iri": row.get("kod_IRI"),
                "chapter_range": chapter_range,
                "chapter_number": row.get("kod_kapitola_cislo"),
                "chapter_name": row.get("nazev_kapitola"),
                "mkn_block_code": block[0] if block else None,
                "mkn_block_label_cs": block[1] if block else None,
                "valid_from": row.get("platnost_od"),
                "valid_to": row.get("platnost_do"),
            },
            aliases=[code, row.get("kod_tecka"), label],
        )
        graph.add_edge(stable_id("dataset", "mkn10_cz"), node_id, "HAS_CODE")
        if chapter_range:
            graph.add_edge(chapter_id, node_id, "CONTAINS_MKN_CODE")
        if block and chapter_range:
            block_code, block_label, source = block
            block_id = stable_id("mkn_block", block_code)
            graph.add_node(
                block_id,
                "mkn_block",
                f"{block_code} {block_label}",
                properties={"block_code": block_code, "block_label_cs": block_label, "source": source},
                aliases=[block_code, block_label],
            )
            graph.add_edge(chapter_id, block_id, "CONTAINS_MKN_BLOCK")
            graph.add_edge(block_id, node_id, "CONTAINS_MKN_CODE")
    return mkn_codes


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def add_infectious_nodes(graph: GraphBuilder, infectious: pd.DataFrame, mkn_codes: set[str]) -> None:
    dataset_id = stable_id("dataset", "infectious_diseases")
    infectious = infectious.copy()
    infectious["diagnoza"] = infectious["diagnoza"].astype(str).str.strip()
    infectious["pocet_pripadu_num"] = numeric_series(infectious, "pocet_pripadu")
    add_measure_node(graph, "infectious_diseases", "pocet_pripadu", "Reported infectious-disease cases")

    diagnosis_summary = (
        infectious.groupby(["diagnoza", "diagnoza_nazev"], dropna=False)
        .agg(
            reported_cases=("pocet_pripadu_num", "sum"),
            row_count=("diagnoza", "size"),
            year_min=("rok", "min"),
            year_max=("rok", "max"),
        )
        .reset_index()
    )
    for _, row in diagnosis_summary.iterrows():
        code = str(row["diagnoza"]).strip()
        label = str(row["diagnoza_nazev"]).strip()
        node_id = stable_id("infectious_diagnosis", code)
        block = block_for_code(code)
        graph.add_node(
            node_id,
            "diagnosis_value",
            f"{code} {label}",
            properties={
                "dataset_key": "infectious_diseases",
                "column": "diagnoza",
                "code": code,
                "label_cs": label,
                "reported_cases": int(row["reported_cases"]),
                "row_count": int(row["row_count"]),
                "year_min": int(row["year_min"]),
                "year_max": int(row["year_max"]),
                "mkn_block_code": block[0] if block else None,
                "mkn_block_label_cs": block[1] if block else None,
            },
            aliases=[code, label],
        )
        graph.add_edge(dataset_id, node_id, "HAS_DIAGNOSIS_VALUE")
        if code in mkn_codes:
            graph.add_edge(node_id, stable_id("mkn_code", code), "SAME_AS_MKN_CODE", properties={"match": "exact"})
        if block:
            graph.add_edge(stable_id("mkn_block", block[0]), node_id, "HAS_TABLE_DIAGNOSIS_VALUE")

    year_summary = (
        infectious.groupby("rok", dropna=False)
        .agg(reported_cases=("pocet_pripadu_num", "sum"), row_count=("rok", "size"))
        .reset_index()
    )
    for _, row in year_summary.iterrows():
        year = int(row["rok"])
        node_id = stable_id("year", year)
        graph.add_node(
            node_id,
            "year",
            str(year),
            properties={
                "year": year,
                "infectious_reported_cases": int(row["reported_cases"]),
                "infectious_row_count": int(row["row_count"]),
            },
            aliases=[str(year)],
        )
        graph.add_edge(dataset_id, node_id, "USES_YEAR")

    month_summary = (
        infectious.groupby("mesic", dropna=False)
        .agg(reported_cases=("pocet_pripadu_num", "sum"), row_count=("mesic", "size"))
        .reset_index()
    )
    for _, row in month_summary.iterrows():
        month = int(row["mesic"])
        node_id = stable_id("month", month)
        graph.add_node(
            node_id,
            "month",
            str(month),
            properties={
                "month": month,
                "infectious_reported_cases": int(row["reported_cases"]),
                "infectious_row_count": int(row["row_count"]),
            },
            aliases=[str(month)],
        )
        graph.add_edge(dataset_id, node_id, "USES_MONTH")

INFECTIOUS_PATH_KIND_ORDER = {
    "mkn_block": 0,
    "diagnosis": 1,
    "year": 2,
    "month": 3,
}


def ordered_path_pair(
    left: tuple[str, str],
    right: tuple[str, str],
) -> tuple[tuple[str, str], tuple[str, str]]:
    return tuple(
        sorted(
            [left, right],
            key=lambda item: (INFECTIOUS_PATH_KIND_ORDER.get(item[0], 99), item[1]),
        )
    )  # type: ignore[return-value]


def sparse_cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left).intersection(right)
    numerator = sum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return safe_divide(numerator, left_norm * right_norm)


def add_infectious_weighted_path_edges(graph: GraphBuilder, infectious: pd.DataFrame, *, top_similar_per_diagnosis: int = 12) -> None:
    work = infectious.copy()
    work["diagnoza"] = work["diagnoza"].astype(str).str.strip()
    work["diagnoza_nazev"] = work["diagnoza_nazev"].astype(str).str.strip()
    work["pocet_pripadu_num"] = numeric_series(work, "pocet_pripadu")

    node_totals: dict[str, float] = defaultdict(float)
    pair_support: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(lambda: {"support": 0.0, "path_count": 0.0})
    total_weight = float(work["pocet_pripadu_num"].sum())

    row_columns = [
        "diagnoza",
        "diagnoza_nazev",
        "rok",
        "mesic",
        "pocet_pripadu_num",
    ]
    for row in work[row_columns].itertuples(index=False):
        weight = float(row.pocet_pripadu_num)
        if weight <= 0:
            continue
        diagnosis_code = str(row.diagnoza).strip()
        block = block_for_code(diagnosis_code)
        entities: list[tuple[str, str]] = []
        if block:
            entities.append(("mkn_block", stable_id("mkn_block", block[0])))
        if diagnosis_code:
            entities.append(("diagnosis", stable_id("infectious_diagnosis", diagnosis_code)))
        if pd.notna(row.rok):
            entities.append(("year", stable_id("year", int(row.rok))))
        if pd.notna(row.mesic):
            entities.append(("month", stable_id("month", int(row.mesic))))

        entities = list(dict.fromkeys(entities))
        for _, node_id in entities:
            node_totals[node_id] += weight
        for left, right in combinations(entities, 2):
            source, target = ordered_path_pair(left, right)
            stats = pair_support[(source[1], target[1], source[0], target[0])]
            stats["support"] += weight
            stats["path_count"] += 1

    for (source_id, target_id, source_kind, target_kind), stats in pair_support.items():
        support = stats["support"]
        if support <= 0:
            continue
        source_total = node_totals[source_id]
        target_total = node_totals[target_id]
        graph.add_edge(
            source_id,
            target_id,
            "WEIGHTED_COOCCURS_WITH",
            properties={
                "dataset_key": "infectious_diseases",
                "projection": "weighted_row_path",
                "measure": "pocet_pripadu",
                "source_kind": source_kind,
                "target_kind": target_kind,
                "entity_pair_kind": f"{source_kind}-{target_kind}",
                "weighted_support": int(round(support)),
                "path_count": int(stats["path_count"]),
                "source_total": int(round(source_total)),
                "target_total": int(round(target_total)),
                "total_weight": int(round(total_weight)),
                "cosine_similarity": rounded(safe_divide(support, math.sqrt(source_total * target_total))),
                "source_to_target_confidence": rounded(safe_divide(support, source_total)),
                "target_to_source_confidence": rounded(safe_divide(support, target_total)),
                "lift": rounded(safe_divide(support * total_weight, source_total * target_total)),
            },
        )

    add_infectious_diagnosis_profile_similarity_edges(
        graph,
        work,
        diagnosis_totals={
            str(code): float(total)
            for code, total in work.groupby("diagnoza")["pocet_pripadu_num"].sum().to_dict().items()
        },
        top_similar_per_diagnosis=top_similar_per_diagnosis,
    )


def diagnosis_dimension_profiles(
    work: pd.DataFrame,
    *,
    dimension: str,
    diagnosis_totals: dict[str, float],
) -> dict[str, dict[str, float]]:
    grouped = (
        work.groupby(["diagnoza", dimension], dropna=False)["pocet_pripadu_num"]
        .sum()
        .reset_index()
    )
    profiles: dict[str, dict[str, float]] = defaultdict(dict)
    for _, row in grouped.iterrows():
        diagnosis_code = str(row["diagnoza"]).strip()
        total = diagnosis_totals.get(diagnosis_code, 0.0)
        if total <= 0:
            continue
        value = str(row[dimension]).strip()
        profiles[diagnosis_code][value] = float(row["pocet_pripadu_num"]) / total
    return profiles


def add_infectious_diagnosis_profile_similarity_edges(
    graph: GraphBuilder,
    work: pd.DataFrame,
    *,
    diagnosis_totals: dict[str, float],
    top_similar_per_diagnosis: int,
) -> None:
    dimensions = {
        "year": "rok",
        "month": "mesic",
    }
    profiles_by_dimension = {
        label: diagnosis_dimension_profiles(work, dimension=column, diagnosis_totals=diagnosis_totals)
        for label, column in dimensions.items()
    }
    codes = sorted(code for code, total in diagnosis_totals.items() if total > 0)
    blocks_by_code = {code: (block_for_code(code) or (None, None, None))[0] for code in codes}
    pair_scores: list[dict[str, Any]] = []
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for left_code, right_code in combinations(codes, 2):
        component_scores = {
            label: sparse_cosine(profiles.get(left_code, {}), profiles.get(right_code, {}))
            for label, profiles in profiles_by_dimension.items()
        }
        available_scores = list(component_scores.values())
        if not available_scores:
            continue
        similarity = sum(available_scores) / len(available_scores)
        if similarity <= 0:
            continue
        record = {
            "left_code": left_code,
            "right_code": right_code,
            "profile_similarity": similarity,
            "component_scores": component_scores,
            "left_total": diagnosis_totals[left_code],
            "right_total": diagnosis_totals[right_code],
            "left_block": blocks_by_code[left_code],
            "right_block": blocks_by_code[right_code],
        }
        pair_scores.append(record)
        by_code[left_code].append(record)
        by_code[right_code].append(record)

    selected_pairs: set[tuple[str, str]] = set()
    for code, candidates in by_code.items():
        candidates_sorted = sorted(candidates, key=lambda item: item["profile_similarity"], reverse=True)
        for candidate in candidates_sorted[:top_similar_per_diagnosis]:
            selected_pairs.add(tuple(sorted([candidate["left_code"], candidate["right_code"]])))

    pair_lookup = {tuple(sorted([item["left_code"], item["right_code"]])): item for item in pair_scores}
    for left_code, right_code in sorted(selected_pairs):
        item = pair_lookup[(left_code, right_code)]
        source_id = stable_id("infectious_diagnosis", left_code)
        target_id = stable_id("infectious_diagnosis", right_code)
        graph.add_edge(
            source_id,
            target_id,
            "SIMILAR_CASE_PROFILE",
            properties={
                "dataset_key": "infectious_diseases",
                "basis": "normalized_case_distribution_by_year_month",
                "ranked_by": "mean_sparse_cosine_across_available_profile_components",
                "profile_similarity": rounded(item["profile_similarity"]),
                "component_similarity": {
                    label: rounded(score)
                    for label, score in sorted(item["component_scores"].items())
                },
                "source_code": left_code,
                "target_code": right_code,
                "source_reported_cases": int(round(item["left_total"])),
                "target_reported_cases": int(round(item["right_total"])),
                "source_mkn_block_code": item["left_block"],
                "target_mkn_block_code": item["right_block"],
                "same_mkn_block": item["left_block"] == item["right_block"],
                "top_similar_per_diagnosis": top_similar_per_diagnosis,
            },
        )


def add_hospitalization_nodes(graph: GraphBuilder, hospitalization: pd.DataFrame, mkn_codes: set[str]) -> None:
    dataset_id = stable_id("dataset", "hospitalization")
    hospitalization = hospitalization.copy()
    hospitalization["ZDG"] = hospitalization["ZDG"].astype(str).str.strip()
    hospitalization["pocet_hosp_num"] = numeric_series(hospitalization, "pocet_hosp")

    numeric_measure_columns = [
        column
        for column in hospitalization.columns
        if column.startswith("OD_") or column in {"pocet_hosp", "operace", "umrti"}
    ]
    for column in numeric_measure_columns:
        add_measure_node(graph, "hospitalization", column)

    diagnosis_summary = (
        hospitalization.groupby("ZDG", dropna=False)
        .agg(
            hospitalizations=("pocet_hosp_num", "sum"),
            row_count=("ZDG", "size"),
            year_min=("rok", "min"),
            year_max=("rok", "max"),
        )
        .reset_index()
    )
    for _, row in diagnosis_summary.iterrows():
        code = str(row["ZDG"]).strip()
        node_id = stable_id("hospital_diagnosis", code)
        graph.add_node(
            node_id,
            "hospital_diagnosis_value",
            code,
            properties={
                "dataset_key": "hospitalization",
                "column": "ZDG",
                "code": code,
                "hospitalizations": int(row["hospitalizations"]),
                "row_count": int(row["row_count"]),
                "year_min": int(row["year_min"]),
                "year_max": int(row["year_max"]),
            },
            aliases=[code],
        )
        graph.add_edge(dataset_id, node_id, "HAS_DIAGNOSIS_VALUE")
        if code in mkn_codes:
            graph.add_edge(node_id, stable_id("mkn_code", code), "SAME_AS_MKN_CODE", properties={"match": "exact"})

    for column in ["operace", "umrti"]:
        for value in sorted(hospitalization[column].dropna().astype(str).unique()):
            node_id = stable_id(column, value)
            graph.add_node(node_id, f"{column}_value", value, properties={"value": value}, aliases=[value])
            graph.add_edge(dataset_id, node_id, f"USES_{column.upper()}")

    for year in sorted(pd.to_numeric(hospitalization["rok"], errors="coerce").dropna().astype(int).unique()):
        node_id = stable_id("year", year)
        graph.add_node(node_id, "year", str(year), properties={"year": int(year)}, aliases=[str(year)])
        graph.add_edge(dataset_id, node_id, "USES_YEAR")


def build_graph(output_dir: Path) -> dict[str, Any]:
    datasets = {key: read_csv(path) for key, path in DATASETS.items()}
    graph = GraphBuilder()
    add_dataset_and_column_nodes(graph, datasets)
    mkn_codes = add_mkn_nodes(graph, datasets["mkn10_cz"])
    add_infectious_nodes(graph, datasets["infectious_diseases"], mkn_codes)
    add_infectious_weighted_path_edges(graph, datasets["infectious_diseases"])
    add_hospitalization_nodes(graph, datasets["hospitalization"], mkn_codes)

    nodes = sorted(graph.nodes.values(), key=lambda item: item["id"])
    edges = sorted(graph.edges, key=lambda item: (item["source"], item["type"], item["target"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / "nodes.jsonl"
    edges_path = output_dir / "edges.jsonl"
    manifest_path = output_dir / "manifest.json"
    write_jsonl(nodes_path, nodes)
    write_jsonl(edges_path, edges)

    type_counts: dict[str, int] = defaultdict(int)
    edge_type_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        type_counts[node["type"]] += 1
    for edge in edges:
        edge_type_counts[edge["type"]] += 1

    manifest = {
        "generated_at": now_iso(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": dict(sorted(type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "source_files": {
            key: {
                "path": str(path.relative_to(ROOT)),
                "sha256": file_sha256(path),
                "rows": int(len(datasets[key])),
                "columns": int(len([column for column in datasets[key].columns if column not in EXCLUDED_DATASET_COLUMNS.get(key, set())])),
            }
            for key, path in DATASETS.items()
        },
        "outputs": {
            "nodes": str(nodes_path.relative_to(ROOT)),
            "edges": str(edges_path.relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
        },
        "notes": [
            "MKN block nodes are derived from configured MKN-10 ranges because the source CSV has chapter columns but no explicit block columns.",
            "Hospitalization diagnosis values are linked to MKN only on exact code matches.",
            "The KG does not import hand-authored query scopes; weighted co-occurrence and similarity edges are derived from source fact rows.",
        ],
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KG nodes and edges for KG-RAG.")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    manifest = build_graph(args.output_dir)
    print(
        f"Wrote KG with {manifest['node_count']} nodes and {manifest['edge_count']} edges "
        f"to {manifest['outputs']['manifest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
