# Annotated data and the frozen forecast benchmark

**Source and citation.** The local `data/enhanced/` files are a quality-annotated derivative of the Terumo BCT Africa Hackathon 2026 **synthetic organiser starter dataset**. See [`data/enhanced/README.md`](../data/enhanced/README.md) for fields, SHA-256 hashes, and limits, and [`data/raw/DATA_DICTIONARY.md`](../data/raw/DATA_DICTIONARY.md) for original meanings. No third-party dataset was acquired or merged. This is not evidence about real Kenyan facilities.

**Evaluation.** On 10 November 2026, the same frozen `forecasting.evaluate` harness was run on `data/raw/` and `data/enhanced/`. Both use 17 weekly July–October 2026 origins, 32 hospitals, eight known blood groups, and 4,352 seven-day forecast cells. The paired bootstrap and calibration settings are unchanged. The JSON metrics and exclusions match exactly, not just at displayed precision.

| Input | 28-day baseline RMSE | Pooled candidate RMSE | Candidate MAE | 90% upper-bound coverage |
|---|---:|---:|---:|---:|
| Official raw starter data | 2.792 | 2.474 | 1.331 | 88.8% |
| Quality-annotated starter data | 2.792 | 2.474 | 1.331 | 88.8% |

The candidate's 11.4% RMSE improvement is **against the 28-day baseline on the same synthetic data**, not a gain caused by enrichment. The forecast only reads `requests` original fields and raw-equivalent `facilities`; the new annotations therefore cannot change its score. Its measured 90% upper-bound coverage is 88.8%, below nominal. Do not describe this as a calibrated clinical probability.

Reproduce from the repository root:

```powershell
uv run python -m forecasting.evaluate --raw-dir data/raw --out-dir data/processed/raw-check
uv run python -m forecasting.evaluate --raw-dir data/enhanced --out-dir data/processed/enhanced-check
uv run python -c "import json,pathlib; p=pathlib.Path('data/processed'); a=json.loads((p/'raw-check/forecast_metrics.json').read_text()); b=json.loads((p/'enhanced-check/forecast_metrics.json').read_text()); print('identical:',a==b)"
```

**Where added fields may help.** `sensor_quality`, `outside_rbc_storage_range`, and `receipt_status` can support explicit missing-evidence and cold-chain scenario checks. `possible_duplicate_group` can support human data review. Those uses need their own fixed scenario protocol and a comparison against the same safety rules before any improvement claim. Never turn an unknown group, receipt, or temperature into a known-safe value, and never use post-origin outcome fields in forecasting.
