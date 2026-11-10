# Damu Grid — pitch deck text (draft for the official template)

Paste each slide into the official Google Slides template (`1Nzz_kXVY6IlkHtiii3Rc2qIEDN9lGqjh_kcmtM-LYQ8`). Eight slides (ADR-001). The story follows `docs/DEMO_AND_SUBMISSION.md`; each slide names the template layout it uses.

**Number rules.** Problem figures below were computed in the window from `data/raw/` on 10 Nov 2026 (method under each slide) or come from the official dataset README. `[[…]]` marks a number or link to fill once it exists. Never fill one from a pitch document. Timi and Blessings sign off on slides 5 and 6.

---

## Slide 1 — Problem and named user
*Template layout: "01 · The problem"*

**Headline:** Red cells expire on one shelf while a hospital a few hours away is short

**Who feels it:** The stock coordinator at a regional blood transfusion centre. Every day they reconcile stock reports from hospitals, many on 3G or 2G, and decide what to send where, with no view of which units will expire unused.

**How big it is (big number):** **23%**
Share of red cell and whole blood units wasted in the synthetic starter year: 8,620 of 37,147 expired or were discarded after temperature problems. In the same year, 3,843 of 31,116 requested red cell units (12.4%) were never issued.

*Footer:* Synthetic official starter dataset (Kenya-modelled, 1 Nov 2025 – 31 Oct 2026). Not facts about real facilities.

> Method: `units.csv` component RBC/WB, status `expired` or `discarded_temperature`; `requests.csv` component RBC, `units_requested − units_issued`.

---

## Slide 2 — How it works today, and our workflow
*Template layouts: "02 · How it works today" (four steps), or "03 · Our solution" if one diagram is clearer*

**Headline:** Today, stock rarely moves sideways

1. **Routine deliveries** — centres send each hospital its usual order, 1–3 times a week.
2. **Stock sits** — some sites over-order, others under-order.
3. **Breaks here:** nobody sees which units will expire unused, or which nearby hospital will run short. Only **177 of 35,181 transfers** were deliberate rebalancing between sites.
4. **Emergency call** — when a hospital runs out, it calls for an emergency delivery (median about 5 hours, dataset README).

**Damu Grid adds one step every morning:** Suggest → Coordinator Accept / Change / Reject → Reserve → Sender dispatches → Receiver confirms. Every step goes into an audit trail.

> Method: `transfers.csv`, `transfer_type = inter_centre_rebalancing`.

---

## Slide 3 — The suggestion card and its safety gates
*Template layout: "03 · Our solution" (Person → System → AI recommends → Person approves)*

**Headline:** Damu Grid: suggests which red cells to move, and a person decides

| Person | System | AI / data recommends | Person approves |
|---|---|---|---|
| Coordinator opens the morning queue | Keeps only eligible units: in stock, known group, not temperature-exposed, not reserved, arrives before expiry, sender keeps its reserve | Ranks moves by expected use before expiry, using the demand forecast and typical travel time | Accept, Change or Reject, each with a reason; Accept reserves the units |

**On every card:** unit IDs, from and to site, blood group, expiry, travel time, sender reserve, recipient gap, data age, uncertainty label, and whether the model or the fallback rule made it.

**Built in 24 hours:** [[list what actually runs end to end at recording time]]
**Mocked:** [[list, or "nothing"]]

---

## Slide 4 — Live demo
*Template layout: "04 · Live demo"*

**Headline:** One coordinator, one transfer, start to finish

**We will show:** The morning queue on the synthetic snapshot of 31 Oct 2026. Accept one move with a reason, change one, reject one. The sender rechecks and dispatches; the receiver confirms arrival and cool-box evidence.

**Watch for:** the reason and uncertainty on the card; a blocked move (expired reservation, or a conflict when the same units are accepted twice); the audit trail.

**Then:** We switch the model off. The fallback rule (nearest eligible site) fills the queue, and we finish the task anyway.

---

## Slide 5 — The AI feature and its baseline
*Template layout: "06 · The AI feature" — needs Blessings' sign-off*

