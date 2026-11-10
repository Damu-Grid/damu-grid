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

## Reference look (adopted 10 Nov 2026)

The visual reference is Blessings' platelet control-room demo: <https://blessingsmambwe.web.app/damu-grid/>. We match its **look**; we do **not** copy its code. That site predates the build window, so every line here is rewritten in `frontend/`, and only public-domain data (Natural Earth) is reused, with attribution.

**Tokens** (implemented in `frontend/app/globals.css`):

| Token | Value | Use |
|---|---|---|
| navy | `#12306b` | primary buttons, headings, active rail icon, fresh stock |
| blue / blue-2 / pale | `#3f7ee0` / `#8db3ee` / `#cfdcf3` | links, focus, mid shelf life, empty ring |
| gold / gold-ink / gold-soft | `#d4a23a` / `#8a6414` / `#f6ecd6` | **expiring**, synthetic pill |
| red | `#cf4a3f` | critical, unmet, close to unusable |
| green | `#2f7d4f` (text on light green: `#2a7047`) | received |
| ink / ink-2 / line / soft | `#0f2350` / `#4a5b7d` / `#e4eaf4` / `#f1f5fb` | text, secondary text, borders, hover |
| background | gradient `#f5f8fd` → `#dce6f7` | page |
| card | white 86% + blur, 16 px radius, soft navy shadow | every surface |

**Type:** DM Sans 400/500/600/700; IBM Plex Mono for IDs and code. Eyebrow labels: 12 px, semibold, uppercase, 0.16em tracking.

**Layout:** a 76 px icon rail on the left (brand mark, one icon per screen, role initials and switch-role at the bottom); each screen starts with an eyebrow ("Red cell network · Kenya" + gold **Synthetic data** pill), an h1, and a one-line purpose.

**Brand mark exception:** the single small drop in the rail is the logo, not decoration. The "no blood-drop decoration" rule above still applies everywhere else.

**Map (DG-34, owner Timi; build only once agreed):**
- Canvas **hex-dot map**, no map library or tiles (works offline and on 2G). Land dots in grey (`#e3e9f3`), Kenya in blue tints, each Kenyan dot shaded by its nearest facility's status. Outlines from **Natural Earth 1:50m (public domain)**; cite it on the map.
- Facilities are white discs with a **ring split by shelf life left** (gold = expiring → blue → navy = fresh), stock count inside, name and demand per day beside.
- Transfers are **curved arrows** with a unit-count bubble: navy for routine top-ups, gold for rescues of expiring stock, dashed while awaiting a decision.
- Late data gets a **dashed halo**; unmet demand a **red ring** with "N unmet".
- A legend panel of status rows with counts: well stocked, below safety level, critically low, at risk of expiring, data arriving late. The table stays the source of truth if the map fails.

**Charts:** one big number with a plain-language caption, a "Damu Grid vs baseline" comparison table, and a small two-line **cumulative sparkline** (ours navy, baseline light). Only in-window numbers; never a "saved" figure that was not computed from our own runs.

**Suggestion cards:** site-initial avatar, "From → To", blood-group badge, units on the right, a short gold or navy bar, the plain-language reason, and a muted line of facts ("Top-up · 3 days of shelf life left · sender confirmed").

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
