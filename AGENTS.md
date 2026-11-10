# AGENTS.md — Team Damu Grid

Read this file first in every AI coding session (Cursor, Claude Code, Codex, Copilot, or similar). Path-scoped extras live in `.cursor/rules/*.mdc`. Claude Code also loads `CLAUDE.md`, which imports this file.

## Project summary

**Damu Grid** is Team Damu Grid's entry for the Terumo BCT Africa Hackathon 2026 technical phase. Assigned challenge area: **redistribution**.

We are building an **expiry-aware red-cell redistribution review queue** for a **regional stock coordinator**. The system:

1. Estimates demand (there is no demand table; derive it from `requests`, optionally `donations`).
2. Suggests transfers of units that will expire at one site to a site that is running short, and shows what that is estimated to save.
3. Requires a person to **Accept, Change or Reject** every recommendation before blood is reserved or moved.
4. Reserves stock, then records **dispatch** and **receipt**, with an **audit trail**.
5. Keeps a **rule-based fallback** if the model is wrong or offline.
6. Compares a demand forecast against a **28-day average baseline**, and optionally compares expiry-aware ranking with **nearest-site-first**.

The team adopted the 10 November 2026 LLM evaluation recommendation as the **core product**, and is also building an ambitious **Tier 2** (map, offline/low-connectivity sync queue, SMS/USSD-style alert simulation, multi-component support such as platelets, scenario replay, cold-chain flags, LLM explanations with a deterministic fallback, country/config settings). Tier 1 must ship. Tier 2 is in the plan, not optional decoration, but **never cut eligibility, human control, the baseline, the fallback, or submission time** to chase Tier 2.

This is a 24-hour build. **All submitted code must be written between Tuesday 10 November 2026, 12:00 EAT and Wednesday 11 November 2026, 12:00 EAT.** Documentation in this folder is planning context, not implementation. Do not copy pre-hackathon project code (Sell-Safe, prior demos, pitch notebooks) into this repository.

## Honesty rules (non-negotiable)

- Never claim clinical clearance, transfusion release, or blood-group compatibility decisions.
- Never present a guess as a fact. Show uncertainty. Label all results as **synthetic**.
- Do not present findings from this data as facts about real Kenyan facilities.
- Do not reuse unverified pitch numbers (for example 11.3% RMSE, 22.3% unmet, AUC claims) as if they were measured in this repo. Recompute everything in the window, or omit the number.
- Acceptance of a suggestion is not physical dispatch and is not a release for transfusion.
- Do not invent missing receipts, blood groups, or historical stock from final unit locations (snapshot leakage).
- Declare every AI coding tool and what it was used for in the root `README.md`.

## Hard do-not rules

- Do not modify, delete, or rewrite files under `data/raw/`. Cite `data/raw/DATA_DICTIONARY.md` for column meanings.
- Do not commit secrets. Use `.env.example` for names only. Never commit `.env`.
- Do not add real donor, patient, or facility records.
- Do not implement an endpoint that releases a unit for transfusion, overrides a laboratory result or quarantine, contacts a real donor or patient, or ranks patients.
- Do not squash the day's history into one large commit at the end. Commit as you go; incremental commits are proof of in-window work.
- Do not push, open GitHub issues, or contact organisers or teammates from an agent unless a human has explicitly approved that specific action.
- Do not backdate commits or check-ins.

## Repo map

| Path | Purpose | Primary owners (no team lead) |
|---|---|---|
| `backend/` | FastAPI, state machine, audit, LLM explanation layer, deployment | Timi (`drizzy765`) |
| `pipeline/` | ETL, validation, SQLite schema, eligibility, cold-chain flags | Brayan (`Sorghobrayan-dotcom`) |
| `forecasting/` | Demand estimator, 28-day baseline, evaluation harness | Blessings (`bleymambwe`) |
| `simulation/` | Scenario replay and policy comparison | Blessings (`bleymambwe`) |
| `frontend/` | Review queue, map, dashboard, PWA/offline UX | Dan (`Dan-Boumba`) |
| `data/raw/` | Official starter dataset (read-only) | everyone (do not edit) |
| `data/processed/` | Derived DB and outputs (gitignored) | pipeline / forecasting |
| `tests/` | pytest and Playwright | everyone |
| `docs/` | Architecture, plan, API, evaluation, domain | everyone |
| `scripts/` | Dev and submission helpers | everyone |
| `notebooks/` | Exploratory work; promote tested code into packages | Blessings / Brayan |
| `slides/` | Pitch deck source | Dan |
| `issues/` | Planned GitHub issues (local until a human publishes them) | everyone |

## Commands (as packages are created in-window)

Until the packages exist, do not invent failing commands. After bootstrap, prefer:

```bash
# Python (planned)
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn backend.app.main:app --reload --port 8000

# Frontend (planned)
cd frontend && pnpm install && pnpm dev
cd frontend && pnpm lint && pnpm test && pnpm exec playwright test
```

See folder READMEs once they list the exact entry points.

## Conventions

- Python 3.11+, type hints, Ruff, pytest. FastAPI + SQLModel/SQLAlchemy + SQLite for the action store. DuckDB or Polars are welcome in the pipeline and evaluation path, not required in the transaction path.
- TypeScript + Next.js App Router + shadcn/ui for the UI. Zod for request/response validation. TanStack Query for server state.
- One suggestion payload and one transactional action function, as specified in `docs/API_SPEC.md` and `docs/ARCHITECTURE.md`.
- Times in the data are East Africa Time (UTC+3). Use timezone-aware timestamps in new records.
- Use `facility_id`, never `facility_name_raw`, as the facility key.
- Forecast **requested** units (`units_requested`), not issued units (`units_issued`).
- Default product scope for Tier 1: `component = RBC` and known exact blood groups (`O+`, `A+`, `B+`, `AB+`, `O-`, `A-`, `B-`, `AB-`). Unknown groups stay unknown.
- Settings (shelf lives, reserves, language, branding) belong in config, not hardcoded, so a second country can be a settings change (Tier 2).
- Tests travel with behaviour. Safety and state-machine tests are not optional.

## Where to read next

1. `docs/PROJECT_BRIEF.md` — official rules, weights, deadlines.
2. `docs/DATA.md` — real schemas, counts, quirks.
3. `docs/ARCHITECTURE.md` and `docs/API_SPEC.md` — boundaries and contracts.
4. `docs/IMPLEMENTATION_PLAN.md` and `docs/ROLES.md` — time and ownership.
5. `docs/EVALUATION.md` — baseline methodology.
6. `docs/TOOLS_AND_SKILLS.md` — approved open-source tools and agent skills.
7. `docs/DESIGN.md`, `docs/DOMAIN.md`, `docs/DECISIONS.md` — UI, domain citations, ADRs.
8. The issue list in `issues/ISSUES.md` before starting a workstream.

If an official organiser document disagrees with a summary in `docs/`, prefer the official original and note the discrepancy.
