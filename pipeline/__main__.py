"""Command line.

    python -m pipeline validate   # DG-01: check the official CSVs, write a row-count report
    python -m pipeline build      # DG-02: validate, then build data/processed/damu_grid.sqlite
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.config import DEFAULT_CONFIG_PATH, load_config
from pipeline.load import RAW_DIR, SchemaError, load_all
from pipeline.snapshot import build_snapshot, write_snapshot
from pipeline.store import DB_PATH, connect, create_schema, write_official

PROCESSED_DIR = RAW_DIR.parent / "processed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    parser.add_argument("command", choices=["validate", "build"])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)

    try:
        tables, report = load_all(args.raw_dir)
    except SchemaError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("\n".join(report.lines()))
    print("all row counts match docs/DATA.md" if report.ok else "ROW COUNT DISCREPANCIES (see above)")
    out = PROCESSED_DIR / "validation_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"row_counts": report.row_counts,
                               "discrepancies": report.row_count_discrepancies}, indent=2))
    print(f"report written to {out}")
    if args.command == "validate":
        return 0 if report.ok else 2

    config = load_config(args.config)
    conn = connect(args.db)
    create_schema(conn)
    write_official(conn, tables)
    snap = build_snapshot(tables, config)
    write_snapshot(conn, snap, config)
    print("\n".join(snap.summary_lines()))
    print(f"database written to {args.db}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
