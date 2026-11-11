"""Fill the survival-score fields of a suggestion. The backend provider calls this.

The backend provider (backend/app/ranking.py) already builds the suggestions from the pipeline
eligibility and the 28-day request average. This module only adds what it leaves empty:
expected_use_*, survival_score_*, send_by and an uncertainty label. Plain data in, plain data
out, so nothing here imports the backend.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.gain import aged_positions, arrival_lag_days, gain_by_day, max_wait_days
from ranking.queue import fefo_use_probabilities
from ranking.score import survival_scores
from ranking.timing import decide_dispatch, routine_run_weekdays
from simulation.compare import SEND_BY_BUFFER_DAYS, transit_days

UNCERTAINTY = {
    "method": "fefo_compound_poisson",
    "nominal_level": 0.8,  # the interval spans the 10th to 90th percentiles of the demand rate
    "label": "model estimate under stated assumptions, not a clinical probability",
}
STOCK_COLUMNS = ["unit_id", "facility_id", "blood_group", "component", "expiry_date"]


@dataclass(frozen=True)
class BatchAnnotation:
    """Survival-score fields for one batch of units moving from one site to another."""

    expected_use_if_stays: float  # sum of the unit scores at the sender
    expected_use_if_moved: float  # sum of the unit scores at the destination
    survival_score_if_stays: float  # mean unit score at the sender
    survival_score_if_moved: float  # mean unit score at the destination
    interval_if_stays: tuple[float, float]  # mean score at the low and high demand rates
    interval_if_moved: tuple[float, float]
    send_by: date | None  # recommended dispatch day; None = no suggestion
    waiting_cost_per_day: float  # expected units lost by waiting one more day
    warnings: tuple[str, ...]
    reason: str  # built only from the numbers above
    net_gain: float = 0.0  # G(tau*) minus the trip cost, expected units
    gain_by_day: tuple[float, ...] = ()  # G(tau) for tau = 0..T
    latest_feasible: date | None = None  # expiry - travel days - buffer (simulation.compare)

    def as_suggestion_update(self, existing_warnings: Sequence[str] = ()) -> dict:
        """Fields to copy onto a backend Suggestion with model_copy(update=...).

        `uncertainty` is returned as a dict (method, nominal_level, label) so that this module
        does not import the backend; the caller builds its Uncertainty model from it. Our
        warnings are added after `existing_warnings` (the suggestion's own), never replacing them.
        """
        return {
            "expected_use_if_stays": self.expected_use_if_stays,
            "expected_use_if_moved": self.expected_use_if_moved,
            "survival_score_if_stays": self.survival_score_if_stays,
            "survival_score_if_moved": self.survival_score_if_moved,
            "send_by": self.send_by,
            "uncertainty": dict(UNCERTAINTY),
            "reason_deterministic": self.reason,
            "warnings": list(dict.fromkeys([*existing_warnings, *self.warnings])),
        }


@dataclass(frozen=True)
class AnnotationInputs:
    """Complete shelves and the demand model, loaded once per snapshot."""

    origin: date  # first day after the snapshot (the as-of time is the end of a day)
    stock: pd.DataFrame  # every unit on every shelf, eligible or not
    demand: DemandModel
    facilities: pd.DataFrame

    def routine_run_days(self, from_id: str, to_id: str) -> frozenset[int]:
        """Weekdays of a routine vehicle from `from_id` to `to_id` (none for a lateral move)."""
        return routine_run_weekdays(self.facilities, from_id, to_id)


def load_annotation_inputs(
    database_path: Path, as_of: datetime, config: RankingConfig
) -> AnnotationInputs:
    """Read dg_snapshot_units, requests and facilities from damu_grid.sqlite (read-only).

    The snapshot rows are those of `as_of` (ISO 8601 with offset, as the pipeline stores it).
    Demand is learned from requests strictly before the first day after the snapshot.
    """
    uri = f"{Path(database_path).resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        stock = pd.read_sql_query(
            "SELECT unit_id, facility_id, component, blood_group, expiry_date "
            "FROM dg_snapshot_units WHERE as_of = ?",
            connection,
            params=(as_of.isoformat(timespec="seconds"),),
        )
        requests = pd.read_sql_query(
            "SELECT facility_id, requested_at, patient_blood_group, component_requested, "
            "units_requested FROM requests",
            connection,
        )
        facilities = pd.read_sql_query(
            "SELECT facility_id, facility_type, supply_centre_id, routine_deliveries_per_week "
            "FROM facilities",
            connection,
        )
    if stock.empty:
        raise ValueError(f"No snapshot units for as-of {as_of.isoformat()}")
    stock["expiry_date"] = pd.to_datetime(stock["expiry_date"])
    requests["requested_at"] = pd.to_datetime(requests["requested_at"])
    requests["units_requested"] = pd.to_numeric(requests["units_requested"]).astype(int)
    origin = as_of.date() + timedelta(days=1)
    demand = DemandModel.from_history(
        requests, facilities, origin, weekday_profile=config.weekday_profile
    )
    return AnnotationInputs(origin, stock, demand, facilities)


def _days_left(expiry: pd.Series, origin: date) -> np.ndarray:
    """Usable days from the origin, today included (expiry_date - origin + 1)."""
    return ((pd.to_datetime(expiry).dt.normalize() - pd.Timestamp(origin)).dt.days + 1).to_numpy()


def _scores_at_destination(
    batch_left: np.ndarray,
    destination_left: np.ndarray,
    rates: np.ndarray,
    factors: tuple[float, float],
    lag: int,
    size_pmf: Sequence[float],
    config: RankingConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scores (p, p_lo, p_hi) of the batch units in the destination queue on arrival.

    The destination queue is aged to the arrival day exactly as in ranking.gain.gain_by_day; the
    batch units join it with their remaining life and sit after existing units of equal expiry.
    """
    kept = destination_left[
        aged_positions(destination_left, rates, lag, size_pmf, config.cap_extra)
    ]
    queue = [(int(d) - lag, 0, -1) for d in kept]
    queue += [(int(d) - lag, 1, i) for i, d in enumerate(batch_left)]
    queue.sort()
    live = [(d, flag, i) for d, flag, i in queue if d >= 1]
    out = np.zeros((3, batch_left.size))
    if not live:
        return out[0], out[1], out[2]
    left = np.array([d for d, _, _ in live])
    future = rates[lag:]
    for row, factor in enumerate((1.0, *factors)):
        p = fefo_use_probabilities(left, future * factor, size_pmf, config.cap_extra)
        for k, (_, flag, i) in enumerate(live):
            if flag:
                out[row, i] = p[k]
    return out[0], out[1], out[2]


def annotate_batch(
    units: pd.DataFrame,
    destination: str,
    stock: pd.DataFrame,
    demand: DemandModel,
    origin: date,
    travel_hours: float,
    routine_run_days: frozenset[int],
    config: RankingConfig,
    *,
    arrival_allowance_hours: float = 6.0,
    min_remaining_days: int = 7,
) -> BatchAnnotation:
    """Score a batch at the sender and at the destination and choose the dispatch day.

    `units` are the batch rows (unit_id, facility_id, blood_group, component, expiry_date);
    `stock` is every unit on the shelf of both sites, so the queues are complete. `send_by` comes
    from ranking.timing.decide_dispatch and is never later than the latest feasible day
    (expiry minus travel minus the buffer the backend already applies). The scores "if moved"
    are for a dispatch today; the dispatch day itself comes from the gain curve G(tau).
    """
    if units.empty:
        raise ValueError("a batch needs at least one unit")
    sender = str(units["facility_id"].iloc[0])
    group = str(units["blood_group"].iloc[0])
    if units["facility_id"].nunique() != 1 or units["blood_group"].nunique() != 1:
        raise ValueError("a batch comes from one site and has one blood group")
    if sender == destination:
        raise ValueError("the destination must differ from the sender")

    shelves = pd.concat([stock[STOCK_COLUMNS], units[STOCK_COLUMNS]]).drop_duplicates("unit_id")
    shelves = shelves[
        shelves["facility_id"].isin([sender, destination]) & (shelves["blood_group"] == group)
    ]
    scored = survival_scores(shelves, demand, origin, config).set_index("unit_id")
    batch = scored.loc[list(units["unit_id"])]
    if batch["p"].isna().any():
        raise ValueError("every unit of the batch must be a scorable product of the pool")
    n = len(batch)
    stays, stays_lo, stays_hi = (float(batch[c].sum()) for c in ("p", "p_lo", "p_hi"))

    queued = scored[scored["rank"].notna()]
    sender_left = queued.loc[queued["facility_id"] == sender, "days_left"].to_numpy(dtype=int)
    dest_left = np.sort(
        queued.loc[queued["facility_id"] == destination, "days_left"].to_numpy(dtype=int)
    )
    batch_left = batch["days_left"].to_numpy(dtype=int)
    horizon = int(max(sender_left.max(initial=1), dest_left.max(initial=1)))
    s_rates = demand.request_rates(sender, group, horizon)
    d_rates = demand.request_rates(destination, group, horizon)
    lag = arrival_lag_days(travel_hours, arrival_allowance_hours)
    factors = demand.rate_interval_factors(destination, group, config.lambda_quantiles)
    moved_p, moved_lo, moved_hi = _scores_at_destination(
        batch_left, dest_left, d_rates, factors, lag, demand.size_pmf, config
    )

    gains = gain_by_day(
        sender_left,
        dest_left,
        batch_left,
        s_rates,
        d_rates,
        demand.size_pmf,
        arrival_lag=lag,
        max_tau=max_wait_days(batch_left, lag, min_remaining_days, config),
        cap_extra=config.cap_extra,
    )
    decision = decide_dispatch(gains, routine_run_days, config, origin=origin)
    first_expiry = pd.Timestamp(units["expiry_date"].min()).date()
    latest = first_expiry - timedelta(days=transit_days(travel_hours) + SEND_BY_BUFFER_DAYS)
    send_by, reason_tail = decision.send_by, decision.reason
    if send_by is not None and send_by > latest:
        send_by = latest
        reason_tail += (
            f" Dispatch is brought forward to {latest.isoformat()}, the latest feasible day."
        )

    if send_by is None:
        warnings: tuple[str, ...] = ("net_gain_below_minimum",)
    elif decision.uses_routine_run and send_by == decision.send_by:
        warnings = ("routine_run_available",)
    else:
        warnings = ("timing_uses_special_trip",)
    moved = float(moved_p.sum())
    reason = (
        f"If the {n} unit(s) stay at {sender}: {stays:.2f} expected to be used (mean score "
        f"{stays / n:.2f}, {stays_lo / n:.2f} to {stays_hi / n:.2f} across the demand-rate "
        f"range). If sent today to {destination}: {moved:.2f} (mean score {moved / n:.2f}, "
        f"{moved_lo.sum() / n:.2f} to {moved_hi.sum() / n:.2f}). {reason_tail} Model estimate on "
        "synthetic data, not a clinical probability."
    )
    return BatchAnnotation(
        expected_use_if_stays=stays,
        expected_use_if_moved=moved,
        survival_score_if_stays=stays / n,
        survival_score_if_moved=moved / n,
        interval_if_stays=(stays_lo / n, stays_hi / n),
        interval_if_moved=(float(moved_lo.sum()) / n, float(moved_hi.sum()) / n),
        send_by=send_by,
        waiting_cost_per_day=decision.waiting_cost_per_day,
        warnings=warnings,
        reason=reason,
        net_gain=decision.net_gain,
        gain_by_day=decision.gain_by_day,
        latest_feasible=latest,
    )
