# pipeline/

ETL, validation against `data/raw/DATA_DICTIONARY.md`, SQLite schema, closing-date snapshot, eligibility engine, and Tier 2 cold-chain flags.

**Owner:** Brayan (`Sorghobrayan-dotcom`).

**Status:** empty on purpose. All application code is written in the official window.

Rules:

- Read official CSVs from `data/raw/`. Never modify that folder.
- Write derived files only to `data/processed/` (gitignored).
- Join facilities on `facility_id` only.
- Demand is not computed here beyond exposing `requests` cleanly; Blessings owns demand maths in `forecasting/`.
- Eligibility must be conservative when safety evidence is missing. Sensor glitches (−99.0, 99.9, 0.0) are not clinical events.

Column facts: `docs/DATA.md`.
