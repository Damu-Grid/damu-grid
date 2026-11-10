# Pre-hackathon experiments: what wins on this dataset

Run on 9 to 10 Nov 2026, before the build window, on the organisers' synthetic starter dataset. **The experiment code is not in this repository** (code written before Tue 12:00 cannot be submitted). These results tell the team what to build. Rebuild the winning pieces inside the window and re-measure before quoting any number.

## Set-up

- **Simulator.** A daily replay of the red-cell network (RBC and WB pooled per ABO/RhD group). It uses the real unit arrivals (tested date + 1 day, at the processing centre), the real hospital RBC requests, the real routes, delivery days and power cuts. Hospitals are served first-expiry-first-out; emergency and urgent requests can use compatible groups (O− last) and trigger emergency dispatch from centres. Routine and proactive transfers arrive the next day (two days if over 12 h of travel).
- **Calibration.** In the status quo (standing orders, no proactive moves), the simulator gives 21.6% to 22.7% waste and 87.9% to 88.4% fill, against 24.0% and 87.6% in the data. One parameter was tuned: the chance a unit is lost when a fridge without backup loses power.
- **Honest split.** Decisions use demand rates learned on Nov to Jun only. Results are reported on **Jul to Oct (test window)**, averaged over 3 random seeds.
- **Waste floor.** Even with perfect timing and routing, about **2,819 red-cell units (8.3%)** must be wasted. Collections exceed compatible demand in A+ (962 surplus), B+ (913) and O+ (658). Only fewer collections or different processing (for example more plasma) fixes that, not redistribution.

## The five hypotheses

| # | Hypothesis | Verdict | Key number (test window unless stated) |
|---|---|---|---|
| H1 | A better demand model beats a plain per-site average | **Rejected** | Hospital-group-week error: plain mean 57.0%, gradient boosting 58.0%, 4-week average 62.2%, last week 75.8%. School-holiday factor on demand: 1.00 (no effect) |
| H2 | Right-sized orders (order-up-to from demand rate) beat standing orders | **Supported** | At 95% service level: waste −13%, unmet −39%, fill 91.1% to 94.5% |
| H3 | Expiry-aware redistribution beats no moves and "nearest site first" | **Supported** | Smart, network-wide: waste −10%, unmet −39%, about 2,200 moves. Nearest-first: similar waste but ~23,400 moves (it thrashes) |
| H4 | Centres send short-dated units to the fastest users | **Rejected** | −0.7% waste: no meaningful effect |
| H5 | A model flags units that will be wasted, better than a rule | **Supported, strongly** | AUC 0.925 vs 0.770 for the best rule; flagging the riskiest 20% of dispatched units catches 74% of waste (85% of expiries) |

## Best combined stack (round 2)

| Policy (test window, Jul to Oct) | Waste | Waste % | Expired at centres + hospitals | Temperature loss | Unmet units | Fill | Proactive moves |
|---|---:|---:|---:|---:|---:|---:|---:|
| Status quo | 3,282 | 25.3% | 2,227 | 1,054 | 949 | 91.1% | 0 |
| **Fallback, AI off:** order-up-to only | 2,855 | 22.1% | 1,645 | 1,210 | 581 | 94.5% | 0 |
| **Order-up-to 0.95 + smart network moves** | **2,528** | **19.5%** | **881** | 1,647 | **239** | **97.7%** | 2,303 |
| Same, only 70% of suggestions accepted | 2,513 | 19.5% | 992 | 1,521 | 249 | 97.7% | 2,096 |
| Same + cold-chain-aware moves | 2,534 | 19.6% | 982 | 1,552 | 248 | 97.7% | 2,410 |

Against the status quo, the best stack cuts **total waste by 23%**, **expiry waste by 60%** and **unmet units by 75%**. It still works when people reject 30% of suggestions. With the AI off, the fallback still cuts waste by 13% and unmet units by 39%.

## What this means for the build

