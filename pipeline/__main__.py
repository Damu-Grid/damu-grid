"""Command line: `python -m pipeline validate`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.load import RAW_DIR, SchemaError, load_all

PROCESSED_DIR = RAW_DIR.parent / "processed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args(argv)

    try:
        _, report = load_all(args.raw_dir)
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
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
