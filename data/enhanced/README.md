# Annotated synthetic starter tables

These CSVs are derived from the organiser's **Hackathon Starter Dataset.zip**, already committed under [`../raw/`](../raw/). They were prepared locally before the code-build window and are supplied as reference data, not submitted application code. No external dataset was imported. Cite the **Terumo BCT Africa Hackathon 2026 synthetic starter dataset** (supplied to participants) and [`../raw/DATA_DICTIONARY.md`](../raw/DATA_DICTIONARY.md) when using these records. All records remain synthetic.

The four tables with new quality annotations are included here, plus `facilities.csv` so the forecast harness can read this directory directly. Join the other six tables from `data/raw/` by their documented IDs. Original row order and row counts are preserved. Original columns are preserved except for 55 invalid temperature sentinels: `temp_c` is blank and the original is retained in `temp_c_raw`.

| Table | Rows | Added fields | Use and limits |
|---|---:|---|---|
| `requests.csv` | 17,430 | `facility_name_canonical`, `blood_group_known` | Canonical name is looked up by `facility_id`; use the ID as the key. The 442 unknown patient groups remain unknown. Do not use fulfillment outcomes as forecast features. |
| `donors.csv` | 43,363 | `blood_group_known`, `possible_duplicate_group` | 904 rows in 452 possible duplicate groups are flagged for review, never merged automatically. 506 donor groups are missing or unknown. No donor contact is authorized. |
| `temperature_logs.csv` | 399,280 | `temp_c_raw`, `sensor_quality`, `outside_rbc_storage_range` | 55 sentinel readings are unknown, not safe. The range flag is a screening aid, not release clearance; keep outage and missing-log context. |
| `transfers.csv` | 35,181 | `receipt_status` | 1,046 absent receipt timestamps are `unconfirmed`, never imputed. |
| `facilities.csv` | 47 | none; exact copy of raw | Included for the standalone forecast command. |

## Integrity and benchmark

The raw-column projection was compared row by row with `data/raw/`: no original fields changed in requests, donors, or transfers; only the 55 invalid `temp_c` values changed in temperature logs, with their originals in `temp_c_raw`. SHA-256 of the committed Git blobs (line-ending conversion may change working-copy bytes on Windows):

| File | SHA-256 |
|---|---|
| `donors.csv` | `6cd7aaa39ab2bc8be9ddc526641da087a74fae97fda5f53a688d45e619fb31d9` |
| `requests.csv` | `cd699c7bf723bb3c01d57767db5c6eb8c7bbe9c69984cb079438a0fee8ef3654` |
| `temperature_logs.csv` | `53bc56596aaedc3f92da102236c9b19672f49a60a11e6a7b0d93152cb71d3791` |
| `transfers.csv` | `bf68f17358395774cfc4d2e915fd13f5a240b1d4d826eedfde73fb28337c1aca` |
| `facilities.csv` | `270565fd9431fc184e786faf82cded0539078b4b4b37942cda4bf3a4a7742d03` |

Run `uv run python -m forecasting.evaluate --raw-dir data/enhanced --out-dir data/processed/enhanced` from the repository root. The current forecast uses only original request fields, so this data does **not** improve the measured forecast score; see `docs/ENHANCED_DATA_EVALUATION.md`. Use these annotations for quality-aware cold-chain, receipt, and donor-review scenarios, and evaluate any policy change on a fixed holdout before claiming improvement. Never infer historical stock from final unit status or use future outcomes at a forecast origin.
