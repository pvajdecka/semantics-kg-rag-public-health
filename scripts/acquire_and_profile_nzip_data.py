#!/usr/bin/env python3
"""Acquire and profile Czech public-health open data for a SEMANTiCS demo study.

This script intentionally stops at data acquisition, validation, profiling, and
research-opportunity discovery. It does not build a KG, RAG system, SQL QA
system, or fixed research claim.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import re
import shutil
import statistics
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

try:
    import pandas as pd
except ImportError:  # pragma: no cover - exercised only in dependency-poor envs.
    pd = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency.
    BeautifulSoup = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
METADATA_DIR = ROOT / "data" / "metadata"
PROCESSED_DIR = ROOT / "data" / "processed"
SAMPLES_DIR = ROOT / "data" / "samples"
REPORTS_DIR = ROOT / "reports"
OUTPUTS_DIR = ROOT / "outputs"

ENCODINGS = ["utf-8-sig", "utf-8", "cp1250", "latin2"]
SEPARATORS = [",", ";", "\t"]
SAMPLE_ROWS = 10_000
HTTP_TIMEOUT_SECONDS = 60
MAX_COMBO_PRODUCT = 2_000_000

CZECH_DIACRITICS = set("áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ")


@dataclass(frozen=True)
class DatasetSpec:
    """Download and profiling specification for one dataset."""

    key: str
    title: str
    page_url: str
    csv_url: str | None
    metadata_url: str | None
    raw_filename: str
    metadata_filename: str
    profile_filename: str
    sample_filename: str
    optional: bool = False
    discover_from_page: bool = False


DATASETS: dict[str, DatasetSpec] = {
    "infectious_diseases": DatasetSpec(
        key="infectious_diseases",
        title="Infectious diseases in the Czech Republic",
        page_url="https://www.nzip.cz/data/2621-infekcni-nemoci-otevrena-data",
        csv_url=(
            "https://datanzis.uzis.gov.cz/data/NR-27-ISIN/NR-27-01/"
            "Otevrena-data-NR-27-01-infekcni-nemoci.csv"
        ),
        metadata_url=(
            "https://datanzis.uzis.gov.cz/data/NR-27-ISIN/NR-27-01/"
            "Otevrena-data-NR-27-01-infekcni-nemoci.csv-metadata.json"
        ),
        raw_filename="infectious_diseases.csv",
        metadata_filename="infectious_diseases.metadata.json",
        profile_filename="infectious_diseases_profile.json",
        sample_filename="infectious_diseases_sample.csv",
    ),
    "age_groups": DatasetSpec(
        key="age_groups",
        title="NZIS age-group code list",
        page_url="https://www.nzip.cz/data/2182-ciselnik-vekove-skupiny-otevrena-data",
        csv_url=(
            "https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/"
            "Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv"
        ),
        metadata_url=(
            "https://datanzis.uzis.gov.cz/data/OIS-12-CIS/OIS-12-01/"
            "Otevrena-data-OIS-12-01-ciselnik-vekove-skupiny.csv-metadata.json"
        ),
        raw_filename="age_groups.csv",
        metadata_filename="age_groups.metadata.json",
        profile_filename="age_groups_profile.json",
        sample_filename="age_groups_sample.csv",
    ),
    "mkn10_cz": DatasetSpec(
        key="mkn10_cz",
        title="MKN-10-CZ code list",
        page_url="https://www.nzip.cz/data/2479-ciselnik-mkn-10-cz-otevrena-data",
        csv_url="https://data.mzcr.cz/data/distribuce/463/Otevrena-data-OIS-12-03-ciselnik-mkn-10-cz.csv",
        metadata_url=None,
        raw_filename="mkn10_cz.csv",
        metadata_filename="mkn10_cz.metadata.json",
        profile_filename="mkn10_cz_profile.json",
        sample_filename="mkn10_cz_sample.csv",
    ),
    "hospitalization": DatasetSpec(
        key="hospitalization",
        title="Hospitalization cases in acute and intensive care",
        page_url="https://www.nzip.cz/data/2225-hospitalizacni-pripady-akutni-intezivni-pece-otevrena-data",
        csv_url=None,
        metadata_url=None,
        raw_filename="hospitalization.csv",
        metadata_filename="hospitalization.metadata.json",
        profile_filename="hospitalization_profile.json",
        sample_filename="hospitalization_sample.csv",
        optional=True,
        discover_from_page=True,
    ),
}


def log(message: str) -> None:
    """Print a timestamped progress message."""

    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] {message}", flush=True)


def now_iso() -> str:
    """Return an ISO 8601 UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_directories() -> None:
    """Create all repository directories used by the pipeline."""

    for directory in [RAW_DIR, METADATA_DIR, PROCESSED_DIR, SAMPLES_DIR, REPORTS_DIR, OUTPUTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def json_default(value: Any) -> Any:
    """Serialize pandas/numpy/scalar objects into JSON-compatible values."""

    if pd is not None:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file with deterministic indentation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)
        handle.write("\n")


