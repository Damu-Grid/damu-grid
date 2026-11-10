
# Damu Grid solution and winning case

Damu Grid helps a regional blood-centre coordinator decide which red-cell units should move, where they are likely to be used before expiry, and whether the movement is safe to consider. A person approves each transfer; sending and receiving officers confirm the movement. The module fits inside a wider blood-bank information system rather than replacing it.

Our recommended product is an expiry-aware review queue supported by a pooled demand forecast, conservative stock accounting, transactional reservations and an audit trail. We prioritise a complete redistribution workflow that can be explained, tested and integrated.


## What the evidence currently supports

- Seven-day forecast RMSE is 2.404 units versus 2.711 for a last-28-day average: 11.3% lower error in retrospective synthetic development evaluation.
- In the latest common-sample comparison, the efficient expiry-aware policy reduces unmet units by 22.3%, expiries by 20.3%, route batches by 13.4% and moved units by 20.0% against nearest-site matching.
- Fourteen safety and workflow tests and 23 existing acceptance checks pass. A local approval-to-receipt demonstration and JSON integration adapter run.

The full solution is not yet submission-ready. A review-screen UI, full-year event replay, host-system adapter and recorded demo remain to be built. No clinical validation, proprietary Terumo integration, deployment or guaranteed 50% overall improvement is claimed.


## How to use this document

Pages 2–8 explain the problem, workflow, evidence and architecture. Pages 9–10 contain the competitive case, spoken pitch and slide story. Pages 11–12 cover delivery, risks, sources and reproducibility. This document supersedes earlier pitch figures where they differ from current benchmark outputs.

Prepared for Team Damu Grid and hackathon reviewers • Status as of 10 November 2026 • All operational evidence below is synthetic unless explicitly identified as external source screening.


# The problem and the user

The primary user is the regional stock coordinator. Today, that person must reconcile local stock reports, identify hospitals running short, find usable products and arrange delivery. Sending and receiving officers then need to agree on what actually left and arrived. Stale stock, unconfirmed receipts and missing temperature evidence make a plausible recommendation unreliable.


## What the supplied dataset shows

| Measure | Current direct count | Interpretation |
| --- | --- | --- |
| Network | 47 synthetic facilities | Kenya-modelled sandbox, not real facility performance |
| RBC and whole blood | 37,147 units | Includes 1,254 still in stock at the end |
| Expired or temperature-discarded | 8,620 units | 4,901 expired and 3,719 temperature-discarded |
| Requested and issued units | 34,242 requested; 29,650 issued | 4,592 requested units not issued across all products |
| Exposure and transfusion | 2,112 RBC/WB units | Recorded as exposed and transfused; not a clinical adjudication |

The 8,620 wasted units represent 23.2% of all RBC/WB units, including closing stock in the denominator. A different denominator excluding unresolved stock gives a different percentage. The 4,592 unissued units are 13.4% of requested units across products; this differs from the share of requests fully fulfilled. We state denominators instead of repeating incompatible headline percentages. [1]


## The decision we improve

The coordinator needs a daily answer: which units are at risk of remaining unused here, which eligible recipient has a genuine target gap, what protects the sender, and what assumptions make the move worthwhile? Distance alone cannot answer that question. Moving stock to another shelf can merely move the expiry problem.

Damu Grid addresses redistribution. Forecasting informs the queue, and safety gates constrain it. Collection planning, patient prioritisation, laboratory release and a national blood-bank system remain separate responsibilities.


## People who act on the recommendation

The coordinator accepts, changes or rejects the recommendation. The sender rechecks the physical unit and dispatch readiness. The receiver confirms arrival and cold-chain evidence. A qualified safety officer controls quarantine decisions; the model cannot release a unit for transfusion.


# The daily workflow

