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
- `GET /suggestions` returns computed cards from an injected ranking provider, or `503 suggestions_not_ready`. It never serves frontend fixture cards as computed results.
- LLM explanations use the configured live provider when enabled. A five-second timeout, rate limit, or other provider error leaves the deterministic reason in place.

## Run

```bash
uv sync
uv run uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

For live explanations, configure `LLM_ENABLED=true`, `LLM_MODEL`, and `LLM_API_KEY` in the ignored local `.env`. `LLM_PROVIDER` and `LLM_BASE_URL` default to the OpenAI-compatible API. Without the required settings, explanations use the deterministic template. The processed pipeline store and ranking provider must be supplied before suggestions are available.
