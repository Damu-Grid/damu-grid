# Glossary

Terms as we use them in this repo. Official CSV column names stay in `docs/DATA.md` and `data/raw/DATA_DICTIONARY.md`.

| Term | Meaning here |
|---|---|
| Accept / Change / Reject | Coordinator decisions on a suggestion. Accept reserves; Change reruns eligibility; Reject records a reason and does not reserve. |
| As-of / snapshot | An explicit closing stock picture at a stated time (planned: end of 31 October 2026). Not a reconstruction from year-end unit locations. |
| Audit trail | Append-only record of who did what, when, to which units and moves, including version conflicts. |
| Baseline (28-day average) | Mandatory simple forecast: seven-day predicted requested units = 7 × (requested RBC in the preceding 28 days ÷ 28). |
| Candidate estimator | The pooled historical-mean + network group-share model we compare to the baseline. It can lose. |
| Closing snapshot | The live-queue inventory cut; see as-of. |
| Cold-chain flag | A warning derived from `temperature_logs`, `power_outages`, `temp_excursion_exposed`, or cool-box temperatures — not automatic clinical disposition. |
| Component | Product type in the data: `RBC`, `WB`, `PLT`, `FFP`, `CRYO`. |
| Coordinator | The regional stock coordinator: our primary user. |
| Data age | Elapsed time between the as-of snapshot (or last successful sync) and "now" in the app. |
| Demand | `requests.units_requested`, never `units_issued` or `daily_stock`. |
| Eligibility | Rules a unit must pass before it may be suggested for transfer. |
| Expiry-aware ranking | Policy that prefers eligible units at risk of unused expiry while respecting reserves and recipient gaps. |
| Fallback | Rule-based suggestions (nearest eligible site + simple historical demand) when the estimator is off or the user toggles model-off. Same human gates. |
| FEFO | First-expiry-first-out. A storage/issue practice; we use expiry in ranking, we do not auto-issue to patients. |
| Facility id | Stable site key (`RBTC-`, `SAT-`, `HSP-`). Always join on this, not on typed names. |
| In-window | Written during the official technical phase (Tue 10 Nov 12:00 EAT–Wed 11 Nov 12:00 EAT). |
| Lease | Short reservation window (design note: at most 30 minutes, configurable) after which an unused reserve is released. |
| LLM explanation | Optional rewrite of a deterministic reason. Never the source of numbers. |
| Model-off | UI/API mode that serves only fallback suggestions. |
| Nearest-site-first | A comparison policy: eligible closest recipient first, used as an optional benchmark, not automatically "better." |
| Pending sync | An offline or disconnected action not yet accepted by the shared store. |
| Person in control | A qualified human makes the transfer decision; software does not silently move stock. |
| Quarantine / blocked | A move or unit that must not be dispatched (or must be held at receipt) because of safety or state-machine rules. Incomplete evidence does not clear it. |
| Receipt | Receiver confirms arrival. **Not** transfusion release. |
| Reservation | Atomic hold on specific unit IDs so they cannot be suggested twice. |
| Reserve (sender reserve) | Stock the sending site must keep after a suggested move. |
| Recipient gap | Documented shortfall relative to a target at the destination, informed by demand estimates. |
| Redistribution | Moving stock between facilities, our assigned challenge area. |
| Remaining shelf life | Time from expected arrival to `expiry_date`. Configurable minimums are policy, not universal law. See `docs/DOMAIN.md`. |
| Suggestion | A proposed transfer object (see `docs/API_SPEC.md`). Not ownership of the unit. |
| Synthetic | Generated official starter data or our modelled outputs. Must be labelled. Not a fact about real Kenyan facilities. |
| Tier 1 / Tier 2 | Must-ship core vs stretch features. See `docs/IMPLEMENTATION_PLAN.md`. |
| Transfusion release | Authorising a unit for a patient. **Out of scope. We never do this.** |
| Uncertainty label | Honest statement about a model quantity (for example a residual upper bound). Not a clinical probability. |
| Unit id | Official synthetic identifier `U<yymm>-<centre>-<serial>-<component>`. |
