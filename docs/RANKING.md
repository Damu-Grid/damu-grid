# Survival score, transfer gain and dispatch day (DG-19)

All data is the official **synthetic** starter dataset. Every number below is printed by
`uv run python -m ranking.evaluate` (default settings) or by the validation run named next to it.
The score is a model estimate under stated assumptions, **not a clinical probability**. It
never decides anything: it ranks moves the pipeline eligibility already allowed, and every
suggestion still needs Accept / Change / Reject by the coordinator.

## What the module adds

`ranking/` is an **annotation layer**, not a second suggestion provider. The backend provider
(`backend/app/ranking.py`) builds the suggestions from the pipeline eligibility and leaves
`expected_use_*`, `survival_score_*` and `send_by` empty. `ranking.annotate.annotate_batch` fills
them. Nothing in `ranking/` imports the backend.

| Module | Content |
|---|---|
| `compound.py` | Compound Poisson law of the units requested over an interval (Panjer recursion) |
| `queue.py` | Exact use probability of every unit of an oldest-first queue; the rank rule as a lower bound |
| `simulate.py` | Seeded Monte Carlo oracle: one queue, and a two-site transfer |
| `demand.py` | Demand per (hospital, group) learned only from requests before the origin |
| `score.py` | Score of every unit of a stock table, `product_type` kept on each row |
| `calibration.py` | Brier, log-loss, AUC, calibration gap, reliability table, isotonic fit |
| `gain.py` | Gain of a transfer, its value by dispatch day, greedy batch plan |
| `timing.py` | Dispatch day: waiting cost against the cost of a trip |
| `annotate.py` | Fields of one backend suggestion, and the SQLite loader |
| `evaluate.py` | `python -m ranking.evaluate`: the validation and closing-stock tables below |

## Method

