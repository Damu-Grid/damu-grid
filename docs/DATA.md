# Starter dataset facts

Inspected from the official `Hackathon Starter Dataset.zip` extracted into `data/raw/` on 10 November 2026. Column meanings are from `data/raw/DATA_DICTIONARY.md`. Headline year figures are from `data/raw/README.md` unless marked as file counts we measured.

Times in the data are East Africa Time (UTC+3). Empty cells mean "not applicable" or "not recorded."

## Terms

See `data/raw/README.md`. No SPDX licence. Official rules: use freely in the hackathon and demo; declare the synthetic starter dataset; do not present findings as facts about real Kenyan facilities; cite any added data; never use real donor, patient or facility records.

Folder size including the original zip: about **75 MB** (under the 90 MB planning threshold). CSVs and docs alone: about 37 MB.

## Tables (measured row counts and columns)

Blood groups: `O+ A+ B+ AB+ O- A- B- AB-`. Components: `RBC` red cells, `WB` whole blood, `PLT` platelets, `FFP` fresh frozen plasma, `CRYO` cryoprecipitate.

The official README lists `blood_system.sqlite`. **It was not in the zip.** Build a local database in `data/processed/` if needed.

| File | Rows (excl. header) | Columns | Date range observed in the file |
|---|---|---|---|
| `facilities.csv` | 47 | `facility_id,name,facility_type,county,lat,lon,keph_level,beds,grid_reliability,connectivity,supply_centre_id,makes_platelets,separates_components,has_blood_fridge_backup_power,routine_deliveries_per_week` | n/a |
| `routes.csv` | 2,162 | `from_facility_id,to_facility_id,road_km,typical_travel_hours,road_quality` | n/a |
| `donors.csv` | 43,363 | `donor_id,sex,birth_date,blood_group,home_county,donor_category,registration_date,registration_site_id,preferred_channel,consent_to_contact,phone_last4` | registration 2025-09-01 .. 2026-10-31 |
| `drives.csv` | 1,091 | `drive_id,date,collecting_site_id,county,venue_type,registered_donors,donations_collected,donors_deferred` | 2025-09-04 .. 2026-10-31 |
| `donations.csv` | 47,363 | `donation_id,donor_id,drive_id,collection_date,collecting_site_id,outcome,deferral_reason,volume_ml,screening_result,tti_marker,tested_date` | collection 2025-09-04 .. 2026-10-31; tested 2025-09-05 .. 2026-11-06 |
| `units.csv` | 49,426 | `unit_id,donation_id,component,blood_group,collection_date,expiry_date,processed_at_id,current_facility_id,status,status_date,temp_excursion_exposed,issued_request_id,opening_stock` | collection 2025-09-04 .. 2026-10-30; expiry 2025-09-10 .. 2027-10-30; status_date 2025-11-01 .. 2026-10-31 |
| `transfers.csv` | 35,181 | `transfer_id,unit_id,from_facility_id,to_facility_id,transfer_type,request_id,dispatched_at,received_at,transport_mode,coolbox_max_temp_c` | dispatched 2025-11-01 02:10:50 .. 2026-10-31 23:16:33; received 2025-11-01 02:52:58 .. 2026-11-01 07:19:53 |
| `requests.csv` | 17,430 | `request_id,facility_id,facility_name_raw,requested_at,clinical_indication,patient_sex,patient_age_band,patient_blood_group,component_requested,units_requested,urgency,units_issued,units_issued_group_substituted,units_from_local_stock,emergency_supplied_from_id,last_unit_available_at,outcome` | requested 2025-11-01 00:01:27 .. 2026-10-31 23:17:43; last_unit_available 2025-11-01 00:46:21 .. 2026-11-01 07:19:53 |
| `daily_stock.csv` | 185,785 | `date,facility_id,component,blood_group,units_in_stock_end_of_day` | 2025-11-01 .. 2026-10-31 |
| `power_outages.csv` | 2,609 | `outage_id,facility_id,start_time,end_time,duration_hours,backup_power_engaged` | start 2025-11-01 06:06:40 .. 2026-10-31 20:38:39 |
| `temperature_logs.csv` | 399,280 | `facility_id,recorded_at,temp_c` | 2025-11-01 00:00:00 .. 2026-10-31 23:00:00 |

