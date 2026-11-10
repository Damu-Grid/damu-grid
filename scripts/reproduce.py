"""One command that reproduces every reported number (forecast + simulation).

Usage (from the repo root, Python 3.11+, after `uv sync` on your machine)::

    uv run python scripts/reproduce.py

It rebuilds the frozen forecast evaluation and the 30-seed transfer-policy
simulation from ``data/raw/`` only, writes all artefacts to ``data/processed/``
(gitignored), and prints their paths. Every figure is synthetic. The 90%
demand upper bound under-covers overall (88.8% measured); that is stated in
the outputs, not hidden.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for module in ("forecasting.evaluate", "simulation.compare"):
        proc = subprocess.run(
            [sys.executable, "-m", module],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit(f"{module} failed with exit code {proc.returncode}")
    print("artefacts in data/processed/: forecast_table.csv, forecast_metrics.json,")
    print("forecast_summary.md, sim_compare.json, sim_summary.md")


if __name__ == "__main__":
    main()
