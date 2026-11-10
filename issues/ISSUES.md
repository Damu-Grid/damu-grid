# Planned GitHub issues

Local drafts only. **Do not open these on GitHub, assign people remotely, or push**, until a teammate explicitly does so. There is no team lead; assignees are area owners. Timi and Blessings carry more hours because they are the most available, not because they outrank Brayan or Dan.

Estimates are **effort hours**, and tracks run in **parallel** during the window (plan start Tue 10 Nov 2026, 15:30 EAT through Wed 11 Nov 2026, 12:00 EAT). They are not an 82-hour sequential backlog. Current estimates sum to 82.5 effort hours across four people working in parallel.

## Hours-per-person summary

| Teammate | GitHub | Tier 1 | Tier 2 | Total |
|---|---|---:|---:|---:|
| Timi (Agoro Oluwatimilehin Teslim) | `drizzy765` | 17.5 | 6.5 | 24 |
| Blessings Mambwe | `bleymambwe` | 16 | 8 | 24 |
| Brayan Sorgho | `Sorghobrayan-dotcom` | 14 | 3.5 | 17.5 |
| Dan Boumba | `Dan-Boumba` | 13 | 4 | 17 |
| **Sum of estimates** |  | **60.5** | **22** | **82.5** |

Shared issues DG-38 and DG-39 are split 0.5 h each across the four teammates.

Milestones: **Check-in 1 — Tue 20:00 EAT**; **Check-in 2 — Wed 06:00 EAT**; **Recording — Wed 10:00 EAT**; **Submit — Wed 12:00 EAT**.

## Tier 1 — must ship

### DG-01: Load official CSVs and validate against the data dictionary

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 3 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `pipeline`
- **Depends on:** none
- **Files:** `pipeline/`, `data/processed/`, `docs/DATA.md`

**Context.** The official zip has 11 CSVs plus docs. `blood_system.sqlite` is listed in the dataset README but is not in the zip. Build from CSVs. Column names and meanings are only those in `data/raw/DATA_DICTIONARY.md` and `docs/DATA.md`. Do not modify `data/raw/`.

**Acceptance criteria.**
- A documented command reads every official CSV from `data/raw/` and writes a derived store under `data/processed/` (gitignored).
- Validation reports row counts that match `docs/DATA.md` (or explains a discrepancy).
- Unknown or mistyped columns fail loudly; facility joins use `facility_id` only.
- No files under `data/raw/` are changed.

### DG-02: Define the SQLite schema for snapshot, units, requests, routes and the action store

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `pipeline`
- **Depends on:** DG-01
- **Files:** `pipeline/`, `docs/ARCHITECTURE.md`

**Context.** Timi's API and Blessings's evaluator must share one schema. Recommendation logic stays out of movement tables. Include version/reservation fields the state machine will need, even if the API writes them later.

**Acceptance criteria.**
- Schema is documented and created by a repeatable command.
- Official columns keep their real names; invented columns are clearly prefixed or documented.
- Timi and Blessings can consume the same file without inventing a second schema.

### DG-03: Build the 31 October 2026 closing snapshot without leakage

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `pipeline`
- **Depends on:** DG-01, DG-02
- **Files:** `pipeline/`, `docs/DATA.md`, `docs/EVALUATION.md`

**Context.** The live queue uses an explicit closing snapshot (planned as-of: end of 31 October 2026), from `daily_stock` for that date plus `units` that are `in_stock` at `current_facility_id` with `expiry_date` still in the future as of that time. Do not reconstruct earlier dates from final year-end locations.

**Acceptance criteria.**
- Snapshot exposes as-of timestamp, unit ids, facility, component, group, expiry, status, and exposure flag.
- A test or documented check shows we are not using post-as-of receipts as if they were already on the shelf at as-of.
- Row counts and filters are written down for the demo.

### DG-04: Implement the RBC eligibility engine

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 3 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `pipeline`
- **Depends on:** DG-03
- **Files:** `pipeline/`, `docs/DATA.md`, `docs/DOMAIN.md`