**Headline:** A demand forecast that sets recipient gaps and sender reserves

- **Method:** pooled estimator: each hospital's red cell demand from its history, split by network-wide blood-group shares. Trained on requests 1 Nov 2025 – 30 Apr 2026; tested at weekly origins, Jul – Oct 2026.
- **Why this?** The card shows the reason in plain words, built only from computed numbers, with an uncertainty label.
- **Who decides:** the regional stock coordinator. Every decision is recorded in the audit trail.
- **If it fails:** model off → nearest eligible site rule, same safety gates, same approval.

**Does it beat a baseline?** (7-day forecast error, RMSE in requested units)
- Baseline, 28-day average: **[[x.xxx]]**
- Our model: **[[y.yyy]]**
- *[[n]] hospital-group-weeks, Jul – Oct 2026, synthetic data.* [[If the model loses, say so here: "The baseline won; the live queue uses it."]]

---

## Slide 6 — Architecture and African conditions
*Template layouts: "05 · How it is built" + "07 · Built for real conditions" — needs Timi's sign-off*

**Headline:** A small stock-coordination module beside existing systems

**Diagram:** [[paste `docs/architecture.png`]] Official CSVs → validation and SQLite → demand estimator + rule fallback → eligibility → review screen → reserve / dispatch / receipt → audit.

- **Stack:** Python, FastAPI, SQLite; Next.js web app; [[hosting, if any]].
- **Place in ABBIS:** extends stock and distribution; reads lab release, stock and requests; never releases blood or clears a quarantine.
- **Standards:** conceptual mapping to HL7 FHIR (BiologicallyDerivedProduct, SupplyRequest, SupplyDelivery), ISBT 128 unit identity, DHIS2 aggregates. No conformant integration is claimed.
- **Security:** demo roles (coordinator, sender, receiver, safety officer), role checks on every action, append-only audit trail.
- **Poor connectivity:** small pages, data age on every card, works with the model off. 3 of 47 sites are 2G only and 19 are 3G. [[Add offline queue / SMS only if they run at recording time.]]

---

## Slide 7 — Limits and what we will not claim
*Template layout: "08 · Pilot pathway" (risks table)*

**Headline:** What this prototype does not prove

| Limit | How we handle it |
|---|---|
| Synthetic, rule-generated data | Every number labelled synthetic; a pilot needs real anonymised stock data |
| Retrospective test on a year we had inspected | Frozen split and method; a pilot needs a fresh period |
| Expected-use figures are model estimates | Shown as estimates, never as clinical probabilities or units saved |
| No courier capacity, cost or patient outcomes modelled | Route workload is left for the pilot |
| Red cells only | Platelets and plasma need their own policies |

**We never:** release blood for transfusion, decide compatibility, clear a quarantine, contact donors or patients, or rank patients.

**Pilot pathway:** Now → prototype on synthetic data · [[__ months]] → shadow mode at one regional centre · [[__ months]] → controlled pilot with one centre and its hospitals.

---

## Slide 8 — Team, AI tools and links
*Template layout: "09 · The team"*

| Name | Role | What they built |
|---|---|---|
| Agoro Oluwatimilehin Teslim (Timi) · Nigeria | Backend | [[API, state machine, audit, deployment]] |
| Blessings Mambwe · Zambia | Forecasting and evaluation | [[forecast, baseline, evaluation harness]] |
| Sorgho Brayan Jovani Aboubacar · Morocco | Data pipeline | [[ETL, snapshot, eligibility]] |
| Dan Boumba · DR Congo | Frontend and demo | Review queue, dispatch and receive screens, evaluation panel, slides and video |

**AI tools we used:** [[copy from README: Claude Code, Cursor, …, and what for]]

**Links:** Repo [[github.com/Damu-Grid/damu-grid]] · Video [[link]] · Live demo [[link + test log-ins]]

**What we need to take this further:** A regional blood transfusion centre willing to run Damu Grid in shadow mode on anonymised stock data for one quarter.

**Friday 13 Nov:** [[who presents in Nairobi / online]]