| Step | What Damu Grid does | Human control |
| --- | --- | --- |
| 1 Establish usable stock | Exclude expired, reserved, in-transit, quarantined and unknown-safety units | Resolve missing or conflicting evidence |
| 2 Estimate demand and gaps | Use historical requested demand, site totals and network group mix | Approve service levels and reserve policy |
| 3 Find candidate moves | Consider near-expiry units and eligible recipient gaps | Check receiving readiness and local policy |
| 4 Explain the queue | Show expiry, sender reserve, recipient gap and route assumptions | Accept, change or reject with a reason |
| 5 Reserve and dispatch | Atomically reserve; recheck safety, lease and ETA | Sender confirms actual dispatch |
| 6 Confirm receipt | Keep product in transit until receipt; preserve quarantine | Receiver records arrival and cold-chain verification |
| 7 Review performance | Compare shortages, expiry and transport workload | Adjust policy only with measured evidence |


## What a recommendation should look like

Illustrative wording: “Consider moving these O-positive red cells from site A to site B. They expire in three days. B has an approved target gap; the sender retains its reserve. Typical travel time is two hours. Demand and travel time are uncertain. Review current stock and receiving readiness before approval.” This is an example, not a claim about a real facility.

The executable fixture demonstrates recommendation, coordinator approval, sender dispatch and receiver confirmation with named demo actors and an audit log. The present interface is a JSON/command-line reference. The proposed review screen still needs to be connected to those actions.


## What happens when conditions change

A recommendation is not ownership of a unit. A version check and reservation prevent tested duplicate-approval paths. A lease expires after at most 30 minutes. New quarantine evidence blocks dispatch. Receipt with uncertain cold-chain evidence never clears a quarantine. A dispatched transfer cannot be silently cancelled as if it never moved.

If the model is unavailable, nearest eligible site matching remains available with the same safety gates and human approval. Offline actions must remain pending until the host validates them; reliable offline synchronisation and SMS are planned, not implemented.


# Forecasting that earns its complexity

Forecast requested units rather than issued units, because shortages constrain issues. For known blood groups, the selected method estimates each hospital’s total daily RBC demand and allocates it using network blood-group proportions learned only from earlier requests. Pooling reduces noise in sparse site-group histories.

| Horizon | Pooled RMSE | Last 28 days RMSE | Error reduction | Upper bound coverage |
| --- | --- | --- | --- | --- |
| 1 day | 0.940 | 0.958 | 1.9% | 98.2% |
| 3 days | 1.607 | 1.699 | 5.4% | 97.0% |
| 7 days | 2.404 | 2.711 | 11.3% | 96.6% |

RMSE is in requested units per hospital and known blood group over the stated horizon. Coverage is measured for a nominal one-sided 95% upper bound, not a central 95% interval. Bounds use pooled calibration residuals by blood group; they are not per-site safety guarantees. [2]


## How the comparison was made

Twelve configurations cover local historical averages, recent windows, pooled estimates and shrinkage strengths. Selection uses pre-May windows, calibration uses May–June, and evaluation uses July–October. Each origin uses earlier observations only. Because the year had already been inspected during development, these are retrospective development results, not a pristine confirmatory test. An independent unseen year remains necessary.

The earlier six-model weekly benchmark selected the same basic pooled approach on MAE. Its 1.312-unit MAE versus 1.320 for an expanding local average is a modest difference. We do not use the larger comparison against a weaker recent-window baseline to imply a large gain over every sensible forecast.


## Safeguards and next improvements

- Do not assign unknown patient blood groups to known groups. Forecast their workload separately when implemented.
- A missing request record is zero demand only if reporting is known complete; the current benchmark assumes completeness.
- Use actual delivery-cycle horizons and validate service-level targets before operational ordering.
- Keep final unit status, future receipts and later temperature events out of historical feature snapshots.
- Promote a more complex model only if it improves out-of-time error, uncertainty and rare-group performance.


# Redistribution evidence and efficiency

The efficient default ranks potential transfers by the change in estimated likelihood of use before expiry, allowing for a next-day arrival allowance, stock ahead under FEFO, sender reserves and recipient gaps. The Poisson expected-use calculation is a modelling assumption, not a calibrated clinical probability. It does not decide compatibility or release blood.


## Latest common-sample comparison

