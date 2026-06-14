#!/usr/bin/env python3
"""Run a SQL file or inline SQL against the local DuckDB database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = ROOT / ".python_packages"
if PROJECT_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_PACKAGES))

import duckdb  # type: ignore  # noqa: E402


DEFAULT_DB_PATH = ROOT / "sql_database" / "db" / "semantics.duckdb"


def read_sql(args: argparse.Namespace) -> str:
    if args.sql:
        return args.sql
    if args.sql_file:
        return args.sql_file.read_text(encoding="utf-8")
    raise ValueError("Provide either a SQL file path or --sql.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SQL against sql_database/db/semantics.duckdb.")
    parser.add_argument("sql_file", type=Path, nargs="?", help="Path to a .sql file.")
    parser.add_argument("--sql", help="Inline SQL string.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--format", choices=["table", "csv", "json"], default="table")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--read-write", action="store_true", help="Open DB read-write instead of read-only.")
    args = parser.parse_args()

    sql = read_sql(args)
    if not args.db.exists():
        raise FileNotFoundError(f"Database not found: {args.db}. Run create_duckdb_database.py first.")

    con = duckdb.connect(str(args.db), read_only=not args.read_write)
    result = con.execute(sql)
    if result.description is None:
        print("OK")
        return 0
    df = result.fetchdf()
    con.close()

    if args.max_rows >= 0:
        df = df.head(args.max_rows)

    if args.format == "csv":
        print(df.to_csv(index=False), end="")
    elif args.format == "json":
        print(json.dumps(json.loads(df.to_json(orient="records", force_ascii=False)), ensure_ascii=False, indent=2))
    else:
        if df.empty:
            print("(no rows)")
        else:
            print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
