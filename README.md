# Damu Grid: expiry-aware blood redistribution review queue

Terumo BCT Africa Hackathon 2026 · Challenge area: redistribution

Damu Grid helps a regional stock coordinator decide which eligible red-cell units can be spared at one site and used at a site that is running short, before they expire. A person Accepts, Changes or Rejects every recommendation. Sending and receiving officers then confirm dispatch and receipt. The workflow still works if the forecasting model is offline.

This README follows the official hackathon README template. **All application code will be written between Tuesday 10 November 2026, 12:00 EAT and Wednesday 11 November 2026, 12:00 EAT.** This repository contains planning material, the official starter dataset, and application code built during the hackathon window.

Planning docs for teammates and AI coding agents are in `docs/` and `AGENTS.md`.

## The problem

The primary user is a **regional stock coordinator** at a regional blood transfusion centre. Today that person must reconcile stock reports, see which hospitals are short, find units that will expire unused, and arrange a transfer. Sending and receiving officers must then agree on what actually left and arrived.

In the official **synthetic** starter dataset (a Kenya-modelled year, 1 November 2025 to 31 October 2026; not facts about real facilities):

- 47 facilities; 49,426 units; 17,430 hospital requests for 34,242 units, with 87% fully met (dataset README).
- About 23% of red cell and whole blood units are wasted (expired on the shelf, or discarded after the fridge got too warm), while other facilities run short (dataset README).
- Emergency resupply takes a median of about 5 hours (dataset README).
- There is no demand table; demand must be estimated from `requests` (and optionally `donations`). `daily_stock` is end-of-day inventory, not demand.

Stale reports, unconfirmed receipts and missing temperature evidence can make a plausible move unsafe. The model never releases a unit for transfusion and never overrides a quarantine.

## What we built

- What works now: the FastAPI health, snapshot, and suggestions endpoints; the human review workflow; the append-only audit trail; and the synthetic forecasting evaluation harness. When the processed store or ranking provider is unavailable, `/suggestions` reports that state instead of returning fake computed cards.
- What remains in progress: connecting the pipeline ranking provider and completing the demo video and slides. Tier 2 items are tracked in `docs/IMPLEMENTATION_PLAN.md`.

Demo video (3 minutes or less): [link to be added]
Live demo: [link] · Test log-in: [user / password to be added]

## How to run it

The forecasting and policy comparison in this branch can be reproduced now with Python 3.11+ and `uv`:

```bash
uv sync
uv run pytest tests/forecasting tests/test_simulation.py
uv run ruff check forecasting simulation tests
uv run python -m forecasting.evaluate
uv run python -m simulation.compare
```

The forecast command writes a row-level table, metrics JSON, and Markdown summary into ignored `data/processed/`. The split, models, upper-bound level, and simulation seeds are fixed in committed code. These commands use only the official synthetic CSVs.

### Backend setup

Copy `.env.example` to `.env`, set `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, and `LLM_BASE_URL` for a live explanation provider, then install and start the API:

```bash
uv sync
uv run uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

Live explanations require `LLM_ENABLED=true`, `LLM_MODEL`, and `LLM_API_KEY` in `.env`. Set `LLM_PROVIDER` and `LLM_BASE_URL` when using a provider other than the OpenAI-compatible defaults. The checked-in `.env.example` leaves the LLM values blank. With explanations disabled or unconfigured, the API uses deterministic template text. Keep the key in `.env` or the shell environment; never commit it. Docker Compose can start the local services with `docker compose up --build`.

The backend exposes `GET /health`, `GET /snapshot`, and `GET /suggestions` for frontend integration. It also provides suggestion accept/change/reject, move dispatch/receive/quarantine, audit, settings, sync-queue, and simulated-alert routes. See [`docs/API_SPEC.md`](docs/API_SPEC.md) for the request and response contracts. Until the pipeline suggestion provider is connected, `/suggestions` reports unavailable inputs instead of returning fake computed cards.

### Real integrations

- The LLM explanation provider is a real live integration when enabled and configured. Calls time out after about five seconds and fall back to deterministic text on provider errors, timeouts, or rate limits.
- SMS alerts are simulated and make no real contact.

The full demo setup follows this outline:

1. Copy `.env.example` to `.env` (no secrets in git).
2. Install Python deps with `uv` and frontend deps with `pnpm` (see folder READMEs).
3. Load the official CSVs from `data/raw/` into a local SQLite database under `data/processed/` (gitignored).
4. Start the API and the Next.js app.
5. Sign in with the demo coordinator / sender / receiver accounts.

Judges should assume a laptop and about 10 minutes. A Docker Compose path is a Tier 2 delivery target.

## Architecture

A diagram will be added at `docs/architecture.png` (or SVG) during the window. The intended flow is documented with mermaid in `docs/ARCHITECTURE.md`:

Official CSVs → validation and local SQLite → demand estimator and rule fallback → eligibility engine → review screen → reservation / dispatch / receipt and audit.

The baseline evaluator is a separate read-only path. The wider laboratory and inventory system is an external boundary. There is no automated laboratory-override or transfusion-release endpoint.

Conceptual mappings to FHIR, ISBT 128 or DHIS2, if added, will be labelled as conceptual unless a profile is actually implemented.

## AI and data