**Context.** A unit is suggestable only if it passes the Tier 1 rules in `docs/DATA.md`: RBC, known exact group, `in_stock`, expiry after expected arrival, not `temp_excursion_exposed`, not already reserved or in transit, sender reserve respected, recipient gap documented, route present. Missing safety evidence is conservative (do not suggest). Remaining-life minima are config, not 'WHO law'.

**Acceptance criteria.**
- A callable function returns eligible units plus a reason for each exclusion category.
- Exposed, expired, unknown-group, reserved, and unrouted units are excluded, with tests.
- Rules read from a shared config object even if the settings UI is later (ADR-006).

### DG-05: Handle official data-quality quirks in the pipeline

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `pipeline`
- **Depends on:** DG-01
- **Files:** `pipeline/`, `docs/DATA.md`

**Context.** Official README: messy facility names on ~14% of requests, 5% emergency unknown groups, ~3% transfers missing `received_at`, 60 temperature glitches (−99.0, 99.9, 0.0), logger drop-outs. These must not silently become clinical facts.

**Acceptance criteria.**
- Requests are keyed by `facility_id`, never `facility_name_raw`.
- Unknown groups remain unknown.
- Missing `received_at` is visible as incomplete evidence, not a fabricated receipt time.
- Temperature glitch values are classified as glitches, not excursions, unless a documented rule says otherwise.

### DG-06: Pipeline and eligibility tests

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `pipeline`, `testing`
- **Depends on:** DG-04, DG-05
- **Files:** `tests/`, `pipeline/`

**Context.** Judges and teammates must be able to rerun validation. Safety filters are not optional tests.

**Acceptance criteria.**
- pytest covers row-count smoke checks, eligibility exclusions, and snapshot as-of behaviour.
- Command is documented in `pipeline/README.md` or `tests/README.md`.

### DG-09: Aggregate hospital demand from requests.units_requested

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `forecasting`
- **Depends on:** DG-01
- **Files:** `forecasting/`, `docs/EVALUATION.md`, `docs/DATA.md`

**Context.** There is no demand table. Use `units_requested`, not `units_issued`. Tier 1: `component_requested = RBC`, known exact `patient_blood_group`, hospital `facility_type` values in `docs/DATA.md` (32 sites: county_referral, county_hospital, national_referral, private_hospital, maternity_hospital, mission_hospital, sub_county_hospital). Disclose excluded unknown-group rows (442 in the file).

**Acceptance criteria.**
- A repeatable function returns daily and period requested units by facility_id and blood group.
- Missing request rows are not silently treated as zero unless the completeness assumption is documented.
- Tests cover the hospital filter and the unknown-group exclusion count.

### DG-10: Implement the mandatory 28-day average baseline

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `forecasting`
- **Depends on:** DG-09
- **Files:** `forecasting/`, `docs/EVALUATION.md`

**Context.** For each hospital and known group: seven-day predicted requested units = 7 × (requested RBC units in the preceding 28 calendar days ÷ 28). This is the submission's required simple baseline.

**Acceptance criteria.**
- The formula is implemented exactly, with the origin-date window using only requests strictly before the origin.
- Unit test of the arithmetic on a tiny fixture, independent of the full CSV.

### DG-11: Implement the pooled candidate demand estimator

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 3 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `forecasting`
- **Depends on:** DG-09
- **Files:** `forecasting/`, `docs/EVALUATION.md`

**Context.** Adopted candidate: seven-day hospital total RBC demand from an expanding historical daily mean, allocated with network-wide known-group request proportions from earlier history. Statistical only; no LLM. Freeze the specification before reading July–October scores.

**Acceptance criteria.**
- Estimator is a documented function with frozen config.
- Uses only pre-origin requests.
- If it loses to the baseline, the live API can still be pointed at the baseline.

### DG-12: Build the frozen forecast evaluation harness (RMSE, MAE, sample size)

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 3.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `forecasting`
- **Depends on:** DG-10, DG-11
- **Files:** `forecasting/`, `docs/EVALUATION.md`

**Context.** Learn 1 Nov 2025–30 Apr 2026; calibrate May–Jun 2026; evaluate seven-day forecasts at weekly origins from 1 Jul 2026 through 21 Oct 2026. Primary metric: RMSE across hospital × known group × origin, in requested units. Also MAE, sample count, optional O-negative error check. Report both models. Label synthetic. Never reuse pitch figures.