def read_json_if_exists(path: Path) -> Any:
    """Read a JSON file if it exists and parses cleanly."""

    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def file_sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a local file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_with_retries(url: str, *, stream: bool = False) -> requests.Response:
    """GET a URL with retries, timeout, and status-code validation."""

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.get(
                url,
                timeout=HTTP_TIMEOUT_SECONDS,
                stream=stream,
                headers={"User-Agent": "semantics-data-profiler/0.1"},
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 3:
                wait = 2**attempt
                log(f"HTTP attempt {attempt} failed for {url}; retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def download_file(url: str, path: Path, *, force: bool = False) -> dict[str, Any]:
    """Download a file if needed and return a download record."""

    record: dict[str, Any] = {
        "url": url,
        "local_path": str(path.relative_to(ROOT)),
        "downloaded_at": now_iso(),
        "status": "unknown",
        "warnings": [],
    }
    if path.exists() and not force:
        record.update(
            {
                "status": "cached",
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
        return record

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".part")
    response = request_with_retries(url, stream=True)
    with temporary_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    temporary_path.replace(path)
    record.update(
        {
            "status": "downloaded",
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    )
    return record


def is_gzip_file(path: Path) -> bool:
    """Return whether a local file has a gzip magic header."""

    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"\x1f\x8b"
    except OSError:
        return False


def ensure_plain_csv(path: Path) -> bool:
    """Decompress a gzip-compressed CSV in place when the target is a .csv file."""

    if not path.exists() or not is_gzip_file(path):
        return False
    decompressed_path = path.with_suffix(path.suffix + ".decompressed")
    with gzip.open(path, "rb") as source, decompressed_path.open("wb") as target:
        shutil.copyfileobj(source, target)
    decompressed_path.replace(path)
    return True


def extract_links_regex(page_html: str, base_url: str) -> list[dict[str, str]]:
    """Extract links from HTML using a regex fallback."""

    links: list[dict[str, str]] = []
    pattern = re.compile(r"<a\b[^>]*?href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<text>.*?)</a>", re.I | re.S)
    for match in pattern.finditer(page_html):
        href = html.unescape(match.group("href"))
        text = re.sub(r"\s+", " ", re.sub(r"<.*?>", " ", match.group("text"))).strip()
        links.append({"url": urljoin(base_url, href), "text": html.unescape(text)})
    return links


def discover_links_from_page(page_url: str) -> dict[str, Any]:
    """Download an NZIP page and discover CSV, JSON, metadata, and PDF links."""

    log(f"Discovering links from {page_url}")
    warnings: list[str] = []
    response = request_with_retries(page_url)
    page_html = response.text
    links: list[dict[str, str]] = []

    if BeautifulSoup is not None:
        soup = BeautifulSoup(page_html, "html.parser")
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if not href:
                continue
            links.append(
                {
                    "url": urljoin(page_url, str(href)),
                    "text": " ".join(anchor.get_text(" ", strip=True).split()),
                }
            )
    else:
        warnings.append("BeautifulSoup is not installed; used regex-based link extraction.")
        links = extract_links_regex(page_html, page_url)

    seen: set[str] = set()
    unique_links: list[dict[str, str]] = []
    for link in links:
        clean_url = link["url"].split("#", 1)[0]
        if clean_url in seen:
            continue
        seen.add(clean_url)
        unique_links.append({"url": clean_url, "text": link.get("text", "")})

    def classified(predicate: Any) -> list[dict[str, str]]:
        return [link for link in unique_links if predicate(link["url"].lower(), link["text"].lower())]

    csv_links = classified(lambda url, text: ".csv" in url or "csv" in text)
    json_links = classified(lambda url, text: ".json" in url or "json" in text)
    metadata_links = classified(lambda url, text: "metadata" in url or "metadata" in text or "csv-metadata" in url)
    pdf_links = classified(lambda url, text: ".pdf" in url or "pdf" in text or "metod" in text)

    return {
        "page_url": page_url,
        "discovered_at": now_iso(),
        "parser": "beautifulsoup" if BeautifulSoup is not None else "regex",
        "all_links": unique_links,
        "csv_links": csv_links,
        "json_links": json_links,
        "metadata_links": metadata_links,
        "pdf_links": pdf_links,
        "warnings": warnings,
    }


def choose_link(links: list[dict[str, str]], *, prefer_csv: bool = False, prefer_metadata: bool = False) -> str | None:
    """Choose a plausible data or metadata URL from discovered links."""

    if not links:
        return None
    ranked: list[tuple[int, str]] = []
    for link in links:
        url = link["url"]
        lowered = url.lower()
        score = 0
        if prefer_csv and lowered.endswith(".csv"):
            score += 20
        if prefer_csv and "metadata" not in lowered and "csv-metadata" not in lowered:
            score += 10
        if prefer_metadata and ("metadata" in lowered or "csv-metadata" in lowered):
            score += 25
        if "otevrena-data" in lowered:
            score += 5
        if urlparse(url).netloc in {"datanzis.uzis.gov.cz", "data.mzcr.cz"}:
            score += 4
        ranked.append((score, url))
    ranked.sort(reverse=True)
    return ranked[0][1]


def sniff_csv(path: Path) -> tuple[str, str, list[str]]:
    """Find a likely CSV encoding and separator without using pandas."""

    warnings: list[str] = []
    best: tuple[int, str, str] | None = None
    for encoding in ENCODINGS:
        try:
            sample = path.read_text(encoding=encoding, errors="strict")[:250_000]
        except UnicodeDecodeError:
            continue
        for separator in SEPARATORS:
            try:
                rows = list(csv.reader(sample.splitlines()[:50], delimiter=separator))
            except csv.Error:
                continue
            widths = [len(row) for row in rows if row]
            if not widths:
                continue
            median_width = int(statistics.median(widths))
            stable_rows = sum(1 for width in widths if width == median_width)
            score = median_width * 100 + stable_rows
            if best is None or score > best[0]:
                best = (score, encoding, separator)
    if best is None:
        warnings.append("Could not confidently sniff encoding/separator; defaulted to utf-8 comma.")
        return "utf-8", ",", warnings
    return best[1], best[2], warnings


def normalize_columns(columns: list[Any]) -> list[str]:
    """Strip whitespace from column names while preserving Czech text."""

    normalized = [str(column).strip() for column in columns]
    seen: dict[str, int] = defaultdict(int)
    result: list[str] = []
    for column in normalized:
        seen[column] += 1
        if seen[column] == 1:
            result.append(column)
        else:
            result.append(f"{column}_{seen[column]}")
    return result


def read_csv_robust(path: Path, *, nrows: int | None = None) -> tuple[Any, str, str, list[str]]:
    """Read a CSV using multiple likely encodings and separators."""

    warnings: list[str] = []
    if pd is None:
        rows, encoding, separator, fallback_warnings = read_csv_stdlib(path, nrows=nrows)
        warnings.extend(fallback_warnings)
        return rows, encoding, separator, warnings

    best: tuple[int, int, str, str, Any] | None = None
    errors: list[str] = []
    for encoding in ENCODINGS:
        for separator in SEPARATORS:
            try:
                df = pd.read_csv(path, encoding=encoding, sep=separator, low_memory=False, nrows=nrows)
            except Exception as exc:  # pandas parser errors vary by version.
                errors.append(f"{encoding}/{repr(separator)}: {exc}")
                continue
            df.columns = normalize_columns(list(df.columns))
            column_count = len(df.columns)
            unnamed_count = sum(1 for column in df.columns if str(column).startswith("Unnamed"))
            score = column_count * 100 - unnamed_count
            if best is None or score > best[0] or (score == best[0] and len(df) > best[1]):
                best = (score, len(df), encoding, separator, df)
    if best is None:
        raise RuntimeError(f"Unable to read {path}; attempts: {' | '.join(errors[:8])}")
    _, _, encoding, separator, df = best
    if len(df.columns) <= 1:
        warnings.append(
            "CSV parsing produced one column; this may be a genuine one-column file or an undetected delimiter issue."
        )
    return df, encoding, separator, warnings


def read_csv_stdlib(path: Path, *, nrows: int | None = None) -> tuple[list[dict[str, str]], str, str, list[str]]:
    """Read CSV records using stdlib as a fallback when pandas is unavailable."""

    encoding, separator, warnings = sniff_csv(path)
    warnings.append("pandas is not installed; used limited stdlib CSV fallback profiling.")
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle, delimiter=separator)
        if reader.fieldnames is None:
            return [], encoding, separator, warnings
        reader.fieldnames = normalize_columns(reader.fieldnames)
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            if nrows is not None and index >= nrows:
                break
            rows.append({str(key).strip(): value for key, value in row.items() if key is not None})
    return rows, encoding, separator, warnings


def df_shape(df: Any) -> tuple[int, int]:
    """Return row and column count for pandas or fallback records."""

    if pd is not None and hasattr(df, "shape"):
        return int(df.shape[0]), int(df.shape[1])
    if isinstance(df, list):
        columns = list(df[0].keys()) if df else []
        return len(df), len(columns)
    return 0, 0


def df_columns(df: Any) -> list[str]:
    """Return dataframe column names."""

    if pd is not None and hasattr(df, "columns"):
        return [str(column) for column in df.columns]
    if isinstance(df, list) and df:
        return list(df[0].keys())
    return []


def has_diacritics(value: Any) -> bool:
    """Return whether a value contains Czech diacritics."""

    return any(character in CZECH_DIACRITICS for character in str(value))


def strip_diacritics(value: str) -> str:
    """Remove diacritics for fuzzy lexical comparisons."""

    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def non_empty_values(series: Any) -> list[str]:
    """Return non-empty stringified values from a pandas Series or fallback list."""

    if pd is not None and hasattr(series, "dropna"):
        values = series.dropna().astype(str).map(str.strip)
        return [value for value in values.tolist() if value and value.lower() not in {"nan", "none", "nat"}]
    return [str(value).strip() for value in series if str(value).strip()]


def value_counter(series: Any, limit: int = 20) -> list[dict[str, Any]]:
    """Return top value counts."""

    if pd is not None and hasattr(series, "value_counts"):
        counts = series.fillna("<MISSING>").astype(str).value_counts(dropna=False).head(limit)
        return [{"value": str(index), "count": int(count)} for index, count in counts.items()]
    counts = Counter(str(value) if value not in {None, ""} else "<MISSING>" for value in series)
    return [{"value": value, "count": int(count)} for value, count in counts.most_common(limit)]


def looks_like_code_column(column: str, values: list[str]) -> bool:
    """Heuristically detect code-like columns."""

    lowered = column.lower()
    if any(token in lowered for token in ["kod", "kód", "code", "diagnoza", "diagnóza", "icd", "mkn"]):
        if not any(token in lowered for token in ["nazev", "název", "label", "name", "popis"]):
            return True
    if not values:
        return False
    sample = values[:200]
    short_share = sum(1 for value in sample if 1 <= len(value) <= 12) / len(sample)
    code_pattern_share = sum(bool(re.fullmatch(r"[A-Z]?\d+[A-Z0-9.\-/]*|[A-Z]{1,4}\d{0,4}", value.upper())) for value in sample) / len(sample)
    return short_share > 0.8 and code_pattern_share > 0.55


def looks_like_label_column(column: str, values: list[str]) -> bool:
    """Heuristically detect human-readable label/name columns."""

    lowered = column.lower()
    if any(token in lowered for token in ["nazev", "název", "label", "name", "popis", "text"]):
        return True
    if not values:
        return False
    sample = values[:200]
    wordy_share = sum((" " in value or has_diacritics(value)) and len(value) > 5 for value in sample) / len(sample)
    return wordy_share > 0.35


def looks_like_abbreviation(value: str) -> bool:
    """Detect abbreviation-like values or labels."""

    tokens = re.findall(r"\b[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]{2,}\b", value)
    return bool(tokens) or bool(re.search(r"\([A-Z0-9]{2,}\)", value))


def analyze_categorical_columns(df: Any, columns: list[str]) -> dict[str, Any]:
    """Profile categorical-looking columns."""

    rows, _ = df_shape(df)
    result: dict[str, Any] = {}
    for column in columns:
        if pd is not None and hasattr(df, "columns"):
            series = df[column]
            unique_count = int(series.nunique(dropna=True))
            dtype = str(series.dtype)
            categorical = (
                dtype == "object"
                or dtype.startswith("category")
                or dtype.startswith("bool")
                or unique_count <= min(1_000, max(25, int(rows * 0.15)))
            )
            values = non_empty_values(series.drop_duplicates().head(500))
        else:
            values_all = [row.get(column, "") for row in df]
            unique_count = len({value for value in values_all if str(value).strip()})
            categorical = unique_count <= min(1_000, max(25, int(rows * 0.15))) or True
            values = list({str(value).strip() for value in values_all if str(value).strip()})[:500]
        if not categorical:
            continue
        result[column] = {
            "unique_count": unique_count,
            "top_20_values": value_counter(df[column] if pd is not None and hasattr(df, "columns") else [r.get(column, "") for r in df]),
            "example_values": values[:20],
            "looks_like_code": looks_like_code_column(column, values),
            "looks_like_label_or_name": looks_like_label_column(column, values),
            "contains_czech_diacritics": any(has_diacritics(value) for value in values),
            "values_with_diacritics_examples": [value for value in values if has_diacritics(value)][:10],
            "possible_abbreviation_examples": [value for value in values if looks_like_abbreviation(value)][:10],
        }
    return result


def to_numeric_series(series: Any) -> Any:
    """Convert a pandas Series to numeric values."""

    if pd is None:
        converted: list[float | None] = []
        for value in series:
            text = str(value).strip().replace(",", ".")
            try:
                converted.append(float(text))
            except ValueError:
                converted.append(None)
        return converted
    return pd.to_numeric(series, errors="coerce")


def analyze_numeric_columns(df: Any, columns: list[str]) -> dict[str, Any]:
    """Profile numeric-looking columns."""

    result: dict[str, Any] = {}
    for column in columns:
        if pd is not None and hasattr(df, "columns"):
            original = df[column]
            numeric = to_numeric_series(original)
            parse_share = float(numeric.notna().mean()) if len(numeric) else 0.0
            is_numeric = pd.api.types.is_numeric_dtype(original) or parse_share >= 0.85
            if not is_numeric:
                continue
            clean = numeric.dropna()
            if clean.empty:
                continue
            result[column] = {
                "min": float(clean.min()),
                "max": float(clean.max()),
                "mean": float(clean.mean()),
                "median": float(clean.median()),
                "sum": float(clean.sum()),
                "zeros": int((clean == 0).sum()),
                "negative_values": int((clean < 0).sum()),
                "missing_values": int(numeric.isna().sum()),
                "parse_share": parse_share,
            }
        else:
            values = to_numeric_series([row.get(column, "") for row in df])
            clean_values = [value for value in values if value is not None]
            if not clean_values or len(clean_values) / max(len(values), 1) < 0.85:
                continue
            result[column] = {
                "min": min(clean_values),
                "max": max(clean_values),
                "mean": statistics.mean(clean_values),
                "median": statistics.median(clean_values),
                "sum": sum(clean_values),
                "zeros": sum(1 for value in clean_values if value == 0),
                "negative_values": sum(1 for value in clean_values if value < 0),
                "missing_values": len(values) - len(clean_values),
                "parse_share": len(clean_values) / max(len(values), 1),
            }
    return result


def detect_time_kind(column: str, values: list[str]) -> str | None:
    """Detect whether a column looks like year, month, or date."""

    lowered = column.lower()
    if lowered in {"rok", "year"} or "rok" in lowered or "year" in lowered:
        return "year"
    if lowered in {"mesic", "měsíc", "month"} or "mesic" in lowered or "měsíc" in lowered or "month" in lowered:
        return "month"
    if "datum" in lowered or "date" in lowered:
        return "date"
    if values:
        year_like = sum(bool(re.fullmatch(r"19\d{2}|20\d{2}", value)) for value in values[:200]) / min(len(values), 200)
        if year_like > 0.8:
            return "year"
    return None


def analyze_time_columns(df: Any, columns: list[str]) -> dict[str, Any]:
    """Detect and summarize year/month/date columns."""

    result: dict[str, Any] = {}
    for column in columns:
        if pd is not None and hasattr(df, "columns"):
            values = non_empty_values(df[column].drop_duplicates().head(500))
        else:
            values = list({str(row.get(column, "")).strip() for row in df if str(row.get(column, "")).strip()})[:500]
        kind = detect_time_kind(column, values)
        if kind is None:
            continue
        numeric_values = [int(float(value)) for value in values if re.fullmatch(r"\d+(\.0)?", value)]
        summary: dict[str, Any] = {"kind": kind, "distinct_values": len(set(values)), "example_values": values[:20]}
        if numeric_values:
            min_value = min(numeric_values)
            max_value = max(numeric_values)
            summary.update({"min": min_value, "max": max_value})
            if kind == "year" and max_value - min_value <= 200:
                present = set(numeric_values)
                summary["missing_years_if_obvious"] = [year for year in range(min_value, max_value + 1) if year not in present]
            if kind == "month":
                present_months = set(value for value in numeric_values if 1 <= value <= 12)
                summary["missing_months_if_obvious"] = [month for month in range(1, 13) if month not in present_months]
        result[column] = summary
    return result


def duplicate_row_count(df: Any) -> int:
    """Count duplicate rows."""

    if pd is not None and hasattr(df, "duplicated"):
        return int(df.duplicated().sum())
    seen: set[tuple[tuple[str, str], ...]] = set()
    duplicates = 0
    for row in df:
        key = tuple(sorted((key, str(value)) for key, value in row.items()))
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def missing_counts(df: Any, columns: list[str]) -> tuple[dict[str, int], dict[str, float]]:
    """Compute missing-value counts and percentages."""

    rows, _ = df_shape(df)
    counts: dict[str, int] = {}
    percentages: dict[str, float] = {}
    for column in columns:
        if pd is not None and hasattr(df, "columns"):
            count = int(df[column].isna().sum() + (df[column].astype(str).str.strip() == "").sum())
        else:
            count = sum(1 for row in df if str(row.get(column, "")).strip() == "")
        counts[column] = count
        percentages[column] = round(100 * count / rows, 3) if rows else 0.0
    return counts, percentages


def dataframe_first_records(df: Any, limit: int = 5) -> list[dict[str, Any]]:
    """Return the first records from a dataframe."""

    if pd is not None and hasattr(df, "head"):
        return df.head(limit).where(pd.notna(df.head(limit)), None).to_dict(orient="records")
    return df[:limit]


def profile_dataframe(
    df: Any,
    *,
    dataset_key: str,
    source_url: str | None,
    local_path: Path,
    encoding: str,
    separator: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Create a JSON-serializable data profile for a loaded dataset."""

    profile_warnings = list(warnings or [])
    rows, columns_count = df_shape(df)
    columns = df_columns(df)
    missing_count, missing_percentage = missing_counts(df, columns)
    if pd is not None and hasattr(df, "dtypes"):
        dtypes = {column: str(dtype) for column, dtype in df.dtypes.items()}
        memory_usage_bytes = int(df.memory_usage(deep=True).sum())
    else:
        dtypes = {column: "string" for column in columns}
        memory_usage_bytes = None
    categorical = analyze_categorical_columns(df, columns)
    numeric = analyze_numeric_columns(df, columns)
    time_columns = analyze_time_columns(df, columns)

    return {
        "dataset_key": dataset_key,
        "profiled_at": now_iso(),
        "source_url": source_url,
        "local_file_path": str(local_path.relative_to(ROOT)),
        "encoding_used": encoding,
        "separator_used": {"\t": "tab"}.get(separator, separator),
        "shape": {"rows": rows, "columns": columns_count},
        "columns": columns,
        "dtypes": dtypes,
        "first_5_rows": dataframe_first_records(df),
        "memory_usage_bytes": memory_usage_bytes,
        "duplicate_row_count": duplicate_row_count(df),
        "missing_value_counts": missing_count,
        "missing_value_percentages": missing_percentage,
        "categorical_columns": categorical,
        "unique_value_counts_for_categorical_columns": {
            column: data["unique_count"] for column, data in categorical.items()
        },
        "numeric_summaries": numeric,
        "time_columns": time_columns,
        "warnings": profile_warnings,
    }


def find_first_existing_column(columns: list[str], candidates: list[str]) -> str | None:
    """Find the first candidate column present, case-insensitively."""

    lowered_to_original = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered_to_original:
            return lowered_to_original[candidate.lower()]
    return None


def detect_column_roles(columns: list[str], profile: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Classify likely semantic roles from column names and categorical profile hints."""

    roles = {
        "diagnosis_code_columns": [],
        "diagnosis_label_columns": [],
        "region_code_columns": [],
        "region_label_columns": [],
        "age_group_code_columns": [],
        "age_group_label_columns": [],
        "sex_columns": [],
        "year_month_columns": [],
        "measure_columns": [],
        "possible_metadata_or_flag_columns": [],
        "other_columns": [],
    }
    numeric_summaries = (profile or {}).get("numeric_summaries", {})
    for column in columns:
        lowered = column.lower()
        assigned = False
        if any(token in lowered for token in ["diagnoza", "diagnóza", "mkn", "icd"]):
            if any(token in lowered for token in ["nazev", "název", "name", "label"]):
                roles["diagnosis_label_columns"].append(column)
            else:
                roles["diagnosis_code_columns"].append(column)
            assigned = True
        if any(token in lowered for token in ["kraj", "region", "okres", "nuts"]):
            if any(token in lowered for token in ["kod", "kód", "code"]):
                roles["region_code_columns"].append(column)
            elif any(token in lowered for token in ["nazev", "název", "name", "label"]):
                roles["region_label_columns"].append(column)
            else:
                roles["region_label_columns"].append(column)
            assigned = True
        if any(token in lowered for token in ["vek", "věk", "age"]):
            if any(token in lowered for token in ["kod", "kód", "code"]):
                roles["age_group_code_columns"].append(column)
            elif any(token in lowered for token in ["nazev", "název", "name", "label"]):
                roles["age_group_label_columns"].append(column)
            else:
                roles["age_group_label_columns"].append(column)
            assigned = True
        if any(token in lowered for token in ["pohlavi", "pohlaví", "sex"]):
            roles["sex_columns"].append(column)
            assigned = True
        if lowered in {"rok", "mesic", "měsíc", "year", "month"} or any(
            token in lowered for token in ["datum", "date"]
        ):
            roles["year_month_columns"].append(column)
            assigned = True
        if (
            column in numeric_summaries
            and any(token in lowered for token in ["pocet", "počet", "cases", "count", "ews", "hodnota"])
        ):
            roles["measure_columns"].append(column)
            assigned = True
        if any(token in lowered for token in ["flag", "priznak", "příznak", "metadata", "zdroj"]):
            roles["possible_metadata_or_flag_columns"].append(column)
            assigned = True
        if not assigned:
            roles["other_columns"].append(column)
    return roles


def group_sum(df: Any, group_columns: list[str], value_column: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Aggregate a measure by one or more columns."""

    if not group_columns or value_column is None:
        return []
    if pd is not None and hasattr(df, "groupby"):
        working = df[group_columns + [value_column]].copy()
        working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0)
        grouped = (
            working.groupby(group_columns, dropna=False)[value_column]
            .sum()
            .reset_index()
            .sort_values(value_column, ascending=False)
        )
        if limit is not None:
            grouped = grouped.head(limit)
        return grouped.where(pd.notna(grouped), None).to_dict(orient="records")

    totals: dict[tuple[str, ...], float] = defaultdict(float)
    for row in df:
        key = tuple(str(row.get(column, "")) for column in group_columns)
        try:
            totals[key] += float(str(row.get(value_column, 0)).replace(",", "."))
        except ValueError:
            totals[key] += 0
    items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    if limit is not None:
        items = items[:limit]
    return [{**{column: key[index] for index, column in enumerate(group_columns)}, value_column: total} for key, total in items]


def unique_values(df: Any, column: str) -> list[Any]:
    """Return unique non-null values for a column."""

    if pd is not None and hasattr(df, "columns"):
        return sorted(df[column].dropna().astype(str).unique().tolist())
    return sorted({str(row.get(column, "")) for row in df if str(row.get(column, "")).strip()})


def infer_grain(df: Any, columns: list[str], grain_candidates: list[str]) -> dict[str, Any]:
    """Test whether a candidate column combination appears to define row grain."""

    present = [column for column in grain_candidates if column in columns]
    rows, _ = df_shape(df)
    result: dict[str, Any] = {
        "tested_columns": present,
        "missing_candidate_columns": [column for column in grain_candidates if column not in columns],
    }
    if not present:
        result["warning"] = "No requested grain columns were available."
        return result
    if pd is not None and hasattr(df, "duplicated"):
        duplicate_mask = df.duplicated(subset=present, keep=False)
        duplicate_count = int(duplicate_mask.sum())
        unique_combinations = int(df[present].drop_duplicates().shape[0])
        result.update(
            {
                "row_count": rows,
                "unique_combinations": unique_combinations,
                "duplicate_rows_on_candidate_grain": duplicate_count,
                "appears_unique": duplicate_count == 0 and unique_combinations == rows,
                "duplicate_examples": df.loc[duplicate_mask, present].head(10).to_dict(orient="records")
                if duplicate_count
                else [],
            }
        )
    else:
        seen: set[tuple[str, ...]] = set()
        duplicate_examples: list[dict[str, str]] = []
        duplicate_count = 0
        for row in df:
            key = tuple(str(row.get(column, "")) for column in present)
            if key in seen:
                duplicate_count += 1
                if len(duplicate_examples) < 10:
                    duplicate_examples.append({column: str(row.get(column, "")) for column in present})
            seen.add(key)
        result.update(
            {
                "row_count": rows,
                "unique_combinations": len(seen),
                "duplicate_rows_on_candidate_grain": duplicate_count,
                "appears_unique": duplicate_count == 0 and len(seen) == rows,
                "duplicate_examples": duplicate_examples,
            }
        )
    return result


def sparse_combination(df: Any, dimensions: list[str], value_column: str | None = None) -> dict[str, Any]:
    """Compute present/absent combination counts when feasible."""

    rows, _ = df_shape(df)
    if not dimensions:
        return {"dimensions": dimensions, "warning": "No dimensions supplied."}
    distinct_counts: dict[str, int] = {column: len(unique_values(df, column)) for column in dimensions}
    total_possible = 1
    for count in distinct_counts.values():
        total_possible *= max(count, 1)
    result: dict[str, Any] = {
        "dimensions": dimensions,
        "distinct_counts": distinct_counts,
        "total_possible_combinations": total_possible,
        "row_count": rows,
    }
    if pd is not None and hasattr(df, "drop_duplicates"):
        present = int(df[dimensions].drop_duplicates().shape[0])
    else:
        present = len({tuple(str(row.get(column, "")) for column in dimensions) for row in df})
    result["present_combinations"] = present
    if total_possible <= MAX_COMBO_PRODUCT:
        result["absent_combinations"] = total_possible - present
        result["sparsity_percentage"] = round(100 * (total_possible - present) / total_possible, 3) if total_possible else 0
    else:
        result["absent_combinations"] = None
        result["sparsity_percentage"] = None
        result["warning"] = "Skipped exact absent-combination enumeration because the Cartesian product is large."
    if value_column and pd is not None and hasattr(df, "groupby"):
        working = df[dimensions + [value_column]].copy()
        working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0)
        grouped = working.groupby(dimensions, dropna=False)[value_column].sum().reset_index()
        result["zero_or_sparse_present_examples"] = grouped.sort_values(value_column).head(10).to_dict(orient="records")
    return result


def compute_top_share(
    df: Any,
    *,
    entity_columns: list[str],
    dimension_column: str,
    value_column: str,
    min_total: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Compute the share of an entity's total concentrated in its top dimension value."""

    if pd is None or not hasattr(df, "groupby") or not entity_columns or dimension_column not in df.columns:
        return []
    working = df[entity_columns + [dimension_column, value_column]].copy()
    working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0)
    grouped = working.groupby(entity_columns + [dimension_column], dropna=False)[value_column].sum().reset_index()
    totals = grouped.groupby(entity_columns, dropna=False)[value_column].sum().reset_index().rename(columns={value_column: "total"})
    merged = grouped.merge(totals, on=entity_columns, how="left")
    merged = merged[merged["total"] >= min_total]
    if merged.empty:
        return []
    merged["share"] = merged[value_column] / merged["total"].replace(0, pd.NA)
    top = merged.sort_values("share", ascending=False).groupby(entity_columns, dropna=False).head(1)
    top = top.sort_values(["share", "total"], ascending=[False, False]).head(limit)
    top = top.rename(columns={dimension_column: "top_dimension_value", value_column: "top_dimension_count"})
    return top.where(pd.notna(top), None).to_dict(orient="records")


def compute_year_variation(
    df: Any,
    *,
    entity_columns: list[str],
    year_column: str,
    value_column: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find diseases/entities with high year-to-year variation."""

    if pd is None or not hasattr(df, "groupby") or year_column not in df.columns:
        return []
    working = df[entity_columns + [year_column, value_column]].copy()
    working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0)
    grouped = working.groupby(entity_columns + [year_column], dropna=False)[value_column].sum().reset_index()
    records: list[dict[str, Any]] = []
    for entity_key, subframe in grouped.groupby(entity_columns, dropna=False):
        if len(subframe) < 3:
            continue
        values = subframe[value_column].astype(float).tolist()
        mean_value = statistics.mean(values)
        if mean_value <= 0:
            continue
        stdev = statistics.pstdev(values)
        entity_values = entity_key if isinstance(entity_key, tuple) else (entity_key,)
        record = {column: entity_values[index] for index, column in enumerate(entity_columns)}
        record.update(
            {
                "years_observed": int(len(subframe)),
                "total": float(sum(values)),
                "mean_per_year": float(mean_value),
                "stddev_per_year": float(stdev),
                "coefficient_of_variation": float(stdev / mean_value),
                "min_year_total": float(min(values)),
                "max_year_total": float(max(values)),
            }
        )
        records.append(record)
    return sorted(records, key=lambda item: (item["coefficient_of_variation"], item["total"]), reverse=True)[:limit]


def compute_seasonality(
    df: Any,
    *,
    entity_columns: list[str],
    month_column: str,
    value_column: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find entities whose monthly distribution is strongly non-uniform."""

    if pd is None or not hasattr(df, "groupby") or month_column not in df.columns:
        return []
    working = df[entity_columns + [month_column, value_column]].copy()
    working[value_column] = pd.to_numeric(working[value_column], errors="coerce").fillna(0)
    grouped = working.groupby(entity_columns + [month_column], dropna=False)[value_column].sum().reset_index()
    records: list[dict[str, Any]] = []
    for entity_key, subframe in grouped.groupby(entity_columns, dropna=False):
        total = float(subframe[value_column].sum())
        if total <= 0 or len(subframe) < 6:
            continue
        shares = [float(value) / total for value in subframe[value_column].tolist() if total]
        entropy = -sum(share * math.log(share) for share in shares if share > 0)
        max_entropy = math.log(min(12, max(len(shares), 1)))
        non_uniformity = 1 - (entropy / max_entropy if max_entropy else 0)
        top_row = subframe.sort_values(value_column, ascending=False).iloc[0]
        entity_values = entity_key if isinstance(entity_key, tuple) else (entity_key,)
        record = {column: entity_values[index] for index, column in enumerate(entity_columns)}
        record.update(
            {
                "total": total,
                "top_month": top_row[month_column],
                "top_month_count": float(top_row[value_column]),
                "top_month_share": float(top_row[value_column] / total),
                "seasonality_non_uniformity_score": float(non_uniformity),
            }
        )
        records.append(record)
    return sorted(records, key=lambda item: (item["seasonality_non_uniformity_score"], item["total"]), reverse=True)[:limit]


def terminology_difficulty(df: Any, code_column: str | None, label_column: str | None) -> dict[str, Any]:
    """Identify labels likely to be hard for lexical retrieval or normalization."""

    if label_column is None:
        return {"warning": "No diagnosis label column detected."}
    if pd is not None and hasattr(df, "columns"):
        labels = sorted(set(non_empty_values(df[label_column])))
        code_by_label = {}
        if code_column and code_column in df.columns:
            code_by_label = (
                df[[code_column, label_column]]
                .dropna()
                .drop_duplicates()
                .astype(str)
                .set_index(label_column)[code_column]
                .to_dict()
            )
    else:
        labels = sorted({str(row.get(label_column, "")).strip() for row in df if str(row.get(label_column, "")).strip()})
        code_by_label = {str(row.get(label_column, "")): str(row.get(code_column, "")) for row in df} if code_column else {}

    long_labels = sorted(labels, key=len, reverse=True)[:20]
    diacritic_labels = [label for label in labels if has_diacritics(label)][:20]
    abbreviation_labels = [label for label in labels if looks_like_abbreviation(label)][:20]
    normalized_groups: dict[str, list[str]] = defaultdict(list)
    for label in labels:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", strip_diacritics(label.lower()))
        normalized = re.sub(r"\s+", " ", normalized).strip()
        prefix = " ".join(normalized.split()[:3])
        if prefix:
            normalized_groups[prefix].append(label)
    variant_groups = [
        {"normalized_prefix": key, "labels": values[:10]}
        for key, values in normalized_groups.items()
        if len(values) > 1
    ][:20]

    similar_pairs: list[dict[str, Any]] = []
    try:
        from difflib import SequenceMatcher

        candidate_labels = labels[:300]
        for index, left in enumerate(candidate_labels):
            left_norm = strip_diacritics(left.lower())
            for right in candidate_labels[index + 1 : min(index + 60, len(candidate_labels))]:
                right_norm = strip_diacritics(right.lower())
                ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
                if 0.86 <= ratio < 1.0:
                    similar_pairs.append({"left": left, "right": right, "similarity": round(ratio, 3)})
                if len(similar_pairs) >= 20:
                    break
            if len(similar_pairs) >= 20:
                break
    except Exception:
        similar_pairs = []

    return {
        "label_column": label_column,
        "code_column": code_column,
        "label_count": len(labels),
        "long_czech_disease_names": [
            {"code": code_by_label.get(label), "label": label, "length": len(label)} for label in long_labels
        ],
        "labels_with_diacritics_examples": diacritic_labels,
        "labels_with_abbreviations_examples": abbreviation_labels,
        "possible_variant_groups_by_prefix": variant_groups,
        "similar_label_pairs": similar_pairs,
        "retrieval_risk_notes": [
            "Long Czech names, diacritics, abbreviations, and near-duplicate labels can weaken exact lexical retrieval.",
            "Diagnosis code ↔ label mapping and MKN-10 hierarchy should be evaluated as recall aids, not assumed to help.",
        ],
    }


def analyze_infectious_disease_dataset(df: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Run infectious-disease specific exploratory analyses."""

    columns = df_columns(df)
    warnings = list(profile.get("warnings", []))
    expected = [
        "rok",
        "mesic",
        "kraj_kod",
        "kraj_nazev",
        "diagnoza",
        "diagnoza_nazev",
        "vek_kod",
        "vek_nazev",
        "pohlavi",
        "EWS",
        "pocet_pripadu",
    ]
    missing_expected = [column for column in expected if column not in columns]
    if missing_expected:
        warnings.append(f"Expected infectious-disease columns missing: {', '.join(missing_expected)}")

    year_col = find_first_existing_column(columns, ["rok", "year"])
    month_col = find_first_existing_column(columns, ["mesic", "měsíc", "month"])
    diagnosis_col = find_first_existing_column(columns, ["diagnoza", "diagnóza"])
    diagnosis_label_col = find_first_existing_column(columns, ["diagnoza_nazev", "diagnóza_název", "diagnoza_název"])
    region_col = find_first_existing_column(columns, ["kraj_kod", "region_code"])
    region_label_col = find_first_existing_column(columns, ["kraj_nazev", "kraj_název", "region"])
    age_col = find_first_existing_column(columns, ["vek_kod", "věk_kod", "age_code"])
    age_label_col = find_first_existing_column(columns, ["vek_nazev", "věk_název", "vek_název"])
    sex_col = find_first_existing_column(columns, ["pohlavi", "pohlaví", "sex"])
    measure_col = find_first_existing_column(columns, ["pocet_pripadu", "počet_případů", "pocet", "count"])
    ews_col = find_first_existing_column(columns, ["EWS", "ews"])

    if measure_col is None:
        numeric_columns = list(profile.get("numeric_summaries", {}).keys())
        measure_col = numeric_columns[-1] if numeric_columns else None
        warnings.append(f"Could not find pocet_pripadu; selected possible measure column {measure_col!r}.")

    disease_entity_columns = [column for column in [diagnosis_col, diagnosis_label_col] if column]
    coverage: dict[str, Any] = {}
    if year_col:
        years = unique_values(df, year_col)
        numeric_years = sorted(int(float(year)) for year in years if re.fullmatch(r"\d+(\.0)?", str(year)))
        coverage["number_of_years"] = len(set(numeric_years)) if numeric_years else len(years)
        coverage["year_range"] = [min(numeric_years), max(numeric_years)] if numeric_years else None
    if diagnosis_col:
        coverage["number_of_diseases"] = len(unique_values(df, diagnosis_col))
    if region_col or region_label_col:
        coverage["number_of_regions"] = len(unique_values(df, region_col or region_label_col))
    if age_col or age_label_col:
        coverage["number_of_age_groups"] = len(unique_values(df, age_col or age_label_col))
    if sex_col:
        coverage["number_of_sex_categories"] = len(unique_values(df, sex_col))

    if measure_col:
        if year_col:
            coverage["total_reported_cases_by_year"] = group_sum(df, [year_col], measure_col, limit=200)
        if region_label_col or region_col:
            coverage["total_reported_cases_by_region"] = group_sum(df, [region_label_col or region_col], measure_col, limit=50)
        if disease_entity_columns:
            coverage["total_reported_cases_by_diagnosis"] = group_sum(df, disease_entity_columns, measure_col, limit=50)
        if age_label_col or age_col:
            coverage["total_reported_cases_by_age_group"] = group_sum(df, [age_label_col or age_col], measure_col, limit=100)
        if sex_col:
            coverage["total_reported_cases_by_sex"] = group_sum(df, [sex_col], measure_col, limit=20)
    if ews_col:
        if year_col:
            coverage["total_EWS_by_year"] = group_sum(df, [year_col], ews_col, limit=200)
        if disease_entity_columns:
            coverage["total_EWS_by_diagnosis"] = group_sum(df, disease_entity_columns, ews_col, limit=50)

    sparse: dict[str, Any] = {}
    sparse_specs = {
        "disease_x_year": [diagnosis_col or diagnosis_label_col, year_col],
        "disease_x_region": [diagnosis_col or diagnosis_label_col, region_col or region_label_col],
        "disease_x_age_group": [diagnosis_col or diagnosis_label_col, age_col or age_label_col],
        "disease_x_sex": [diagnosis_col or diagnosis_label_col, sex_col],
        "disease_x_year_x_region": [diagnosis_col or diagnosis_label_col, year_col, region_col or region_label_col],
    }
    for name, dims in sparse_specs.items():
        present_dims = [dimension for dimension in dims if dimension is not None]
        if len(present_dims) == len([dimension for dimension in dims if dimension is not None]) and len(present_dims) >= 2:
            sparse[name] = sparse_combination(df, present_dims, measure_col)

    high_total = group_sum(df, disease_entity_columns, measure_col, limit=20) if measure_col and disease_entity_columns else []
    year_variation = (
        compute_year_variation(df, entity_columns=disease_entity_columns, year_column=year_col, value_column=measure_col)
        if year_col and measure_col and disease_entity_columns
        else []
    )
    regional_concentration = (
        compute_top_share(
            df,
            entity_columns=disease_entity_columns,
            dimension_column=region_label_col or region_col,
            value_column=measure_col,
            min_total=100,
        )
        if (region_label_col or region_col) and measure_col and disease_entity_columns
        else []
    )
    age_concentration = (
        compute_top_share(
            df,
            entity_columns=disease_entity_columns,
            dimension_column=age_label_col or age_col,
            value_column=measure_col,
            min_total=100,
        )
        if (age_label_col or age_col) and measure_col and disease_entity_columns
        else []
    )
    seasonality = (
        compute_seasonality(df, entity_columns=disease_entity_columns, month_column=month_col, value_column=measure_col)
        if month_col and measure_col and disease_entity_columns
        else []
    )
    terminology = terminology_difficulty(df, diagnosis_col, diagnosis_label_col)

    grain_candidates = [
        "rok",
        "mesic",
        "kraj_kod",
        "kraj_nazev",
        "diagnoza",
        "diagnoza_nazev",
        "vek_kod",
        "vek_nazev",
        "pohlavi",
    ]
    grain = infer_grain(df, columns, grain_candidates)

    sparse_diseases = []
    broad_diseases = []
    if pd is not None and hasattr(df, "groupby") and disease_entity_columns and year_col and (region_col or region_label_col):
        region_dimension = region_col or region_label_col
        summary = (
            df[disease_entity_columns + [year_col, region_dimension]]
            .drop_duplicates()
            .groupby(disease_entity_columns, dropna=False)
            .agg(years_observed=(year_col, "nunique"), regions_observed=(region_dimension, "nunique"))
            .reset_index()
        )
        sparse_diseases = summary.sort_values(["years_observed", "regions_observed"], ascending=[True, True]).head(15).to_dict(
            orient="records"
        )
        broad_diseases = summary.sort_values(["years_observed", "regions_observed"], ascending=[False, False]).head(15).to_dict(
            orient="records"
        )

    return {
        "warnings": warnings,
        "expected_columns": expected,
        "available_columns": columns,
        "missing_expected_columns": missing_expected,
        "column_roles": detect_column_roles(columns, profile),
        "detected_key_columns": {
            "year": year_col,
            "month": month_col,
            "diagnosis_code": diagnosis_col,
            "diagnosis_label": diagnosis_label_col,
            "region_code": region_col,
            "region_label": region_label_col,
            "age_group_code": age_col,
            "age_group_label": age_label_col,
            "sex": sex_col,
            "measure": measure_col,
            "ews": ews_col,
        },
        "grain_analysis": grain,
        "coverage_analysis": coverage,
        "sparse_combination_analysis": sparse,
        "interesting_disease_candidates": {
            "high_total_counts": high_total,
            "strong_year_to_year_variation": year_variation,
            "regionally_concentrated_counts": regional_concentration,
            "age_group_concentrated_counts": age_concentration,
            "clear_seasonality_by_month": seasonality,
            "enough_data_across_years_and_regions": broad_diseases,
            "sparse_but_interesting_coverage": sparse_diseases,
            "retrieval_or_matching_difficulty": terminology,
        },
        "seasonality_analysis": {
            "method": "For each diagnosis, aggregate monthly case counts and compute normalized entropy; higher non-uniformity indicates stronger seasonality.",
            "top_candidates": seasonality,
        },
        "regional_contrast_analysis": {
            "method": "For each diagnosis, compute the share of total reported cases in its top region.",
            "top_candidates": regional_concentration,
        },
        "age_profile_analysis": {
            "method": "For each diagnosis, compute the share of total reported cases in its top age-group category.",
            "top_candidates": age_concentration,
        },
        "terminology_and_retrieval_difficulty_analysis": terminology,
    }


def identify_code_and_label_columns(profile: dict[str, Any]) -> tuple[str | None, str | None]:
    """Identify likely code and label columns from a profile."""

    categorical = profile.get("categorical_columns", {})
    code_candidates = [column for column, info in categorical.items() if info.get("looks_like_code")]
    label_candidates = [column for column, info in categorical.items() if info.get("looks_like_label_or_name")]
    columns = profile.get("columns", [])
    if not code_candidates:
        code_candidates = [column for column in columns if any(token in column.lower() for token in ["kod", "kód", "code"])]
    if not label_candidates:
        label_candidates = [
            column for column in columns if any(token in column.lower() for token in ["nazev", "název", "label", "name"])
        ]
    return (code_candidates[0] if code_candidates else None, label_candidates[0] if label_candidates else None)


def compare_code_sets(
    source_df: Any,
    source_column: str | None,
    codelist_df: Any,
    code_column: str | None,
) -> dict[str, Any]:
    """Compare codes in a source table to a supporting code list."""

    if source_column is None or code_column is None:
        return {"warning": "Could not compare code sets because one or both code columns were not detected."}
    source_codes = {str(value).strip() for value in unique_values(source_df, source_column) if str(value).strip()}
    codelist_codes = {str(value).strip() for value in unique_values(codelist_df, code_column) if str(value).strip()}
    return {
        "source_column": source_column,
        "codelist_code_column": code_column,
        "source_code_count": len(source_codes),
        "codelist_code_count": len(codelist_codes),
        "unmatched_source_codes": sorted(source_codes - codelist_codes)[:200],
        "codelist_codes_not_used_in_source": sorted(codelist_codes - source_codes)[:200],
        "matched_code_count": len(source_codes & codelist_codes),
    }


def analyze_age_group_codelist(
    age_df: Any,
    age_profile: dict[str, Any],
    infectious_df: Any | None,
    infectious_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Analyze age-group code list usefulness and source coverage."""

    code_col, label_col = identify_code_and_label_columns(age_profile)
    infectious_age_col = None
    if infectious_analysis:
        infectious_age_col = infectious_analysis.get("detected_key_columns", {}).get("age_group_code")
    comparison = (
        compare_code_sets(infectious_df, infectious_age_col, age_df, code_col)
        if infectious_df is not None
        else {"warning": "Infectious-disease dataset was unavailable; skipped cross-check."}
    )
    return {
        "detected_code_column": code_col,
        "detected_label_column": label_col,
        "infectious_age_group_code_column": infectious_age_col,
        "code_coverage_against_infectious_diseases": comparison,
        "usefulness_assessment": [
            "Useful for interpreting official age-group categories if codes match.",
            "Useful for normalization only when a user phrase can be grounded in code-list intervals or labels.",
            "Future semantic modelling should keep code and Czech label mappings inspectable.",
        ],
    }


def analyze_mkn10_codelist(
    mkn_df: Any,
    mkn_profile: dict[str, Any],
    infectious_df: Any | None,
    infectious_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Analyze MKN-10-CZ code list usefulness and source coverage."""

    code_col, label_col = identify_code_and_label_columns(mkn_profile)
    columns = df_columns(mkn_df)
    hierarchy_columns = [
        column
        for column in columns
        if any(
            token in column.lower()
            for token in ["kapit", "chapter", "blok", "block", "skup", "group", "uroven", "úroveň", "nadraz", "nadřaz"]
        )
    ]
    infectious_diag_col = None
    measure_col = None
    if infectious_analysis:
        key_columns = infectious_analysis.get("detected_key_columns", {})
        infectious_diag_col = key_columns.get("diagnosis_code")
        measure_col = key_columns.get("measure")
    comparison = (
        compare_code_sets(infectious_df, infectious_diag_col, mkn_df, code_col)
        if infectious_df is not None
        else {"warning": "Infectious-disease dataset was unavailable; skipped cross-check."}
    )
    chapter_counts: list[dict[str, Any]] = []
    if (
        pd is not None
        and infectious_df is not None
        and infectious_diag_col
        and code_col
        and measure_col
        and hierarchy_columns
        and hasattr(infectious_df, "merge")
    ):
        chapter_col = hierarchy_columns[0]
        left = infectious_df[[infectious_diag_col, measure_col]].copy()
        left[measure_col] = pd.to_numeric(left[measure_col], errors="coerce").fillna(0)
        right_cols = [code_col, chapter_col]
        if label_col:
            right_cols.append(label_col)
        right = mkn_df[right_cols].drop_duplicates().astype(str)
        merged = left.astype({infectious_diag_col: str}).merge(
            right, left_on=infectious_diag_col, right_on=code_col, how="left"
        )
        if chapter_col in merged.columns:
            chapter_counts = (
                merged.groupby(chapter_col, dropna=False)[measure_col]
                .sum()
                .reset_index()
                .sort_values(measure_col, ascending=False)
                .head(50)
                .to_dict(orient="records")
            )
    return {
        "detected_code_column": code_col,
        "detected_label_column": label_col,
        "infectious_diagnosis_code_column": infectious_diag_col,
        "code_coverage_against_infectious_diseases": comparison,
        "possible_hierarchy_columns": hierarchy_columns,
        "exploratory_counts_by_first_hierarchy_column": chapter_counts,
        "usefulness_assessment": [
            "MKN-10-CZ is a plausible normalization/hierarchy source if infectious diagnosis codes match.",
            "Hierarchy should be used experimentally for retrieval/scope expansion, not asserted as a final contribution yet.",
            "Unmatched codes require manual inspection before any graph or recall evaluation.",
        ],
    }


def analyze_optional_hospitalization_dataset(
    hospitalization_df: Any | None,
    hospitalization_profile: dict[str, Any] | None,
    infectious_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Analyze optional hospitalization data if available."""

    if hospitalization_df is None or hospitalization_profile is None:
        return {
            "loaded": False,
            "warnings": ["Hospitalization dataset was not available or was skipped."],
            "future_extension_assessment": "No cross-table opportunity can be assessed until a CSV is discovered and loaded.",
        }
    hospital_columns = set(hospitalization_profile.get("columns", []))
    infectious_columns = set((infectious_profile or {}).get("columns", []))
    shared_exact_columns = sorted(hospital_columns & infectious_columns)
    likely_shared_concepts = {
        "diagnosis": sorted([column for column in hospital_columns if "diag" in column.lower() or "mkn" in column.lower()]),
        "age": sorted([column for column in hospital_columns if "vek" in column.lower() or "věk" in column.lower()]),
        "year_or_date": sorted(
            [column for column in hospital_columns if any(token in column.lower() for token in ["rok", "datum", "date"])]
        ),
        "region": sorted([column for column in hospital_columns if "kraj" in column.lower() or "region" in column.lower()]),
        "sex": sorted([column for column in hospital_columns if "pohlav" in column.lower() or "sex" in column.lower()]),
    }
    return {
        "loaded": True,
        "shared_exact_columns_with_infectious_diseases": shared_exact_columns,
        "likely_shared_concepts": likely_shared_concepts,
        "future_extension_assessment": (
            "Potentially useful as a future extension if shared diagnosis, age, region, year, or sex concepts can be "
            "validated. It should not be joined in this profiling stage."
        ),
        "risks": [
            "Different analytical grain may make direct comparisons invalid.",
            "Indicators may have different semantics from infectious-disease case counts.",
            "Hospitalization indicators must not be interpreted as treatment-effectiveness evidence without a proper study design.",
            "Cross-table analysis can invite causal misinterpretation if not carefully scoped.",
        ],
    }


def create_sample_files(
    loaded: dict[str, dict[str, Any]],
    *,
    sample_rows: int = SAMPLE_ROWS,
) -> dict[str, Any]:
    """Create UTF-8 sample CSV files for successfully loaded datasets."""

    sample_records: dict[str, Any] = {}
    for key, info in loaded.items():
        df = info.get("df")
        spec: DatasetSpec = info["spec"]
        sample_path = SAMPLES_DIR / spec.sample_filename
        if df is None:
            continue
        if pd is not None and hasattr(df, "head"):
            df.head(sample_rows).to_csv(sample_path, index=False, encoding="utf-8")
            row_count = min(len(df), sample_rows)
        else:
            rows = df[:sample_rows]
            columns = df_columns(rows)
            with sample_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            row_count = len(rows)
        sample_records[key] = {"path": str(sample_path.relative_to(ROOT)), "rows": row_count}
    return sample_records


def make_question(
    qid: str,
    question: str,
    involved_columns: list[str],
    required_filters: list[str],
    required_grouping: list[str],
    required_aggregation: str,
    difficulty_level: str,
    why_interesting: str,
    possible_semantic_or_kg_role: str,
    possible_recall_issue: str,
) -> dict[str, Any]:
    """Build a candidate research question record."""

    return {
        "id": qid,
        "question": question,
        "involved_columns": involved_columns,
        "required_filters": required_filters,
        "required_grouping": required_grouping,
        "required_aggregation": required_aggregation,
        "difficulty_level": difficulty_level,
        "why_interesting": why_interesting,
        "possible_baseline": "Pandas/SQL aggregation over the profiled table with exact column/value selection.",
        "possible_semantic_or_kg_role": possible_semantic_or_kg_role,
        "possible_rag_role": "Retrieve metadata/methodology snippets to explain caveats and dataset scope.",
        "possible_recall_issue": possible_recall_issue,
        "needs_manual_validation": True,
    }


def generate_candidate_questions(infectious_analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Generate candidate research/demo questions grounded in detected columns."""

    key_columns = (infectious_analysis or {}).get("detected_key_columns", {})
    diagnosis_label = key_columns.get("diagnosis_label") or "diagnoza_nazev"
    diagnosis_code = key_columns.get("diagnosis_code") or "diagnoza"
    region = key_columns.get("region_label") or key_columns.get("region_code") or "kraj_nazev"
    age = key_columns.get("age_group_label") or key_columns.get("age_group_code") or "vek_nazev"
    year = key_columns.get("year") or "rok"
    month = key_columns.get("month") or "mesic"
    sex = key_columns.get("sex") or "pohlavi"
    measure = key_columns.get("measure") or "pocet_pripadu"

    return [
        make_question(
            "RQ-001",
            "Which infectious diseases have the strongest regional concentration of reported cases?",
            [diagnosis_code, diagnosis_label, region, measure],
            [],
            [diagnosis_label, region],
            f"sum({measure}) and top-region share",
            "medium",
            "Regional contrast is visually and analytically useful for a demo while remaining one-table-first.",
            "Ground region mentions in official categories and explain selected dimensions.",
            "User phrasing may not exactly match official region labels.",
        ),
        make_question(
            "RQ-002",
            "Which diseases show the clearest seasonal pattern by month?",
            [diagnosis_code, diagnosis_label, month, measure],
            [],
            [diagnosis_label, month],
            f"sum({measure}), monthly share, entropy/non-uniformity",
            "medium",
            "Seasonality gives a concrete analytical pattern that can be shown without overclaiming clinical meaning.",
            "Connect disease labels/codes to selected seasonal analytical scope.",
            "A user may ask for a disease family or Czech variant not matching the table label.",
        ),
        make_question(
            "RQ-003",
            "Compare reported cases for a selected diagnosis block across regions and age groups.",
            [diagnosis_code, diagnosis_label, year, region, age, measure],
            ["disease code range or block", "explicit year values"],
            [diagnosis_label, year, region, age],
            f"sum({measure})",
            "high",
            "This tests multi-value analytical scope construction before query execution.",
            "Expand validated code ranges or blocks to diagnosis codes and keep year constraints explicit.",
            "Simple retrieval may miss relevant individual diagnosis codes and age/region categories.",
        ),
        make_question(
            "RQ-004",
            "For a disease with a long Czech name, can a user phrase retrieve the correct diagnosis code and label?",
            [diagnosis_code, diagnosis_label],
            ["natural-language disease phrase"],
            [],
            "entity retrieval top-k recall",
            "high",
            "Terminology normalization is likely central for Czech public-health table exploration.",
            "Use code-label edges, diacritic normalization, and MKN hierarchy if validated.",
            "Exact lexical retrieval may fail under inflection, missing diacritics, abbreviations, or partial labels.",
        ),
        make_question(
            "RQ-005",
            "Which diseases have reported cases concentrated in particular age groups?",
            [diagnosis_code, diagnosis_label, age, measure],
            [],
            [diagnosis_label, age],
            f"sum({measure}) and top-age-group share",
            "medium",
            "Age profiles can support a compact demo of categorical value selection and explanation.",
            "Ground age constraints in official age interval columns.",
            "Broad age wording may not retrieve all expected official age bands without explicit interval evidence.",
        ),
        make_question(
            "RQ-006",
            "Are there disease-year-region combinations that are absent or sparse in the table?",
            [diagnosis_code, diagnosis_label, year, region, measure],
            [],
            [diagnosis_label, year, region],
            "coverage/sparsity counts",
            "high",
            "Coverage gaps matter for honest public-health data exploration and evidence-aware answering.",
            "Represent analytical scope explicitly and flag missing combinations before aggregation.",
            "A retriever may only surface present rows and hide absent combinations.",
        ),
        make_question(
            "RQ-007",
            "How do reported cases vary by sex for selected diseases and years?",
            [diagnosis_code, diagnosis_label, year, sex, measure],
            ["selected disease or disease family", "selected years"],
            [diagnosis_label, year, sex],
            f"sum({measure})",
            "low",
            "A simple but useful baseline case for exact-value filtering and grouped aggregation.",
            "Semantic support is mostly value normalization and scope explanation.",
            "Recall risk is lower when the disease and year are explicitly specified.",
        ),
        make_question(
            "RQ-008",
            "Can MKN-10-CZ hierarchy improve retrieval for group-level disease questions?",
            [diagnosis_code, diagnosis_label],
            ["group-level disease phrase"],
            [diagnosis_label],
            "retrieved relevant diagnosis codes / all relevant codes",
            "high",
            "This is a plausible SEMANTiCS contribution if MKN hierarchy and code coverage are sufficient.",
            "Use MKN code hierarchy/chapter/block relations for expansion after validating code matches.",
            "Simple lexical/vector retrieval may return only the closest label and miss sibling diagnoses.",
        ),
    ]


def generate_candidate_demo_scenarios(
    infectious_analysis: dict[str, Any] | None,
    age_analysis: dict[str, Any] | None,
    mkn_analysis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Generate ranked candidate demo scenarios."""

    key_columns = (infectious_analysis or {}).get("detected_key_columns", {})
    cols = [column for column in key_columns.values() if column]
    mkn_match_count = (
        ((mkn_analysis or {}).get("code_coverage_against_infectious_diseases") or {}).get("matched_code_count") or 0
    )
    age_match_count = (
        ((age_analysis or {}).get("code_coverage_against_infectious_diseases") or {}).get("matched_code_count") or 0
    )
    return [
        {
            "id": "DS-001",
            "title": "Recall-aware Czech disease value retrieval",
            "short_description": "Evaluate whether code-label normalization and optional MKN expansion improve retrieval of diagnosis values from Czech user phrases.",
            "dataset": "infectious_diseases with MKN-10-CZ as supporting code list",
            "columns_used": [key_columns.get("diagnosis_code"), key_columns.get("diagnosis_label")],
            "example_questions": [
                "Find diagnoses matching an explicit MKN code range.",
                "Show cases for a selected diagnosis code by region.",
            ],
            "baseline_version": "Lexical/vector retrieval over raw table values.",
            "possible_semantic_version": "Diacritic/morphology-aware label normalization and type-specific candidate retrieval.",
            "possible_kg_version": "Diagnosis code ↔ label plus MKN hierarchy expansion if validated.",
            "possible_rag_version": "Retrieve metadata/methodology explanations for chosen diagnosis codes.",
            "expected_benefit_to_test": "Higher diagnosis-code recall@k for code ranges and partial Czech disease phrases.",
            "risks": ["MKN code coverage may be incomplete.", "Independent reference sets are needed for measurement."],
            "demo_paper_fit_score_1_to_5": 5 if mkn_match_count else 4,
        },
        {
            "id": "DS-002",
            "title": "Analytical-scope construction before SQL",
            "short_description": "Turn vague multi-aspect questions into typed disease/year/region/age/measure scopes before executing table aggregations.",
            "dataset": "infectious_diseases",
            "columns_used": cols,
            "example_questions": [
                "Compare an explicit diagnosis set across regions and age groups.",
                "Which age groups and regions should be inspected for selected seasonal disease trends?",
            ],
            "baseline_version": "Prompt-to-SQL or manual pandas aggregation using exact values.",
            "possible_semantic_version": "Normalize only phrases grounded in source labels, code ranges, or numeric constraints.",
            "possible_kg_version": "Typed entities and relations for disease, region, age group, time, and measures.",
            "possible_rag_version": "Use metadata to explain scope limits and avoid clinical overinterpretation.",
            "expected_benefit_to_test": "Improved dimension/value recall and fewer incomplete analytical scopes.",
            "risks": ["Scope measurement needs careful reference annotations.", "May be too broad for a first 5-page demo."],
            "demo_paper_fit_score_1_to_5": 4,
        },
        {
            "id": "DS-003",
            "title": "Seasonality explorer with evidence-aware summaries",
            "short_description": "Identify diseases with non-uniform monthly distributions and generate cautious summaries grounded in table profiles.",
            "dataset": "infectious_diseases",
            "columns_used": [
                key_columns.get("diagnosis_code"),
                key_columns.get("diagnosis_label"),
                key_columns.get("month"),
                key_columns.get("measure"),
            ],
            "example_questions": ["Which diseases appear most seasonal by month?", "Show monthly patterns for selected diseases."],
            "baseline_version": "Monthly aggregation and entropy/top-month-share ranking.",
            "possible_semantic_version": "Normalize disease names and explain selected time dimension.",
            "possible_kg_version": "Low need for KG unless connecting to disease hierarchy or metadata.",
            "possible_rag_version": "Summarize results with dataset caveats and methodology retrieval.",
            "expected_benefit_to_test": "Clear, cautious analytical explanations rather than raw chart-only output.",
            "risks": ["Seasonality is descriptive only.", "Counts must not be treated as incidence without documentation."],
            "demo_paper_fit_score_1_to_5": 3,
        },
        {
            "id": "DS-004",
            "title": "Age-interval normalization for public-health questions",
            "short_description": "Map explicit numeric age constraints to official age-group codes and labels before table aggregation.",
            "dataset": "infectious_diseases with age-group code list",
            "columns_used": [key_columns.get("age_group_code"), key_columns.get("age_group_label"), key_columns.get("measure")],
            "example_questions": ["Which diseases are concentrated in an explicit age interval?", "Compare selected official age groups for selected diagnoses."],
            "baseline_version": "Exact filtering on official age-group values.",
            "possible_semantic_version": "Interval-based mapping from explicit numeric age constraints to official categories.",
            "possible_kg_version": "Age-group code ↔ label and broader age-band relations.",
            "possible_rag_version": "Retrieve code-list metadata for interpretation of age categories.",
            "expected_benefit_to_test": "Higher recall of expected official age categories for explicit interval queries.",
            "risks": ["Requires validated interval semantics.", "Official code list may not encode every broader user category."],
            "demo_paper_fit_score_1_to_5": 4 if age_match_count else 3,
        },
        {
            "id": "DS-005",
            "title": "Coverage-gap explanation for sparse disease-region-year combinations",
            "short_description": "Show where requested analytical combinations are present, sparse, absent, or too large to enumerate.",
            "dataset": "infectious_diseases",
            "columns_used": [
                key_columns.get("diagnosis_code"),
                key_columns.get("year"),
                key_columns.get("region_label") or key_columns.get("region_code"),
                key_columns.get("measure"),
            ],
            "example_questions": ["Do all regions have records for this disease every year?", "Which disease-year-region combinations are sparse?"],
            "baseline_version": "Group-by counts and Cartesian coverage checks.",
            "possible_semantic_version": "Explain missing scope elements and distinguish absent table combinations from zero counts where possible.",
            "possible_kg_version": "Represent requested scope as graph-shaped constraints with explicit coverage status.",
            "possible_rag_version": "Retrieve metadata notes about aggregation and reporting limitations.",
            "expected_benefit_to_test": "Better coverage explanation completeness compared with row retrieval alone.",
            "risks": ["Zero versus missing may not be inferable from the table alone."],
            "demo_paper_fit_score_1_to_5": 4,
        },
    ]


def markdown_table(headers: list[str], rows: list[list[Any]], max_rows: int | None = None) -> str:
    """Create a compact Markdown table."""

    selected_rows = rows[:max_rows] if max_rows else rows
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in selected_rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    if max_rows and len(rows) > max_rows:
        lines.append(f"| ... | {len(rows) - max_rows} more rows omitted |" + " |" * max(0, len(headers) - 2))
    return "\n".join(lines)


def write_data_inventory(
    downloads: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    failed: dict[str, Any],
    discovered_links: dict[str, Any],
) -> None:
    """Write the data inventory report."""

    rows = []
    for key, profile in profiles.items():
        shape = profile.get("shape", {})
        rows.append(
            [
                key,
                profile.get("source_url"),
                profile.get("local_file_path"),
                f"{shape.get('rows')} x {shape.get('columns')}",
                profile.get("encoding_used"),
                profile.get("separator_used"),
            ]
        )
    failed_rows = [[key, value.get("stage"), "; ".join(value.get("warnings", []))] for key, value in failed.items()]
    text = [
        "# Data inventory",
        "",
        f"Generated: {now_iso()}",
        "",
        "This inventory records acquisition and profiling status for the Czech public-health open-data sources used in the exploratory SEMANTiCS demo preparation.",
        "",
        "Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.",
        "",
        "## Loaded datasets",
        "",
        markdown_table(["Dataset", "Source URL", "Local file", "Shape", "Encoding", "Separator"], rows) if rows else "No datasets loaded.",
        "",
        "## Download records",
        "",
        "```json",
        json.dumps(downloads, ensure_ascii=False, indent=2, default=json_default)[:20_000],
        "```",
        "",
        "## Failed or skipped datasets",
        "",
        markdown_table(["Dataset", "Stage", "Warnings"], failed_rows) if failed_rows else "No failed datasets.",
        "",
        "## Discovered web-page links",
        "",
        "The full machine-readable discovery output is saved in `data/metadata/discovered_links.json`.",
        "",
    ]
    for key, discovery in discovered_links.items():
        text.extend(
            [
                f"### {key}",
                "",
                f"- CSV links discovered: {len(discovery.get('csv_links', []))}",
                f"- JSON links discovered: {len(discovery.get('json_links', []))}",
                f"- metadata links discovered: {len(discovery.get('metadata_links', []))}",
                f"- PDF/methodology links discovered: {len(discovery.get('pdf_links', []))}",
                "",
            ]
        )
    (REPORTS_DIR / "data_inventory.md").write_text("\n".join(text), encoding="utf-8")


def summarize_profile_markdown(profile: dict[str, Any]) -> list[str]:
    """Render shared profile details as Markdown."""

    shape = profile.get("shape", {})
    categorical = profile.get("categorical_columns", {})
    numeric = profile.get("numeric_summaries", {})
    time_columns = profile.get("time_columns", {})
    missing_rows = [
        [column, profile.get("missing_value_counts", {}).get(column), profile.get("missing_value_percentages", {}).get(column)]
        for column in profile.get("columns", [])
    ]
    categorical_rows = [
        [
            column,
            info.get("unique_count"),
            info.get("looks_like_code"),
            info.get("looks_like_label_or_name"),
            info.get("contains_czech_diacritics"),
            ", ".join(str(value) for value in info.get("example_values", [])[:5]),
        ]
        for column, info in categorical.items()
    ]
    numeric_rows = [
        [
            column,
            round(info.get("min", 0), 3),
            round(info.get("max", 0), 3),
            round(info.get("mean", 0), 3),
            round(info.get("median", 0), 3),
            round(info.get("sum", 0), 3),
            info.get("zeros"),
            info.get("negative_values"),
        ]
        for column, info in numeric.items()
    ]
    lines = [
        f"- Source URL: {profile.get('source_url')}",
        f"- Local file: `{profile.get('local_file_path')}`",
        f"- Shape: {shape.get('rows')} rows x {shape.get('columns')} columns",
        f"- Encoding/separator: {profile.get('encoding_used')} / {profile.get('separator_used')}",
        f"- Duplicate row count: {profile.get('duplicate_row_count')}",
        f"- Memory usage bytes: {profile.get('memory_usage_bytes')}",
        "",
        "## Columns",
        "",
        ", ".join(f"`{column}`" for column in profile.get("columns", [])),
        "",
        "## Missing values",
        "",
        markdown_table(["Column", "Missing count", "Missing %"], missing_rows, max_rows=80),
        "",
        "## Categorical-looking columns",
        "",
        markdown_table(
            ["Column", "Unique", "Code-like", "Label-like", "Diacritics", "Examples"],
            categorical_rows,
            max_rows=80,
        )
        if categorical_rows
        else "No categorical-looking columns detected.",
        "",
        "## Numeric-looking columns",
        "",
        markdown_table(["Column", "Min", "Max", "Mean", "Median", "Sum", "Zeros", "Negative"], numeric_rows, max_rows=80)
        if numeric_rows
        else "No numeric-looking columns detected.",
        "",
        "## Time columns",
        "",
        "```json",
        json.dumps(time_columns, ensure_ascii=False, indent=2, default=json_default),
        "```",
        "",
        "## Warnings",
        "",
    ]
    warnings = profile.get("warnings", [])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["No profile warnings."])
    return lines


def write_profile_report(dataset_key: str, title: str, profile: dict[str, Any], analysis: dict[str, Any] | None = None) -> None:
    """Write a Markdown profile report for a dataset."""

    path_by_key = {
        "infectious_diseases": "data_profile_infectious_diseases.md",
        "age_groups": "data_profile_age_groups.md",
        "mkn10_cz": "data_profile_mkn10.md",
        "hospitalization": "data_profile_hospitalization.md",
    }
    lines = [
        f"# Data profile: {title}",
        "",
        f"Generated: {now_iso()}",
        "",
        "Public-health aggregated data should not be used for clinical treatment recommendations or causal claims.",
        "",
    ]
    lines.extend(summarize_profile_markdown(profile))
    if analysis:
        lines.extend(["", "## Dataset-specific analysis", "", "```json"])
        lines.append(json.dumps(analysis, ensure_ascii=False, indent=2, default=json_default))
        lines.extend(["```", ""])
    (REPORTS_DIR / path_by_key[dataset_key]).write_text("\n".join(lines), encoding="utf-8")


def first_available_candidate(analysis: dict[str, Any] | None, bucket: str) -> dict[str, Any] | None:
    """Return the first candidate from a named infectious-analysis bucket."""

    candidates = ((analysis or {}).get("interesting_disease_candidates") or {}).get(bucket, [])
    return candidates[0] if candidates else None


def write_research_opportunity_notes(
    profiles: dict[str, dict[str, Any]],
    failed: dict[str, Any],
    infectious_analysis: dict[str, Any] | None,
    age_analysis: dict[str, Any] | None,
    mkn_analysis: dict[str, Any] | None,
    hospitalization_analysis: dict[str, Any] | None,
    questions: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> None:
    """Write the research-opportunity report."""

    loaded_names = sorted(profiles.keys())
    top_scenario = scenarios[0] if scenarios else None
    high_total = first_available_candidate(infectious_analysis, "high_total_counts")
    seasonal = first_available_candidate(infectious_analysis, "clear_seasonality_by_month")
    regional = first_available_candidate(infectious_analysis, "regionally_concentrated_counts")
    age = first_available_candidate(infectious_analysis, "age_group_concentrated_counts")

    scenario_rows = [
        [
            scenario["id"],
            scenario["title"],
            scenario["demo_paper_fit_score_1_to_5"],
            "; ".join(scenario.get("risks", [])),
        ]
        for scenario in scenarios
    ]
    question_rows = [
        [
            question["id"],
            question["difficulty_level"],
            question["question"],
            question["possible_recall_issue"],
        ]
        for question in questions
    ]

    text = [
        "# Research opportunity notes",
        "",
        f"Generated: {now_iso()}",
        "",
        "This report is an exploratory profiling output. It does not claim that a KG, RAG system, SQL QA system, or final SEMANTiCS paper contribution has already been justified.",
        "",
        "Public-health aggregated data should not be used for clinical treatment recommendations or causal claims. Reported case counts are treated here only as reported table measures unless official documentation is later reviewed and supports stronger terminology.",
        "",
        "## 1. Executive summary",
        "",
        f"- Datasets loaded successfully: {', '.join(loaded_names) if loaded_names else 'none'}",
        f"- Datasets failed or skipped: {', '.join(sorted(failed.keys())) if failed else 'none'}",
        "- The infectious-disease table is the most suitable first-demo candidate because it has the richest analytical dimensions and is the requested primary dataset.",
        f"- Current best first-demo direction: {top_scenario['title'] if top_scenario else 'undetermined until data loads'}",
        "- Evidence is still exploratory: retrieval quality, semantic expansion value, and user-facing usefulness must be tested empirically.",
        "",
        "## 2. Dataset understanding",
        "",
    ]
    if "infectious_diseases" in profiles:
        profile = profiles["infectious_diseases"]
        shape = profile.get("shape", {})
        grain = (infectious_analysis or {}).get("grain_analysis", {})
        key_columns = (infectious_analysis or {}).get("detected_key_columns", {})
        text.extend(
            [
                "### Main infectious-disease table",
                "",
                f"- Shape: {shape.get('rows')} rows x {shape.get('columns')} columns.",
                f"- Detected key columns: `{json.dumps(key_columns, ensure_ascii=False)}`.",
                f"- Apparent grain tested with requested columns: appears unique = `{grain.get('appears_unique')}`; duplicate rows on candidate grain = `{grain.get('duplicate_rows_on_candidate_grain')}`.",
                "- Main measure appears to be the reported case-count column detected in profiling. The script avoids interpreting it as prevalence, incidence, or unique-patient count.",
                "- Main limitations: metadata/methodology needs human review; zero versus missing combinations may not always be distinguishable; disease-group semantics need validated code-list support.",
                "",
            ]
        )
    else:
        text.extend(["The infectious-disease table did not load, so dataset understanding is incomplete.", ""])

    text.extend(
        [
            "### Supporting code lists",
            "",
            f"- Age-group code-list assessment: {json.dumps((age_analysis or {}).get('usefulness_assessment', []), ensure_ascii=False)}",
            f"- MKN-10-CZ possible hierarchy columns: {', '.join((mkn_analysis or {}).get('possible_hierarchy_columns', [])) or 'none detected'}",
            f"- Hospitalization extension: {(hospitalization_analysis or {}).get('future_extension_assessment', 'not assessed')}",
            "",
            "## 3. Promising demo/research directions",
            "",
            markdown_table(["ID", "Title", "Fit", "Risks"], scenario_rows),
            "",
        ]
    )
    for scenario in scenarios:
        text.extend(
            [
                f"### {scenario['id']}: {scenario['title']}",
                "",
                scenario["short_description"],
                "",
                f"- Data columns involved: {', '.join(str(column) for column in scenario.get('columns_used', []) if column)}",
                f"- Example user question: {scenario.get('example_questions', [''])[0]}",
                f"- Why interesting: {scenario.get('expected_benefit_to_test')}",
                f"- Simple table/SQL enough? Baseline is: {scenario.get('baseline_version')}",
                f"- Semantic technologies may help: {scenario.get('possible_semantic_version')}",
                f"- KG might help: {scenario.get('possible_kg_version')}",
                f"- RAG might help: {scenario.get('possible_rag_version')}",
                f"- Recall may be a problem: {'recall' in scenario.get('expected_benefit_to_test', '').lower() or 'retrieval' in scenario.get('title', '').lower()}",
                f"- Must be tested empirically: {scenario.get('expected_benefit_to_test')}",
                f"- Risk level: {'medium' if scenario.get('demo_paper_fit_score_1_to_5', 0) >= 4 else 'high'}",
                f"- Suitability for a 5-page SEMANTiCS demo paper: {scenario.get('demo_paper_fit_score_1_to_5')}/5",
                "",
            ]
        )

    text.extend(
        [
            "## 4. Possible semantic/KG/RAG opportunities",
            "",
            "- Czech disease-name/value linking via `diagnoza` and `diagnoza_nazev`.",
            "- Code/label mapping for diagnosis and age-group categories.",
            "- MKN-10 hierarchy or chapter/block expansion, only if code coverage and hierarchy columns are validated.",
            "- Czech morphology, diacritics, aliases, abbreviations, and partial-label normalization.",
            "- Analytical-scope construction before SQL for complex disease/year/region/age/measure questions.",
            "- Related-dimension recommendations based on observed coverage, seasonality, region concentration, and age concentration.",
            "- Relation/path explanation across disease, region, age group, year, month, sex, and reported case counts.",
            "- Detecting incomplete analytical scope and sparse/missing combinations before answering.",
            "- Evidence-aware summarization using metadata and methodology documents discovered from NZIP pages.",
            "- Improving recall of relevant categorical values or dimensions for group-level disease and informal age/region queries.",
            "",
            "## 5. Cases where semantic/KG methods may not help much",
            "",
            "- Simple top-N by disease or year when all values are exact.",
            "- Simple regional totals with official region names already supplied.",
            "- A yearly trend for one exact diagnosis code.",
            "- Exact filtering by `rok`, `mesic`, `kraj_kod`, `vek_kod`, or `pohlavi`.",
            "- Basic counting where all values and aggregation dimensions are explicitly specified.",
            "",
            "## 6. Candidate first-demo recommendation",
            "",
            "Recommended first demo: recall-aware Czech disease value retrieval with one-table-first analysis and supporting code lists used only for labels, normalization, and validated hierarchy.",
            "",
            f"- Chosen main dataset: infectious_diseases.",
            f"- Candidate disease examples from high totals: {json.dumps(high_total, ensure_ascii=False, default=json_default) if high_total else 'not available'}",
            f"- Candidate seasonal example: {json.dumps(seasonal, ensure_ascii=False, default=json_default) if seasonal else 'not available'}",
            f"- Candidate regional-contrast example: {json.dumps(regional, ensure_ascii=False, default=json_default) if regional else 'not available'}",
            f"- Candidate age-profile example: {json.dumps(age, ensure_ascii=False, default=json_default) if age else 'not available'}",
            "- Chosen dimensions: diagnosis code/label first, then year, region, month, age group, and sex as needed.",
            "- Example questions: group-level disease retrieval, regional comparison for selected disease families, and age/seasonal scope exploration.",
            "- Minimal baseline: exact/lexical retrieval of table values plus pandas or SQL aggregation.",
            "- Possible semantic/KG/RAG-enhanced version: type-specific value retrieval, code-label mapping, MKN hierarchy expansion after validation, and metadata-aware caveat summaries.",
            "- Evidence showing improvement: higher recall@k for diagnosis codes or official categorical values, better dimension recall in multi-aspect scopes, and clearer coverage-gap explanations.",
            "- Avoid in the demo paper: clinical recommendations, causal claims, prevalence/incidence language without documentation, and a broad multi-table system before the one-table case is reliable.",
            "- Keep the demo one-table-first. Use supporting code lists only for labels, hierarchy, and normalization until cross-table semantics are validated.",
            "",
            "## 7. Next-step implementation plan",
            "",
            "- Future: `scripts/build_value_indexes.py` for typed value indexes.",
            "- Future: `scripts/create_baseline_sql_queries.py` for exact table baselines.",
            "- Future: `scripts/prototype_scope_detection.py` for typed analytical-scope construction.",
            "- Future: `scripts/evaluate_retrieval_recall.py` for recall@k experiments.",
            "- Future: `scripts/build_table_derived_kg.py` for a validated table-derived graph.",
            "- Future: `scripts/prototype_demo_ui.py` for an interactive demo after the claim is narrowed.",
            "",
            "## Candidate questions",
            "",
            markdown_table(["ID", "Difficulty", "Question", "Recall issue"], question_rows),
            "",
        ]
    )
    (REPORTS_DIR / "research_opportunity_notes.md").write_text("\n".join(text), encoding="utf-8")


def build_dataset_summary(
    downloads: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    failed: dict[str, Any],
    scenarios: list[dict[str, Any]],
    all_warnings: list[str],
) -> dict[str, Any]:
    """Build the machine-readable dataset summary."""

    year_ranges = {}
    unique_value_counts = {}
    for key, profile in profiles.items():
        year_ranges[key] = {
            column: {"min": info.get("min"), "max": info.get("max")}
            for column, info in profile.get("time_columns", {}).items()
            if info.get("kind") == "year"
        }
        unique_value_counts[key] = profile.get("unique_value_counts_for_categorical_columns", {})
    return {
        "generated_at": now_iso(),
        "downloaded_files": downloads,
        "loaded_datasets": sorted(profiles.keys()),
        "failed_datasets": failed,
        "shapes": {key: profile.get("shape") for key, profile in profiles.items()},
        "columns": {key: profile.get("columns") for key, profile in profiles.items()},
        "year_ranges": year_ranges,
        "unique_value_counts": unique_value_counts,
        "recommended_first_demo_dataset": "infectious_diseases" if "infectious_diseases" in profiles else None,
        "top_candidate_demo_scenarios": scenarios[:3],
        "warnings": all_warnings,
        "next_steps": [
            "Review official metadata/methodology before using epidemiological terminology.",
            "Create typed value indexes and independent reference sets for recall measurement.",
            "Evaluate exact lexical/vector baselines before adding KG or semantic expansion.",
            "Keep the first demo one-table-first unless supporting code-list coverage is clearly useful.",
        ],
    }


def write_json_outputs(
    downloads: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    failed: dict[str, Any],
    questions: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    """Write required machine-readable outputs."""

    write_json(OUTPUTS_DIR / "candidate_research_questions.json", questions)
    write_json(OUTPUTS_DIR / "candidate_demo_scenarios.json", scenarios)
    write_json(OUTPUTS_DIR / "dataset_summary.json", build_dataset_summary(downloads, profiles, failed, scenarios, warnings))


def discover_supporting_metadata(spec: DatasetSpec, discovered_links: dict[str, Any]) -> str | None:
    """Discover metadata URL for code-list datasets with no direct metadata URL."""

    if spec.metadata_url:
        return spec.metadata_url
    try:
        discovery = discover_links_from_page(spec.page_url)
    except Exception as exc:
        discovered_links[spec.key] = {"page_url": spec.page_url, "warnings": [f"Discovery failed: {exc}"]}
        return None
    discovered_links[spec.key] = discovery
    return choose_link(discovery.get("metadata_links", []) or discovery.get("json_links", []), prefer_metadata=True)


def resolve_dataset_spec(spec: DatasetSpec, discovered_links: dict[str, Any]) -> DatasetSpec:
    """Resolve discovered URLs for optional or page-discovered datasets."""

    if not spec.discover_from_page:
        return spec
    discovery = discover_links_from_page(spec.page_url)
    discovered_links[spec.key] = discovery
    csv_url = choose_link(discovery.get("csv_links", []), prefer_csv=True)
    metadata_url = choose_link(discovery.get("metadata_links", []) or discovery.get("json_links", []), prefer_metadata=True)
    return DatasetSpec(
        key=spec.key,
        title=spec.title,
        page_url=spec.page_url,
        csv_url=csv_url,
        metadata_url=metadata_url,
        raw_filename=spec.raw_filename,
        metadata_filename=spec.metadata_filename,
        profile_filename=spec.profile_filename,
        sample_filename=spec.sample_filename,
        optional=spec.optional,
        discover_from_page=spec.discover_from_page,
    )


def load_and_profile_dataset(
    spec: DatasetSpec,
    *,
    force: bool,
    sample_only: bool,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Download, load, and profile one dataset."""

    if spec.csv_url is None:
        raise RuntimeError(f"No CSV URL available for {spec.key}.")
    raw_path = RAW_DIR / spec.raw_filename
    metadata_path = METADATA_DIR / spec.metadata_filename
    profile_path = PROCESSED_DIR / spec.profile_filename

    log(f"Downloading/checking {spec.key} CSV")
    download_record = {"csv": download_file(spec.csv_url, raw_path, force=force)}
    decompressed = ensure_plain_csv(raw_path)
    decompression_warnings: list[str] = []
    if decompressed:
        download_record["csv"]["decompressed_gzip_to_csv"] = True
        download_record["csv"]["bytes_after_decompression"] = raw_path.stat().st_size
        download_record["csv"]["sha256_after_decompression"] = file_sha256(raw_path)
        decompression_warnings.append("Downloaded source was gzip-compressed; decompressed it into the requested .csv file.")
    if spec.metadata_url:
        try:
            log(f"Downloading/checking {spec.key} metadata")
            download_record["metadata"] = download_file(spec.metadata_url, metadata_path, force=force)
        except Exception as exc:
            download_record["metadata"] = {
                "url": spec.metadata_url,
                "local_path": str(metadata_path.relative_to(ROOT)),
                "status": "failed",
                "warnings": [str(exc)],
            }

    nrows = SAMPLE_ROWS if sample_only else None
    log(f"Loading {spec.key} CSV")
    df, encoding, separator, read_warnings = read_csv_robust(raw_path, nrows=nrows)
    read_warnings.extend(decompression_warnings)
    if sample_only:
        read_warnings.append(f"--sample-only used; profile is based on the first {SAMPLE_ROWS} rows.")
    profile = profile_dataframe(
        df,
        dataset_key=spec.key,
        source_url=spec.csv_url,
        local_path=raw_path,
        encoding=encoding,
        separator=separator,
        warnings=read_warnings,
    )
    write_json(profile_path, profile)
    return df, profile, download_record


def main() -> int:
    """Run the data-acquisition and profiling pipeline."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Redownload existing files.")
    parser.add_argument("--skip-optional", action="store_true", help="Skip optional hospitalization discovery/profiling.")
    parser.add_argument("--sample-only", action="store_true", help="Profile only an initial sample after downloading.")
    args = parser.parse_args()

    ensure_directories()
    log("Starting NZIP data acquisition and profiling")
    if sys.version_info < (3, 11):
        log("Warning: Python 3.11 or newer is recommended.")

    downloads: dict[str, Any] = {}
    loaded: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    failed: dict[str, Any] = {}
    discovered_links: dict[str, Any] = read_json_if_exists(METADATA_DIR / "discovered_links.json") or {}
    warnings: list[str] = []

    if pd is None:
        warnings.append("pandas is not installed; the script used a limited stdlib fallback where possible.")

    specs = [DATASETS["infectious_diseases"], DATASETS["age_groups"], DATASETS["mkn10_cz"]]
    if not args.skip_optional:
        specs.append(DATASETS["hospitalization"])

    for original_spec in specs:
        spec = original_spec
        try:
            if spec.discover_from_page:
                spec = resolve_dataset_spec(spec, discovered_links)
                if spec.csv_url is None:
                    raise RuntimeError("Automatic discovery did not find a CSV link on the NZIP page.")
            elif spec.key == "mkn10_cz":
                metadata_url = discover_supporting_metadata(spec, discovered_links)
                if metadata_url:
                    spec = DatasetSpec(**{**spec.__dict__, "metadata_url": metadata_url})

            df, profile, download_record = load_and_profile_dataset(spec, force=args.force, sample_only=args.sample_only)
            downloads[spec.key] = download_record
            loaded[spec.key] = {"df": df, "profile": profile, "spec": spec}
            profiles[spec.key] = profile
            log(f"Profiled {spec.key}: {profile['shape']['rows']} rows x {profile['shape']['columns']} columns")
        except Exception as exc:
            message = str(exc)
            if spec.optional:
                log(f"Optional dataset {spec.key} failed/skipped: {message}")
            else:
                log(f"Dataset {spec.key} failed: {message}")
            failed[spec.key] = {
                "stage": "download/load/profile",
                "optional": spec.optional,
                "warnings": [message],
                "page_url": spec.page_url,
                "csv_url": spec.csv_url,
            }
            warnings.append(f"{spec.key}: {message}")

    write_json(METADATA_DIR / "discovered_links.json", discovered_links)

    infectious_analysis = None
    age_analysis = None
    mkn_analysis = None
    hospitalization_analysis = None

    if "infectious_diseases" in loaded:
        log("Running infectious-disease specific analyses")
        infectious_analysis = analyze_infectious_disease_dataset(
            loaded["infectious_diseases"]["df"],
            loaded["infectious_diseases"]["profile"],
        )
        profiles["infectious_diseases"]["dataset_specific_analysis"] = infectious_analysis
        write_json(PROCESSED_DIR / DATASETS["infectious_diseases"].profile_filename, profiles["infectious_diseases"])

    if "age_groups" in loaded:
        log("Running age-group code-list analyses")
        age_analysis = analyze_age_group_codelist(
            loaded["age_groups"]["df"],
            loaded["age_groups"]["profile"],
            loaded.get("infectious_diseases", {}).get("df"),
            infectious_analysis,
        )
        profiles["age_groups"]["dataset_specific_analysis"] = age_analysis
        write_json(PROCESSED_DIR / DATASETS["age_groups"].profile_filename, profiles["age_groups"])

    if "mkn10_cz" in loaded:
        log("Running MKN-10-CZ code-list analyses")
        mkn_analysis = analyze_mkn10_codelist(
            loaded["mkn10_cz"]["df"],
            loaded["mkn10_cz"]["profile"],
            loaded.get("infectious_diseases", {}).get("df"),
            infectious_analysis,
        )
        profiles["mkn10_cz"]["dataset_specific_analysis"] = mkn_analysis
        write_json(PROCESSED_DIR / DATASETS["mkn10_cz"].profile_filename, profiles["mkn10_cz"])

    if "hospitalization" in loaded:
        log("Running optional hospitalization analyses")
        hospitalization_analysis = analyze_optional_hospitalization_dataset(
            loaded["hospitalization"]["df"],
            loaded["hospitalization"]["profile"],
            loaded.get("infectious_diseases", {}).get("profile"),
        )
        profiles["hospitalization"]["dataset_specific_analysis"] = hospitalization_analysis
        write_json(PROCESSED_DIR / DATASETS["hospitalization"].profile_filename, profiles["hospitalization"])
    elif not args.skip_optional:
        hospitalization_analysis = analyze_optional_hospitalization_dataset(None, None, profiles.get("infectious_diseases"))

    log("Creating sample files")
    sample_records = create_sample_files(loaded)
    downloads["samples"] = sample_records

    log("Generating candidate questions and scenarios")
    questions = generate_candidate_questions(infectious_analysis)
    scenarios = generate_candidate_demo_scenarios(infectious_analysis, age_analysis, mkn_analysis)

    log("Writing Markdown reports")
    write_data_inventory(downloads, profiles, failed, discovered_links)
    for key, info in loaded.items():
        analysis = {
            "infectious_diseases": infectious_analysis,
            "age_groups": age_analysis,
            "mkn10_cz": mkn_analysis,
            "hospitalization": hospitalization_analysis,
        }.get(key)
        write_profile_report(key, info["spec"].title, profiles[key], analysis)
    if "hospitalization" not in loaded:
        placeholder = [
            "# Data profile: Hospitalization cases in acute and intensive care",
            "",
            f"Generated: {now_iso()}",
            "",
            "The optional hospitalization dataset was not loaded.",
            "",
            "Automatic discovery from the NZIP page either failed, was skipped, or did not find a usable CSV link.",
            "",
            "This is not a blocker for the one-table-first infectious-disease profiling stage.",
            "",
            "Hospitalization indicators must not be interpreted as treatment-effectiveness evidence without a proper study design.",
            "",
            "```json",
            json.dumps(failed.get("hospitalization", {}), ensure_ascii=False, indent=2),
            "```",
        ]
        (REPORTS_DIR / "data_profile_hospitalization.md").write_text("\n".join(placeholder), encoding="utf-8")
    write_research_opportunity_notes(
        profiles,
        failed,
        infectious_analysis,
        age_analysis,
        mkn_analysis,
        hospitalization_analysis,
        questions,
        scenarios,
    )

    log("Writing JSON outputs")
    write_json_outputs(downloads, profiles, failed, questions, scenarios, warnings)

    if failed:
        log(f"Completed with {len(failed)} failed/skipped dataset(s): {', '.join(failed)}")
    else:
        log("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
