# Tools, skills and open-source leverage

Use these to go faster **in the official window**. Links were checked on 10 November 2026. If a package API has changed, follow the live docs, not a memorised snippet. Do not vendor a teammate's pre-window application code into this repo.

## Agent skills and practices (everyone)

Every coding agent (Cursor, Claude Code, Codex, or similar) must read `AGENTS.md` first.

| Practice | Why | Link / location |
|---|---|---|
| `AGENTS.md` at the repo root | Shared project context: honesty rules, repo map, commands, do-not list | This repo; convention also used by Claude Code — [CLAUDE.md docs](https://code.claude.com/docs/en/claude-md) (import with `@AGENTS.md`, already done in `CLAUDE.md`) |
| Cursor project rules | Path-scoped, always-on constraints for backend, pipeline, forecasting, frontend | [Cursor rules](https://cursor.com/docs/rules); files in `.cursor/rules/*.mdc` |
| Official shadcn skill / registry tools | Add components the documented way; do not hand-roll a parallel design system | [shadcn/ui docs](https://ui.shadcn.com/docs) and [Next.js install](https://ui.shadcn.com/docs/installation/next) |
| Design research before inventing UI | Ground screens in real healthcare operations and logistics patterns, not generic AI-dashboard chrome | Team Refero / Mobbin connectors when available; see `docs/DESIGN.md` |
| Incremental commits and small PRs | Proof that code was written in the window; easier review | `docs/GITHUB_RULES.md` |
| No secrets in prompts or repos | `.env` stays local; agents must not paste keys | `.env.example` (names only) |

When an agent proposes a change: cite `data/raw/DATA_DICTIONARY.md` for column names, do not touch `data/raw/`, and do not claim a metric that has not been computed in-window.

## Backend and data (Timi, Brayan, Blessings)

| Tool | Why we would use it | Docs |
|---|---|---|
| Python 3.11+ | Shared language across API, pipeline, forecast, sim | — |
| [uv](https://docs.astral.sh/uv) | Fast, reproducible Python installs and lockfile | https://docs.astral.sh/uv |
| [Ruff](https://docs.astral.sh/ruff) | Lint and format in one tool | https://docs.astral.sh/ruff |
| [pytest](https://docs.pytest.org) | API, eligibility, and evaluation tests | https://docs.pytest.org |
| [FastAPI](https://fastapi.tiangolo.com) | Suggestion and action API; Timi has shipped FastAPI before | https://fastapi.tiangolo.com |
| [FastAPI full-stack template](https://fastapi.tiangolo.com/project-generation/) | Optional reference for SQLModel + frontend + Docker Compose + Playwright layout — copy patterns, not a pre-built Damu Grid app | https://fastapi.tiangolo.com/project-generation/ |
| [SQLModel](https://sqlmodel.tiangolo.com) / [SQLAlchemy](https://www.sqlalchemy.org) | Typed models over SQLite for the action store | https://sqlmodel.tiangolo.com ; https://docs.sqlalchemy.org |
| SQLite | Local, file-backed, demo-friendly action and snapshot store | — |
| [DuckDB](https://duckdb.org) + [Polars](https://pola.rs) | Fast scans of large CSVs (`temperature_logs`, `daily_stock`) without a warehouse | [DuckDB + Polars](https://duckdb.org/docs/stable/guides/python/polars) |
| [pandas](https://pandas.pydata.org) | Acceptable where already fluent; prefer Polars/DuckDB for the big tables if comfortable | https://pandas.pydata.org |

## Forecasting, simulation, allocation (Blessings; optional optimisation)

| Tool | Why we would use it | Docs |
|---|---|---|
| Mandatory 28-day average | Official-style simple baseline; implement ourselves, no library required | `docs/EVALUATION.md` |
| [StatsForecast](https://nixtlaverse.nixtla.io/statsforecast) | If a classical statistical candidate is added later; keep the 28-day baseline regardless | https://nixtlaverse.nixtla.io/statsforecast |
| [Darts](https://unit8co.github.io/darts/) | Optional richer forecasting experiments; heavier than we need for Tier 1 | https://unit8co.github.io/darts/ |
| [Prophet](https://facebook.github.io/prophet/) | Optional only; often heavier than the window justifies | https://facebook.github.io/prophet/ |
| [OR-Tools](https://developers.google.com/optimization) or [PuLP](https://coin-or.github.io/pulp/) | Only if a later allocation formulation is clearly specified; Tier 1 ranking can be rule-based | https://developers.google.com/optimization ; https://coin-or.github.io/pulp/ |

Do not spend the first night swapping forecast libraries. The adopted candidate is a pooled historical mean with network-wide group shares.

## Frontend, maps, offline (Dan; Timi for sync API)

| Tool | Why we would use it | Docs |
|---|---|---|
| [Next.js](https://nextjs.org) (App Router) + TypeScript | App shell, review screens, demo reliability | https://nextjs.org/docs |
| [shadcn/ui](https://ui.shadcn.com/docs) + Tailwind | Accessible primitives; tables, dialogs, forms, buttons | https://ui.shadcn.com/docs |
| [Zod](https://zod.dev) | Shared request/response validation with the API types | https://zod.dev |
| [TanStack Query](https://tanstack.com/query/latest) | Server state, retries, stale-time — useful on flaky networks | https://tanstack.com/query/latest |
| [Recharts](https://recharts.org) | Default charts for the forecast table and stock views | https://recharts.org |
| [Tremor](https://www.tremor.so) | Optional dashboard blocks on top of the same design system; do not run two incompatible kits | https://www.tremor.so |
| [MapLibre GL JS](https://maplibre.org) (preferred) or [Leaflet](https://leafletjs.com) | Site map; prefer MapLibre for vector tiles if bandwidth allows, Leaflet if we need a simpler raster fallback | https://maplibre.org ; https://leafletjs.com |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Map data; **required attribution** | https://www.openstreetmap.org/copyright |
| [Playwright](https://playwright.dev) | Critical click-path for accept / reject / fallback | https://playwright.dev |
| [Workbox](https://developer.chrome.com/docs/workbox) | Service worker / PWA caching for Tier 2 offline | https://developer.chrome.com/docs/workbox |
| [Dexie](https://dexie.org) (IndexedDB) | Local outbox for pending sync events | https://dexie.org |

## Messaging simulation and LLMs (Timi; Dan for UI)

| Tool | Why we would use it | Docs |
|---|---|---|
| [Africa's Talking](https://developers.africastalking.com/docs/authentication) SMS **sandbox** | Realistic African SMS API shape; username in sandbox is `sandbox`; **simulation only**, no real donor or patient contact | https://developers.africastalking.com/docs/authentication ; sandbox API `https://api.sandbox.africastalking.com/version1/messaging` |
| Local mock if no sandbox key | Same request/response contract, deterministic fixtures for the demo | — |
| LLM SDK (OpenAI-compatible or whatever the team already uses) | Optional rewrite of a **deterministic** explanation; never the source of numbers | Provider docs at use time |
| No billed production SMS | Hard rule | `docs/API_SPEC.md` |

## DevOps

| Tool | Why we would use it | Docs |
|---|---|---|
| [Docker Compose](https://docs.docker.com/compose/) | One-command demo for judges | https://docs.docker.com/compose/ |
| Optional Render (API) + Vercel (Next.js) | Public URL if it does not delay the 10:00 EAT recording; Timi has operated this shape before | Provider docs at use time |

## Design skills (Dan, with review from everyone)

See `docs/DESIGN.md`. In short: research operations/inventory approval queues and logistics dispatch screens; high contrast; expiry/safety red is semantic, not decoration; low-bandwidth and projector-readable; keyboard paths for the recorded demo.

## What we will not pull in

- A pre-built blood-bank product or Blessings's pre-window analysis as if it were already this repo's implementation.
- Heavy AutoML or closed commercial optimisation suites.
- Real patient or donor messaging tools.
- Map tiles that forbid OSM attribution or require a paid key we cannot show in the README.
