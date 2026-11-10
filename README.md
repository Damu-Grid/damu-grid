# Damu Grid: expiry-aware blood redistribution review queue

Terumo BCT Africa Hackathon 2026 · Challenge area: redistribution

Damu Grid helps a regional stock coordinator decide which eligible red-cell units can be spared at one site and used at a site that is running short, before they expire. A person Accepts, Changes or Rejects every recommendation. Sending and receiving officers then confirm dispatch and receipt. The workflow still works if the forecasting model is offline.

This README follows the official hackathon README template. The local prototype code was written during the 24-hour window. It runs on the official synthetic starter dataset and uses a frozen 31 October closing snapshot and demo clock. Its HTTP server is a local rehearsal tool, not a production deployment.

Planning docs for teammates and AI coding agents are in `docs/` and `AGENTS.md`.

Submission readiness: [DG-39 blocker register, rehearsal and freeze checklist](docs/DEMO_AND_SUBMISSION.md#dg-39-readiness-record). The inspected foundation has no application implementation yet; the checklist records missing evidence rather than claiming readiness.

## The problem

The primary user is a **regional stock coordinator** at a regional blood transfusion centre. Today that person must reconcile stock reports, see which hospitals are short, find units that will expire unused, and arrange a transfer. Sending and receiving officers must then agree on what actually left and arrived.

In the official **synthetic** starter dataset (a Kenya-modelled year, 1 November 2025 to 31 October 2026; not facts about real facilities):

- 47 facilities; 49,426 units; 17,430 hospital requests for 34,242 units, with 87% fully met (dataset README).
- About 23% of red cell and whole blood units are wasted (expired on the shelf, or discarded after the fridge got too warm), while other facilities run short (dataset README).
- Emergency resupply takes a median of about 5 hours (dataset README).
- There is no demand table; demand must be estimated from `requests` (and optionally `donations`). `daily_stock` is end-of-day inventory, not demand.

Stale reports, unconfirmed receipts and missing temperature evidence can make a plausible move unsafe. The model never releases a unit for transfusion and never overrides a quarantine.

## What we built

- What works now: computed RBC recommendation queue; nearest eligible fallback; local browser review with Accept, Change and Reject; transactional reservation and audit; sender dispatch and receiver receipt; a reproducible forecast comparison. A schematic site plot and table, browser pending-action tray, demo-only officer alert log and fixed settings view are included. Five safety and workflow tests pass, including lease recovery.
- What remains: a production FastAPI/Next.js stack, live as-of reconciliation, full cold-chain and logger-gap evaluation, server-side offline sync, real map tiles, SMS gateway, editable second-country settings, scenario replay, demo video and final slides. The current interface uses a Python standard-library HTTP server and static HTML to provide a clean local run.

Demo video (3 minutes or less): [link to be added]
Live demo: [link] · Test log-in: [user / password to be added]

## How to run it

From a clean checkout with Python 3.11+, run `python -m backend.prototype` and open `http://127.0.0.1:8000`. No extra packages or credentials are needed. The first start builds an ignored local database in `data/processed/`. Use the queue to Accept a card, then Dispatch and Receive it in the move panel; the model-off selector shows fallback. The UI supplies clearly named demo actors. Run `python -m unittest discover -s tests -p test_prototype.py` for workflow tests and `python forecasting/evaluate.py` for the frozen evaluation. To reset a rehearsal, stop the server, remove only `data/processed/prototype.sqlite`, and restart it.

These are synthetic replay actions under a frozen demo clock. The actor labels are not secure authentication, and the server binds to `127.0.0.1` only.
Lease recovery exists as a tested trusted-server function (`backend.prototype.expire_leases`) but is not scheduled automatically in this local demo.
The browser pending tray stores an action and its event ID if the local API is unreachable; manual retry sends the same ID and stops on a conflict for fresh review. It is a local demonstration of pending semantics, not a durable multi-device sync service. The site plot uses synthetic coordinates without a basemap; the list remains available. Alerts are recorded locally for demo officers and are never sent.

## Architecture

The planned architecture and workflow diagrams are already available as Mermaid in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). They describe the intended design; implementation alignment still needs review:

Official CSVs → validation and local SQLite → demand estimator and rule fallback → eligibility engine → review screen → reservation / dispatch / receipt and audit.

The baseline evaluator is a separate read-only path. The wider laboratory and inventory system is an external boundary. There is no automated laboratory-override or transfusion-release endpoint.

Conceptual mappings to FHIR, ISBT 128 or DHIS2, if added, will be labelled as conceptual unless a profile is actually implemented.

## AI and data

