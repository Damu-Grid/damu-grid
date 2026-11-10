# pipeline/

ETL, validation against `data/raw/DATA_DICTIONARY.md`, SQLite schema, closing-date snapshot, eligibility engine, and Tier 2 cold-chain flags. All data is synthetic.

**Owner:** Brayan (`Sorghobrayan-dotcom`).

## Commands

From the repository root (Python 3.11+, `pandas`, `numpy`; dev: `pytest`, `ruff`):

```bash
uv sync                          # or: pip install pandas numpy pytest ruff
uv run python -m pipeline validate   # DG-01: check every official CSV, report row counts
uv run python -m pipeline build      # DG-02: validate, then build data/processed/damu_grid.sqlite
uv run pytest tests/pipeline         # pipeline tests (the `dataset` ones read the full CSVs)
```

Outputs go to `data/processed/` (gitignored): `validation_report.json`, `damu_grid.sqlite`. Nothing under `data/raw/` is ever written.

## Validation (DG-01)

`pipeline/load.py` reads each CSV with the types in `pipeline/schema.py` and fails loudly on: missing or unexpected columns, values that do not parse as their declared type, empty or duplicate keys, categorical values outside the data dictionary, and any facility id not present in `facilities.csv`. Row counts are compared with `docs/DATA.md`; on 10 November 2026 all 11 tables matched.

## Shared database schema (DG-02)

One file, `data/processed/damu_grid.sqlite`, created by `pipeline/store.py:create_schema`. The API and the evaluator read the same file.

- **Official tables** keep their official names and columns: `facilities`, `routes`, `donors`, `drives`, `donations`, `units`, `transfers`, `requests`, `daily_stock`, `power_outages`, `temperature_logs`. Dates are `YYYY-MM-DD`, official timestamps `YYYY-MM-DD HH:MM:SS` in EAT, booleans `0/1`, missing cells `NULL`.
- **Added tables** are all prefixed `dg_`:

| Table | Purpose |
|---|---|
| `dg_snapshot_meta` | As-of time, product scope, unit count, reconciliation with `daily_stock` |
| `dg_snapshot_units` | Units on the shelf at the as-of time, with receipt evidence |
| `dg_cold_chain_flags` | Site and unit evidence: fridge excursion, outage without backup, cool-box excursion, logger gap, sensor glitch, unconfirmed receipt |
| `dg_moves` | Human decisions and physical steps only (state machine in `docs/ARCHITECTURE.md`), with `version` for optimistic locking and `reserved_until` for the lease |
| `dg_audit_events` | Append-only trail (UPDATE and DELETE refused by triggers), hash-chained, `event_id` as idempotency key |

Safety constraints enforced by the database itself:

- a unit can be in at most one active move (`Reserved`, `Dispatched`, `InTransit`, `ReceivedHeld`): a second accept fails;
- a move cannot go from a site to itself, and only the documented states are accepted;
- audit rows cannot be edited or deleted.

No model score is stored in `dg_moves`: recommendations stay out of the movement tables.

## Settings (ADR-006)

`pipeline/config.py` holds one `PipelineConfig` object, loaded from `pipeline/settings/kenya_default.toml`. Shelf lives, which components are in the queue, the remaining life required on arrival, the arrival allowance, the sender reserve, the cold-chain thresholds and which evidence blocks a suggestion are all settings, not code. They are team defaults chosen in-window, not regulations. Another country is another TOML file.

## Rules

- Join facilities on `facility_id` only.
- Demand is not computed here beyond exposing `requests` cleanly; Blessings owns demand maths in `forecasting/`.
- Eligibility is conservative when safety evidence is missing. Sensor glitches (−99.0, 99.9, 0.0) are not clinical events.