The official README describes the modelled year as 1 November 2025 to 31 October 2026. Opening stock exists because units collected in September and October 2025 that were still on the shelf on 1 November are included (`opening_stock = True` on `units`). Some testing and receipt timestamps extend slightly into 6–7 November 2026.

Facility types include regional and satellite blood centres and several hospital types. `facility_id` prefixes: `RBTC-xxx`, `SAT-xxx`, `HSP-xxx`. Connectivity: 4G, 3G, 2G. `transfer_type`: `routine`, `emergency_request`, `emergency_cross_region`, `inter_centre_rebalancing`. Unit `status`: `in_stock`, `transfused`, `expired`, `discarded_temperature`. Request `outcome`: `fulfilled`, `partially_fulfilled`, `not_fulfilled`, `deferred_to_later`. Cool-box max above 10°C is an excursion (data dictionary). Safe fridge range for red cells and whole blood is 2 to 6°C.

Official README headline figures (not all re-derived here): 45,699 donation attempts in the period (the `donations.csv` file has 47,363 rows — do not silently average these); 11% deferred; 7.9% of collected donations reactive and discarded; about 6 in 10 donors are students; 17,430 requests for 34,242 units, 87% fully met; emergency resupply median about 5 hours; about 23% of red cell and whole blood units wasted; 2,119 units given to patients after a fridge or cool box had been out of range.

Blessings's later pitch notes that waste percentages move with the denominator (for example 8,620 wasted units as 23.2% of RBC/WB including closing stock). **Do not treat pitch percentages as already verified.** If we quote a waste or exposure count, recompute it, state the denominator, and label it synthetic. The evaluation also flagged 2,119 vs a later 2,112 figure — do not average them; check the product and denominator on the CSVs.

## How demand is derived

There is **no demand table**.

- Demand for forecasting and gaps: `requests.units_requested` joined on `requests.facility_id`, filtered to the product scope (Tier 1: `component_requested = RBC` and known `patient_blood_group`). Use requested quantity, not `units_issued`, because shortages constrain issues.
- Do not treat a missing request row as zero demand unless a completeness assumption is explicitly stated (see `docs/EVALUATION.md`).
- Unknown patient blood groups stay unknown; do not assign them to known groups.
- `daily_stock.units_in_stock_end_of_day` is inventory, not demand.
- `donations` may inform supply or collection context (Tier 2 / optional). They are not hospital demand.
- Use `facility_id`. `facility_name_raw` is messy on about 14% of requests.

## Snapshot convention (avoid leakage)

The live review queue is built from an **explicit closing-date snapshot** (planned default: end of 31 October 2026), using `daily_stock` for that date plus `units` that are `in_stock` at `current_facility_id` with `expiry_date` still in the future as of that as-of time.

Do **not** reconstruct a July inventory from final `current_facility_id` / `status` at year end. Forecast features may use only requests **strictly before** each forecast origin.

### Closing snapshot as built (measured 10 November 2026, `python -m pipeline build`)

As-of `2026-10-31T23:59:59+03:00`. Filters applied in `pipeline/snapshot.py`, in order:

| Filter | Units |
|---|---:|
| `units.status = in_stock` | 8,666 |
| removed: `expiry_date` on or before the as-of date | 0 |
| removed: donation tested after the as-of time (not yet released) | 0 |
| removed: last transfer received after the as-of time (still in transit) | 0 |
| removed: last transfer destination differs from `current_facility_id` | 0 |
| **On the shelf at as-of** | **8,666** |
| of which receipt never confirmed (`received_at` missing), kept and flagged | 27 |
| of which `temp_excursion_exposed = True`, kept and flagged | 111 |

Reconciliation: the 8,666 units match `daily_stock` for 31 October 2026 in every facility × component × group cell (509 cells, 0 differences). By component: FFP 6,889, RBC 738, WB 516, CRYO 504, PLT 19. RBC on the shelf: 504 at hospitals, 234 at regional centres.

Leakage guard: the snapshot refuses any as-of earlier than the last recorded status change or dispatch (`LeakageError`), because `current_facility_id` and `status` are year-end values. Tests in `tests/pipeline/test_snapshot.py` check that a unit received after the as-of time, or tested after it, is not counted on the shelf.

## Eligibility rules (Tier 1 default)

A unit is eligible for a suggested transfer only if all of the following hold. Settings should be configurable (Tier 2 country/config).

