# backend/

FastAPI application: suggestion and action API, workflow state machine, audit store, optional LLM explanation layer, optional sync and SMS-simulation endpoints, settings, and deployment config.

**Owner:** Timi (`drizzy765`). No team lead; this is an area, not a rank.

Application code is being built in the official window (Tue 10 Nov 2026, 12:00 EAT–Wed 11 Nov 2026, 12:00 EAT). Do not paste pre-window projects here.

Intended shape (see `docs/ARCHITECTURE.md` and `docs/API_SPEC.md`):

- Python 3.11+, `uv`, Ruff, pytest
- FastAPI + SQLModel/SQLAlchemy + SQLite action store
- One suggestion object, one transactional action function
- Demo roles only; no transfusion-release endpoint

## Current API

- `GET /health` is a liveness check.
- `GET /snapshot` reports table counts when a processed SQLite store exists; it reports unavailable values as `null` otherwise.
- `GET /suggestions` uses a local SQLite ranking provider by default, or returns `503 suggestions_not_ready` when its required snapshot tables are unavailable. It never serves frontend fixture cards as computed results.
- The default provider forecasts a seven-day recipient gap from known-group RBC requests in the preceding 28 days. It reads `dg_snapshot_units` and `dg_cold_chain_flags`, and applies `pipeline.eligibility.unit_eligibility` and `check_move`; this preserves the pipeline's as-of, receipt, cold-chain, route, arrival-life, and sender-reserve checks. `expiry_aware` orders by expiry; `nearest` and `fallback` order by route time. These are synthetic estimates for human review.
- Accept and dispatch recheck the selected units against the snapshot and action-store state. Reservations and in-transit moves are excluded from later offers and inbound demand gaps.
- LLM explanations use the configured live provider when enabled. A five-second timeout, rate limit, or other provider error leaves the deterministic reason in place.

## Run

```bash
uv sync
uv run python -m pipeline build
uv run uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

Build the shared ignored `data/processed/damu_grid.sqlite` with the pipeline before starting the API. To build to a separate path without replacing an existing snapshot, use `uv run python -m pipeline build --db data/processed/validation.sqlite`.

For live explanations, configure `LLM_ENABLED=true`, `LLM_MODEL`, and `LLM_API_KEY` in the ignored local `.env`. `LLM_PROVIDER` and `LLM_BASE_URL` default to the OpenAI-compatible API. Without the required settings, explanations use the deterministic template. The suggestion-ranking provider itself is local and does not require an LLM or network access.
