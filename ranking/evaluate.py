"""python -m ranking.evaluate: reproduce the validation table of the survival score.

Same split as docs/EVALUATION.md: calibration origins in May-June 2026, test origins weekly from
1 July to 21 October 2026, units scored only when their outcome is final (expiry on or before
31 October 2026). Results are reported separately for whole blood and red cells (product_type),
with a total row in addition, never instead. Compared with: constant base rate, days left only,
the rank rule used by simulation/compare.py, and the exact queue. Writes
data/processed/ranking_evaluation.json and .md. Step 4.
"""

from __future__ import annotations


def main() -> int:
    raise NotImplementedError("DG-19 step 4")


if __name__ == "__main__":
    raise SystemExit(main())
