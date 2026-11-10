# Implementation plan

Aim: win, not a minimal subset. The team intends to stay online through the window. **Tier 1 still has priority at every cut.** If something has to slip, drop later Tier 2 items, never eligibility, human decisions, the 28-day baseline, the fallback, or submission artefacts.

Planning clock for this document: **Tuesday 10 November 2026, 15:30 EAT** (13:30 WAT) through **Wednesday 11 November 2026, 12:00 EAT** (10:00 WAT). Official check-ins: Tue 20:00 EAT and Wed 06:00 EAT. Record by Wed 10:00 EAT. Submit before Wed 12:00 EAT.

All application code is written in the official window. This document is a plan, not a claim that earlier checkpoints are done. If the roster/GitHub form was due at 14:00 EAT and is not in, do that immediately.

## Tiers

### Tier 1 — must ship (adopted evaluation core)

1. Load official CSVs. Closing-date snapshot. RBC, known exact groups, `facility_id`. Eligibility report excluding exposed, expired, unavailable or unresolved units.
2. Demand-informed suggestions: pooled (or baseline) demand, sender reserve, recipient gap, expiry, typical route time, transparent reason and uncertainty.
3. Human workflow: Accept / Change / Reject, atomic reservation, sender dispatch, receiver confirmation, audit trail.
4. Rule-based fallback (nearest eligible site + simple historical demand rule), same gates.
5. Reproducible 28-day average forecast comparison, both numbers, sample size, period.
6. Official README, architecture diagram, ≤3-minute video, eight slides, AI-tool declaration, public repo.

Optional inside Tier 1 if it does not threaten the above: nearest-site-first transfer comparison on a small documented scenario.

### Tier 2 — stretch, still in the plan

Map view; offline-first / low-connectivity mode with a sync queue; SMS/USSD-style alert **simulation**; multi-component support (platelets first); scenario replay comparing policies; cold-chain flags from `temperature_logs` and `power_outages`; LLM plain-language explanations with a deterministic fallback; country/config settings; dashboard polish; Docker Compose / public demo hosting; Playwright path.

## Hour-by-hour (EAT)

Parallel tracks: Timi (API/state), Blessings (forecast/eval/sim), Brayan (data/eligibility/cold-chain), Dan (UI/map/demo). Pair at integration points.

| EAT | WAT | What | Exit condition |
|---|---|---|---|
| 15:30–16:00 | 13:30–14:00 | If Q&A is still running, one teammate attends (ask about sender reserve, receiving-readiness, and what evidence should block a transfer when safety or receipts are missing). Others: confirm tiers, create/push skeleton if not already, inspect `data/raw/DATA_DICTIONARY.md`, agree snapshot date 2026-10-31. | Shared as-of convention written; question list asked or queued |
| 16:00–18:00 | 14:00–16:00 | Brayan: load CSVs, schema, validation. Blessings: request aggregation and baseline scaffolding. Timi: FastAPI health, suggestion schema, empty action stubs. Dan: app shell, coordinator queue layout, design tokens. | `GET /health` and a validated database; UI shell renders a placeholder list that is clearly labelled "not computed yet" until hooked |
| 18:00–20:00 | 16:00–18:00 | Hook eligibility + first real suggestions on the snapshot. One card with a traceable reason. Dan replaces placeholders with API data. Start accept path if possible. | **Check-in 1 (20:00):** two honest lines — what actually runs, what is blocked. No static cards presented as computation |
| 20:00–22:00 | 18:00–20:00 | Finish Accept / Change / Reject, reservation, audit. Blessings runs or prepares the frozen forecast split. Brayan starts cold-chain flag queries. Dan starts sender/receiver views. | Reserved unit cannot be suggested twice |
| 22:00–00:00 | 20:00–22:00 | Dispatch and receipt states. Fallback policy endpoint. Frontend wires model-off toggle. Blessings continues evaluation run. Dan sketch map. | Approval-to-receipt works on at least one fixture |
| 00:00–03:00 | 22:00–01:00 | Preferred short rest if people need it. Anyone staying online works **Tier 2 only** on a branch: map tiles, LLM explanation stub, settings file, simulator scaffolding, PWA shell. Do not break `main`. | `main` remains demoable |
| 03:00–06:00 | 01:00–04:00 | Clean-start run. Recompute frozen metrics. Critical fixes. Hook fallback in the UI. Merge map if stable. **Check-in 2 (06:00):** honest status and an explicit Tier 2 cut list if needed | Metrics table exists or the blocker is named |
| 06:00–08:00 | 04:00–06:00 | Tests, README, architecture diagram. Simulator / LLM / offline queue / SMS simulation / platelets — as far as they are stable. Dan locks the demo script and fixture IDs. | One person can follow README from a clean clone (minus secrets) |
| 08:00–10:00 | 06:00–08:00 | Rehearse. **Record the video by 10:00.** Finalise eight slides. Verify duration ≤ 3 minutes. | Video file and slide link exist |
| 09:30 | 07:30 | **Merge freeze** except critical fixes | |
| 10:00–11:00 | 08:00–09:00 | Repo public; video and slides permissions; baseline numbers in README; AI-tool declaration; Friday attendance. Submit early if complete. | Form contents ready |
| 11:15–12:00 | 09:15–10:00 | **Submission freeze** and buffer. Report technical problems to organisers before 12:00 if the form fails. Do not assume an extension. | Submission confirmed |

## Merge freezes

See also `docs/GITHUB_RULES.md`. Freeze feature merges at 09:30 EAT before recording and at 11:15 EAT before submit.

## Cut order (only if Tier 1 is at risk)

1. Public hosting and extra visual polish.
2. SMS/USSD simulation.
3. Platelets / extra components.
4. LLM explanations (keep deterministic text).
5. Full-year or large simulator expansions (keep a small policy comparison if it already runs).
6. Offline sync (keep "pending" as a labelled limitation if needed).
7. Map (keep table + facility ids).
8. Never cut eligibility, human decisions, baseline numbers, fallback, README, video, or slides.

## Demo story (target, 3 minutes)

0:00–0:20 Named regional stock coordinator; synthetic snapshot count of near-expiry eligible RBC and sites below target.
0:20–0:50 One computed card: ids, reserve, gap, expiry, travel time, data age, uncertainty.
0:50–1:30 Accept one, change one, reject one (or reset fixture). Show reservation and audit. Show an invalid move blocked.
1:30–1:50 Sender dispatch; receiver receipt. State that receipt is not transfusion release.
1:50–2:15 Baseline vs candidate RMSE, period, sample count. Say so if the candidate loses.
2:15–2:40 Model off; fallback; complete the same review. If Tier 2 is ready: 2G/offline pending, or a cold-chain flag, or the map — only if it is real.
2:40–3:00 Architecture, main limitation, Friday attendance, end on time.
