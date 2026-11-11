"""Best dispatch day: waiting cost against the cost of a trip."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from ranking.config import RankingConfig

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# Routine deliveries per week -> weekdays of the run (0 = Monday), team convention of the plan.
ROUTINE_WEEKDAYS = {3: frozenset({0, 2, 4}), 2: frozenset({1, 4}), 1: frozenset({2})}
BLOOD_CENTRE_TYPES = ("regional_blood_centre", "satellite_blood_centre")


@dataclass(frozen=True)
class DispatchDecision:
    """Chosen dispatch day of one batch and the numbers that justify it."""

    send_by: date | None  # None = no suggestion (net gain below min_gain_units)
    net_gain: float
    gain_by_day: tuple[float, ...]  # G(tau) for tau = 0..T
    waiting_cost_per_day: float  # G(0) - G(1)
    uses_routine_run: bool
    reason: str  # built only from the numbers above


def routine_weekdays(deliveries_per_week: float | None) -> frozenset[int]:
    """Weekdays of the routine run for a delivery frequency (3, 2 or 1 per week; else none)."""
    if deliveries_per_week is None or pd.isna(deliveries_per_week):
        return frozenset()
    return ROUTINE_WEEKDAYS.get(int(deliveries_per_week), frozenset())


def routine_run_weekdays(facilities: pd.DataFrame, from_id: str, to_id: str) -> frozenset[int]:
    """Weekdays on which a routine vehicle goes from `from_id` to `to_id`.

    Routine vehicles only go from a blood centre to the hospitals it supplies
    (facilities.supply_centre_id); a hospital-to-hospital move is always a special trip.
    """
    rows = facilities.set_index("facility_id")
    if from_id not in rows.index or to_id not in rows.index:
        return frozenset()
    if rows.at[from_id, "facility_type"] not in BLOOD_CENTRE_TYPES:
        return frozenset()
    if rows.at[to_id, "supply_centre_id"] != from_id:
        return frozenset()
    return routine_weekdays(rows.at[to_id, "routine_deliveries_per_week"])


def decide_dispatch(
    gain_by_day: tuple[float, ...],
    routine_run_days: frozenset[int],
    config: RankingConfig,
    *,
    origin: date,
) -> DispatchDecision:
    """net(tau) = G(tau) - trip_cost(tau), trip_cost = 0 on a routine-run day, trip_cost_units
    otherwise; tau* = argmax net. G(tau) for tau > 0 uses the conditional waiting value
    pi_loc + (1 - pi_loc) * p_dest (ranking.gain.gain_by_day).

    A later day must beat an earlier one by more than config.timing_tolerance_units (the
    measured accuracy of the G(tau) approximation), so tau* is the earliest day whose net gain
    is within that tolerance of the best. `routine_run_days` are weekdays (0 = Monday) of a
    routine vehicle on this route and `origin` is day tau = 0. Below min_gain_units there is no
    suggestion (send_by is None).
    """
    if not gain_by_day:
        raise ValueError("gain_by_day needs at least the value for dispatch today")
    days = [origin + timedelta(days=tau) for tau in range(len(gain_by_day))]
    routine = [day.weekday() in routine_run_days for day in days]
    net = [
        g - (0.0 if r else config.trip_cost_units)
        for g, r in zip(gain_by_day, routine, strict=True)
    ]
    # Only days that clear the minimum compete; among them, the earliest within the tolerance
    # of the best. With none, the best day is reported as below the minimum.
    viable = [t for t in range(len(net)) if net[t] >= config.min_gain_units] or list(
        range(len(net))
    )
    top = max(net[t] for t in viable)
    best = next(t for t in viable if net[t] >= top - config.timing_tolerance_units)
    waiting_cost = gain_by_day[0] - gain_by_day[1] if len(gain_by_day) > 1 else 0.0
    decision_day = days[best]
    if net[best] < config.min_gain_units:
        reason = (
            f"No dispatch day recommended: the best net expected gain is {net[best]:.2f} units "
            f"({decision_day.isoformat()}), below the {config.min_gain_units:.2f}-unit minimum for "
            "a transfer."
        )
        return DispatchDecision(
            None, net[best], tuple(gain_by_day), waiting_cost, routine[best], reason
        )
    when = f"{WEEKDAY_NAMES[decision_day.weekday()]} {decision_day.isoformat()}"
    if best == 0:
        trip = (
            "routine run"
            if routine[0]
            else f"special trip (cost {config.trip_cost_units:.2f} units)"
        )
        reason = (
            f"Send today, {when}, by {trip}: net expected gain {net[0]:.2f} units; waiting one "
            f"day would lose {waiting_cost:.2f} units."
        )
    elif routine[best]:
        loss = gain_by_day[0] - gain_by_day[best]
        reason = (
            f"Waiting until {when} for the routine run saves a special trip "
            f"(cost {config.trip_cost_units:.2f} units) for an expected loss of {loss:.2f} units; "
            f"net expected gain {net[best]:.2f} units."
        )
    else:
        reason = (
            f"Send on {when} by special trip (cost {config.trip_cost_units:.2f} units): the "
            f"expected gain then is {gain_by_day[best]:.2f} units against {gain_by_day[0]:.2f} "
            f"today; net expected gain {net[best]:.2f} units."
        )
    return DispatchDecision(
        decision_day, net[best], tuple(gain_by_day), waiting_cost, routine[best], reason
    )