**Acceptance criteria.**
- One command rebuilds the table from `data/raw/` into `data/processed/` plus a short README snippet.
- Both baseline and candidate are shown, even if the candidate loses.
- Split dates and filters are frozen in config before evaluation outcomes are inspected for tuning.

### DG-13: Calibrate and report a residual upper-bound uncertainty label

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `forecasting`
- **Depends on:** DG-12
- **Files:** `forecasting/`, `docs/API_SPEC.md`

**Context.** The adopted design asked for a non-negative upper prediction bound from May–June residuals, coverage measured not asserted, labelled as a model estimate rather than a clinical probability. This supports suggestion-card honesty.

**Acceptance criteria.**
- Bound method, nominal level, and measured coverage (if computed) are documented.
- API-facing fields match the `uncertainty` object in `docs/API_SPEC.md`.
- Copy never calls the bound a clinical probability.

### DG-14: Forecast tests and a one-command reproducibility pack

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 1 · **Estimate:** 2.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `forecasting`, `testing`
- **Depends on:** DG-12, DG-13
- **Files:** `forecasting/`, `tests/`, `notebooks/`, `scripts/`

**Context.** Reproducibility is part of Blessings's track and of judging 'AI and data approach'. A notebook may explore, but the demo path must call package code.

**Acceptance criteria.**
- pytest covers baseline arithmetic, no-future-leakage on a fixture, and metric aggregation.
- README documents the exact command, frozen config, and that results are synthetic.
- Any useful notebook code is promoted into `forecasting/`.

### DG-18: Bootstrap FastAPI with /health and /snapshot

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-02
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** Empty stubs are fine until the database exists, but by check-in 1 `/health` should run and `/snapshot` should report as-of time, table counts and product scope from Brayan's store once it lands. Python 3.11+, uv, Ruff.

**Acceptance criteria.**
- Local server starts from a documented command.
- `GET /health` returns success.
- `GET /snapshot` exposes as-of, counts, and RBC scope without inventing metrics.
- `.env.example` names only; no secrets committed.

### DG-19: Suggestion ranking API (expiry-aware, demand-informed)

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 3 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-04, DG-09, DG-18
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** One suggestion object as specified: unit IDs, source, destination, component/group, as-of, expiry, route time, reserve, recipient gap, deterministic reason, uncertainty, policy, fallback flag. Ranking uses eligibility + demand (or baseline if the candidate is not ready) + expiry + typical_travel_hours. Recommendation logic is separate from movement records.

**Acceptance criteria.**
- `GET /suggestions` returns real computed cards from the snapshot, or an error — never a static fake card labelled as computed.
- Payload matches `docs/API_SPEC.md` fields (nulls allowed where not yet computed, with honest reasons).
- Check-in 1 can show at least one traceable card.

