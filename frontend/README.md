# frontend/

Next.js App Router UI: coordinator review queue, sender and receiver views, evaluation panel, and Tier 2 map, dashboard, PWA/offline outbox, settings and alert simulation.

**Owner:** Dan (`Dan-Boumba`). Design brief: `docs/DESIGN.md`.

**Status:** empty on purpose. All application code is written in the official window.

Intended stack: TypeScript, shadcn/ui, Tailwind, Zod, TanStack Query, Recharts, MapLibre or Leaflet + OpenStreetMap attribution, Playwright. See `docs/TOOLS_AND_SKILLS.md`.

The UI is a client of the backend API, not a second stock ledger. Do not hard-code suggestion numbers in the recorded demo. If the API is not ready, label the screen as a layout placeholder.

Package manager and scripts will be added here at bootstrap (`pnpm` planned).
