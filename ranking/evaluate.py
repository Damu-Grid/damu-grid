"""python -m ranking.evaluate: reproduce the validation table of the survival score.

Same split as docs/EVALUATION.md: calibration origins in May-June 2026, test origins weekly from
1 July to 21 October 2026, units scored only when their outcome is final (expiry on or before
31 October 2026). Results are reported separately for whole blood and red cells (product_type),
with a total row in addition, never instead. Compared with: constant base rate, days left only,
the rank rule (the compound Poisson lower bound of ranking.queue) and the exact queue. Writes
data/processed/ranking_evaluation.json and .md.

The only inputs are the official CSVs; nothing is random, so two runs give the same numbers.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from forecasting.config import CONFIG, HOSPITAL_FACILITY_TYPES, PROCESSED_DIR, evaluation_origins
from pipeline.config import load_config
from pipeline.load import load_all
from pipeline.snapshot import build_snapshot
from ranking.calibration import (
    auc,
    brier,
    calibration_gap,
    isotonic_apply,
    isotonic_fit,
    log_loss,
    reliability_table,
)
from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.queue import rank_lower_bound
from ranking.score import survival_scores

END = pd.Timestamp("2026-10-31")  # last day of the data: outcomes are final up to here
DAYS_LEFT_SCALE = 7.0  # the "days left only" baseline is days_left / (days_left + this)
FINAL_STATUSES = ("transfused", "expired")
TABLES = ["facilities", "donations", "units", "transfers", "daily_stock", "requests"]
METHODS = {
    "constant": "Constant base rate (calibration window)",
    "days_left": "Days left only",
    "rank_rule": "Rank rule, compound Poisson",
    "exact": "Exact oldest-first queue",
    "exact_isotonic": "Exact queue + isotonic recalibration (calibration window)",
}


def calibration_origins() -> list[date]:
    """Weekly origins of the calibration window: 1 May to 26 June 2026."""
    first = CONFIG.calibration_start
    count = (date(2026, 6, 26) - first).days // 7 + 1
    return [first + timedelta(days=7 * k) for k in range(count)]


def arrived_units(
    units: pd.DataFrame, transfers: pd.DataFrame, hospitals: set[str], components: Sequence[str]
) -> pd.DataFrame:
    """Units of the pool that ended in a hospital, with the day they arrived there.

    The arrival day is the receipt (else the dispatch) of the unit's last transfer. A unit is
    only placed on a hospital shelf from that day on, so a final location is never used to put a
    unit somewhere earlier. Units that never moved have no recorded arrival and are left out.
    """
    pool = units[
        units["component"].isin(components)
        & units["blood_group"].notna()
        & units["current_facility_id"].isin(hospitals)
    ].copy()
    last = (
        transfers[transfers["unit_id"].isin(pool["unit_id"])]
        .sort_values("dispatched_at")
        .groupby("unit_id")
        .tail(1)
        .set_index("unit_id")
    )
    pool["arrival"] = pool["unit_id"].map(last["received_at"].fillna(last["dispatched_at"]))
    pool["arrival"] = pool["arrival"].dt.normalize()
    pool["last_day"] = pool["status_date"].fillna(END)
    return pool[pool["arrival"].notna()]


def shelf_at(pool: pd.DataFrame, origin: date) -> pd.DataFrame:
    """Units of `pool` on a hospital shelf on `origin` and not yet expired, as a stock table."""
    day = pd.Timestamp(origin)
    on_shelf = pool[
        (pool["arrival"] <= day) & (pool["last_day"] >= day) & (pool["expiry_date"] >= day)
    ]
    return on_shelf.rename(columns={"current_facility_id": "facility_id"})[
        ["unit_id", "facility_id", "blood_group", "component", "expiry_date", "status"]
    ]


def rank_rule(scored: pd.DataFrame, demand: DemandModel) -> pd.Series:
    """The rank-rule score of every queued unit of `scored` (NaN for the others)."""
    out = pd.Series(np.nan, index=scored.index)
    queued = scored.dropna(subset=["rank"])
    for (site, group), queue in queued.groupby(["facility_id", "blood_group"]):
        queue = queue.sort_values("rank")
        left = queue["days_left"].to_numpy(dtype=int)
        rates = demand.request_rates(site, group, int(left.max()))
        out.loc[queue.index] = rank_lower_bound(left, rates, demand.size_pmf)
    return out


def score_origins(
    origins: Sequence[date],
    pool: pd.DataFrame,
    requests: pd.DataFrame,
    facilities: pd.DataFrame,
    config: RankingConfig,
) -> pd.DataFrame:
    """Score every unit on a shelf at each origin and attach its final outcome.

    Only units whose outcome is final are returned (transfused, or expired on or before the
    last day of the data): column y is 1 if the unit was transfused. Demand is learned from the
    requests strictly before each origin.
    """
    parts = []
    for origin in origins:
        demand = DemandModel.from_history(
            requests, facilities, origin, weekday_profile=config.weekday_profile
        )
        stock = shelf_at(pool, origin)
        scored = survival_scores(stock, demand, origin, config, with_interval=False)
        scored["p_rank"] = rank_rule(scored, demand)
        scored["origin"] = pd.Timestamp(origin)
        parts.append(scored)
    result = pd.concat(parts, ignore_index=True)
    final = result["status"].isin(FINAL_STATUSES) & (result["expiry_date"] <= END)
    result = result[final & result["p"].notna()].copy()
    result["y"] = (result["status"] == "transfused").astype(float)
    return result


def _metrics(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Brier, log-loss, calibration gap, AUC and mean score of one method on one subset."""
    return {
        "brier": brier(p, y),
        "log_loss": log_loss(p, y),
        "calibration_gap": calibration_gap(p, y),
        "auc": auc(p, y),
        "mean_p": float(np.mean(p)),
    }


