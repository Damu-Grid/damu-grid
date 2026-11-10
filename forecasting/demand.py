"""Hospital demand from requests.units_requested (issue DG-09).

There is no demand table. Demand is the requested quantity, not the issued quantity, because
shortages constrain issues. The slice is hospital x known blood group x calendar day, for the
configured component (Tier 1: RBC).

Missing request rows are zero demand only under the explicit completeness assumption in
``ForecastConfig.assume_complete_requests``; the exclusions are counted and reported, never
silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from forecasting.config import (
    CONFIG,
    HOSPITAL_FACILITY_TYPES,
    KNOWN_GROUPS,
    RAW_DIR,
    ForecastConfig,
)


@dataclass(frozen=True)
class DemandSlice:
    """Daily requested units for the configured slice, plus an account of what was excluded."""

    daily: pd.DataFrame  # columns: facility_id, blood_group, day (Timestamp), units_requested
    hospitals: tuple[str, ...]
    groups: tuple[str, ...]
    exclusions: dict[str, int] = field(default_factory=dict)


def load_requests(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read the official requests file. facility_id is the key; facility_name_raw is ignored."""
    columns = [
        "request_id",
        "facility_id",
        "requested_at",
        "patient_blood_group",
        "component_requested",
        "units_requested",
    ]
    return pd.read_csv(raw_dir / "requests.csv", usecols=columns, parse_dates=["requested_at"])


def load_facilities(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    return pd.read_csv(raw_dir / "facilities.csv", usecols=["facility_id", "facility_type"])


def hospital_ids(
    facilities: pd.DataFrame, hospital_types: tuple[str, ...] = HOSPITAL_FACILITY_TYPES
) -> tuple[str, ...]:
    """Demand sites: facilities whose type is one of the configured hospital classes."""
    mask = facilities["facility_type"].isin(hospital_types)
    return tuple(sorted(facilities.loc[mask, "facility_id"]))


def build_demand_slice(
    requests: pd.DataFrame,
    facilities: pd.DataFrame,
    config: ForecastConfig = CONFIG,
) -> DemandSlice:
    """Filter to hospital x component x known group and aggregate to daily requested units."""
    hospitals = hospital_ids(facilities)
    exclusions: dict[str, int] = {"request_rows_total": len(requests)}

    is_hospital = requests["facility_id"].isin(hospitals)
    exclusions["not_hospital"] = int((~is_hospital).sum())
    step = requests[is_hospital]

    is_component = step["component_requested"] == config.component
    exclusions["other_component"] = int((~is_component).sum())
    step = step[is_component]

    group = step["patient_blood_group"]
    known = group.isin(KNOWN_GROUPS)
    exclusions["unknown_or_missing_group"] = int((~known).sum())
    step = step[known]
    exclusions["request_rows_used"] = len(step)

    step = step.assign(day=step["requested_at"].dt.normalize())
    daily = (
        step.groupby(["facility_id", "patient_blood_group", "day"], as_index=False)[
            config.quantity_column
        ]
        .sum()
        .rename(
            columns={
                "patient_blood_group": "blood_group",
                config.quantity_column: "units_requested",
            }
        )
    )
    return DemandSlice(daily=daily, hospitals=hospitals, groups=KNOWN_GROUPS, exclusions=exclusions)


def load_demand_slice(raw_dir: Path = RAW_DIR, config: ForecastConfig = CONFIG) -> DemandSlice:
    return build_demand_slice(load_requests(raw_dir), load_facilities(raw_dir), config)


def _as_timestamp(value: date | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def period_totals(
    daily: pd.DataFrame,
    start: date | pd.Timestamp,
    end: date | pd.Timestamp,
    hospitals: tuple[str, ...],
    groups: tuple[str, ...],
    assume_complete: bool = True,
) -> pd.Series:
    """Requested units per (facility_id, blood_group) for days in [start, end).

    With ``assume_complete`` a hospital x group with no request rows is zero; otherwise it is NaN
    so callers cannot mistake absence of a record for zero demand.
    """
    start_ts, end_ts = _as_timestamp(start), _as_timestamp(end)
    window = daily[(daily["day"] >= start_ts) & (daily["day"] < end_ts)]
    totals = window.groupby(["facility_id", "blood_group"])["units_requested"].sum()
    index = pd.MultiIndex.from_product([hospitals, groups], names=["facility_id", "blood_group"])
    return totals.reindex(index, fill_value=0.0 if assume_complete else float("nan")).astype(float)


def window_days(start: date, end: date) -> int:
    return (end - start).days


__all__ = [
    "DemandSlice",
    "build_demand_slice",
    "hospital_ids",
    "load_demand_slice",
    "load_facilities",
    "load_requests",
    "period_totals",
    "timedelta",
    "window_days",
]
