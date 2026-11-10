"""The pooled candidate demand estimator (issue DG-11).

Specification (frozen in docs/EVALUATION.md before any result was computed):

1. Hospital seven-day total = 7 x the hospital's expanding historical daily mean of requested
   RBC units, over all days from the data start up to, but not including, the origin.
2. Split that total across the eight known groups with the network-wide known-group request
   proportions, computed from the same earlier history.

Statistical only. No LLM. Only requests strictly before the origin are read.

The one-line reason it can beat a short moving average on this data: demand is close to flat, so
a long history has less sampling noise than a 28-day window, and pooling the group mix across
32 hospitals stabilises rare groups (O-, AB-) that a single hospital sees only a few times a year.
That is a hypothesis the evaluation tests; it is not assumed.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from forecasting.config import CONFIG, ForecastConfig


def candidate_forecast(
    daily: pd.DataFrame,
    origin: date,
    hospitals: tuple[str, ...],
    groups: tuple[str, ...],
    config: ForecastConfig = CONFIG,
) -> pd.Series:
    """Seven-day forecast per (facility_id, blood_group) made at ``origin`` (00:00 EAT)."""
    elapsed_days = (origin - config.data_start).days
    if elapsed_days <= 0:
        raise ValueError(f"No history before {origin}; data starts {config.data_start}.")

    origin_ts = pd.Timestamp(origin)
    history = daily[daily["day"] < origin_ts]

    hospital_units = (
        history.groupby("facility_id")["units_requested"].sum().reindex(hospitals, fill_value=0.0)
    )
    hospital_daily_mean = hospital_units / elapsed_days

    group_units = (
        history.groupby("blood_group")["units_requested"].sum().reindex(groups, fill_value=0.0)
    )
    total_group_units = group_units.sum()
    if total_group_units <= 0:
        raise ValueError("No known-group requests before the origin; cannot form group shares.")
    group_share = group_units / total_group_units

    index = pd.MultiIndex.from_product([hospitals, groups], names=["facility_id", "blood_group"])
    values = [
        config.horizon_days * hospital_daily_mean[h] * group_share[g]
        for h, g in index.to_flat_index()
    ]
    return pd.Series(values, index=index, dtype=float)
