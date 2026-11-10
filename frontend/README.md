# frontend/

Next.js App Router UI: coordinator review queue, sender and receiver views, evaluation panel, and Tier 2 map, dashboard, PWA/offline outbox, settings and alert simulation.

**Owner:** Dan (`Dan-Boumba`). Design brief: `docs/DESIGN.md`.

**Status:** app shell, demo role picker and coordinator queue layout (DG-30). Accept / Change / Reject wiring (DG-31), dispatch/receive (DG-32) and the evaluation panel (DG-33) are next.

Stack: Next.js 15 (App Router), TypeScript, shadcn/ui, Tailwind 4, Zod, TanStack Query. Planned: Recharts, MapLibre or Leaflet + OpenStreetMap attribution, Playwright. See `docs/TOOLS_AND_SKILLS.md`.

The UI is a client of the backend API, not a second stock ledger. Do not hard-code suggestion numbers in the recorded demo. If the API is not ready, label the screen as a layout placeholder.

## Run it

Requires Node 20+ and pnpm (`corepack enable pnpm`).

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
```

### Which backend

The app talks to `/api/backend/*`, which Next.js relays to `BACKEND_URL` (default `http://127.0.0.1:8000`). The backend needs no CORS headers.

| Setting (in `frontend/.env.local`) | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_BACKEND` | `prototype` | `prototype` = Blessings' `backend/prototype.py` (#50); `spec` = the contract in `docs/API_SPEC.md` (planned FastAPI) |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Where the relay sends requests |
| `NEXT_PUBLIC_API_BASE_URL` | `/api/backend` | Set a full URL only to bypass the relay (the backend must then allow CORS) |

Both drivers live in `lib/api/backend.ts`; the screens do not change when the backend does.

To run against the prototype: from the repo root (with `backend/prototype.py`), run `python backend/prototype.py`, then `pnpm dev` here. To reset its demo state, stop it and delete `data/processed/prototype.sqlite`.

Prototype differences the adapter handles: one unit per suggestion; actions at `POST /accept|change|reject|dispatch|receive` keyed by `unit_id` + `unit_version`; a reason on every action; `transit` → in transit; receipt with uncertain cold chain → held for safety review; move lists rebuilt from `/audit` (no `GET /moves` list yet); lease enforced by the prototype's frozen demo clock.

Checks: `pnpm lint`, `pnpm typecheck`, `pnpm build:check`. Use `build:check` (it builds into `.next-check/`) while `pnpm dev` is running: a plain `pnpm build` overwrites `.next/` and makes the dev server return Internal Server Error until restarted. The e2e tests build into `.next-e2e/` for the same reason.

Integration test against the real prototype: `pnpm test:prototype` (starts `backend/prototype.py` with a fresh demo database; set `PROTOTYPE_DIR` if the prototype is in another checkout).

End-to-end tests: `pnpm test:e2e`. Playwright starts a **test-only mock API** (`e2e/mock-api.mjs`, fake `MOCK-…` data following `docs/API_SPEC.md`) and the app, then drives accept / change / reject, a 409 conflict, model-off, role limits and the API-down banner. Locally it uses the installed Microsoft Edge; elsewhere run `pnpm exec playwright install chromium` and set `PW_CHANNEL=chromium`.

## Layout

| Path | What |
|---|---|
| `app/login/` | Demo role picker (coordinator, sender, receiver, safety). Not production sign-in |
| `app/queue/` | Coordinator review queue, model-off (fallback) switch, decisions made this session |
| `components/action-dialog.tsx` | Accept / Change / Reject with a required reason, one `event_id` per decision, 403/409/422 messages, Ctrl+Enter to submit |
| `e2e/` | Playwright tests and the test-only mock API |
| `app/dispatch/` | Sender: reserved moves, lease countdown, recheck checklist, dispatch |
| `app/receive/` | Receiver: moves in transit, cold-chain evidence, receipt (not a release for transfusion) |
| `app/moves/[id]/` | Move state and audit trail; held-for-safety banner |
| `app/evaluation/` | Forecast vs 28-day baseline from `GET /evaluation/forecast`: plain-language verdict (says so if the candidate loses), RMSE/MAE/n/coverage table, split and exclusions, `/snapshot` counts if provided. Shows "Not computed yet" and no numbers until the API returns them |
| `lib/api/schemas.ts` | Zod schemas mirroring `docs/API_SPEC.md` |
| `lib/api/client.ts` | Fetch wrapper: base URL, error mapping (403/409/422/503), `event_id` |
| `lib/fixtures/` | Fake layout placeholders (`FIXTURE-…` IDs), shown only when the API is unreachable, under a "Not computed" banner |
| `components/` | Suggestion card, status chips (expiry, data age, fallback, synthetic) |