Across four equally represented scenarios and seeds 4000–4029, compared with nearest-site matching, the one-shot expiry-aware policy achieves the following aggregate reductions. These figures use the same cases for both policies. [4, 5]

| Outcome | Reduction versus nearest | Meaning |
| --- | --- | --- |
| Unmet requested units | 22.3% | More of the recorded requested demand is supplied |
| Expired units | 20.3% | Fewer products expire inside the seven-day window |
| Route batches | 13.4% | Fewer origin–destination–day batches |
| Moved units | 20.0% | Fewer unit movements to process |


## What was simulated

The study uses demand rates estimated from pre-July starter requests at 12 hospitals for four blood groups. It generates initial stock imbalance, shelf life and demand independently with fixed random seeds. It compares ordinary demand, a demand surge, route closures and unknown cold-chain safety. Initial inventory, demand, routes and next-day arrival assumptions remain common across policies.

Inventory conservation and absence of uncleared issues are asserted. Unknown-safety products are never used. Transfers assume full human acceptance and successful next-day receipt. There is no replenishment, courier capacity limit or patient-level outcome model. This is a seven-day scenario replay, not a counterfactual replay of the organiser year.


## Why this is the recommended default

The policy improves service and expiry while reducing movement workload. That is a stronger operational proposition than an allocator that improves shortages by ordering many more deliveries. Route batches are a workload proxy, not actual trips, costs or an optimised courier schedule. The next evaluation must add vehicle capacity, receiving hours, transport costs and rejected suggestions.

Earlier results on seeds 2000–2029 remain in MANAGEMENT_BENCHMARK.md. They are a separate sample and should not be mixed into the latest aggregate percentages. [3]


# The fifty percent target and the trade offs

The request for 50% general improvement was tested rather than treated as a promise. The first new rolling planner reduced combined unmet-and-expired units by 35.4% on seeds 3000–3029. A broader balanced planner then considered longer-life stock and additional expected-use opportunities. On new seeds 4000–4029 it reduced combined loss by 41.4%, with a paired seed-block bootstrap 95% interval of 39.2%–43.5%. It did not achieve 50%. [4]

| Latest policy comparison | Unmet reduction | Expiry reduction | Route batch change |
| --- | --- | --- | --- |
| Efficient expiry aware | 22.3% | 20.3% | 13.4% fewer |
| Daily rolling | 48.4% | 27.4% | 210.7% more |
| Daily balanced | 55.0% | 27.9% | 315.5% more |

The balanced policy’s reduction in unmet units exceeds 50%, but that is not 50% general improvement. It moves about 150.5% more units than nearest matching. Its service gain comes with materially greater coordination and transport demand. The daily planner’s sender reserve was selected on development seeds; the baseline retains its original two-day reserve.


## A transparent broader score

A provisional operational score weights reductions in unmet units at 40%, expiry at 30%, route batches at 20% and moved units at 10%. Each component is normalised against the same nearest-site baseline. These are engineering assumptions, not agreed clinical or business valuations. They were not adjusted to make the score reach 50%. [5]

| Policy | Provisional general improvement |
| --- | --- |
| Efficient expiry aware | 19.7% |
| Daily rolling | −23.6% |
| Daily balanced | −47.8% |

Safety is a mandatory condition and cannot be traded for a higher score. Forecasting, usability, actual cost and integration effort are excluded from this scalar because comparable evidence is unavailable. We retain the efficient default and keep balanced planning experimental. A relaxed zero-travel pooling reference shows headroom but is neither deployable nor a proved optimum for combined loss.


# Architecture and safety controls

The architecture is deliberately small: an existing blood-bank system supplies reconciled as-of stock and demand to the local module; the module produces recommendations; host screens collect approval; the action core reserves, dispatches and confirms receipt; audit and export adapters return the outcome. Python’s standard library and SQLite run the action core. NumPy is needed for the benchmark studies, not the transaction engine.

