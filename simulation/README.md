# simulation/

Seven-day synthetic redistribution comparison: nearest-site-first vs expiry-aware
ranking, run with `uv run python -m simulation.compare` (or the one-command
`uv run python scripts/reproduce.py`, ~20 minutes). Both policies face the same
30 fixed-seed Poisson demand draws (seeds 4000–4029) plus one documented surge.

What changed in the DG-15 to DG-17 rebuild:

- Daily restocking: regional centres receive fresh RBC (+42-day life) and WB
  (+35-day life, medians measured from `data/raw/units.csv`) at October mean
  inflow rates, and push need-based top-ups to hospitals on their scheduled
  delivery days (`facilities.routine_deliveries_per_week`).
- Courier limit: at most 6 redistribution units per route per day.
- Imbalance overlay (synthetic, identical for both policies): donor HSP-001
  holds 34 closing WB units expiring on/before 8 Nov 2026; recipient HSP-004
  (0.48 h away) holds zero closing RBC/WB stock; +6 O+ and +6 A+ surge units on
  days 2–3. No units were added; the seeding is the pair plus the surge.
- Waste reported alongside unmet, split by product. WB matches ABO-identical
  requests only (exact group); RBC uses standard compatibility. Every unit keeps
  its `product_type`.
- `send_by` = expiry − travel days − 1-day buffer; late moves are ineligible.
- Train/test split mirrors the forecast rule: every rate, inflow, mix, and the
  snapshot uses data ≤ 31 Oct 2026 only; the test window (1–7 Nov) starts after
  all forecast evaluation origins. Results are mean ± SD over seeds.
- Used-before-expiry survival scores (same field names as the API's
  `survival_score_if_stays`/`survival_score_if_moved`; the pipeline has no
  producer yet) with a Brier score and 5-bin reliability table pooled over
  unit-days. Outcomes are use-within-the-7-day-window — a lower bound on
  use-before-expiry — so high-predicted buckets over-shoot by construction.

Latest measured result (`data/processed/sim_compare.json`, `sim_summary.md`):

| Policy | Unmet | Expired RBC | Expired WB | Moved RBC | Moved WB | Batches | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| nearest | 68.1±8.4 | 0.7±0.6 | 14.1±2.0 | 389.3±25.0 | 285.7±25.2 | 265.9±17.0 | 0.214 |
| expiry_aware | 75.9±7.8 | 0.6±0.7 | 14.5±3.9 | 175.7±17.8 | 835.0±35.1 | 507.7±23.9 | 0.221 |

Honest reading: restocking (not policy) cut unmet from the old ~333-unit
no-restock scenario; the policy gap is small (nearest lower unmet by ~8 with
overlapping ranges) and waste is tied, while expiry-aware moves ~3× more WB in
~2× the route batches. We report this plainly and pitch the forecast plus the
human review workflow. The one-sided 90% demand upper bound under-covers
overall (88.8% measured). Synthetic demand, not observed November events.

**Owner:** Blessings (`bleymambwe`).

Hold safety rules, initial stock, arrivals, demand, reserves, transport
constraints and acceptance assumptions constant across policies. Report unmet
units, expired units, moved units and route batches separately. Never claim
lives or money saved.
