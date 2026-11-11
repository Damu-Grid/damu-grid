# scripts/

Small developer and submission helpers created in the window (for example: load CSVs, run the evaluation command, export a metrics snippet for the README, check that `.env` is not staged).

**Owners:** everyone.

Use `uv run python -m pipeline build` to validate the official synthetic CSVs and build the shared ignored `data/processed/damu_grid.sqlite`. The pipeline verifies the 31 October 2026 closing-stock rows and writes the as-of snapshot and cold-chain flags. To preserve an existing snapshot, provide a separate path with `--db data/processed/validation.sqlite`. The source files under `data/raw/` are read-only.

No secrets in scripts. No rewrite of files under `data/raw/`.