1. **The AI that earns its place is the expiry-risk flag (H5), not a demand forecaster (H1).** Use a plain per-site average with a Poisson interval for demand (80% intervals covered 82.9% of outcomes, a good match). Spend model effort on "which units will be wasted where they are".
2. **Decisions beat predictions.** Most of the gain comes from two plain mechanisms: order-up-to targets and matching at-risk units to sites with room to use them in time. Present the model as the thing that ranks what a person should look at first.
3. **The baseline to beat is "nearest site first".** It is the brief's own example. In this data it moves ten times as many units for a similar result, which is a clear story for judges.
4. **The person-in-control and fallback stories are real, not decoration.** 70% acceptance loses almost nothing; AI-off still beats the status quo.
5. **The remaining waste is cold chain and over-collection, not routing.** After the best stack, temperature loss is the largest single part, and it grows as more stock sits at hospitals. Fix by placing stock where fridges have backup power. Adding backup power at Nairobi and Mombasa centres removes their temperature losses, but in the status quo those units then expire instead: the surplus has to go somewhere. Say this plainly in the pitch; it shows the team understands where the system fails.

## Watch-outs

- **O− unmet rises slightly** with order-up-to (test window 42 vs 35 units) even as total unmet falls 75%. Holding O− at more hospitals spreads a scarce group thinly. Treat O− with a pooled, centre-held rule and show it.
- **Synthetic data may make prediction easier than reality.** The generator follows rules; AUC 0.925 will not transfer as is. Say so.
- **Simulator assumptions:** RBC and WB pooled; one-day transit; temperature loss modelled from outage hours with one calibrated parameter; transfers never fail in transit (the dataset has no cool-box excursions above 10°C).
- **Order-up-to raises routine deliveries** (8,988 to about 12,000 units in the test window). The extra courier cost is not modelled.

## Next experiments (inside the window, if time allows)

- Feed the H5 risk score into the matching step instead of the rate rule, and measure the extra gain.
- A separate O− policy (centre-pooled).
- Per-site temperature risk in placement: hold buffer stock at the centre for sites with no backup and a weak grid.

---

## Rounds 3 and 4 (supersede the round 1 and 2 numbers above)

**What changed.** The kit's `gen.py` (the organisers' generator) was read and used. It showed the true mechanics: hospitals order up to a par level distorted by a per-hospital factor; demand is flat Poisson with a fixed national group mix (Sundays 0.77×); fridge excursions are 4+ hours above 6°C after outages without backup, with 45% of units discarded and the rest left in use; hospitals issue oldest-first only 78% to 90% of the time. A second simulator was built on these mechanics (calibration: 22.0% waste and 88.1% fill vs 24.0% and 87.6% in the data), and **three fresh synthetic years** were generated with new seeds (7, 11, 99) to test generalisation.

**Findings.**

