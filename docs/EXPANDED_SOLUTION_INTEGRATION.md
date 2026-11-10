# Expanded Damu Grid solution: integration brief

**Status: proposed team direction, 10 November 2026.** This document makes the strongest local research ideas reviewable against what the team has actually built. It does not approve clinical use, replace the accepted Tier 1 plan, or turn pre-window experiments into submission results. The team should decide at check-in which extensions fit before the recording freeze.

## The decision to make

Keep the adopted product as the working base: a regional coordinator reviews **eligible, exact-group RBC** transfer suggestions; a sender dispatches and a receiver confirms; the unit remains subject to safety gates and audit. Add an **optional waste-risk ranking** and stronger stock targets only after they are implemented from scratch in the official window and evaluated against the same simple baselines. The nearest eligible site rule remains the model-off fallback. This preserves a demoable workflow if the expanded model slips.

The [early winning hypothesis](../research/pre-window/early-winning-hypothesis.md) proposed a waste-risk classifier, target stock, site temperature screening, hybrid matching and a receiver response. The [later local solution](../research/pre-window/later-local-solution.md) favored efficient expiry-aware ranking and found more aggressive balanced planning gained service at much greater transport workload. These are **different experiments with different comparisons**; their percentages cannot be combined or pasted into the pitch. Their application code must not be copied into this repository. See `AGENTS.md` and ADR-002.

## Evidence ledger

| Claim or feature | Provenance | Can be shown as an achieved result now? | Next evidence |
|---|---|---|---|
| Seven-day pooled demand forecast vs 28-day average: RMSE 2.474 vs 2.792 on 4,352 synthetic forecasts | In-window `forecasting/evaluate.py`, merged via PR #47 | **Yes**, with retrospective synthetic and reporting-completeness limits | Display both numbers and split in API, UI and slides |
| Nominal 90% demand upper bound: 88.8% overall coverage | In-window `forecasting/uncertainty.py`, PR #47 | **Yes, as a shortfall**, not a safety guarantee | Investigate calibration only in a new, separately declared experiment |
| One-shot nearest vs expiry-aware scenario: both move one unit on average | In-window `simulation/compare.py`, PR #47 | **Yes**, but too narrow for a broad impact claim | Add capacity, receipt, rejections and larger relevant scenarios before promoting |
| Waste-risk AUC around 0.925 vs 0.770; large unmet/waste reductions and zero exposed transfusions | **Pre-window** [early experiments](../research/pre-window/early-experiments.md) | **No**. Research hypothesis only | New in-window label/feature construction, frozen split, baseline, calibration and policy replay |
| Later local efficient and balanced planner results (including 22.3% unmet reduction or 41.4% combined-loss reduction) | Separate [local solution](../research/pre-window/later-local-solution.md) and scenario model | **No**. Different assumptions and transport burden | Reimplement and rerun on shared in-window scenarios; report movements and route batches |
| Safe physical transfer and clinical clearance | No real host integration or clinical SOP approval | **No** | Authenticated host, reconciliation, approved safety SOP and prospective shadow evaluation |

## One integration path, in dependency order

1. **Reconcile the official closing stock.** Pipeline branch `feat/DG-01-pipeline` should produce a dated, repeatable store from the 11 official CSVs and explicitly reconcile `daily_stock` against eligible unit IDs. Exclude unknown groups and missing safety evidence; do not invent earlier stock from final locations. Preserve site/group counts and exclusion reasons for each card.
2. **Choose the API contract.** Review PR #51 (`feat/dg-18-29-backend`) as the primary FastAPI action service. Review PR #50 (`feat/dg-local-demo-prototype`) as a local fallback and reference; it uses a frozen clock and a different forecast implementation. Do not merge both forecast implementations as peers. PR #47 is the canonical in-window forecast benchmark. The shared suggestion payload must carry `as_of`, data age, unit/version, exact group/component, sender reserve, recipient gap, route time, deterministic reason, uncertainty and `fallback`.
3. **Connect one computed card end to end.** Review PR #52 (`feat/connect-prototype`) against the chosen API. Run accept, change/reject, stale-version conflict, dispatch, uncertain receipt, quarantine block and audit on a reproducible synthetic fixture. A placeholder card is visibly labelled and cannot serve as the recorded computed-card evidence. Do not claim receipt is transfusion release.
4. **Add the expanded model behind a flag.** Build new labels only from outcomes after a dispatch or candidate origin. Features must be available at that origin: shelf life, group, historical requested demand, eligible stock, route and known site conditions. Split by time before training; report sample counts, class balance, AUC/PR-AUC, calibration and subgroup results. Compare with an expiry/nearest rule on the *same* sample. If it fails or is late, keep the tested pooled-demand queue and fallback.
5. **Test policy benefit separately from classifier accuracy.** Compare nearest eligible, expiry-aware and risk-ranked policies on common synthetic seeds, stock, routes, safety exclusions and acceptance assumptions. Report unmet demand, expiries, moved units, route batches, O-negative outcomes and quarantine violations separately. Vary courier capacity, reporting delay and acceptance rate. A classifier AUC cannot establish stock saved or clinical benefit.
6. **Package the demo.** The eight official-template slides and <=3-minute video must show what actually runs. Use the in-window table above; show the expanded model only if steps 4–5 pass. Confirm repo, deck and video viewing permissions and Friday attendance in `DEMO_AND_SUBMISSION.md`.

## Interfaces and safety invariants for every track

The pipeline owns the as-of snapshot and safety evidence; forecasting provides demand estimates without writing stock; ranking produces proposals but never reserves them; the backend alone makes versioned, idempotent state transitions; the frontend displays age, uncertainty, fallback and action errors. A safety role controls quarantine under an approved SOP. Temperature logs can flag review, but without a defensible fridge-to-unit mapping they must not silently clear or condemn a particular unit. Offline actions remain pending until the server accepts them; no local device may promise the same unit exclusively.

Use the same tracked dataset under `data/raw/`. The supplied kit files are under `starter-kit/` after PR #47. The 38 MB zip adds no data; its 17 files match the tracked contents after line-ending normalization. `blood_system.sqlite` is listed in the starter README but absent from the archive, so the pipeline must derive it from CSVs.

## Check-in decisions

- **Timi / backend:** select the action API and fixture, document auth and facility scope for demo accounts, show blocked dispatch and audit.
- **Brayan / pipeline:** deliver reconciled closing snapshot, eligibility reasons, and documented treatment of sensor glitches and missing receipts.
- **Blessings / evaluation:** maintain the frozen forecast result; own any new risk-model experiment and the common policy replay. Do not reuse pre-window AUC or savings figures.
- **Dan / frontend and demo:** bind to the selected API, keep the table usable without a map, record the actual accepted/blocked/fallback flow, and fill the official eight-slide template.
- **Everyone:** decide whether the expanded classifier has passed its evidence gate by the merge freeze. Record the decision and any cut features in `docs/DECISIONS.md`; appoint the form operator and confirm a Friday presenter.
