# Architecture decision log

Record decisions as they are taken. Date in EAT. A later official organiser message can override a hackathon-rule decision; if that happens, add a new ADR rather than silently editing history.

## ADR-001 — Eight slides, official template

- **Status:** Accepted (10 November 2026, planning).
- **Context:** The Technical Phase Brief says "up to 8 slides" and to use the official template. The 10 November kickoff recap from hany@talo.africa says "8 to 10 slides."
- **Decision:** Produce **eight slides** on the official Google Slides template. Do not add a ninth or tenth slide unless organisers confirm in writing that 10 is allowed.
- **Consequences:** `docs/DEMO_AND_SUBMISSION.md` and the slide issue follow this. Dan owns layout; factual claims still need team review.

## ADR-002 — No pre-window metrics or pre-written application code

- **Status:** Accepted.
- **Context:** Team pitches (including Blessings's later document and Timi's Notion-era notes) contain figures that the 10 November evaluation asked us not to reuse unverified (among others: 11.3% RMSE improvement, 22.3% unmet, 20.3% expiry, AUC claims, "50% general improvement," and waste or exposure counts that shift with the denominator). Official rules also disqualify pre-existing projects; every application line must be written in the window.
- **Decision:** Recompute every result in-window from `data/raw/`. Pitch and evaluation scores are not product metrics. This repo starts with documentation and empty implementation folders only. Do not paste pre-window analysis scripts in as if they were already accepted production code.
- **Consequences:** README, slides and video show only in-window numbers, or they omit the number.

## ADR-003 — Ambitious Tier 2, but Tier 1 never yields

- **Status:** Accepted.
- **Context:** The 10 November evaluation recommended a reduced expiry-aware review queue and cut map, offline, SMS, multi-component, simulation scale, and similar features for 24-hour feasibility. The team then chose **not** to minimise scope: people will stay online and are aiming to win.
- **Decision:** Ship the evaluation's **must-ship core as Tier 1**. Plan the cut features as **Tier 2** (map, offline-first sync queue, SMS/USSD-style alert simulation, platelets and other components, scenario replay, cold-chain flags, LLM explanations with deterministic fallback, country/config, hosting polish). If time slips, follow the cut order in `docs/IMPLEMENTATION_PLAN.md`. Never cut eligibility, human control, the 28-day baseline, the fallback, or submission artefacts.
- **Consequences:** Issues and the hour plan include Tier 2. Check-ins must report what actually runs, not the aspiration.

## ADR-004 — Equal team, no team lead

- **Status:** Accepted.
- **Context:** The team is four people with different strengths. Timi and Blessings are the most available.
- **Decision:** No team-lead title. Ownership is by area (`docs/ROLES.md`). Heavier tracks go to Timi (backend, state machine, LLM layer, deployment) and Blessings (forecast, evaluation, simulator, reproducibility). Brayan and Dan have full ownership of their areas. Shared work (README, tests, demo) is everyone's.
- **Consequences:** `CODEOWNERS` and issues use area ownership, not a manager. Check-in speakers rotate or are agreed, not appointed as leads.

## ADR-005 — Demand, snapshot, and live queue conventions

- **Status:** Accepted (from the adopted evaluation, recorded here).
- **Context:** There is no demand table. `daily_stock` is inventory. Final unit locations leak the future.
- **Decision:** Demand = `requests.units_requested`. Live queue from a verified closing snapshot (planned 31 October 2026). Forecast features use only requests strictly before each origin. Learn 1 Nov 2025–30 Apr 2026, calibrate May–Jun 2026, evaluate weekly origins 1 Jul–21 Oct 2026. Hospital filter = the seven hospital `facility_type` values listed in `docs/DATA.md` (32 sites), unless we document a change.
- **Consequences:** Pipeline and evaluation issues implement this exactly.

## ADR-006 — Remaining shelf-life rules are configurable

- **Status:** Accepted.
- **Context:** Some local policies use a 10-day remaining red-cell life; Australian national guidance discusses a 7–14 day remaining-life planning range. These are not a single international law. See `docs/DOMAIN.md`.
- **Decision:** Encode remaining-life limits in settings, with a documented default chosen in-window. Do not comment the code as "WHO/AABB requires 10 days."
- **Consequences:** Settings API (Tier 2) and eligibility (Tier 1) share the same config object even if the UI comes later.

## ADR-007 — MIT for our code; dataset terms unchanged

- **Status:** Accepted.
- **Context:** The official starter data has usage terms but no SPDX licence.
- **Decision:** `LICENSE` is MIT for original team code and docs we write. Official CSVs, `gen.py`, kit docs and logos remain under their official terms (`data/raw/README.md`). We do not relicense the dataset.
- **Consequences:** README states both.

## ADR-008 — Code licence and AI-tool declaration live in the official README

- **Status:** Accepted.
- **Context:** The official README template requires an AI-tool declaration. Tools are allowed if declared.
- **Decision:** Declare every AI coding tool actually used, in the README section, before submission. Do not hide agent use.
- **Consequences:** Update the README during the window, not after the form is sent, as a living list.

## Proposed, not yet decided

- Default numeric sender reserve and recipient target (ask at Q&A if still open; otherwise pick a documented, conservative rule and say it is our choice).
- Public hosting vs local Docker-only for the judged demo.
- MapLibre vs Leaflet as the shipped map.
- Whether a small nearest-site transfer comparison is pulled into Tier 1 if the harness is early.
