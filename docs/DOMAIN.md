# Domain primer (blood inventory and redistribution)

This is orientation for the team and for coding agents. It is **not** clinical advice, not a claim of compliance, and not a reason to hard-code another country's policy as if it were universal. Shelf lives, reserves and remaining-life rules belong in config (`docs/API_SPEC.md` settings). Our product suggests transfers for a coordinator; it does not release blood for transfusion or decide compatibility.

## What the official dataset already models

From `data/raw/README.md` (synthetic, Kenya-inspired year 1 November 2025–31 October 2026):

- Shelf lives in the model: red cells 42 days, whole blood 35 days, platelets 5 days, plasma and cryo 1 year.
- Safe fridge range stated for red cells and whole blood: 2 to 6°C. Cool-box maximum above 10°C is an excursion (data dictionary).
- Units can be marked `temp_excursion_exposed`. Official headline: 2,119 units were given to patients after a fridge or cool box had been out of range (recompute before quoting a new figure).
- Connectivity and power vary by site; temperature loggers drop out; some transfers lack `received_at`.

## Why redistribution exists

Blood components are perishable, demand is uneven, and a unit that will expire in a low-use fridge can sometimes be used at a higher-use site if it is moved with enough remaining life and a documented chain of custody. That is the coordinator problem we are building for. Guidance below is from public inventory-management documents, cited so we can stay honest about what is a **local policy** versus a widely stated practice.

## Widely stated practices (cited)

**First-expiry-first-out (FEFO) and moving soon-to-outdate units.** Canadian Blood Services' inventory best-practices guide describes FEFO (shortest shelf life issued first), tagging soon-to-outdate units, and redistributing those units to nearby higher-demand hospitals with validated temperature-controlled packaging and complete transfer documentation. ([CBS inventory management best practices](https://professionaleducation.blood.ca/en/transfusion/best-practices/blood-utilization-best-practices/blood-system-inventory-management-best); [CBS hospital redistribution overview](https://www.blood.ca/en/hospital-services/inventory-ordering/hospital-redistribution).)

**Documented transfer arrangements and remaining shelf life as an agreed range, not a single global law.** Australia's National Blood Authority, *National Guidance for the Management of Red Blood Cell Inventory* (September 2025), recommends that laboratories set transfer arrangements so older red cells move to sites more likely to use them before expiry, that the transfer age is agreed and documented, and that **7–14 days' shelf life remaining on arrival** is a commonly used planning range. The receiving site should be notified so the units enter its inventory count and it does not over-order. ([PDF](https://www.blood.gov.au/sites/default/files/documents/2025-09/National%20Guidance%20for%20the%20Management%20of%20Red%20Blood%20Cell%20Inventory.pdf); [resource page](https://www.blood.gov.au/blood-products/blood-product-management/blood-and-inventory-management-resources).)

**A local minimum remaining life can be stricter.** Newfoundland and Labrador's *Inter-Hospital Transfer of Blood Components and Blood Products* policy requires red-cell units to have **at least 10 days remaining** at transfer unless the receiving hospital agrees to a shorter remaining shelf life. That is a **provincial policy**, not a world standard. We may offer 10 days as one configurable default, never as "the AABB/WHO rule." ([PDF](https://www.gov.nl.ca/hcs/files/bloodservices-resources-pdf-inter-hospital-transfer.pdf).)

**Establishment practices: storage, records, temperature, expiry separation.** WHO, *Good practices for blood establishments* (2025), published as Annex 4 of WHO Technical Report Series 1060 (ISBN 978-92-4-011361-9), discusses secure and segregated storage, monitoring within defined temperature limits, alarms and contingencies for equipment or power failure, first-expiring-first-out, and distribution that does not compromise quality. Use this as a reminder that quarantine, incomplete temperature evidence, and missing receipt records are operationally meaningful — which is why our eligibility engine is conservative and receipt is not transfusion release. ([WHO publication page](https://www.who.int/publications/m/item/trs-1060---annex-4--good-practices-for-blood-establishments); [WHO bibliographic record](https://www.who.int/publications/b/78804).)

**AABB Standards.** The AABB *Standards for Blood Banks and Transfusion Services*, 34th edition, became effective 1 April 2024. The text is paid; this team has not relied on a cover-to-cover reading. Do not invent clause numbers or numeric limits and attribute them to AABB. If a specific standard is later cited, quote only from a source someone on the team has actually read.

## How this maps to Damu Grid

| Domain idea | Our implementation choice |
|---|---|
| FEFO / soon-to-outdate movement | Expiry-aware ranking on eligible `in_stock` RBC (Tier 1), not automatic issue to a patient |
| Remaining shelf life on arrival | Config: expected travel from `routes.typical_travel_hours` plus a documented allowance; optional minimum remaining days (default to be chosen in-window, not asserted as international law) |
| Documented transfers | Accept / Change / Reject, reservation, dispatch, receipt, audit |
| Temperature and power | Tier 2 flags from `temperature_logs` and `power_outages`; glitch values (−99.0, 99.9, 0.0) are not clinical events |
| Person in control | No silent move; fallback if the estimator is off |
| Different products | Platelets (5-day model life) are Tier 2 and need a tighter policy than RBC |

## What we will not decide in software

- Transfusion release or ABO/Rh compatibility matching.
- Overriding a quarantine from incomplete evidence.
- Ranking patients.
- Contacting real donors or patients.
- Claiming a modelled reduction in expiry equals lives or money saved.
