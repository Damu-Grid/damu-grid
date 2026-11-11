# API specification (planned)

Implement during the window. This is the contract so frontend, backend and evaluation stay aligned. Field names below are proposed; do not invent official CSV columns — map to the real names in `docs/DATA.md`.

Base URL (dev): `http://localhost:8000`. JSON, EAT timestamps in ISO 8601 with explicit offset (`+03:00`).

## Auth (demo only)

Four demo roles: `coordinator`, `sender`, `receiver`, `safety`. Test logins will be listed in the README for judges. This is not a production IAM system.

## Suggestion object

```json
{
  "suggestion_id": "sug_...",
  "as_of": "2026-10-31T23:59:59+03:00",
  "data_age_hours": 0,
  "component": "RBC",
  "blood_group": "O+",
  "unit_ids": ["U2610-RBTC-...-RBC"],
  "from_facility_id": "RBTC-...",
  "to_facility_id": "HSP-...",
  "expiry_date": "2026-11-03",
  "typical_travel_hours": 1.4,
  "sender_reserve_units": 2,
  "sender_stock_after": 6,
  "recipient_gap_units": 3,
  "expected_use_if_moved": 0.0,
  "expected_use_if_stays": 0.0,
  "uncertainty": {
    "method": "pooled_residual_upper_bound",
    "nominal_level": 0.95,
    "label": "model estimate, not a clinical probability"
  },
  "reason_deterministic": "Plain-language reason built only from the fields above.",
  "reason_llm": null,
  "policy": "expiry_aware",
  "fallback": false,
  "eligibility_ok": true,
  "warnings": []
}
```

`expected_use_*` values are modelling assumptions (for example a Poisson expected-use calculation). Never call them clinical clearance. If not yet computed, use `null` and explain the ranking rule in `reason_deterministic`.

The pipeline-backed provider fills `expected_use_*`, `survival_score_*` and `send_by` with `ranking.annotate` (exact oldest-first queue under compound Poisson demand, `uncertainty.method = "fefo_compound_poisson"`; see `docs/RANKING.md`). When the score cannot be computed for a batch (for example a blood-centre sender, which has no demand model, or a database without unit history), all five fields stay `null` and the provider's own uncertainty and reason are kept. The score never adds, drops or reorders suggestions: eligibility alone decides what is listed. `send_by` is `null` with the warning `net_gain_below_minimum` when the expected gain does not cover a special trip.

## Endpoints (Tier 1)

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | any | Liveness |
| GET | `/snapshot` | any | As-of timestamp, table counts, product scope |
| GET | `/suggestions` | coordinator | Ranked queue; `policy=expiry_aware` or `policy=nearest` or `policy=fallback` |
| GET | `/suggestions/{id}` | coordinator | One card |
| POST | `/suggestions/{id}/accept` | coordinator | Atomic reservation |
| POST | `/suggestions/{id}/change` | coordinator | Cancel reservation if any, eligibility rerun, new suggestion |
| POST | `/suggestions/{id}/reject` | coordinator | Record reason, no reservation |
| POST | `/moves/{id}/dispatch` | sender | Recheck unit, safety, lease, ETA |
| POST | `/moves/{id}/receive` | receiver | Confirm arrival; optional cold-chain note |
| GET | `/moves/{id}` | any scoped | State and audit for one move |
| GET | `/audit` | any scoped | Filter by unit, actor, time |
| GET | `/evaluation/forecast` | any | Frozen baseline vs candidate table |
| POST | `/evaluation/forecast/run` | operator | Recompute if needed (should be rare after freeze) |

Action bodies include `actor_id`, `role`, `reason`, and a `unit_version` or reservation token. Server time is taken from the server, not the client.

The default local suggestion provider reads the pipeline-built `dg_snapshot_units` and `dg_cold_chain_flags` tables and reuses `pipeline.eligibility.unit_eligibility` and `check_move`. It estimates a seven-day recipient gap from known-group RBC requests in the preceding 28 days. A missing or mismatched pipeline snapshot returns `503`; it does not fall back to final-location `units` rows or fixture cards. Suggestions remain synthetic coordinator-review candidates, not transfusion decisions.

Error model: `409` for stale version or conflicting reservation; `403` for wrong role; `422` for eligibility failure; `503` when the estimator is down and the client should switch to `/suggestions?policy=fallback` (the API may also auto-offer fallback suggestions with `fallback: true`).

## Endpoints (Tier 2)

| Method | Path | Purpose |
|---|---|---|
| GET | `/map/stock` | Sites, stock, expiry risk, connectivity — for MapLibre |
| GET | `/flags/cold-chain` | Units or sites flagged from `temperature_logs` / `power_outages` |
| POST | `/explanations/llm` | Optional rewrite of `reason_deterministic`; must echo source numbers |
| POST | `/sync/queue` | Push pending offline actions; idempotent by event id |
| GET | `/sync/status` | Pending / accepted / rejected-on-reconcile |
| POST | `/alerts/simulate` | SMS or USSD-style sandbox or mock; no real donor/patient contact |
| GET | `/settings` | Country/config: shelf lives, reserves, language, branding |
| PUT | `/settings` | Coordinator or operator update; audited |
| GET | `/simulation/results` | Latest policy comparison artefact (read-only) |
| GET | `/components` | Enabled products (RBC, optional PLT, …) |

### `GET /components` (pipeline contract, DG-08)

`pipeline.eligibility.component_catalog(config)` returns one entry per product: `component`, `enabled_in_queue`, `shelf_life_days`, `min_remaining_hours_on_arrival`, `max_travel_hours`, `storage_range_c` and `storage_evidence_in_dataset`. Only RBC is enabled by default. When platelets are enabled, each platelet unit carries the warning `no_storage_evidence` in `warnings`, which the card must display.

### `GET /flags/cold-chain` (pipeline contract, DG-07)

Built by `python -m pipeline build` into `dg_cold_chain_flags`. The backend can run `pipeline.coldchain.COLD_CHAIN_QUERY` as is, with optional `facility_id` and `unit_id` query parameters. Response rows:

```json
{
  "flag_id": "unit-000123",
  "flag_type": "fridge_excursion",
  "scope": "unit",
  "facility_id": "HSP-001",
  "unit_id": "U2610-...-RBC",
  "evidence_at": "2026-10-25T02:00:00+03:00",
  "end_at": "2026-10-25T05:00:00+03:00",
  "value": 7.5,
  "source_table": "temperature_logs",
  "source_ref": null,
  "blocks_suggestion": true,
  "note": "while on this shelf: 3 consecutive hourly readings outside 2-6 C, peak 7.5 C"
}
```

`flag_type` is one of `fridge_excursion`, `outage_no_backup`, `logger_gap`, `coolbox_excursion`, `receipt_unconfirmed`, `official_exposure` (and `sensor_glitch`, which the query leaves out because it is never a clinical event). Timestamps follow the API-wide rule: ISO 8601 with an explicit `+03:00` offset. The database keeps the same instants as EAT text without an offset (`YYYY-MM-DD HH:MM:SS`, the form of the official CSVs), so the endpoint must append `+03:00` when it serialises `evidence_at` and `end_at`. `value` is the peak temperature, the outage hours or the missing hours. A flag can only add caution: no endpoint may use the absence of a flag to declare a unit safe or to clear a quarantine.

## Idempotency

Every write accepts an `event_id`. Repeating the same `event_id` with the same payload returns the original result. Conflicting payloads with a reused `event_id` fail.

## What this API will never include

- Transfusion release or compatibility matching.
- Automatic messages to real donors or patients.
- Patient ranking.
- Silent overwrite of quarantine.
