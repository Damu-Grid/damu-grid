# Evaluation methodology

This is the mandatory AI/data comparison for the submission. It follows the 10 November 2026 team evaluation (adopted recommendation) and the official brief's example of a forecast against last month's average. **Numbers are computed in the window. Pitch figures are not results.**

The product remains redistribution: the forecast informs recipient gaps and sender reserves. Transfer "savings" are a separate, assumption-based exhibit.

## Honesty rules

- Label every result **synthetic**. Do not present it as evidence about real Kenyan facilities or as clinical, financial, or lives-saved impact.
- Report the candidate even if it loses. If it loses, use the simpler baseline operationally and say so in the demo.
- Freeze the candidate specification **before** reading evaluation outcomes. No new hyperparameter search after seeing July–October scores.
- Use only `requests` strictly before each origin. No future receipts, later temperature events, or final unit locations in historical features.
- Do not reuse unverified pitch claims (11.3% RMSE improvement, 22.3% unmet, 20.3% expiry, AUC figures, "50% general improvement") as if reproduced.

## Data slice

- Source: official `requests.csv` joined to `facilities.csv` on `facility_id`.
- Quantity: `units_requested`, not `units_issued`.
- Tier 1 product: `component_requested = RBC`.
- Groups: known exact blood groups only. Report how many rows were excluded for `unknown` or missing groups.
- Facilities: hospital facilities (`facility_id` prefix `HSP-` / `facility_type` in the hospital classes). Confirm the hospital filter against actual `facility_type` values before coding.
- `daily_stock` is inventory, not demand.

Disclose the number of hospital × group × origin observations and any completeness assumption. A missing request is zero demand only if we explicitly assume complete reporting for that site and day.

## Time split

- **Learn** the pooled estimator from 1 November 2025–30 April 2026.
- **Calibrate** (for residual / upper-bound coverage, if implemented) on May–June 2026.
- **Evaluate** seven-day forecasts at weekly origins starting 1 July 2026, then every seven days through 21 October 2026, so all outcomes lie within 31 October 2026.

## Mandatory baseline (28-day average)

For each hospital and known group:

`seven-day predicted requested units = 7 × (requested RBC units in the preceding 28 calendar days ÷ 28)`

This is the submission's required simple baseline.

## Candidate estimator

Seven-day hospital total RBC demand from an expanding historical daily mean, allocated using network-wide known-group request proportions computed from the same earlier history. This is a statistical data feature. No LLM is required.

If this candidate does not beat the baseline on the frozen split, keep the baseline in the live queue and still show both numbers.

## Metrics

Primary: **RMSE** across hospital × known group × seven-day origin, in requested units.

Also report MAE, sample count, and (if the bound is implemented) upper-bound coverage at the nominal level (the evaluation specified a non-negative upper prediction bound from May–June residuals; coverage is measured, not asserted). Include a separate O-negative error check if observations exist.

Show the table in the README, the demo, and `/evaluation/forecast`.

## Live queue versus backtest

Build the live review queue from a **verified end-of-dataset snapshot** (planned: 31 October 2026), not a July state reconstructed from final unit locations. Expiry is a recorded `expiry_date`, not something to forecast.

Any "expected reduction in unused units before expiry" shown on a card is an assumption-based estimate. Do not call it measured blood saved.

## Optional stronger comparison (Tier 2, but planned)

If the harness is ready, compare nearest eligible recipient first versus expiry-aware ranking over the same documented seven-day synthetic scenarios, seeded from official closing inventory and earlier request rates. Hold safety rules, initial stock, arrivals, demand, reserves, transport constraints and acceptance assumptions constant. Report unmet units, expired units, moved units and route batches separately.

Added scenario demand is synthetic, not observed November demand. This must not displace the mandatory forecast benchmark.

## Reproducibility

Blessings owns the harness. Required artefacts (all generated in-window):

- A command that rebuilds the forecast table from `data/raw/`.
- Frozen config (split dates, filters, formula).
- Seeds for any simulator.
- Written output under `data/processed/` (gitignored) plus a short summary pasted into the README.
- A notebook is optional; promotion of tested functions into `forecasting/` is required for the demo path.
