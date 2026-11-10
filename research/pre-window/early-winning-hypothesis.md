# The solution to build

The recommended design after four rounds of experiments (9 to 10 Nov 2026, before the build window). Evidence is in [EXPERIMENTS.md](EXPERIMENTS.md). Every number here must be re-derived with code written inside the window before it is quoted.

## One line

**Damu Grid tells a regional blood centre's stock coordinator, every morning, which red-cell units will be wasted where they sit and where they would be used in time. A person approves every move, and a unit that has been too warm is never moved or issued.**

## Users (two roles, as the brief's "could win" column asks)

1. **Stock coordinator at a regional blood transfusion centre.** Reviews the morning queue, accepts, changes or rejects each suggested move.
2. **Blood bank officer at the receiving hospital.** Confirms the unit is wanted and on arrival (the receiver's live-shelf check). Can work by SMS on 2G sites.

## The daily workflow

| Step | What happens | Who decides | Built from |
|---|---|---|---|
| 1. Cold-chain gate | Fridge logs are scanned for excursions (4 consecutive hourly readings above 6°C, sensor glitches dropped). Every unit in that fridge is **quarantined**: it cannot be issued or moved until a qualified person releases or discards it | Qualified person, never the AI | `temperature_logs`, `units` |
| 2. Stock targets | Each hospital and blood group gets a target stock: pooled demand rate (hospital total × national group mix) over review period + 1 day, Poisson 95% level. **O− is held at 80% in hospitals** and pooled at the centre for emergencies | Coordinator can override per site | `requests`, `facilities` |
| 3. Risk scan | For every unit: probability it expires before local demand reaches it (Poisson, by its first-expiry-first-out position) combined with the site's temperature-loss risk. Units at 50% risk or more are flagged | Shown with the probability | `daily_stock`, `units` |
| 4. Match | Each flagged unit is matched to a site **below its target** where it is most likely to be used in time, within 12 h of travel, minus a travel penalty | Suggestion only | `routes` |
| 5. Review queue | One card per suggestion: unit, from, to, reason in plain words, probability before and after, units saved. **Accept / Change / Reject**, written to an audit log with who, when and why | Coordinator | |
| 6. Lease check | Before dispatch the sender's live shelf is checked; a unit already used or quarantined is dropped (with late reports this caught about 134 phantom moves per 4 months) | Automatic, logged | |
| 7. Fallback | With the model off: the same targets plus a plain rule (move units whose days of cover exceed their days of life to the nearest site below target). Still works offline on a facility device | Coordinator | |

## The AI feature and its baseline (the brief asks for both numbers)

**Feature: waste-risk score at dispatch.** A gradient-boosting classifier that predicts whether a red-cell unit sent to a hospital will be wasted there (features: days of life left, whole blood vs red cells, destination demand rate, destination stock, power reliability and backup, connectivity, delivery frequency, blood group).

| Model | AUC on held-out months | AUC on three new synthetic years | Riskiest 20% catches |
|---|---:|---:|---:|
| Baseline rule: fewest days of life left first | 0.770 | 0.739 to 0.770 | about 40% of waste |
| **Waste-risk model** | **0.925** | **0.911 to 0.922** | **73% to 74% of waste** |

Use it to order the review queue and to warn at dispatch ("this unit is likely to be wasted at Lodwar; send it to Eldoret's referral hospital instead"). Show the probability, not a yes or no.

**What was rejected:** demand forecasting models. A plain average beat moving averages and gradient boosting; demand is flat Poisson noise (only Sundays differ, at 0.77×). Use the average and show its Poisson interval (80% intervals covered 83.6% of outcomes).

## Expected results (simulator, test window Jul to Oct, mean of 4 independent synthetic years, 3 seeds each)

| Policy | Waste change | Unmet change | Fill rate | O− unmet | Heat-exposed units given to patients |
|---|---:|---:|---:|---:|---:|
| Status quo | 0% | 0% | 91.4% | 67.5 | 685 |
| AI off: targets only | −6.9% | −28.0% | 93.8% | 80.9 | 640 |
| Nearest site below target (rule) | −11.2% | −61.3% | 96.7% | 73.2 | 801 |
| Hybrid matching | −8.6% | −65.3% | 97.0% | 58.5 | 768 |
| **Hybrid matching + quarantine (recommended)** | **−15.6%** | **−51.2%** | **95.8%** | **66.1** | **0** |

Least favourable year for the recommended stack: waste −5.8%, unmet −43.2%. It holds when people accept only 70% of suggestions, and with late reports from 2G and 3G sites when the nowcast is on.

**The honest ceiling.** About 8.3% of red-cell supply cannot be used by anyone: collections exceed compatible demand in A+, B+ and O+. Fitting backup power to all 14 sites without it removes most temperature loss, but the surplus then expires instead. Say this in the pitch: the remaining waste is a collection-planning problem (a hand-off to the Forecasting and Donors workflows of ABBIS), not a routing one.

**Where the hybrid is not better.** Against a well-designed "nearest site below target" rule, the hybrid gains on unmet (−65% vs −61%) and on O− (58 vs 73 unmet units) but not on waste. The clear AI win is the risk score (AUC 0.92 vs 0.77). Present the rule as the fallback and the AI as what ranks and explains.

## What each scoring criterion sees

| Criterion (weight) | Show |
|---|---|
| Working prototype (25) | The morning queue on the starter data: quarantine banner, suggestion cards, Accept / Change / Reject, audit log, two roles |
| Technical depth (20) | The seven-step flow, lease check, failure-mode table, calibrated simulator replaying the year |
| AI and data (15) | Risk score vs rule, both numbers, tested on new synthetic years; Poisson intervals; AI-off fallback measured |
| Problem and user (15) | Coordinator at a regional centre; 24% of red cells wasted while 12% of requested units go unmet; 2,119 exposed units transfused |
| African conditions (15) | 2G sites with late reports, nowcast, SMS confirmation, settings file for shelf lives, thresholds, language |
| Demo (10) | The 3-minute story below |

## Three-minute demo

1. **The problem (20 s).** Map: Mombasa centre has O+ units expiring in 6 days; Kilifi is below target. A fridge at Lodwar went above 6°C last night.
2. **The queue (60 s).** Coordinator opens the morning queue. Lodwar's units are quarantined and cannot be moved. Top card: "Move 4 O+ from Mombasa centre to Kilifi County Hospital. 82% chance they expire if they stay; 9% at Kilifi. 1.4 h by road." Accept. One card is changed (3 units instead of 4), one rejected with a reason. The audit log updates.
3. **Receiving officer (30 s).** Kilifi confirms by a simple screen or SMS; the lease check passes.
4. **AI off (30 s).** Switch the model off. The rule still produces a shorter queue; the coordinator finishes the task.
5. **Evidence (40 s).** Risk score 0.92 vs rule 0.77; replay of Jul to Oct: unmet −51%, waste −16%, zero exposed units issued; the 8.3% waste floor and what would fix it.

## Build order inside the 24 hours

1. Load data into SQLite; excursion detector; quarantine list (safety first, simplest, high value).
2. Pooled demand rates and targets; Poisson risk per unit; matching to sites below target.
3. Review queue UI with Accept / Change / Reject and audit log (coordinator role).
4. Risk-score model and its baseline, evaluated on held-out months.
5. Replay harness for the before/after numbers (status quo vs recommended, test window).
6. Receiving-officer view, lease check, AI-off switch.
7. Settings file, FHIR mapping in the docs, SMS confirmation mock.

Cut from the bottom if time runs short. Never cut steps 1 to 3, the baseline comparison or the fallback.

## Limits to state

- Synthetic data generated by rules; real accuracy will be lower than AUC 0.92.
- Red cells and whole blood pooled; platelets not covered.
- Courier cost not modelled; the recommended stack makes about 2,300 trips per 4 months across 47 sites (about 19 a day network-wide).
- Temperature risk learned from 8 months of logs per site; sites with few excursions get little warning.


---

## Upgrades from the research (10 Nov)

The literature check in [RESEARCH.md](RESEARCH.md) adds seven things to the build. None changes the core design; each answers a known failure of real redistribution programmes.

1. **Two-tier cold-chain alert.** Warn at the first reading above 8 °C (about 2 hours earlier, median); quarantine at 4 hours above 6 °C; only a qualified person releases, with a recorded reason (Irish Blood Transfusion Service policy; WHO cold chain manual).
2. **Cold-chain record on every card.** Route hours (cap 12, WHO limit 24), cool-box maximum temperature, sender and receiver sign-off. Cold-chain validation is "the critical requirement and the key inhibitor" in UK transshipment case studies (Stanger et al. 2013).
3. **Model track-record panel.** Predicted vs actual waste for recent weeks, next to the queue. Stanford's 3.2% vs 10.5% platelet model was never put into production for lack of human trust; the follow-up built a trust dashboard.
4. **Conformal "confident / unsure" label** on each card. Unsure units (2% to 8%) go to a person first.
5. **Receiver protection.** Only send to sites below target; show the receiver's own expiry risk; offer a forward-on rule if the unit is unused by a set day.
6. **Money line.** About 1,350 units and USD 130,000 a year in this synthetic network, at USD 97 a unit (assumption, with source).
7. **Transit-failure honesty.** State that Ontario lost 5.3% of redistributed products in transit and that the design stays better than the status quo at four times that rate.

**Updated pitch line.** "A published programme moved CAD 17.6 million of near-outdate blood products between 130 hospitals for about CAD 45,000, and lost 5% of them in transit. Damu Grid does that for red cells, with a person approving every move, fridge failures quarantined, and a rule that keeps working when the model is off."
