# Damu Grid — pitch deck text, page by page for the official template

Official Google Slides template: `1Nzz_kXVY6IlkHtiii3Rc2qIEDN9lGqjh_kcmtM-LYQ8` (10 pages: title + sections 01–09). Each section below matches one template page and fills its boxes in order. Replace `[TEAM NAME]` in every footer with **Damu Grid**.

**Slide count.** The brief allows up to 8 slides; ADR-001 says 8. The template has 10 pages. If the title page does not count, drop **04 Live demo**: the video and the live demo show it. If the title page counts, also drop **08 Pilot pathway**, and move its "We never" line to 06. Confirm with the organisers if unsure.

**Number rules.** Problem figures were computed in the window from `data/raw/` on 10 Nov 2026 (method notes at the end) or come from the official dataset README. `[[…]]` marks something to fill once it exists. Never fill one from a pitch document. Blessings signs off 06, and Timi signs off 05 and 07.

---

## Title page

- **Workflow line:** REDISTRIBUTION: EXPIRY-AWARE TRANSFER REVIEW
- **Project name:** DAMU GRID
- **Team name:** Team Damu Grid
- **One sentence:** Lets a regional blood centre's stock coordinator move red cells that would expire unused to a nearby hospital that will use them, with a person approving every move.
- **Footer:** BUILDING BETTER BLOOD SYSTEMS FOR AFRICA · DAMU GRID · DR CONGO, MOROCCO, NIGERIA, ZAMBIA

---

## 01 · The problem

**Headline:** Red cells expire on one shelf while a hospital a few hours away runs short

**Who feels it:** The stock coordinator at a regional blood transfusion centre, who decides each day what to send to which hospital.

**Where they work:** Hospital stock reports arrive late or not at all. 22 of 47 sites have only 3G or 2G, and power and fridge backup vary by site.

**How big it is:** **23%**
Share of red cell and whole blood units wasted (expired or discarded after temperature problems): 8,620 of 37,147, synthetic starter year 1 Nov 2025 – 31 Oct 2026.

---

## 02 · How it works today — Where the current workflow breaks

1. **Routine delivery.** The regional centre sends each hospital its usual order, 1–3 times a week. *Who:* centre stock coordinator, [[tool: confirm at the expert Q&A, e.g. order sheet or spreadsheet]].
2. **Stock sits.** Some hospitals over-order, others under-order. *Who:* hospital blood bank officer, [[local register]].
3. **Breaks here.** Nobody sees which units will expire unused or which nearby hospital will run short. *Breaks here:* units expire on the shelf. Only 177 of 35,181 transfers were deliberate rebalancing between sites.
4. **Emergency call.** A hospital that runs out calls the centre for an emergency delivery. *Who:* hospital officer, by phone.

**The cost today:** 8,620 red cell and whole blood units wasted, and 3,843 of 31,116 requested red cell units (12.4%) never issued. Emergency resupply takes a median of about 5 hours (dataset README).

---

## 03 · Our solution

**Headline:** DAMU GRID: SUGGESTS WHICH RED CELLS TO MOVE BEFORE THEY EXPIRE

| Person | System | AI recommends | Person approves |
|---|---|---|---|
| **Coordinator opens the morning queue** | **Eligible stock found** | **Best move suggested** | **Coordinator accepts** |
| Review queue, synthetic stock as of 31 Oct 2026 | Keeps only in-stock, known-group, not heat-exposed, unreserved units that arrive before expiry, leaving the sender its reserve | Ranks moves by expected use before expiry, from the demand forecast and travel time, with the reason and uncertainty on the card | Accept, Change or Reject with a reason. Accept reserves the units; the sender dispatches and the receiver confirms. All in the audit trail |

**Built in 24 hours:** [[fill at recording: e.g. review queue, Accept / Change / Reject, dispatch and receipt, audit trail, fallback rule, forecast vs baseline — only what runs end to end]]
**Mocked:** [[e.g. "nothing", or what is shown but not built]]

---

## 04 · Live demo · 5 minutes  *(drop first if limited to 8)*

**Headline:** ONE COORDINATOR, ONE TRANSFER, START TO FINISH

**We will show:** The coordinator's morning queue on synthetic stock. Accept one move, change one, reject one; the sender dispatches and the receiver confirms arrival and cool-box evidence.

**Watch for:** The reason and uncertainty on each card, the approval step, a blocked move, and the audit trail.

**Then:** We switch the AI off and finish the task anyway. *(Template text; keep as is.)*

---

## 05 · How it is built — Architecture and where it fits in ABBIS

**Diagram box:** [[paste `docs/architecture.png`]] Coordinator, sender and receiver → Next.js web app → FastAPI → eligibility engine, demand forecast and rule fallback → SQLite with an audit trail; official CSVs loaded through a validation pipeline.

**Stack:** Python, FastAPI, SQLite; Next.js and TypeScript web app; [[hosting, if any]].

**Place in ABBIS:** Extends stock and distribution. Reads unit, stock and request records; never touches lab release, compatibility or transfusion.

