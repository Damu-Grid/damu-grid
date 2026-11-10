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

The API base URL comes from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`, see the root `.env.example`).

Checks: `pnpm lint`, `pnpm typecheck`, `pnpm build`.

End-to-end tests: `pnpm test:e2e`. Playwright starts a **test-only mock API** (`e2e/mock-api.mjs`, fake `MOCK-…` data following `docs/API_SPEC.md`) and the app, then drives accept / change / reject, a 409 conflict, model-off, role limits and the API-down banner. Locally it uses the installed Microsoft Edge; elsewhere run `pnpm exec playwright install chromium` and set `PW_CHANNEL=chromium`.

## Layout

| Path | What |
|---|---|
| `app/login/` | Demo role picker (coordinator, sender, receiver, safety). Not production sign-in |
| `app/queue/` | Coordinator review queue, model-off (fallback) switch, decisions made this session |
| `components/action-dialog.tsx` | Accept / Change / Reject with a required reason, one `event_id` per decision, 403/409/422 messages, Ctrl+Enter to submit |
| `e2e/` | Playwright tests and the test-only mock API |
| `app/dispatch/`, `app/receive/`, `app/evaluation/` | Stubs until DG-32 / DG-33 |
| `lib/api/schemas.ts` | Zod schemas mirroring `docs/API_SPEC.md` |
| `lib/api/client.ts` | Fetch wrapper: base URL, error mapping (403/409/422/503), `event_id` |
| `lib/fixtures/` | Fake layout placeholders (`FIXTURE-…` IDs), shown only when the API is unreachable, under a "Not computed" banner |
| `components/` | Suggestion card, status chips (expiry, data age, fallback, synthetic) |