- What the AI or data feature does: a pooled demand estimator (hospital-total RBC demand allocated by historical known-group proportions) informs recipient gaps and sender reserves. Suggestions rank eligible exact-group red-cell units by estimated use before expiry, given typical route time. This is a statistical data feature. An optional Tier 2 LLM only drafts a plain-language explanation from those numbers; it must not invent stock or demand figures.
- Baseline we compared against: for each hospital and known group, seven-day predicted requested units = 7 × (requested RBC units in the preceding 28 calendar days ÷ 28). Optional second comparison: nearest eligible site first versus expiry-aware ranking, on documented synthetic scenarios.
- Result (recomputed in this build window on the official **synthetic** requests): the seven-day 28-day-average baseline has RMSE **2.792** and MAE **1.482**; the frozen pooled expanding-mean candidate has RMSE **2.474** and MAE **1.331**. This covers 4,352 hospital/group forecasts at 17 weekly origins from 1 July to 21 October 2026. The candidate's RMSE is 11.4% lower on this retrospective synthetic split. See [`docs/EVALUATION.md`](docs/EVALUATION.md) for the methodology and [`forecasting/evaluate.py`](forecasting/evaluate.py) for the reproducible command; no independent unseen-year result is claimed.
- Uncertainty: a one-sided **90%** upper bound calibrated on eight May–June origins covers **88.8%** of July–October cases overall and **91.5%** of O-negative cases. Overall coverage falls short of the nominal level; the bound is a model estimate, not a clinical probability or per-site guarantee.
- Optional transfer scenario: `uv run python -m simulation.compare` compares one-shot nearest and expiry-aware rankings on the same 30 fixed-seed, seven-day synthetic demand draws. Mean unmet units are **333.3** versus **332.7**, mean expiries **1.03** versus **1.00**, and both policies move **1.0** unit in **1.0** route batch. This narrow scenario is not evidence of large general improvement or a replay of observed November demand.
- How a user sees the reason for a recommendation: each card shows unit/group, sender reserve, recipient gap, expiry, typical travel time, data age, assumed benefit, and uncertainty. Deterministic text first; optional LLM rewrite of the same numbers.
- Who approves it (Accept / Change / Reject): the regional stock coordinator. The sender rechecks and dispatches. The receiver confirms arrival. A qualified safety role controls quarantine; the model cannot clear it.
- What happens if the AI is wrong or offline: nearest eligible site matching using a simple historical demand rule, with the same safety gates and human decisions. Offline or disconnected actions remain pending until reconciled (Tier 2 sync queue).

## Data

We use the official synthetic starter dataset in `data/raw/`. Tables used for the core workflow: `facilities`, `routes`, `units`, `daily_stock`, `requests`, `transfers`. Optional / Tier 2: `donations`, `power_outages`, `temperature_logs`. Donor tables are not required for redistribution decisions and will not be displayed as personal data.

The supplied [competition brief and deck templates](starter-kit/README.md) are in `starter-kit/`. The dataset CSVs are already tracked under `data/raw/`; the large zip is not duplicated.

Licence / terms: there is no SPDX licence on the dataset. Official rules: use it freely in the hackathon and demo; say that we used the synthetic starter dataset; do not present findings as facts about real Kenyan facilities; cite any other data (we do not plan to add any); no real donor, patient or facility records. See `data/raw/README.md` and `docs/DATA.md`.

## African conditions

Facilities in the starter data include `grid_reliability`, `connectivity` (2G / 3G / 4G), and `has_blood_fridge_backup_power`. The Tier 1 product must remain usable on a basic browser and a slow connection: small payloads, visible data age, and a model-off fallback. Tier 2 adds a PWA / offline sync queue, SMS or USSD-style alert simulation (sandbox or mock only; no real patient or donor contact), and country/config settings so rules, language and branding can change without a code fork.

## AI tools we used

OpenAI Codex assisted the in-window evaluation harness, tests, kit inventory, benchmark reproduction and README edits. The team must add every other AI coding tool actually used on its own work. Every team member must be able to explain the submitted code.

## Team

There is **no team lead**. Everyone is an equal teammate. Blessings and Timi are taking the heavier implementation tracks because they can stay most active, not because they outrank anyone.

| Name | Role (ownership area, not seniority) | Country | Presenting Friday (in person / online) |
|------|------|---------|-----------------------------------------|
| Agoro Oluwatimilehin Teslim (Timi) | Backend, workflow state machine, LLM explanations, deployment | Nigeria | To confirm |
| Blessings Mambwe | Forecasting, baseline evaluation, simulation, reproducibility | Zambia | To confirm |
| Sorgho Brayan Jovani Aboubacar | Data pipeline, schema, eligibility, cold-chain flags | Morocco | To confirm |
| Dan Boumba | Frontend, map, dashboard, UX, demo video and slides | Democratic Republic of the Congo | To confirm |

## Known limits and next steps

- Forecast results above were computed in the window on synthetic data only. They assume the request record is complete; missing rows are treated as zero demand.
- Tier 1 is known-group RBC. Other components (for example platelets, 5-day shelf life in the dataset model) are Tier 2 and need their own policy before they are treated like red cells.
- Historical inventory will use an explicit closing snapshot, not a reconstruction from final unit locations.
- About 3% of `transfers` lack `received_at`; 14% of `requests` have messy typed facility names (use `facility_id`); 5% of emergency requests have unknown blood group; temperature logs contain gaps and 60 documented sensor glitches.
- The dataset README lists `blood_system.sqlite`, which was not in the official zip we received.

Next steps after the hackathon, if any, will be listed here after the demo.
