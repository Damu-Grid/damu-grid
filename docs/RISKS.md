# Risks and mitigations

Ordered by impact on a winning, honest submission.

| Risk | Why it matters | Mitigation | Owner |
|---|---|---|---|
| Scope eats the video or README | Demo/readiness is 10% but a missing video is a failed submission | Tier 1 first; cut order in `IMPLEMENTATION_PLAN.md`; merge freezes 09:30 and 11:15 EAT | All |
| Snapshot leakage (using final unit locations as historical stock) | Invalid evaluation; judging "AI and data approach" | Closing snapshot only; documented as-of; evaluator is read-only | Blessings, Brayan |
| Treating `units_issued` or `daily_stock` as demand | Wrong baseline; conflicts with official dictionary | Demand = `units_requested` from `requests` | Blessings |
| Facility-name joins (14% messy names) | Broken transfers and maps | Join only on `facility_id` | Brayan, Dan |
| Double reservation / lost audit | Broken workflow; lost trust | One transactional action function; versions; tests | Timi |
| Presenting a guess as fact | Honesty rule and disqualification risk | Deterministic reason fields; LLM may only rephrase those fields; uncertainty labelled | Timi |
| Reusing pitch or early Blessings metrics | False results | Recompute in-window; pitch numbers stay out of README and slides | Blessings |
| Claiming clinical clearance or lives saved | Rule and ethics breach | README and demo language reviewed; no transfusion release in the API | All |
| Uploading secrets | Disqualification / security | `.env` gitignored; `.env.example` names only; PR checklist | All |
| Official SQLite missing from the zip | Wasted time hunting a file | Build from CSVs; do not wait for `blood_system.sqlite` | Brayan |
| Messy temperature values (−99.0, 99.9, 0.0) | False cold-chain flags | Follow official glitch guidance; do not treat glitches as clinical events | Brayan |
| LLM or SMS provider down or unpaid | Demo freeze | Deterministic explanations always work; SMS is a sandbox or mock | Timi, Dan |
| Slide-count confusion (8 vs 8–10) | Formal non-compliance | ADR-001: eight slides, official template | Dan |
| Time-zone mistakes at check-in or submit | Missed gates | All deadlines shown in EAT and WAT | All |
| Pre-window code appearing in the repo | Disqualification | Empty implementation folders at start; first app commits after 12:00 EAT Tue; no copy-paste of Blessings's earlier scripts as if already accepted | All |
| Connectivity during the demo | African-conditions criterion | Fallback policy, optional offline queue, recorded video backup | Timi, Dan |
| Uneven integration | UI shows invented cards | No placeholder numbers in the recorded demo; hook or omit | Dan, Timi |
| Git history not proving in-window work | Organiser doubt | Incremental commits, PRs, no force-push on `main` | All |
| Dataset larger than expected for GitHub | Awkward large-file issues | Current raw tree including zip is under 90 MB; do not add derived copies to git | Brayan |

If a risk materialises, write the limitation in the README rather than hiding it.
