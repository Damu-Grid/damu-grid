# tests/

Shared automated tests. Safety and state-machine tests are not optional.

**Owners:** everyone, in their area.

## Commands

From the repository root:

```bash
uv sync                               # or: pip install pandas numpy pytest ruff
uv run pytest                         # everything
uv run pytest tests/pipeline -m "not dataset"   # pipeline unit tests only (~10 s, tiny synthetic fixtures)
uv run pytest -m dataset              # smoke checks on the full official CSVs (~1 min)
uv run ruff check .
```

## Pipeline (`tests/pipeline/`)

- `conftest.py` writes a tiny world (3 sites, 12 units, planted excursion, glitch, outage, logger gap, unconfirmed receipt, in-transit and unreleased units) as official-format CSVs and loads it through the real loader.
- `test_load.py` (DG-01): missing, unexpected or mistyped columns fail loudly; unknown facility ids fail; `data/raw` is never written; official row counts.
- `test_store.py` (DG-02): official column names kept, added tables prefixed `dg_`, one active move per unit, audit trail append-only.
- `test_snapshot.py` (DG-03): as-of behaviour — a unit received or released after the as-of time is not on the shelf; earlier as-of refused; reconciliation with `daily_stock`.
- `test_eligibility.py` (DG-04): every exclusion category (exposed, expired, unknown group, reserved, unrouted, short life, sender reserve, no recipient gap) and the shared config.
- `test_quality.py` (DG-05): facility names, unknown groups, missing receipts, glitches, logger gaps, donor duplicates.
- `test_coldchain.py` (DG-07): excursion events, outages, gaps, unit attachment by time on shelf, missing evidence never marks a unit safe.
- `test_components.py` (DG-08): per-component policy, platelets behind a flag.
- `test_official_dataset.py` (DG-06, `dataset` marker): pins the measured numbers in `docs/DATA.md` and runs `python -m pipeline build` end to end.

## Planned

- `pytest` for API actions (version conflicts, double reservation, quarantine cannot be cleared by the model) and the frozen evaluation arithmetic
- Playwright for the coordinator accept / change / reject / fallback click path
