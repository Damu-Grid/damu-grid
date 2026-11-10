# forecasting/

Demand estimator, mandatory 28-day average baseline, optional candidate model, uncertainty labels, and the frozen evaluation harness.

**Owner:** Blessings (`bleymambwe`).

**Status:** empty on purpose. All application code is written in the official window. Do not import pre-window pitch notebooks or unpublished metrics as if they were already this project's results.

Methodology is fixed in `docs/EVALUATION.md`:

- Demand = `requests.units_requested` (not `units_issued`, not `daily_stock`)
- Time split: learn 1 Nov 2025–30 Apr 2026; calibrate May–Jun; evaluate weekly origins 1 Jul–21 Oct 2026
- If the candidate loses, say so and use the baseline operationally

This package is a **read-only** input to the live API. It must not write reservations.