### DG-20: State machine: Accept / Change / Reject with atomic reservation

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 3.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-19
- **Files:** `backend/`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`

**Context.** One transactional action function writes the decision and audit row. Reservations are version-checked. Duplicate accept of the same unit fails. Change reruns eligibility and cancels an existing reservation if needed. Lease is short (design note: at most 30 minutes, configurable). Roles: only coordinator for these three actions.

**Acceptance criteria.**
- Accept, Change and Reject endpoints work with `event_id` idempotency.
- A reserved unit cannot appear as available in a later suggestion list.
- Stale versions return 409; wrong role returns 403; eligibility failure returns 422.
- Tests cover double-accept and change-after-reserve.

### DG-21: Dispatch and receipt transitions

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-20
- **Files:** `backend/`, `docs/ARCHITECTURE.md`

**Context.** Sender rechecks and dispatches; receiver confirms. A blocked or expired reservation cannot dispatch. Incomplete cold-chain evidence at receipt never clears a quarantine and never implies transfusion release. A dispatched transfer cannot be silently deleted.

**Acceptance criteria.**
- `POST /moves/{id}/dispatch` and `/receive` enforce roles and states.
- ReceivedHeld / Quarantined behaviour is implemented or an honest subset is documented if cold-chain flags are not ready.
- API copy and errors never say transfusion release.

### DG-22: Append-only audit trail API

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-20
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** Every accept, change, reject, reserve, cancel, dispatch, receipt and settings change is attributable. Required for trust and for the demo.

**Acceptance criteria.**
- `GET /audit` can filter by unit, move, actor and time.
- Audit rows are not updated in place; corrections are new rows.
- A fixture shows the path of one accepted move end to end.

### DG-23: Rule-based fallback suggestion policy

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `backend`
- **Depends on:** DG-19, DG-04
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** If the estimator is down or the user toggles model-off, serve nearest eligible site plus a simple historical demand rule, with the same eligibility and human gates. `fallback: true` on the payload. May also auto-offer fallback on 503.

**Acceptance criteria.**
- `GET /suggestions?policy=fallback` (and `policy=nearest` if distinct) returns eligible suggestions without the candidate estimator.
- Accept/Change/Reject still work on fallback cards.
- A test or demo toggle proves the path without the model process.

### DG-24: Backend state-machine and API tests

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `backend`, `testing`
- **Depends on:** DG-21, DG-22, DG-23
- **Files:** `tests/`, `backend/`

**Context.** Safety and workflow tests travel with the API. This is also evidence of in-window engineering quality.

**Acceptance criteria.**
- pytest covers reservation conflicts, wrong-role 403, lease expiry or cancel, fallback flag, and idempotent event_id.
- Command documented for a clean checkout.

### DG-25: Docker Compose path and optional public hosting

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `backend`, `deployment`
- **Depends on:** DG-18
- **Files:** `backend/`, `frontend/`, `docs/ARCHITECTURE.md`

**Context.** Compose is the preferred reliable 'how to run it' for judges (Tier 1 if time; otherwise a clearly documented uv/pnpm path). Public Render/Vercel hosting is Tier 2 and must not delay the 10:00 EAT recording.

**Acceptance criteria.**
- README can start the stack without secrets in git.
- If Compose is not finished, the manual path is complete and Compose is listed as unfinished, not faked.
- Any public URL is optional and does not block the video.

### DG-30: Next.js app shell, design tokens and coordinator queue layout

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 2.5 h
- **Milestone:** Check-in 1 — Tue 20:00 EAT
- **Labels:** `tier-1`, `frontend`
- **Depends on:** none
- **Files:** `frontend/`, `docs/DESIGN.md`

**Context.** Operations workbench, not a marketing page. Follow `docs/DESIGN.md`: high contrast, semantic colour for expiry/safety, placeholder list clearly labelled if not yet hooked to the API. shadcn/ui + Tailwind.

**Acceptance criteria.**
- App starts from a documented command and renders the queue layout.
- Placeholders cannot be mistaken for computed suggestions in a screenshot.
- Design tokens cover text, surfaces, expiry/fallback chips, and focus states.

### DG-31: Wire the review screen: Accept / Change / Reject

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 3 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `frontend`
- **Depends on:** DG-30, DG-20
- **Files:** `frontend/`, `docs/DESIGN.md`, `docs/API_SPEC.md`

**Context.** Each card shows the fields in `docs/DESIGN.md` and `docs/API_SPEC.md`. Actions require a short reason. Keyboard path for the recorded demo. Hook real API data; do not invent numbers.

**Acceptance criteria.**
- Queue loads from `GET /suggestions`.
- Accept, Change and Reject call the API and reflect new state, including 409 conflicts.
- Uncertainty and synthetic labels are visible.
- Playwright or a rehearsed keyboard path covers open → accept.

### DG-32: Sender dispatch and receiver confirmation views

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 2 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-1`, `frontend`
- **Depends on:** DG-31, DG-21
- **Files:** `frontend/`

**Context.** Role-appropriate screens. On-screen language: receipt is not transfusion release. Blocked or expired reservations cannot be dispatched.

**Acceptance criteria.**
- Demo accounts can complete dispatch and receipt on a fixture move.
- Audit or state history is visible on the move.
- Copy review done with Timi so API errors surface clearly.

