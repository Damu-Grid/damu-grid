"""The frozen forecast evaluation harness (issue DG-12).

One command rebuilds everything from ``data/raw/``:

    uv run python -m forecasting.evaluate

Outputs go to ``data/processed/`` (git-ignored): the row-level forecast table, a metrics JSON and
a short Markdown summary ready to paste into the README. Both models are always reported, even
when the candidate loses. Every figure is synthetic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from forecasting.baseline import baseline_forecast
from forecasting.candidate import candidate_forecast
from forecasting.config import (
    CONFIG,
    PROCESSED_DIR,
    RAW_DIR,
    ForecastConfig,
    calibration_origins,
    evaluation_origins,
)
from forecasting.demand import DemandSlice, load_demand_slice, period_totals
from forecasting.uncertainty import calibrate, coverage, upper_bound

MODELS = ("baseline", "candidate")
BOOTSTRAP_SEED = 2026
BOOTSTRAP_DRAWS = 5000


@dataclass(frozen=True)
class EvaluationResult:
    table: pd.DataFrame  # origin, facility_id, blood_group, actual, baseline, candidate
    metrics: dict
    exclusions: dict[str, int]


def forecast_table(
    sliced: DemandSlice, origins: list[date], config: ForecastConfig = CONFIG
) -> pd.DataFrame:
    """One row per origin x hospital x known group with the actual and both forecasts."""
    frames = []
    for origin in origins:
        outcome_end = origin + timedelta(days=config.horizon_days)
        if outcome_end - timedelta(days=1) > date(2026, 10, 31):
            raise ValueError(f"Outcome window for origin {origin} runs past the end of the data.")
        actual = period_totals(
            sliced.daily,
            origin,
            outcome_end,
            sliced.hospitals,
            sliced.groups,
            config.assume_complete_requests,
        )
        frame = pd.DataFrame(
            {
                "actual": actual,
                "baseline": baseline_forecast(
                    sliced.daily, origin, sliced.hospitals, sliced.groups, config
                ),
                "candidate": candidate_forecast(
                    sliced.daily, origin, sliced.hospitals, sliced.groups, config
                ),
            }
        )
        frame.insert(0, "origin", pd.Timestamp(origin))
        frames.append(frame.reset_index())
    return pd.concat(frames, ignore_index=True)


def error_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    """RMSE, MAE, bias (mean predicted minus actual) and sample count, in requested units."""
    error = predicted - actual
    return {
        "rmse": float(np.sqrt((error**2).mean())),
        "mae": float(error.abs().mean()),
        "bias": float(error.mean()),
        "n": int(len(error)),
    }


def paired_rmse_difference(
    table: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED
) -> dict:
    """Candidate RMSE minus baseline RMSE, with a bootstrap over forecast origins.

    Resampling whole origins keeps the dependence between cells that share a week. A negative
    difference means the candidate has the lower error.
    """
    grouped = table.groupby("origin")
    sq_candidate = grouped.apply(lambda g: ((g["candidate"] - g["actual"]) ** 2).sum()).to_numpy()
    sq_baseline = grouped.apply(lambda g: ((g["baseline"] - g["actual"]) ** 2).sum()).to_numpy()
    counts = grouped.size().to_numpy().astype(float)

    point = float(
        np.sqrt(sq_candidate.sum() / counts.sum()) - np.sqrt(sq_baseline.sum() / counts.sum())
    )
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(counts), size=(draws, len(counts)))
    n = counts[picks].sum(axis=1)
    diffs = np.sqrt(sq_candidate[picks].sum(axis=1) / n) - np.sqrt(
        sq_baseline[picks].sum(axis=1) / n
    )
    low, high = np.percentile(diffs, [2.5, 97.5])
    return {
        "rmse_difference": point,
        "ci95_low": float(low),
        "ci95_high": float(high),
        "draws": draws,
        "seed": seed,
        "resampled_unit": "forecast origin",
    }


def summarise(table: pd.DataFrame) -> dict:
    metrics: dict = {"overall": {}, "o_negative": {}}
    for model in MODELS:
        metrics["overall"][model] = error_metrics(table["actual"], table[model])
        oneg = table[table["blood_group"] == "O-"]
        metrics["o_negative"][model] = error_metrics(oneg["actual"], oneg[model])

    base, cand = metrics["overall"]["baseline"], metrics["overall"]["candidate"]
    metrics["rmse_reduction_pct"] = float(100 * (base["rmse"] - cand["rmse"]) / base["rmse"])
    metrics["mae_reduction_pct"] = float(100 * (base["mae"] - cand["mae"]) / base["mae"])
    metrics["paired_bootstrap"] = paired_rmse_difference(table)
    metrics["candidate_wins"] = bool(cand["rmse"] < base["rmse"])
    metrics["share_of_zero_actual_cells"] = float((table["actual"] == 0).mean())
    metrics["observations"] = {
        "rows": int(len(table)),
        "origins": int(table["origin"].nunique()),
        "hospitals": int(table["facility_id"].nunique()),
        "groups": int(table["blood_group"].nunique()),
    }
    return metrics


def evaluate(raw_dir: Path = RAW_DIR, config: ForecastConfig = CONFIG) -> EvaluationResult:
    sliced = load_demand_slice(raw_dir, config)
    calibration = forecast_table(sliced, calibration_origins(config), config)
    origins = evaluation_origins(config)
    table = forecast_table(sliced, origins, config)
    multiplier = calibrate(calibration, config.upper_bound_level, config.upper_bound_scale_offset)
    table["candidate_upper"] = upper_bound(
        table["candidate"], multiplier, config.upper_bound_scale_offset
    )
    metrics = summarise(table)
    metrics["upper_bound"] = {
        "method": "scaled one-sided residual bound",
        "nominal_level": config.upper_bound_level,
        "multiplier": multiplier,
        "calibration_origins": len(calibration_origins(config)),
        "calibration_rows": len(calibration),
        "overall": coverage(table["actual"], table["candidate_upper"]),
        "o_negative": coverage(
            table.loc[table["blood_group"] == "O-", "actual"],
            table.loc[table["blood_group"] == "O-", "candidate_upper"],
        ),
        "note": (
            "Synthetic retrospective coverage; not a clinical probability "
            "or per-site guarantee"
        ),
    }
    return EvaluationResult(table=table, metrics=metrics, exclusions=sliced.exclusions)


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def summary_markdown(result: EvaluationResult, config: ForecastConfig = CONFIG) -> str:
    m, o = result.metrics, result.metrics["observations"]
    base, cand = m["overall"]["baseline"], m["overall"]["candidate"]
    ob, oc = m["o_negative"]["baseline"], m["o_negative"]["candidate"]
    boot = m["paired_bootstrap"]
    bound = m["upper_bound"]
    verdict = (
        "The candidate has the lower RMSE."
        if m["candidate_wins"]
        else "The candidate does NOT beat the baseline; the live queue should use the baseline."
    )
    ex = result.exclusions
    return "\n".join(
        [
            "## Demand forecast: baseline vs candidate (synthetic data)",
            "",
            f"Seven-day requested {config.component} units per hospital x known blood group, "
            "forecast at "
            f"{o['origins']} weekly origins from {config.first_origin} to {config.last_origin}. "
            f"{o['rows']:,} observations ({o['hospitals']} hospitals x {o['groups']} groups x "
            f"{o['origins']} origins). {_fmt(100 * m['share_of_zero_actual_cells'], 1)}% of cells "
            "have zero actual demand; a missing request is treated as zero under the stated "
            "completeness assumption.",
            "",
            "| Model | RMSE | MAE | Bias | N |",
            "|---|---:|---:|---:|---:|",
            f"| 28-day average (baseline) | {_fmt(base['rmse'])} | {_fmt(base['mae'])} | "
            f"{_fmt(base['bias'])} | {base['n']:,} |",
            f"| Pooled expanding mean (candidate) | {_fmt(cand['rmse'])} | {_fmt(cand['mae'])} | "
            f"{_fmt(cand['bias'])} | {cand['n']:,} |",
            "",
            f"{verdict} RMSE changes by {_fmt(m['rmse_reduction_pct'], 1)}% and MAE by "
            f"{_fmt(m['mae_reduction_pct'], 1)}% (positive = candidate better). "
            "Paired bootstrap over origins, candidate minus baseline RMSE: "
            f"{_fmt(boot['rmse_difference'])} "
            f"(95% interval {_fmt(boot['ci95_low'])} to {_fmt(boot['ci95_high'])}; "
            "a negative value "
            "favours the candidate).",
            "",
            f"O-negative only (N={ob['n']:,}): baseline RMSE {_fmt(ob['rmse'])}, candidate RMSE "
            f"{_fmt(oc['rmse'])}.",
            "",
            f"One-sided {bound['nominal_level']:.0%} upper bound calibrated on "
            f"{bound['calibration_origins']} May–June origins "
            f"({bound['calibration_rows']:,} cells): measured July–October coverage "
            f"{bound['overall']['rate']:.1%} overall and "
            f"{bound['o_negative']['rate']:.1%} for O-negative. This is a synthetic "
            "retrospective model bound, not a clinical probability or per-site guarantee.",
            "",
            f"Slice: {ex['request_rows_used']:,} of {ex['request_rows_total']:,} "
            "request rows used. "
            f"Excluded: {ex['not_hospital']:,} non-hospital rows, {ex['other_component']:,} other "
            f"component rows, {ex['unknown_or_missing_group']:,} unknown or missing "
            "blood group rows.",
            "",
            f"Frozen split: estimator specified on data to {config.learn_end}; "
            "upper-bound calibration "
            f"{config.calibration_start} to {config.calibration_end}; evaluation origins "
            f"{config.first_origin} to {config.last_origin}. Features use only requests strictly "
            "before each origin. Results describe the synthetic starter dataset, "
            "not real facilities.",
            "",
        ]
    )


def write_outputs(result: EvaluationResult, out_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "table": out_dir / "forecast_table.csv",
        "metrics": out_dir / "forecast_metrics.json",
        "summary": out_dir / "forecast_summary.md",
    }
    result.table.to_csv(paths["table"], index=False)
    payload = {"metrics": result.metrics, "exclusions": result.exclusions}
    paths["metrics"].write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths["summary"].write_text(summary_markdown(result), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rebuild the frozen demand forecast evaluation.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args(argv)
    result = evaluate(args.raw_dir)
    paths = write_outputs(result, args.out_dir)
    print(summary_markdown(result))
    for label, path in paths.items():
        print(f"wrote {label}: {path}")


if __name__ == "__main__":
    main()