- What the AI or data feature does: a pooled demand estimator (hospital-total RBC demand allocated by historical known-group proportions) informs recipient gaps and sender reserves. Suggestions rank eligible exact-group red-cell units by estimated use before expiry, given typical route time. This is a statistical data feature. An optional Tier 2 LLM only drafts a plain-language explanation from those numbers; it must not invent stock or demand figures.
- Baseline we compared against: for each hospital and known group, seven-day predicted requested units = 7 × (requested RBC units in the preceding 28 calendar days ÷ 28). Optional second comparison: nearest eligible site first versus expiry-aware ranking, on documented synthetic scenarios.
- Result from the in-window `forecasting/evaluate.py`: seven-day RMSE **2.792** for the 28-day site/group baseline versus **2.580** for the pooled candidate; MAE **1.482** versus **1.382**. This uses 17 seven-day origins from 1 July to 21 October 2026 and 4,352 hospital/group predictions on synthetic requests. The evaluator excludes 410 unknown-group RBC hospital requests. No independent unseen-year result is claimed; missing request rows are treated as zero under an unverified reporting-completeness assumption.
- How a user sees the reason for a recommendation: each card shows unit/group, sender reserve, recipient gap, expiry, typical travel time, data age, assumed benefit, and uncertainty. Deterministic text first; optional LLM rewrite of the same numbers.
- Who approves it (Accept / Change / Reject): the regional stock coordinator. The sender rechecks and dispatches. The receiver confirms arrival. A qualified safety role controls quarantine; the model cannot clear it.
- What happens if the AI is wrong or offline: nearest eligible site matching using a simple historical demand rule, with the same safety gates and human decisions. Offline or disconnected actions remain pending until reconciled (Tier 2 sync queue).

## Data

We use the official synthetic starter dataset in `data/raw/`. Tables used for the core workflow: `facilities`, `routes`, `units`, `daily_stock`, `requests`, `transfers`. Optional / Tier 2: `donations`, `power_outages`, `temperature_logs`. Donor tables are not required for redistribution decisions and will not be displayed as personal data.

Licence / terms: there is no SPDX licence on the dataset. Official rules: use it freely in the hackathon and demo; say that we used the synthetic starter dataset; do not present findings as facts about real Kenyan facilities; cite any other data (we do not plan to add any); no real donor, patient or facility records. See `data/raw/README.md` and `docs/DATA.md`.

## African conditions

Facilities in the starter data include `grid_reliability`, `connectivity` (2G / 3G / 4G), and `has_blood_fridge_backup_power`. The Tier 1 product must remain usable on a basic browser and a slow connection: small payloads, visible data age, and a model-off fallback. Tier 2 adds a PWA / offline sync queue, SMS or USSD-style alert simulation (sandbox or mock only; no real patient or donor contact), and country/config settings so rules, language and branding can change without a code fork.

## AI tools we used

OpenAI Codex was used on 10 November 2026 to inspect GitHub issues and the supplied proposal, write the submission checklist, implement the local prototype and forecast evaluator, run tests, and update this README. The team must add any other tools actually used and review and explain submitted work.

## Team

There is **no team lead**. Everyone is an equal teammate. Blessings and Timi are taking the heavier implementation tracks because they can stay most active, not because they outrank anyone.

| Name | Role (ownership area, not seniority) | Country | Presenting Friday (in person / online) |
|------|------|---------|-----------------------------------------|
| Agoro Oluwatimilehin Teslim (Timi) | Backend, workflow state machine, LLM explanations, deployment | Nigeria | To confirm |
| Blessings Mambwe | Forecasting, baseline evaluation, simulation, reproducibility | Zambia | To confirm |
| Sorgho Brayan Jovani Aboubacar | Data pipeline, schema, eligibility, cold-chain flags | Morocco | To confirm |
| Dan Boumba | Frontend, map, dashboard, UX, demo video and slides | Democratic Republic of the Congo | To confirm |

## Known limits and next steps

- Results in this README will be computed in the window on synthetic data only.
- Tier 1 is known-group RBC. Other components (for example platelets, 5-day shelf life in the dataset model) are Tier 2 and need their own policy before they are treated like red cells.
- Historical inventory will use an explicit closing snapshot, not a reconstruction from final unit locations.
- About 3% of `transfers` lack `received_at`; 14% of `requests` have messy typed facility names (use `facility_id`); 5% of emergency requests have unknown blood group; temperature logs contain gaps and 60 documented sensor glitches.
- The dataset README lists `blood_system.sqlite`, which was not in the official zip we received.

Next steps after the hackathon, if any, will be listed here after the demo.