### DG-33: Evaluation panel and modest dashboard

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `frontend`
- **Depends on:** DG-30, DG-12
- **Files:** `frontend/`, `docs/EVALUATION.md`

**Context.** Show the frozen baseline vs candidate table, period, sample size, and a synthetic badge. No unverified 'units saved' KPI. Forecast numbers come from the API or a committed snippet generated in-window, not from pitches.

**Acceptance criteria.**
- Both models appear, even if the candidate loses.
- No pitch metrics (11.3% RMSE, etc.) are hardcoded.
- Dashboard counts, if shown, match `/snapshot` or are omitted.

### DG-36: Eight official-template slides

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `demo`, `docs`
- **Depends on:** DG-33
- **Files:** `slides/`, `docs/DEMO_AND_SUBMISSION.md`

**Context.** ADR-001: eight slides, official template, no ninth unless organisers confirm. Timi and Blessings sign off on architecture and evaluation slides. Confirm logo use before adding kit logos.

**Acceptance criteria.**
- Eight slides, official template, view-only link ready.
- Only in-window or official-README figures; synthetic labelled.
- Story matches `docs/DEMO_AND_SUBMISSION.md`.

### DG-37: Record the ≤3-minute demo video

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 1 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `demo`
- **Depends on:** DG-32, DG-23, DG-36
- **Files:** `slides/`, `docs/IMPLEMENTATION_PLAN.md`, `docs/DEMO_AND_SUBMISSION.md`

**Context.** Record by Wed 11 Nov 2026, 10:00 EAT. Script in the implementation plan. Show running software. Skip Tier 2 that does not actually run. Say 'synthetic official starter dataset' early. End before 3:00.

**Acceptance criteria.**
- Video file or shareable link, anyone-with-link can view, duration ≤ 3 minutes.
- Includes accept/change/reject (or a documented subset that still shows human control), fallback or an honest skip, and the baseline table if computed.
- No clinical-clearance or lives-saved claims.

### DG-38: Assemble the official README, architecture diagram and AI-tool declaration