| Boundary | Responsibility | Current status |
| --- | --- | --- |
| Source adapter | Reconcile unit events, snapshots, late reports and timestamps | Contract described; real host adapter pending |
| Demand and allocation | Estimate demand; rank eligible exact-group RBC moves | Implemented reference methods |
| Action core | Store units, moves and audit; enforce state transitions | SQLite reference implemented |
| Host application | Authenticate users; scope facilities; show decisions | UI and production auth pending |
| System export | Map approved movements to the receiving system | JSON reference; proprietary mapping pending |


## Safety properties exercised by tests

- Unknown or quarantined safety cannot reserve stock; quarantine after approval blocks dispatch.
- Quarantine raised during transit is preserved at receipt.
- Only the expected role performs coordinator, sender, receiver or safety-officer actions.
- Transactions and state checks reject tested duplicate reservations; repeated identical event IDs are idempotent.
- Conflicting event IDs, expired leases and invalid movement states fail.
- The allocator retains sender reserves, avoids duplicate candidates and rejects routes that cannot support arrival before expiry.

Fourteen tests currently pass. These cover concrete code paths, not all possible failures or clinical certification. Multi-process contention, tamper resistance, full reconciliation, crash recovery and production load still require dedicated testing. SQLite audit rows are append-only through the module, not tamper-proof against an administrator. [6]


## Clinical boundaries

The module implements known-group RBC transfers only. It does not decide cross-group compatibility, rank patients, interpret laboratory tests or provide a transfusion-release endpoint. Shelf-life precision, transport rules, quarantine and reserve levels require approved local SOPs. Whole blood, platelets and plasma need distinct product policies before inclusion.


# Integration into ABBIS and Terumo workflows

Damu Grid is an integration reference for the wider ABBIS concept described in the team design. No proprietary Terumo API specification or implementation access has been supplied. We therefore offer a small versioned JSON contract and an action library, with adapters to be agreed with the receiving technical team. This makes the next discussion concrete without pretending an integration already exists. [7]


## Input and output contract

Input includes schema version 1.0, a timezone-aware as-of timestamp, synthetic data origin, units, routes, site/group deficits, sender reserves and demand rates. Each unit has an identifier, location, group, component, expiry, safety and state. Balanced mode additionally accepts a remaining planning horizon of up to seven days. The host must subtract valid confirmed inbound when calculating gaps.

Output includes unit, origin, destination, score, reason, estimated travel time, uncertainty and an approval-required flag. Exact-group RBC is the only supported product scope. Source units, late events, timestamps and safety clearance must be reconciled before a real host can use the module.


## Writing actions safely

The host passes authenticated actor and role plus server time separately from the action payload. It must enforce facility scope; a role alone is insufficient. Accept uses the expected unit version and a short reservation lease. Change cancels the prior reservation and creates a revised move. Dispatch rechecks state, safety, lease and ETA. Receiving confirmation closes transit; incomplete cold-chain evidence does not imply clearance.


## Proposed standards mappings

Use a local identifier mapping table rather than fabricating standard codes. Unit identity can map to ISBT 128 donation, product and division identifiers. Product and supply events may map to the recipient’s FHIR BiologicallyDerivedProduct, SupplyRequest and SupplyDelivery profiles. Weekly aggregates may map to its DHIS2 organisation units and data elements. These are conceptual mappings only; versions, profiles and conformance remain unverified.


## Practical next steps with the receiving team

- Exchange the synthetic example request, output and acceptance report; obtain the host schema, sandbox and authentication model.
- Agree on source-of-truth ownership, retry/idempotency rules, safety SOPs and facility-scoped permissions.
- Connect a read-only adapter, validate balances and run shadow recommendations.
- Wire the host review screen and receiver confirmation to tested actions; add production writes only after shadow and failure testing.


# Why Damu Grid could win

The strongest case is a focused operational workflow backed by inspectable evidence. A coordinator can understand the recommendation, retain control and trace the unit through dispatch and receipt. The efficient policy improves both service and workload in the tested scenarios. Forecasting earns its place through a baseline comparison, while the module remains useful without a fitted model.