- `component = RBC` (Tier 2 may add `PLT` and others with their own shelf-life policy).
- `blood_group` is a known exact group, not missing or `unknown`.
- `status = in_stock`.
- `expiry_date` is after expected arrival (`typical_travel_hours` plus a documented allowance).
- `temp_excursion_exposed` is not true. Missing safety evidence is treated conservatively (do not suggest).
- The unit is not already reserved or in transit in our action store.
- Sender remains at or above its reserve after the move; recipient has a documented target gap.
- Route exists and `road_quality` / travel time are recorded.

Historical `transfers` inform workload and optional policy comparison; they do not bypass eligibility.

### Eligibility as implemented (`pipeline/eligibility.py`, measured 10 November 2026)

Team defaults from `pipeline/settings/kenya_default.toml` (our choice, configurable, not a regulation): RBC must keep **168 hours (7 days)** of life after the expected arrival; expected arrival = as-of + `typical_travel_hours` + **6 hours** allowance; a unit is treated as expiring at 00:00 on its `expiry_date`; the sender keeps **2 units** of the same component and group by default (the forecast may pass a per-site reserve); the recipient must be one of the 32 hospitals with a gap supplied by the demand estimator or the fallback rule.

Unit-level result on the closing snapshot, before cold-chain flags: of **738 RBC** on the shelf, **637 are eligible**; 87 are excluded because `temp_excursion_exposed = True` and 17 because their last receipt was never confirmed (3 units have both). With the DG-07 cold-chain flags, **488** remain eligible (see below). No RBC on the shelf has an unknown group. Eligible RBC: 406 at hospitals, 231 at regional centres. Each excluded unit carries every reason that applies (`reasons`), so the review screen and the judges can see why.

## Deliberate data-quality problems (official README)

- About 450 donors (1%) are registered twice under different IDs.
- About 1.2% of donor records have no blood group.
- 14% of requests have the facility name typed differently; `facility_id` is the truth.
- 5% of emergency requests record the patient blood group as `unknown`.
- About 3% of transfers have no `received_at`.
- Temperature loggers drop out for hours, more often on 2G or 3G.
- 60 temperature readings are sensor glitches: `-99.0`, `99.9` or `0.0`.
- Some donors gave blood again before the minimum gap.

Shelf lives in the model (dataset README): red cells 42 days, whole blood 35, platelets 5, plasma and cryo 1 year.

### How the pipeline handles them (`pipeline/quality.py`, measured 10 November 2026)

`python -m pipeline validate` writes these counts to `data/processed/quality_report.json`.

| Problem | Measured in the CSVs | Handling |
|---|---|---|
| Facility names typed differently | 1,852 of 17,430 requests (10.6%) differ from `facilities.name`: 1,142 by case or spacing only, 710 by abbreviation (`CRH`, `Hosp.`, a missing "(Nairobi)"). Every one of them resolves to the recorded `facility_id`: 0 ambiguous, 0 pointing to another facility, 0 unmatched | Keyed by `facility_id`; the typed name is kept as typed and only compared. Ambiguous or wrong-site names would be flagged for a human look. The official README says about 14%: our exact-string comparison finds 10.6%, a discrepancy we report rather than adjust |
| Unknown patient group | 442 requests, all emergencies (5.0% of 8,768) | Stays `unknown`; never assigned to a group |
| Missing `received_at` | 1,046 of 35,181 transfers (3.0%) | `receipt_status = unconfirmed`, no transit time; in the snapshot, 27 units on the shelf (17 RBC) are flagged and not suggested |
| Temperature glitches | 55 readings: 17 × −99.0, 16 × 99.9, 22 × 0.0 | Classified `glitch`, never an excursion. The official README says 60; we find 55 exact matches and report the difference |
| Readings above 6 °C (RBC/WB range) | 4,607 (none below 2 °C apart from the 0.0 glitches) | Input to DG-07 cold-chain events |
| Logger drop-outs | 373 silences of 6 hours or more, 12,230 missing hours in total (3 of them still open at the as-of time: HSP-021 for 22 h, RBTC-ELD for 8 h, RBTC-EMB for 9 h) | Reported as missing evidence (DG-07), never as "no problem" |
| Donor duplicates | 452 sets, 904 records sharing birth date, sex, county and phone last 4 | Listed for review, never merged automatically |
| Donors with no group | 506 (1.2%) | Kept missing |

### Cold-chain flags (`pipeline/coldchain.py`, DG-07, measured 10 November 2026)