- **Assignee:** `drizzy765`, `bleymambwe`, `Sorghobrayan-dotcom`, `Dan-Boumba` (Timi (Agoro Oluwatimilehin Teslim), Blessings Mambwe, Brayan Sorgho, Dan Boumba)
- **Tier:** 1 · **Estimate:** 2 h (split {'drizzy765': 0.5, 'bleymambwe': 0.5, 'Sorghobrayan-dotcom': 0.5, 'Dan-Boumba': 0.5})
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-1`, `docs`, `demo`
- **Depends on:** DG-12, DG-19, DG-25
- **Files:** `README.md`, `docs/ARCHITECTURE.md`

**Context.** The root README already follows the official template with placeholders. Before recording, fill what actually works, how to run it, baseline results (computed in-window), African-conditions notes, team, and every AI tool used. Everyone contributes; Dan and Timi tidy structure; Blessings supplies the metrics snippet; Brayan supplies data/run commands.

**Acceptance criteria.**
- Template sections are complete enough to submit.
- AI-tool declaration lists tools actually used.
- Architecture diagram exists (export mermaid or a committed image).
- No secrets, no pitch metrics, synthetic labelled.

### DG-39: Demo rehearsal, merge freezes and submission-form checklist

- **Assignee:** `drizzy765`, `bleymambwe`, `Sorghobrayan-dotcom`, `Dan-Boumba` (Timi (Agoro Oluwatimilehin Teslim), Blessings Mambwe, Brayan Sorgho, Dan Boumba)
- **Tier:** 1 · **Estimate:** 2 h (split {'drizzy765': 0.5, 'bleymambwe': 0.5, 'Sorghobrayan-dotcom': 0.5, 'Dan-Boumba': 0.5})
- **Milestone:** Submit — Wed 12:00 EAT
- **Labels:** `tier-1`, `demo`
- **Depends on:** DG-37, DG-38
- **Files:** `docs/DEMO_AND_SUBMISSION.md`, `README.md`

**Context.** Rehearse the script. Freeze feature merges at 09:30 EAT (recording) and 11:15 EAT (submit). One agreed person fills the official form. Public repo, video and slides permissions, Friday 13 Nov 16:00–18:00 EAT attendance confirmation. Prefer submit by 11:00 EAT. This issue does not authorise an agent to submit or email anyone.

**Acceptance criteria.**
- Checklist in `docs/DEMO_AND_SUBMISSION.md` is ticked or blockers are named.
- Repo is ready to be made public by a human (no `.env`, no secrets).
- A speaker for the form is agreed at the 06:00 check-in.

## Tier 2 — stretch, still in the plan

### DG-07: Cold-chain and power-outage flags from temperature_logs and power_outages

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 2 · **Estimate:** 2.5 h
- **Milestone:** Check-in 2 — Wed 06:00 EAT
- **Labels:** `tier-2`, `pipeline`
- **Depends on:** DG-03, DG-05
- **Files:** `pipeline/`, `docs/API_SPEC.md`, `docs/DOMAIN.md`

**Context.** Tier 2: surface warnings from `temperature_logs` and `power_outages` (and existing `temp_excursion_exposed` / cool-box fields) onto suggestion cards. Fridge range in the dictionary for RBC/WB is 2–6°C; cool-box max above 10°C is an excursion. Flags never auto-clear a quarantine.

**Acceptance criteria.**
- A documented query flags units or sites with evidence of excursion, outage without backup, or logger gaps, with the evidence timestamp.
- Glitch readings are not treated as clinical events.
- API or table contract matches `GET /flags/cold-chain` in `docs/API_SPEC.md` (Timi can wrap it).
- Incomplete evidence cannot be used to mark a unit safe.

### DG-08: Extend eligibility and shelf-life config to platelets (and hook other components)

- **Assignee:** `Sorghobrayan-dotcom` (Brayan Sorgho)
- **Tier:** 2 · **Estimate:** 1 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `pipeline`
- **Depends on:** DG-04
- **Files:** `pipeline/`, `docs/DATA.md`

**Context.** Model shelf lives: RBC 42d, WB 35, PLT 5, plasma/cryo 1 year. Requests include 378 PLT rows. Platelets need a tighter remaining-life and routing policy than RBC. Only enable in the live queue when Blessings's multi-component demand path and Timi's API settings are ready enough to demo honestly.

**Acceptance criteria.**
- Config carries per-component shelf life and eligibility.
- PLT can be computed without breaking the RBC default scope.
- If not demo-ready, the code stays behind a flag and the README does not claim multi-component support.

### DG-15: Scenario replay simulator comparing policies

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 2 · **Estimate:** 4 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `simulation`
- **Depends on:** DG-03, DG-04, DG-09
- **Files:** `simulation/`, `docs/EVALUATION.md`

**Context.** Compare policies over documented seven-day synthetic scenarios seeded from official closing inventory and earlier request rates. Added demand is synthetic, not observed November demand. This must not displace the mandatory forecast benchmark.

**Acceptance criteria.**
- At least one documented scenario runs two policies with shared assumptions held constant.
- Outputs unmet, expired, moved units and route batches separately.
- Seeds and assumptions are written down. No lives-saved or money claims.

### DG-16: Nearest-site-first versus expiry-aware transfer comparison

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `simulation`
- **Depends on:** DG-15
- **Files:** `simulation/`, `docs/EVALUATION.md`

**Context.** Optional stronger comparison from the adopted evaluation. If the harness is early and stable, this can appear in the demo; otherwise keep it in docs as not finished. Same safety rules as the live engine.

**Acceptance criteria.**
- Nearest eligible recipient first is implemented as a policy, not a hardcoded 'winner'.
- Results sit beside, not instead of, the 28-day forecast table.
- Limitations of the synthetic scenario are stated in the README snippet.

### DG-17: Multi-component demand path for platelets

- **Assignee:** `bleymambwe` (Blessings Mambwe)
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `forecasting`
- **Depends on:** DG-09, DG-08
- **Files:** `forecasting/`

**Context.** Official requests include 378 PLT and 843 FFP rows. Platelets' 5-day model shelf life changes both demand windows and transfer value. Only surface in the product if eligibility and UI can show it honestly.

**Acceptance criteria.**
- Demand aggregation can be filtered to PLT without changing RBC defaults.
- If included in the demo, sample sizes are disclosed and labelled synthetic.
- FFP/CRYO are optional hooks, not a requirement for this issue.

### DG-26: LLM plain-language explanations with deterministic fallback

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `backend`
- **Depends on:** DG-19
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** Optional rewrite of `reason_deterministic`. The LLM must only rephrase provided fields; it must not invent stock, demand, or clinical claims. If the provider is down, the deterministic text remains on the card.

**Acceptance criteria.**
- `reason_deterministic` always present on suggestions.
- Optional `reason_llm` echoes the same numbers; mismatch is rejected or discarded.
- No API key in git. Demo works with the model off.

### DG-27: Offline sync queue API (idempotent pending actions)

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `backend`
- **Depends on:** DG-20
- **Files:** `backend/`, `docs/API_SPEC.md`

**Context.** Pairs with Dan's PWA outbox. `POST /sync/queue` accepts pending events; conflicts never drop a quarantine. Idempotent by `event_id`.

**Acceptance criteria.**
- Pending, accepted, and rejected-on-reconcile states are queryable.
- Replayed event_ids do not double-reserve.
- A conflict involving safety evidence stays blocked.

### DG-28: SMS or USSD-style alert simulation backend

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 2 · **Estimate:** 1.5 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `backend`
- **Depends on:** DG-21
- **Files:** `backend/`, `docs/TOOLS_AND_SKILLS.md`

**Context.** Simulation only. Prefer Africa's Talking sandbox shape (username `sandbox`) or a local mock with the same contract. No real donor or patient contact. Alerts go to demo officer roles (coordinator/sender/receiver).

**Acceptance criteria.**
- `POST /alerts/simulate` records a message to a demo actor and never requires a production SMS key.
- README states that this is a simulation.
- No phone numbers from `donors.phone_last4` are messaged.

### DG-29: Country and config settings API

- **Assignee:** `drizzy765` (Timi (Agoro Oluwatimilehin Teslim))
- **Tier:** 2 · **Estimate:** 1 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `backend`
- **Depends on:** DG-18, DG-04
- **Files:** `backend/`, `docs/API_SPEC.md`, `docs/DECISIONS.md`

**Context.** Shelf lives, remaining-life minimum, reserves, language, branding. Eligibility and forecast should read the same config (ADR-006). Changes are audited.

**Acceptance criteria.**
- `GET /settings` and an audited `PUT /settings` exist or a file-based config is documented if PUT slips.
- Defaults are written down as our choices, not as international law.

### DG-34: Map view of sites, stock and expiry risk

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `frontend`
- **Depends on:** DG-30, DG-19
- **Files:** `frontend/`, `docs/DESIGN.md`

**Context.** Use `facilities.lat` / `lon`. MapLibre (preferred) or Leaflet. OpenStreetMap attribution is required. The table remains usable if tiles fail or on a 2G story. Merge only if stable before the 09:30 EAT freeze.

**Acceptance criteria.**
- Map renders official sites and can focus a suggestion's source and destination.
- OSM copyright is visible.
- The review flow works with the map hidden.

### DG-35: PWA / low-connectivity client outbox and settings/alert UI

- **Assignee:** `Dan-Boumba` (Dan Boumba)
- **Tier:** 2 · **Estimate:** 2 h
- **Milestone:** Recording — Wed 10:00 EAT
- **Labels:** `tier-2`, `frontend`
- **Depends on:** DG-31, DG-27
- **Files:** `frontend/`, `docs/DESIGN.md`

**Context.** Workbox + Dexie/IndexedDB outbox talking to Timi's `/sync/queue`. Pending-sync tray. Optional settings screen and SMS/USSD simulation preview (demo officers only). If the API slips, ship a labelled pending tray mock only if it is not presented as a completed sync.

**Acceptance criteria.**
- An action taken while the API is stopped is queued and can sync later without double-submit, or the limitation is labelled.
- No production SMS is sent from the browser.
- Settings, if present, do not claim unshipped behaviour.