| Judging criterion | Competitive evidence | What still strengthens the entry |
| --- | --- | --- |
| Working prototype 25% | Action core and synthetic end-to-end workflow run | Review screen and recorded live workflow |
| Architecture 20% | Clear boundaries, transactional state, JSON contract | Real as-of adapter and full event replay |
| AI and data 15% | Baselines, uncertainty, explanations and fallback | Independent unseen-year confirmation |
| Problem and user 15% | Named coordinator, sender and receiver tasks | Documented blood-service expert feedback |
| African conditions 15% | Small local core and explicit stale/offline limits | Tested offline path or actual SMS |
| Demo readiness 10% | Runnable examples and concise story | Three-minute video and team readiness |


## The case to make to judges

We address a specific daily decision rather than promise to automate a whole blood service. We avoid spending the same unit twice. We preserve uncertainty instead of manufacturing missing receipts or blood groups. We demonstrate the fallback and explain where a recommendation could fail. We expose the transport trade-off rather than hide it behind a favourable shortage statistic.

Our technical depth comes from the connection between demand, expiry, safety, state and human action. Our integration case comes from a portable contract and a small module that can sit inside an existing system. These are reasons to compete strongly, not a prediction of judges’ scores or a guarantee of winning.


## What would weaken the pitch

Claiming 50% general improvement, clinical validation, production integration, working SMS or a completed user interface would go beyond current evidence. Reusing earlier AUC, annual savings or zero-exposure figures as if remeasured by the current implementation would also be misleading. The pitch should foreground the efficient default, not the expensive experimental planner.


# The pitch and the demonstration story


## Three minute spoken pitch

Blood can expire on one shelf while another hospital is short. The stock coordinator has to make a decision from reports that may be late, incomplete or unconfirmed. A map showing stock is useful, but it does not tell that person which move is worth making.

We are building Damu Grid, a redistribution module for a wider blood-bank system. It recommends which red-cell units to move, where they are likely to be used before expiry, and why the sender can spare them. A coordinator accepts, changes or rejects each suggestion. The sender rechecks the unit, and the receiver confirms arrival. Unknown safety and quarantine are gates; the model never releases blood for transfusion.

The local workflow already runs from recommendation through approval, dispatch and receipt with an audit trail. We cleaned more than 783,000 synthetic starter records while preserving the raw evidence. Missing arrivals stay unconfirmed, uncertain donor matches stay flagged, and unknown blood groups stay unknown.

We tested the data feature against simple baselines. Our pooled seven-day demand forecast has 11.3% lower RMSE than a last-28-day average. In the latest synthetic management comparison, the efficient policy reduces unmet units by about 22%, expiries by 20%, and route batches by 13% against nearest-site matching. These are bounded simulation results, not clinical outcomes or a claim about real Kenyan hospitals.

We also tried more aggressive daily planning. It improved service further but required many more deliveries. We kept the efficient policy as our default because a blood service has to staff and fund the movement, not just optimise a chart.

Damu Grid has a versioned JSON adapter and a small Python and SQLite core. The next integration step is a read-only adapter to the host system, followed by a review screen and shadow evaluation. The nearest-site fallback remains available when the model is off.

Our case is a focused, explainable decision that respects people, stock and safety. We want to turn a coordinator’s uncertain morning into a short, reviewable queue—and show the evidence for each move.


## Eight slide outline and demo readiness

1 Problem and user; 2 dataset and integrity; 3 morning recommendation card; 4 approval to receipt; 5 forecast baseline; 6 management results and transport trade-off; 7 architecture and integration; 8 limits, next steps and team. Rehearse the script to remain below three minutes. It is a script, not a recorded video.

For the demo, add the review UI first. Then show one accepted card, one changed or rejected card, a safety block, receiver confirmation and the AI-off fallback. Until the screen is built, label the working component as the executable local reference rather than imply the screen exists.


# Delivery plan and feasibility


## What exists today

- Cleaned organiser tables, raw hashes and row-level data-quality reports.
- Forecast selection and calibration benchmarks with saved machine-readable results.
- Expiry-aware, nearest and experimental balanced allocators.
- SQLite action core, JSON CLI, synthetic workflow and an integration handover.
- Scenario studies, bootstrap uncertainty, safety tests and an acceptance runner.


