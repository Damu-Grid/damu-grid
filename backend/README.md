# backend/

FastAPI application: suggestion and action API, workflow state machine, audit store, optional LLM explanation layer, optional sync and SMS-simulation endpoints, settings, and deployment config.

**Owner:** Timi (`drizzy765`). No team lead; this is an area, not a rank.

**Status:** empty on purpose. All application code is written in the official window (Tue 10 Nov 2026, 12:00 EAT–Wed 11 Nov 2026, 12:00 EAT). Do not paste pre-window projects here.

Intended shape (see `docs/ARCHITECTURE.md` and `docs/API_SPEC.md`):

- Python 3.11+, `uv`, Ruff, pytest
- FastAPI + SQLModel/SQLAlchemy + SQLite action store
- One suggestion object, one transactional action function
- Demo roles only; no transfusion-release endpoint

Entry points will be listed here once they exist (`uv run uvicorn ...`). Until then, do not invent a failing command in the root README.