def _subsets(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The frame split by product_type, plus the total (always last)."""
    parts = {str(k): g for k, g in frame.groupby("product_type")}
    return {**parts, "total": frame}


def method_table(calibration: pd.DataFrame, test: pd.DataFrame) -> dict[str, dict]:
    """Metrics of every method on the test window, per product_type and in total."""
    cal_parts, test_parts = _subsets(calibration), _subsets(test)
    table: dict[str, dict] = {}
    for name, part in test_parts.items():
        cal = cal_parts.get(name)
        entry: dict = {"n": len(part), "observed_rate": float(part["y"].mean()), "methods": {}}
        if cal is not None and len(cal):
            base = float(cal["y"].mean())
            entry["calibration_n"] = len(cal)
            entry["calibration_observed_rate"] = base
            scores = {
                "constant": np.full(len(part), base),
                "days_left": (part["days_left"] / (part["days_left"] + DAYS_LEFT_SCALE)).to_numpy(),
                "rank_rule": part["p_rank"].to_numpy(),
                "exact": part["p"].to_numpy(),
            }
            thresholds, values = isotonic_fit(cal["p"].to_numpy(), cal["y"].to_numpy())
            scores["exact_isotonic"] = isotonic_apply(thresholds, values, part["p"].to_numpy())
        else:
            entry["calibration_n"] = 0
            scores = {"rank_rule": part["p_rank"].to_numpy(), "exact": part["p"].to_numpy()}
        y = part["y"].to_numpy()
        entry["methods"] = {m: _metrics(p, y) for m, p in scores.items()}
        table[name] = entry
    return table


def reliability(test: pd.DataFrame, min_bin: int) -> dict[str, list[dict]]:
    """Reliability table of the exact score on the test window, per product_type and total."""
    return {
        name: reliability_table(part["p"].to_numpy(), part["y"].to_numpy(), min_bin).to_dict(
            "records"
        )
        for name, part in _subsets(test).items()
    }


def group_families(test: pd.DataFrame) -> list[dict]:
    """Mean announced score, observed rate and AUC by blood-group family (test window)."""
    families = np.where(
        test["blood_group"].isin(["O+", "A+", "B+"]),
        "common (O+, A+, B+)",
        np.where(test["blood_group"] == "AB+", "AB+", "Rh-negative"),
    )
    rows = []
    for name, part in test.groupby(families):
        rows.append(
            {
                "family": str(name),
                "n": len(part),
                "mean_p": float(part["p"].mean()),
                "observed_rate": float(part["y"].mean()),
                "auc": auc(part["p"].to_numpy(), part["y"].to_numpy()),
            }
        )
    return rows


def closing_stock(
    tables: dict[str, pd.DataFrame], requests: pd.DataFrame, config: RankingConfig
) -> dict:
    """Expected units that expire unused from the closing stock of the hospitals, per product.

    Every unit on a hospital shelf at the snapshot counts (eligible or not), scored on the first
    day after the snapshot. Expected expired = sum of (1 - p).
    """
    snapshot = build_snapshot(tables, load_config())
    origin = snapshot.as_of.date() + timedelta(days=1)
    hospitals = set(
        tables["facilities"].loc[
            tables["facilities"]["facility_type"].isin(HOSPITAL_FACILITY_TYPES), "facility_id"
        ]
    )
    stock = snapshot.units[
        snapshot.units["facility_id"].isin(hospitals) & snapshot.units["blood_group"].notna()
    ]
    stock = stock[stock["component"].isin(config.pool_components)]
    demand = DemandModel.from_history(
        requests, tables["facilities"], origin, weekday_profile=config.weekday_profile
    )
    scored = survival_scores(stock, demand, origin, config, with_interval=False)
    result: dict = {"origin": origin.isoformat()}
    for name, part in _subsets(scored).items():
        result[name] = {
            "units": len(part),
            "expected_expired": float((1.0 - part["p"]).sum()),
            "units_below_half": int((part["p"] < 0.5).sum()),
        }
    return result


def evaluate(config: RankingConfig) -> dict:
    """Run the whole evaluation for one configuration and return the JSON-ready payload."""
    tables, _ = load_all(names=TABLES)
    requests = tables["requests"].assign(
        units_requested=tables["requests"]["units_requested"].astype(int)
    )
    facilities = tables["facilities"]
    hospitals = set(
        facilities.loc[facilities["facility_type"].isin(HOSPITAL_FACILITY_TYPES), "facility_id"]
    )
    pool = arrived_units(tables["units"], tables["transfers"], hospitals, config.pool_components)
    cal_origins, test_origins = calibration_origins(), evaluation_origins()
    calibration = score_origins(cal_origins, pool, requests, facilities, config)
    test = score_origins(test_origins, pool, requests, facilities, config)
    return {
        "config": asdict(config),
        "split": {
            "calibration_origins": [cal_origins[0].isoformat(), cal_origins[-1].isoformat()],
            "calibration_origin_count": len(cal_origins),
            "test_origins": [test_origins[0].isoformat(), test_origins[-1].isoformat()],
            "test_origin_count": len(test_origins),
            "outcomes_final_through": END.date().isoformat(),
        },
        "methods": method_table(calibration, test),
        "reliability_exact_test": reliability(test, config.calibration_min_bin),
        "blood_group_families_test": group_families(test),
        "closing_stock": closing_stock(tables, requests, config),
    }


def _fmt(value: float, digits: int = 3) -> str:
    """Format a number for the markdown tables."""
    return "n/a" if value is None or np.isnan(value) else f"{value:.{digits}f}"


def render_markdown(payload: dict) -> str:
    """Human-readable report of the payload. Same numbers as the JSON, nothing added."""
    config, split = payload["config"], payload["split"]
    lines = [
        "# Survival-score evaluation (synthetic data)",
        "",
        f"Pool of products in one queue: {', '.join(config['pool_components'])}. "
        f"Weekday profile: {'on' if config['weekday_profile'] else 'off'}.",
        f"Calibration origins: {split['calibration_origins'][0]} to "
        f"{split['calibration_origins'][1]} ({split['calibration_origin_count']} weekly). "
        f"Test origins: {split['test_origins'][0]} to {split['test_origins'][1]} "
        f"({split['test_origin_count']} weekly). Units are scored only when their outcome is "
        f"final (expiry on or before {split['outcomes_final_through']}).",
        "",
        "The score is a model estimate under stated assumptions, not a clinical probability. It "
        "is evidence as a ranking and the table below shows where it is off; do not read an "
        "announced 85% as 'true 85% of the time'.",
    ]
    for name, entry in payload["methods"].items():
        lines += ["", f"## Test window, {name}", ""]
        lines.append(
            f"{entry['n']:,} unit-origin pairs in test, observed use rate "
            f"{_fmt(entry['observed_rate'])}; {entry['calibration_n']:,} in calibration"
            + (
                f" (rate {_fmt(entry['calibration_observed_rate'])})."
                if entry["calibration_n"]
                else "."
            )
        )
        lines += ["", "| Method | Brier | Log-loss | Calibration gap | AUC | Mean score |"]
        lines.append("|---|---:|---:|---:|---:|---:|")
        for key, m in entry["methods"].items():
            lines.append(
                f"| {METHODS[key]} | {_fmt(m['brier'], 4)} | {_fmt(m['log_loss'])} | "
                f"{_fmt(m['calibration_gap'])} | {_fmt(m['auc'])} | {_fmt(m['mean_p'])} |"
            )
    for name, rows in payload["reliability_exact_test"].items():
        lines += ["", f"## Reliability of the exact score, test window, {name}", ""]
        lines += [
            "| Announced range | n | Announced mean | Observed | Gap |",
            "|---|---:|---:|---:|---:|",
        ]
        for r in rows:
            lines.append(
                f"| {_fmt(r['p_low'])} to {_fmt(r['p_high'])} | {r['n']:,} | "
                f"{_fmt(r['announced'])} | {_fmt(r['observed'])} | {_fmt(r['gap'])} |"
            )
    lines += ["", "## By blood-group family, test window", ""]
    lines += ["| Family | n | Mean score | Observed | AUC |", "|---|---:|---:|---:|---:|"]
    for r in payload["blood_group_families_test"]:
        lines.append(
            f"| {r['family']} | {r['n']:,} | {_fmt(r['mean_p'])} | {_fmt(r['observed_rate'])} | "
            f"{_fmt(r['auc'])} |"
        )
    closing = payload["closing_stock"]
    lines += ["", f"## Closing stock of the hospitals (scored from {closing['origin']})", ""]
    lines += [
        "| Product | Units | Expected to expire unused | Units with score below 0.5 |",
        "|---|---:|---:|---:|",
    ]
    for name, c in closing.items():
        if name != "origin":
            lines.append(
                f"| {name} | {c['units']:,} | {_fmt(c['expected_expired'], 1)} | "
                f"{c['units_below_half']:,} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point: evaluate, print the report and write the JSON and markdown."""
    parser = argparse.ArgumentParser(description="Evaluate the survival score on the history.")
    parser.add_argument(
        "--pool-components",
        default=",".join(RankingConfig().pool_components),
        help="products sharing one queue, comma separated (default RBC,WB)",
    )
    parser.add_argument(
        "--flat-weekdays", action="store_true", help="ignore the weekday demand profile"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROCESSED_DIR,
        help="where ranking_evaluation.json and .md are written",
    )
    args = parser.parse_args(argv)
    config = RankingConfig(
        pool_components=tuple(c.strip() for c in args.pool_components.split(",") if c.strip()),
        weekday_profile=not args.flat_weekdays,
    )
    payload = evaluate(config)
    report = render_markdown(payload)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ranking_evaluation.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "ranking_evaluation.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