## What to build next in order

| Priority | Deliverable | Evidence required |
| --- | --- | --- |
| 1 | Review screen over the tested actions | Coordinator and receiver complete one transfer |
| 2 | As-of event adapter and reconciliation | No future-state leakage; balanced inventory |
| 3 | Full-year replay and transport constraints | Compare service, expiry, costs and workload |
| 4 | Offline or SMS path | Pending actions, retries and conflict tests |
| 5 | Independent validation and shadow pilot | Frozen model; approved safety and data governance |

Keep a single local application/API and database for the prototype. Avoid microservices and a heavy solver until a simpler allocator has been evaluated under the same constraints. Country rules, language, service levels and branding should move into reviewed settings; the complete second-country settings interface is not yet implemented.


## Costs and benefit claims

The current studies count products, movements and route batches. They do not measure monetary savings, patient lives saved or actual courier time. A feasibility model needs cost per trip, vehicle capacity, receiving workload, transport loss, staff review time and value of usable products. Do not annualise a seven-day scenario result or turn old published unit costs into present-day savings without a sensitivity analysis.


## The risks we must manage

Synthetic demand may be easier than real demand. Sparse group/site histories can hide poor subgroup performance. Missing reports are not zeros. Capacity limits can erase unconstrained transfer benefits. Safety evidence can arrive late. Human acceptance can be lower than the simulation assumes. Every one of these risks needs an explicit test, a visible limitation and a fallback.

The team named in the design is Blessings Mambwe, Sorgho Brayan Jovani Aboubacar, Dan Boumba and Agoro Oluwatimilehin Teslim. Official roster, roles and showcase attendance remain for team verification. Record code history, respect the brief’s build window and disclose Codex use.


# Evidence sources and reproducibility

The technical brief requires a working workflow, a simple baseline, human approval, uncertainty, fallback, architecture and a demo of three minutes or less. External records must meet the brief’s restrictions: synthetic or openly licensed and cited; no real donor, patient or facility records. The brief resolves earlier ambiguity in the starter README. [8]


## Internal evidence index

| Reference | File or source |
| --- | --- |
| 1 | data/cleaned/*.csv; reports/DATA_CLEANING.md; organiser README and dictionary |
| 2 | reports/FORECAST_ITERATIONS.md and forecast_iterations.json |
| 3 | reports/MANAGEMENT_BENCHMARK.md and management_benchmark.json |
| 4 | reports/TARGET_50_PERCENT.md; target50.json; first iteration preserved separately |
| 5 | reports/OVERALL_IMPROVEMENT.md and overall_score.json |
| 6 | scripts/test_grid.py; reports/acceptance.json; reports/demo_workflow.json |
| 7 | integration/HANDOVER.md; example_request.json; scripts/grid_cli.py |
| 8 | Supplied Technical Phase Brief PDF; reports/technical_brief.txt |


## External dataset research and citation policy

External sources were screened, not merged. WHO aggregates may inform synthetic calibration, Delhi instances a separate routing benchmark. UCI donor-return data provides no unit-expiry labels. Inconsistent synthetic candidates were excluded. Scenario parameters remain assumed, not claimed as WHO estimates.

Source links: WHO report — https://www.who.int/publications/i/item/9789240121546 ; Delhi routing dataset — https://doi.org/10.17632/sbbm87s638.1 ; UCI donor-return dataset — https://doi.org/10.24432/C5GS39 . Detailed access, licence and suitability notes are in research/EXTERNAL_DATASET_RESEARCH.md and source_manifest.csv. No fresh web verification was undertaken for this consolidation.


## Reproduce the current implementation

Run node scripts/clean-data.cjs to regenerate the clean layer. With Python 3.11+ and NumPy, run python scripts/acceptance.py, python scripts/target50.py and python scripts/overall_score.py. The action core and python scripts/demo_workflow.py require only the standard library. Full machine-specific runtime instructions are in the integration handover.

OpenAI Codex assisted research, cleaning, implementation, testing and this document. The team must review and explain submitted work. No submission, deployment or clinical validation is claimed.