**Standards:** Conceptual mapping only: HL7 FHIR (BiologicallyDerivedProduct, SupplyRequest, SupplyDelivery), ISBT 128 unit identity, DHIS2 aggregates.

**Security:** Demo roles (coordinator, sender, receiver, safety officer) checked on every action; append-only audit trail; synthetic data only.

---

## 06 · The AI feature

**Headline:** WHICH HOSPITAL WILL USE THESE RED CELLS BEFORE THEY EXPIRE

- **Method:** A pooled demand forecast: each hospital's red cell demand from its request history, split by network-wide blood-group shares. It sets recipient gaps and sender reserves for ranking. Data: hospital requests, units, routes.
- **Why this?** Each card says in plain words why the move is suggested, using only computed numbers: expiry, travel time, the recipient's gap, the reserve the sender keeps, and an uncertainty label. The forecast's 90% upper bound held in 88.8% of test weeks (91.5% for O−): close to nominal, and shown as an estimate, not a clinical probability.
- **Who decides:** The regional stock coordinator accepts, changes or rejects. Every decision is recorded in the audit trail with who, when and why.
- **If it fails:** Model off → nearest eligible site rule, with the same safety checks and the same approval.

**Does it beat a baseline?**
- 28-day average: **2.792**
- Our model: **2.474** (11.4% lower)
- *7-day forecast error (RMSE, requested red cell units) on held-out weekly origins, Jul – Oct 2026; 4,352 hospital × blood group × week observations; synthetic starter data.*

*Source: Blessings' `python -m forecasting.evaluate` (PR #47), computed in the window. Re-check against `data/processed/forecast_summary.md` after #47 merges, and before recording.*

---

## 07 · Built for real conditions — One system, many blood banks

- **Poor connectivity:** Small pages, data age on every card, and the fallback rule when the model is down. [[Add "decisions made offline are queued and sync once, without duplicates" only if the offline queue runs at recording time.]]
- **Paper and spreadsheets:** Damu Grid reads the unit, stock and request records a centre already keeps. The prototype loads them from CSV exports through a validation step. Coordinators enter nothing new.
- **Another country:** Shelf lives, minimum remaining shelf life, reserves and language are settings, not code. [[Confirm DG-29 settings are built before claiming a live switch.]]
- **Traceability:** Every unit keeps one ID from the source records (mapped conceptually to ISBT 128). Every accept, change, reject, dispatch and receipt records who, when and why.

---

## 08 · Pilot pathway  *(drop if the title page counts toward 8)*

- **Now — Prototype:** [[what works on synthetic data at recording time]].
- **[[3]] months — MVP:** Connect to one regional centre's stock system read-only and run in shadow mode. With: the centre's IT and blood service staff. Indicative cost: [[estimate or "to scope with the centre"]].
- **[[6]] months — Controlled pilot:** One regional centre and its hospitals. Success measured as units expired and requests unmet, against the same months a year earlier.

| Top risks | How we would handle it |
|---|---|
| Access to real stock data | Shadow mode on anonymised data first, under the centre's approval |
| The model is wrong on real demand | The baseline and rule fallback stay available; every move needs a person |
| Late or missing reports from 2G sites | Data age on every card; the sender rechecks the physical units before dispatch |

---

## 09 · The team — Who built it, and what we need next

| Name | Role | What they built |
|---|---|---|
| Agoro Oluwatimilehin Teslim (Timi) | Backend | [[API, state machine, audit trail, deployment]] |
| Blessings Mambwe | Forecasting and evaluation | [[demand forecast, baseline, evaluation]] |
| Sorgho Brayan Jovani Aboubacar | Data pipeline | [[data loading, stock snapshot, eligibility]] |
| Dan Boumba | Frontend and demo | Review queue, dispatch and receipt screens, evaluation panel, slides and video |

The fifth box is unused; delete it.

**What we need to take this further:** A regional blood transfusion centre willing to run Damu Grid in shadow mode on anonymised stock data for one quarter.

*Not in this template, so put it in the README and the submission form: AI tools used, repo / video / demo links, and who presents in Nairobi or online on Friday.*

---

## Method notes (for reviewers, not for the slides)

- 23% wasted: `units.csv`, component RBC or WB, status `expired` (4,901) or `discarded_temperature` (3,719), out of 37,147 RBC/WB units.
- 3,843 not issued: `requests.csv`, `component_requested = RBC`, sum of `units_requested − units_issued` (31,116 requested, 27,273 issued).
- 177 rebalancing: `transfers.csv`, `transfer_type = inter_centre_rebalancing`, out of 35,181 transfers.
- 22 of 47 on 3G or 2G: `facilities.csv` connectivity (3G 19, 2G 3, 4G 25).
- 1–3 routine deliveries a week and the ~5 h emergency median: official dataset README.
- Slide 06 forecast figures: PR #47 description (`forecasting/evaluate.py`; nominal 90% one-sided upper bound). The expiry-aware vs nearest-site scenario in #47 showed no meaningful difference (333.3 vs 332.7 mean unmet units), so no transfer-benefit figure appears on the slides.
