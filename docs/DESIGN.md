# Design system and screens

Dan owns visual design, the review UI, map, dashboard, and demo click path. This document is the brief, not a completed interface.

## Product stance

This is a **regional stock-coordination workbench** for a named coordinator, plus sender and receiver officers. It should feel like an operations tool used on a tired afternoon and a flaky connection, not a marketing landing page and not a consumer health app. We do not dress the UI as a certified medical device.

## Research before inventing chrome

When Refero, Mobbin, or public references are available, look at:

- Hospital or laboratory inventory and issue queues.
- Logistics dispatch and transfer-approval screens (accept / amend / reject).
- Map + list operational dashboards that still work when the map is hidden.
- Low-density data tables with sticky status, not ornamental gradient cards.

Do not copy a competitor product, and do not imitate consumer wellness palettes. Record the pattern names you used in the PR, not screenshots of copyrighted UI in the repo unless we have rights.

## Screens (Tier 1)

1. **Coordinator review queue** — ranked suggestion cards or a compact table with a detail pane. Each card shows unit IDs, source and destination names and `facility_id`, component, group, as-of time and data age, expiry, typical travel hours, sender reserve and stock after, recipient gap, deterministic reason, uncertainty label, policy name, and fallback flag. Actions: Accept, Change, Reject, all requiring a short reason.
2. **Move detail / audit** — state, actors, timestamps, version conflicts.
3. **Sender dispatch** — recheck unit, safety, lease remaining, ETA; cannot dispatch a blocked or expired reservation.
4. **Receiver confirmation** — arrival, optional cold-chain note; language on screen: receipt is not transfusion release.
5. **Evaluation panel** — frozen baseline vs candidate table, period, sample size, "synthetic" badge.
6. **Fallback / model-off toggle** — same review flow, clearly labelled.

## Screens (Tier 2)

7. **Map** — sites from `facilities.lat` / `lon`, stock and expiry risk, connectivity. OSM attribution. A table remains the source of truth if tiles fail.
8. **Dashboard** — snapshot counts, open moves, flags. No unverified "units saved" KPI.
9. **Offline / pending-sync tray** — queued actions, conflicts.
10. **Alert simulation** — SMS/USSD-style preview to a demo officer role only.
11. **Settings** — country/config: shelf lives, reserve policy, language, branding.
12. **Cold-chain flag list** — linked from a suggestion warning, never auto-cleared.

## Colour, type, density

- **Base:** a cool, dark-accessible navy or deep teal surface system, light mode as the demo default unless contrast testing prefers dark. High contrast text (WCAG 2.2 AA at least).
- **Semantic colour only:** expiry and quarantine in a distinct red/amber that is not used for branding; fulfilled / received in a restrained green; fallback or "model off" in a clearly different chip colour.
- **Type:** a readable sans already in the Next.js / shadcn stack. Body ≥ 16px on the demo path. Tabular figures for counts and hours.
- **Density:** comfortable, not airy marketing spacing. The projector and a 13-inch laptop must show unit id, expiry and the three actions without horizontal scroll tricks.
- **Do not** use blood-drop decoration, stock-photo patients, or unverified impact numbers on the home screen.

Official kit includes `data/raw/logos.png`. Confirm permitted use with the brief/recap before putting sponsor marks on slides or the app chrome. When in doubt, use text credit only.

## Accessibility and keyboard demo

- Visible focus, labelled buttons, not icon-only primary actions.
- One keyboard path for: open queue → open card → accept → confirm. Dan rehearses this for the recording.
- Do not rely on colour alone for expiry or fallback.
- Motion is optional and never required to complete an action.

## Low-bandwidth and African conditions

- The app must be usable on a 2G/3G story: static shell, no autoplay, compressed images, map optional.
- Show **data age** and connectivity when we have it (`facilities.connectivity` is `4G` / `3G` / `2G`).
- Offline-first (Tier 2): optimistic local write, `pending_sync`, conflict resolution that never drops a quarantine.
- Copy should stay short. Settings may later add a second language; English is the demo default unless the team agrees otherwise in time to rehearse.

## Frontend stack

Next.js App Router, TypeScript, shadcn/ui, Tailwind, Zod, TanStack Query, Recharts (Tremor only if it does not fork the design system), MapLibre or Leaflet + OSM attribution, Playwright for the critical path. See `docs/TOOLS_AND_SKILLS.md`.
