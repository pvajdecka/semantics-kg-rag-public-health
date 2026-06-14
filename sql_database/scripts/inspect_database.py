#!/usr/bin/env python3
"""Inspect tables, row counts, and the final table schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = ROOT / ".python_packages"
if PROJECT_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_PACKAGES))

import duckdb  # type: ignore  # noqa: E402
import pandas as pd  # noqa: E402


DEFAULT_DB_PATH = ROOT / "sql_database" / "db" / "semantics.duckdb"
FINAL_TABLE = "fact_infectious_disease_cases_enriched"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the SEMANTiCS DuckDB database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    if not args.db.exists():
        raise FileNotFoundError(f"Database not found: {args.db}. Run create_duckdb_database.py first.")

    con = duckdb.connect(str(args.db), read_only=True)
    tables = con.execute(
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_type, table_name
        """
    ).fetchdf()
    rows = []
    for table_name, table_type in tables[["table_name", "table_type"]].itertuples(index=False):
        if table_type == "BASE TABLE":
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        else:
            count = None
        rows.append({"table_name": table_name, "table_type": table_type, "row_count": count})

    print("Tables and views")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nFinal table schema")
    print(con.execute(f"DESCRIBE {FINAL_TABLE}").fetchdf().to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