1. **Pooled demand rates** (hospital total × national group share) are as accurate as per-cell rates (WAPE 56.6% vs 57.0%); both sit near the Poisson noise floor. Forecasting is not the lever.
2. **An oldest-first nudge at hospitals has no measurable effect** (+0.5% waste). Dropped.
3. **Order-up-to targets doubled O− shortages** (49 to 99 units) because rare-group targets round to zero. **Holding O− at 80% in hospitals and pooling it at the centre fixes this** (O− unmet 39, below the status quo's 49).
4. **The naive risk-based matching sent units to sites that did not need them** (they expired there). Restricting receivers to sites below target ("hybrid") fixed it.
5. **Quarantining heat-exposed units** (never issued or moved) removes all ~685 exposed transfusions per test window and lowers waste further; it costs some unmet improvement.
6. **Late reports from 2G and 3G sites** created ~134 phantom moves per 4 months; the lease check caught them all and the nowcast restored the full benefit.
7. **Backup power at all 14 weak sites** cuts temperature loss by ~80%, but total waste barely moves: the surplus expires instead.
8. **The waste-risk model transfers to new years:** trained on the given year, AUC 0.911 to 0.922 on seeds 7, 11 and 99 (rule: 0.739 to 0.770); the riskiest 20% catch 73% to 74% of waste.

**Final comparison (mean of 4 years, test window, 3 seeds each).**

| Policy | Waste | Unmet | O− unmet | Exposed issued | Trips |
|---|---:|---:|---:|---:|---:|
| Status quo | 0% | 0% | 67.5 | 685 | 0 |
| AI off: targets only | −6.9% | −28.0% | 80.9 | 640 | 0 |
| Nearest site below target | −11.2% | −61.3% | 73.2 | 801 | 2,289 |
| Risk-based (no need check) | −12.9% | −49.1% | 65.8 | 644 | 1,759 |
| Hybrid, risk ≥ 0.5 | −8.6% | −65.3% | 58.5 | 768 | 2,660 |
| Hybrid, risk ≥ 0.7 | −10.9% | −63.6% | 61.0 | 779 | 2,064 |
| **Hybrid + quarantine** | **−15.6%** | **−51.2%** | 66.1 | **0** | 2,300 |
| Hybrid, late reports + nowcast | −9.6% | −64.3% | 58.6 | 784 | 2,551 |
| Hybrid, 70% accepted | −8.5% | −64.5% | 58.8 | 764 | 2,582 |

The recommended design is in [WINNING_SOLUTION.md](WINNING_SOLUTION.md).


---

## Round 5: stress tests prompted by the literature (10 Nov)

All results are the mean of four independent synthetic years, test window July to October, three seeds each. Source for the transit-loss rates: the Ontario redistribution programme (Hajjaj et al., Transfusion 2024), where 816 of 15,499 redistributed products (5.3%) were discarded after transport failures.

**1. Transit failure.** A share of proactively moved units is lost in transit (counted as waste).

| Loss in transit | Nearest site below target: waste / unmet | Recommended (hybrid + quarantine): waste / unmet | Recommended, worst year (waste) |
|---|---:|---:|---:|
| 0% | −11.2% / −61.3% | −15.6% / −51.2% | −5.8% |
| 3% | −10.6% / −61.5% | −15.9% / −49.6% | −7.6% |
| **5.3% (Ontario)** | −10.4% / −60.8% | **−15.9% / −48.7%** | −8.6% |
| 10% | −11.3% / −59.4% | −15.5% / −46.4% | −8.8% |
| 20% | −10.4% / −56.6% | −14.7% / −40.6% | −10.6% |
| 35% | −7.2% / −49.7% | −11.6% / −31.0% | −8.1% (the simple rule is **+4.2% worse** in its worst year) |

Moved units are the ones about to be wasted anyway, so losing some in transit costs little. The design still beats the status quo in every year at a loss rate more than six times Ontario's.

**2. Conformal uncertainty sets** on the waste-risk model (split-conformal, calibrated April to June, tested July to mid-September): at a 90% target, coverage was 91.3%, 90.9%, 89.5% and 92.9% in the four years; 2% to 8% of units were flagged "uncertain" and their true waste rate was 40% to 56%. Accuracy on the confident units was 89% to 92%.

**3. Fridge-event detection.** 360 events in the year (4 consecutive hourly readings above 6 °C): median peak 9.8 °C, 44% above 10 °C, median duration 6 hours. A trigger on the first reading above 8 °C fires a median 2 hours earlier. 91 events (25%) are at the three 2G sites.

**4. Money and volume (annualised from the test window).** Status quo wastes about 2,900 red-cell and whole-blood units per four months. The recommended design avoids about **1,350 wasted units a year** and supplies about **1,400 more requested units a year**. At the Kenyan service's stated cost of about KES 10,000 (USD 97) per unit, avoided waste is worth about **USD 130,000 a year** in this synthetic network. The cost figure is from a 2017 report; treat it as an assumption.