Team defaults: an excursion is at least **2 consecutive hourly readings** outside 2–6 °C (glitches and gaps break a run); a logger gap is **6 hours** or more without a reading; an outage counts if it lasts **1 hour** or more with no backup on the blood fridge; a cool box above **10 °C** is an excursion (data dictionary). Fridge evidence is attached only to components kept in the blood fridge (RBC, WB); the dataset has no storage evidence for platelets or frozen plasma.

| Evidence | Sites (events) | RBC on the shelf at as-of, evidence anywhere in their custody (units) |
|---|---:|---:|
| Fridge excursion | 553 | 100 |
| Outage without backup | 1,017 | 120 |
| Logger gap | 373 | 200 |
| Cool-box excursion | — | 0 |
| Official `temp_excursion_exposed` | — | 87 |
| Receipt unconfirmed | — | 17 |

### Other components (DG-08, Tier 2, behind a flag)

Each component has its own policy in `pipeline/settings/kenya_default.toml`: shelf life (RBC 42, WB 35, PLT 5, FFP and CRYO 365 days, all matching `expiry_date − collection_date` in `units.csv`), whether it is in the queue, the remaining life required on arrival (PLT 24 hours) and a maximum road time (PLT 6 hours). Only RBC is in the queue by default. `python -m pipeline build --enable PLT` computes platelet eligibility without changing the RBC result: 19 platelets are on the shelf at as-of and all 19 pass the unit checks. Caveat: the dataset has no storage evidence for platelets (the fridge logs describe the 2–6 °C blood fridge), so platelet eligibility is less informed than RBC. Do not present multi-component support in the demo or README unless the demand path and API are ready (DG-17, DG-29).

A site event is attached to a unit only if it happened while the unit was at that site, using the unit's own time-stamped custody chain (processing centre from release to first dispatch, then each destination from recorded receipt to the next dispatch), never its final location. With these flags, **488 of 738 RBC** remain eligible. A fridge that stops reporting and never reports again is silent through the as-of time: the trailing silence counts as a logger gap (3 fridges, 113 RBC on their shelves).

**Check against the official flag:** of the 87 RBC on the shelf that the dataset marks `temp_excursion_exposed = True`, our evidence independently finds **all 87** (111 of 111 for RBC and WB together). It also finds evidence on **149 more RBC** (251 RBC and WB) that the official flag does not mark: short excursions, outages without backup, and logger gaps (many from the three fridges that went silent before the closing time); they are held back for review, not declared unsafe. Peak temperature is the reading furthest outside 2–6 °C.

## Redistribution starting tables

The official dataset README says to start redistribution work with `daily_stock`, `units`, `routes`, and `transfers`. We also need `requests` (demand), `facilities` (context), and for Tier 2 cold-chain flags `power_outages` and `temperature_logs`.

## Measured category counts (from the CSVs, 10 November 2026)

These are file counts, not official README headlines.

**`facilities.facility_type` (47 rows):** `county_referral` 21, `satellite_blood_centre` 9, `regional_blood_centre` 6, `county_hospital` 4, `national_referral` 2, `private_hospital` 2, `maternity_hospital` 1, `mission_hospital` 1, `sub_county_hospital` 1.

Hospital demand filter (planned default): the seven hospital types above (32 sites), not the 15 blood centres, unless a later written decision expands it. Confirm in code against this list, not against guessed KEPH labels. `keph_level` is missing on 15 facilities (the 15 blood centres).

**`facilities.connectivity`:** `4G` 25, `3G` 19, `2G` 3.

**`requests.component_requested`:** `RBC` 16,209, `FFP` 843, `PLT` 378 (no `WB` or `CRYO` request rows in this file).

**`requests.urgency`:** `emergency` 8,768, `urgent` 4,384, `routine` 4,278.

**`requests.patient_blood_group`:** `O+` 7,821, `A+` 4,272, `B+` 3,454, `AB+` 671, `unknown` 442, `O-` 333, `A-` 198, `B-` 189, `AB-` 50.

**`units.status`:** `transfused` 29,650, `in_stock` 8,666, `expired` 7,173, `discarded_temperature` 3,937.

**`units.component`:** `RBC` 24,067, `WB` 13,080, `FFP` 8,681, `PLT` 3,040, `CRYO` 558.

**`units.temp_excursion_exposed`:** `False` 42,314, `True` 7,112.
