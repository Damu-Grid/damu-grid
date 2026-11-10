"""DG-04 (and DG-08): which units may be suggested for a transfer, and why the others may not.

Two levels, both conservative when evidence is missing (docs/DATA.md, Tier 1 rules):

1. `unit_eligibility`: properties of the unit itself at the as-of time
   (component in the queue, known exact group, in stock, not expired, not exposed, no blocking
   cold-chain or receipt evidence, not already reserved or moving).
2. `check_move` / `candidate_moves`: one unit to one destination
   (route recorded, enough remaining life after the expected arrival, sender keeps its reserve,
   destination is a hospital with a documented gap).

Every limit comes from `PipelineConfig` (ADR-006). Nothing here decides blood-group compatibility,
releases a unit for transfusion, or clears a quarantine: an eligible unit is only a unit the
coordinator may be *shown* as a candidate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline.config import PipelineConfig

# Unit-level exclusion reasons, in the order they are checked.
UNIT_REASONS = (
    "component_not_in_queue",
    "unknown_blood_group",
    "not_in_stock",
    "expired_at_as_of",
    "temp_excursion_exposed",
    "exposure_not_recorded",
    "receipt_unconfirmed",
    "cold_chain_evidence",
    "reserved_or_in_transit",
)

# Move-level exclusion reasons.
MOVE_REASONS = (
    "same_site",
    "recipient_not_hospital",
    "no_route",
    "route_time_missing",
    "route_too_long_for_component",
    "insufficient_life_on_arrival",
    "sender_below_reserve",
    "no_documented_recipient_gap",
)


@dataclass
class EligibilityResult:
    units: pd.DataFrame  # snapshot units + `eligible`, `reasons` (tuple), `reason` (first)

    @property
    def eligible(self) -> pd.DataFrame:
        return self.units[self.units["eligible"]]

    @property
    def excluded(self) -> pd.DataFrame:
        return self.units[~self.units["eligible"]]

    def exclusion_counts(self) -> dict[str, int]:
        """Units excluded for each reason (a unit can count under several reasons)."""
        counts = dict.fromkeys(UNIT_REASONS, 0)
        for reasons in self.units["reasons"]:
            for r in reasons:
                counts[r] += 1
        return counts


def unit_eligibility(
    snapshot_units: pd.DataFrame,
    config: PipelineConfig,
    as_of: pd.Timestamp,
    reserved_unit_ids: Iterable[str] = (),
    unit_flags: pd.DataFrame | None = None,
) -> EligibilityResult:
    """Check every unit of the snapshot. `unit_flags` has columns unit_id, flag_type, blocks_suggestion
    (from pipeline.coldchain); `reserved_unit_ids` comes from active moves in the action store."""
    df = snapshot_units.copy()
    enabled = set(config.enabled_components())
    reserved = set(reserved_unit_ids)
    blocking_types = set(config.blocking_flags)
    blocked_by_flag: set[str] = set()
    if unit_flags is not None and len(unit_flags):
        f = unit_flags[unit_flags["blocks_suggestion"].astype(bool)]
        blocked_by_flag = set(f.loc[f["flag_type"].isin(blocking_types), "unit_id"])

    exposed = df["temp_excursion_exposed"]
    checks = {
        "component_not_in_queue": ~df["component"].isin(enabled),
        "unknown_blood_group": ~df["blood_group"].isin(config.known_blood_groups),
        "not_in_stock": df["status"].ne("in_stock"),
        "expired_at_as_of": df["expiry_date"] <= as_of.normalize(),
        "temp_excursion_exposed": exposed.fillna(False).astype(bool),
        "exposure_not_recorded": exposed.isna(),
        "receipt_unconfirmed": df["receipt_status"].eq("unconfirmed")
        & ("receipt_unconfirmed" in blocking_types),
        "cold_chain_evidence": df["unit_id"].isin(blocked_by_flag),
        "reserved_or_in_transit": df["unit_id"].isin(reserved),
    }
    flags = np.column_stack([checks[r].fillna(True).astype(bool).to_numpy() for r in UNIT_REASONS])
    names = np.array(UNIT_REASONS, dtype=object)
    df["eligible"] = ~flags.any(axis=1)
    df["reasons"] = [tuple(names[row]) for row in flags]
    df["reason"] = np.where(df["eligible"], None, names[flags.argmax(axis=1)])
    return EligibilityResult(df)


@dataclass(frozen=True)
class NetworkIndex:
    """Route and facility lookups built once, so checking thousands of moves stays fast."""
    routes: dict[tuple[str, str], tuple[float | None, str | None]]
    facility_types: dict[str, str]

    @classmethod
    def build(cls, routes: pd.DataFrame, facilities: pd.DataFrame) -> NetworkIndex:
        r = {(a, b): (None if pd.isna(h) else float(h), q)
             for a, b, h, q in zip(routes["from_facility_id"], routes["to_facility_id"],
                                   routes["typical_travel_hours"], routes["road_quality"], strict=True)}
        return cls(r, dict(zip(facilities["facility_id"], facilities["facility_type"], strict=True)))


def remaining_hours_on_arrival(expiry_date: pd.Timestamp, as_of: pd.Timestamp, travel_hours: float,
                               config: PipelineConfig) -> float:
    """Hours of shelf life left when the unit is expected to arrive. Conservatively, a unit is
    treated as expiring at the start (00:00) of its `expiry_date`."""
    arrival = as_of + pd.Timedelta(hours=travel_hours + config.arrival_allowance_hours)
    return (pd.Timestamp(expiry_date) - arrival) / pd.Timedelta(hours=1)


def check_move(
    unit: Mapping,
    to_facility_id: str,
    *,
    as_of: pd.Timestamp,
    config: PipelineConfig,
    routes: pd.DataFrame,
    facilities: pd.DataFrame,
    sender_available: int,
    recipient_gap: float | None,
    sender_reserve: int | None = None,
    units_moving: int = 1,
    index: NetworkIndex | None = None,
) -> dict:
    """Check one unit (already unit-eligible) for one destination. Returns the facts the suggestion
    card needs plus `reasons` (empty = the move may be shown to the coordinator).
    Pass a prebuilt `index` when checking many moves."""
    reasons: list[str] = []
    src = unit["facility_id"]
    reserve = config.default_sender_reserve_units if sender_reserve is None else sender_reserve
    index = index or NetworkIndex.build(routes, facilities)
    route = index.routes.get((src, to_facility_id))

    if src == to_facility_id:
        reasons.append("same_site")
    if index.facility_types.get(to_facility_id) not in config.recipient_facility_types:
        reasons.append("recipient_not_hospital")
    travel = None
    if route is None:
        reasons.append("no_route")
    else:
        travel = route[0]
        if travel is None:
            reasons.append("route_time_missing")
    remaining = None
    policy = config.policy(unit["component"])
    if travel is not None:
        if policy.max_travel_hours is not None and travel > policy.max_travel_hours:
            reasons.append("route_too_long_for_component")
        remaining = remaining_hours_on_arrival(unit["expiry_date"], as_of, float(travel), config)
        if remaining < policy.min_remaining_hours_on_arrival:
            reasons.append("insufficient_life_on_arrival")
    stock_after = sender_available - units_moving
    if stock_after < reserve:
        reasons.append("sender_below_reserve")
    if recipient_gap is None or pd.isna(recipient_gap) or recipient_gap <= 0:
        reasons.append("no_documented_recipient_gap")
    return {
        "unit_id": unit["unit_id"], "from_facility_id": src, "to_facility_id": to_facility_id,
        "component": unit["component"], "blood_group": unit["blood_group"],
        "expiry_date": unit["expiry_date"],
        "typical_travel_hours": None if travel is None else float(travel),
        "road_quality": None if route is None else route[1],
        "remaining_hours_on_arrival": remaining,
        "sender_reserve_units": reserve, "sender_stock_after": stock_after,
        "recipient_gap_units": recipient_gap,
        "reasons": tuple(reasons), "ok": not reasons,
    }


def candidate_moves(
    result: EligibilityResult,
    *,
    as_of: pd.Timestamp,
    config: PipelineConfig,
    routes: pd.DataFrame,
    facilities: pd.DataFrame,
    recipient_gaps: Mapping[tuple[str, str, str], float],
    sender_reserves: Mapping[tuple[str, str, str], int] | None = None,
) -> pd.DataFrame:
    """Every (eligible unit, destination with a documented gap for that component and group) pair,
    checked with `check_move`. Gaps and reserves are keyed by (facility_id, component, blood_group)
    and come from the demand estimator (forecasting/) or the rule-based fallback, not from here.
    For each destination, units leave the sender in expiry order and only units that pass every
    check count as leaving, so the sender always keeps its reserve."""
    sender_reserves = sender_reserves or {}
    index = NetworkIndex.build(routes, facilities)
    ok = result.eligible.sort_values(["facility_id", "component", "blood_group", "expiry_date"])
    rows = []
    for (src, comp, grp), group in ok.groupby(["facility_id", "component", "blood_group"]):
        n = len(group)
        dests = [f for (f, c, g) in recipient_gaps if c == comp and g == grp and f != src]
        for dest in dests:
            leaving = 0
            for unit in group.to_dict("records"):
                move = check_move(
                    unit, dest, as_of=as_of, config=config, routes=routes, facilities=facilities,
                    sender_available=n, units_moving=leaving + 1,
                    recipient_gap=recipient_gaps[(dest, comp, grp)],
                    sender_reserve=sender_reserves.get((src, comp, grp)), index=index,
                )
                leaving += move["ok"]
                rows.append(move)
    return pd.DataFrame(rows)


def sender_reserves_from_demand(daily_demand: Mapping[tuple[str, str, str], float], cover_days: float,
                                minimum: int) -> dict[tuple[str, str, str], int]:
    """Turn a forecast of daily requested units per (facility, component, group) into a reserve:
    enough units to cover `cover_days` of expected demand, never below `minimum`. Replaces the flat
    default once the demand estimator (forecasting/) is available."""
    return {k: max(minimum, int(np.ceil(rate * cover_days))) for k, rate in daily_demand.items()}


def shelf_life_check(units: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    """Compare the configured shelf life of each component with `expiry_date - collection_date`
    in the data, so a wrong setting is caught before it reaches the queue."""
    days = (units["expiry_date"] - units["collection_date"]).dt.days
    obs = days.groupby(units["component"]).agg(["min", "max", lambda d: d.mode().iloc[0], "size"])
    obs.columns = ["observed_min_days", "observed_max_days", "observed_mode_days", "units"]
    obs["configured_days"] = [config.policy(c).shelf_life_days for c in obs.index]
    obs["matches"] = obs["observed_mode_days"].eq(obs["configured_days"])
    obs["in_queue"] = [config.policy(c).enabled_in_queue for c in obs.index]
    return obs.reset_index()


def active_reserved_units(conn) -> set[str]:
    """Units already in an active move in the action store (cannot be suggested again)."""
    from pipeline.store import ACTIVE_MOVE_STATES

    q = f"SELECT unit_id FROM dg_moves WHERE state IN ({', '.join('?' * len(ACTIVE_MOVE_STATES))})"
    return {r[0] for r in conn.execute(q, ACTIVE_MOVE_STATES)}