**Demand.** For a hospital `s` and blood group `g`, units per day `m(s,g)` is
`forecasting.candidate.candidate_forecast / 7` (the team's frozen estimator, not recomputed here).
Requests ask for 1 to 6 units with the empirical law of `units_requested` over red-cell requests
before the origin; the request rate is `m / E[K]`, shaped by a Monday-to-Sunday profile learned
before the origin (mean 1). Demand over an interval is compound Poisson.

**Score (exact oldest-first queue).** One queue per (hospital, blood group) holds every unit on
the shelf, eligible or not, sorted by expiry. A unit is usable up to and including its expiry day
(`days_left = expiry_date - origin + 1`). With `D_j` the demand between the expiries of units
`j - 1` and `j`, the leftover demand follows `X_0 = 0`, `A_j = X_{j-1} + D_j`,
`X_j = max(A_j - 1, 0)`, and unit `j` is used if `A_j >= 1`. The full law of `X` is carried, so
`p_j = 1 - P(X_{j-1} = 0) P(D_j = 0)` is exact when every request takes the unexpired unit
closest to its expiry. Issuing the oldest unit first is optimal for most criteria in Pierskalla
and Roach (1972, *Optimal Issuing Policies for Perishable Inventory*, Management Science 18(11),
603-614). The rank rule `P(D(L_j) >= j)` is a lower bound of this score; the tests check it.

**Red cells and whole blood (team decision).** `RankingConfig.pool_components = ("RBC", "WB")`:
one queue holds both products, the demand is the exact group's red-cell requests, and every row
keeps its `product_type` so results are reported per product. `("RBC",)` reproduces the
red-cell-only design measurements.

**Interval.** The request rate is taken as `Gamma(N + 0.5)` distributed (`N` past requests of the
pair). The score at its 10th and 90th percentiles gives `p_lo` and `p_hi`: uncertainty on the
demand rate only, not model error.

**Gain of a transfer.** For a batch `B` from `s` to `d`, the gain today with no transit is exact:
`G(0) = [EU_d(S_d + B) - EU_d(S_d)] + [EU_s(S_s - B) - EU_s(S_s)]`, `EU` being the sum of the
scores of a queue. The second bracket is negative: the batch no longer serves the sender, but its
other units move up. For a dispatch on day `tau` with an arrival lag
`a = ceil((travel hours + arrival allowance) / 24)`, each unit is worth
`pi_loc + (1 - pi_loc) p_dest`. `pi_loc` is its chance of being used at the sender before `tau`
(every sender expiry cut at `tau`), and `p_dest` its value in the destination queue aged to the
arrival day. Without `pi_loc`, waiting would look free. This approximation is checked against the
two-site Monte Carlo (`tests/ranking/test_gain_timing.py`: mean absolute difference below 0.03
unit on random cases).

**Dispatch day.** `net(tau) = G(tau) - trip cost`, with no cost on a weekday when a routine
vehicle runs on the route (`facilities.routine_deliveries_per_week`: 3 = Mon/Wed/Fri,
2 = Tue/Fri, 1 = Wed). Routine vehicles only go from a blood centre to the hospitals it supplies,
so a hospital-to-hospital move is a special trip. The earliest day within
`timing_tolerance_units` (0.03, the approximation's tested accuracy) of the best net gain is
chosen. Below `min_gain_units` (0.10) there is no suggestion. `send_by` never passes the latest
feasible day of `simulation/compare.py` (expiry - travel days - 1).

**Batches.** Starting from the moves the pipeline eligibility allowed, the greedy accepts the best
(unit, destination), updates both queues, re-scores what they touch, and stops at
`min_gain_units` per unit, the sender reserve (counted on eligible units, as in `check_move`) or
the cooler capacity. Units are then grouped per route, so the trip cost is paid once per batch.

## Reproduce

```bash
uv sync
uv run python -m ranking.evaluate                                     # default: RBC + WB, weekday profile
uv run python -m ranking.evaluate --pool-components RBC --flat-weekdays --output-dir <dir>   # design check
uv run pytest tests/ranking
```

The command writes `data/processed/ranking_evaluation.json` and `.md`. It reads only the
official CSVs and is deterministic (the Monte Carlo check uses the fixed `RankingConfig.seed`).
The split is the team's: calibration
origins weekly from 1 May to 26 June 2026 (9), test origins weekly from 1 July to 21 October 2026
(17). Units are scored only when their outcome is final (expiry on or before 31 October 2026), so
each row is a (unit, origin) pair. Shelves are rebuilt from each unit's own arrival day; a unit
that never moved has no recorded arrival and is left out.

## Results

### Design check: red cells only, flat weekdays (`--pool-components RBC --flat-weekdays`)

This reproduces the design measurements exactly: 8,865 test and 5,296 calibration pairs,
observed use rate 0.931 (test) and 0.976 (calibration).

| Method (test window) | Brier | Log-loss | Calibration gap | AUC |
|---|---:|---:|---:|---:|
| Constant base rate | 0.0659 | 0.278 | 0.044 | 0.500 |
| Days left only | 0.0754 | 0.299 | 0.179 | 0.916 |
| Rank rule, compound Poisson | 0.0413 | 0.133 | 0.035 | 0.963 |
| **Exact oldest-first queue** | **0.0371** | **0.118** | **0.023** | **0.966** |

Closing stock: 504 red cells on hospital shelves, **17.1** expected to expire unused if nothing
moves.

### Default: red cells and whole blood in one queue

| Test window | Pairs | Observed use | Brier | Log-loss | Calibration gap | AUC | Mean score |
|---|---:|---:|---:|---:|---:|---:|---:|
| RBC, exact queue | 8,865 | 0.931 | 0.0393 | 0.127 | 0.031 | 0.962 | 0.900 |
| WB, exact queue | 6,070 | 0.365 | 0.4638 | 3.103 | 0.476 | 0.616 | 0.840 |
| Total, exact queue | 14,935 | 0.701 | 0.2118 | 1.336 | 0.177 | 0.701 | 0.876 |

**Whole blood is badly scored in the pooled queue.** The score announces 0.840 on average where
0.365 is observed, and "days left only" ranks whole blood better (AUC 0.766) than the exact queue.
Red cells are also slightly worse than in the red-cell-only queue (Brier 0.0393 against 0.0371).
The reason is in the data, not in the code. The command finds that 7 of the 32 hospitals
transfused more whole blood than red cells over the year; the others use red cells first and
let whole blood expire. A single oldest-first queue does not describe that. A per-hospital product preference would be the next step; it is
not built.

Reliability of the exact score, red cells, test window (default run): every band is used more
often than announced, so the score is conservative. The 0.4-0.5 band has the largest gap: 0.451
announced, 0.673 observed. The 0.9-1.0 band, which holds 6,965 of the 8,865 pairs, is close:
0.989 announced, 0.997 observed. Rh-negative units are under-scored (all products: 0.461
announced, 0.684 observed): exact-group demand ignores the other patients these units can serve.

An isotonic recalibration fitted on May-June is in the table of the command, but it is **not
applied**: the base rate moves between the windows (0.976 in calibration, 0.931 in test).

Closing stock (default run, scored from 1 November 2026):

| Product | Units on hospital shelves | Expected to expire unused | Score below 0.5 |
|---|---:|---:|---:|
| RBC | 504 | 21.6 | 10 |
| WB | 263 | 24.2 | 16 |
| Total | 767 | 45.7 | 26 |

### Transfer plan on the closing stock (model estimate, not observed)

Default run: 5,070 eligible hospital-to-hospital moves cover 339 red cells. The greedy plans 23
units in 19 batches, worth 3.55 expected extra units if all were sent today, before trip costs.
With a special-trip cost of 0.20 unit, **one batch** passes the 0.10 minimum: 4 O+ units from
HSP-025 to HSP-003, sent on 1 November. It is worth 0.65 expected extra units before the trip
cost and 0.45 after it. The Monte Carlo re-estimate is 0.66 (95% interval 0.64 to 0.68). The
other batches are single units whose gain does not cover a special trip.

Design check run (red cells only): 6,111 eligible moves, 10 units in 10 planned batches worth 1.43
expected units before trip costs, and **no batch suggested** after the trip cost.

So the measured opportunity is small and depends on `trip_cost_units`, a team setting that is not
in the data. The gain is computed by the model (no lateral transfer exists in the history),
and the total is a sum of per-batch checks, not one joint simulation.

## Limits

- **Exact group only**: the score is conservative, most of all for Rh-negative units.
- **Stationary demand**: no seasonality (holidays) beyond the weekday profile.
- **Oldest-first issuing is assumed**; the dataset serves each hospital's preferred product first,
  which breaks the pooled whole-blood score (see above).
- **No lateral transfer in the history**: the effect of moves is computed by the model, not
  observed. It is measured only indirectly by the team simulation (`simulation/compare.py`).
- **The cost of a trip is not in the data** (`trip_cost_units` = 0.2 is a team choice).
- The historical shelves leave out units that never moved (no recorded arrival).
- The waiting value for `tau > 0` and any transit lag is an approximation, checked against Monte
  Carlo on random cases.
- Never report "lives saved" or "units saved": report expected extra units used, under these
  assumptions.

## Connecting to the backend (not applied)

`backend/app/ranking.py` is the provider's file. The change below has to be made with its owner,
so it is described here and not committed. In `_load_context`, load the queues once. In
`_build_suggestion`, annotate the batch and copy the fields:

```python
from ranking.annotate import annotate_batch, load_annotation_inputs
from ranking.config import RankingConfig

# _load_context, once per request:
ranking_inputs = load_annotation_inputs(self.database_path, self.as_of, RankingConfig())

# _build_suggestion, after building `suggestion` (units: the batch rows):
note = annotate_batch(
    pd.DataFrame(units), destination, ranking_inputs.stock, ranking_inputs.demand,
    ranking_inputs.origin, route[0], ranking_inputs.routine_run_days(source, destination),
    RankingConfig(),
    arrival_allowance_hours=context["config"].arrival_allowance_hours,
    min_remaining_days=settings["remaining_life_min_days"]["RBC"],
)
update = note.as_suggestion_update(suggestion.warnings)
update["uncertainty"] = Uncertainty(**update["uncertainty"])
return suggestion.model_copy(update=update)
```

`send_by` is `None` with the warning `net_gain_below_minimum` when the net gain is below the
minimum; the provider then decides whether to drop or flag the card. `policy` is not touched.
