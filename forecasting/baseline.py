"""The mandatory 28-day average baseline (issue DG-10).

For each hospital and known group:

    seven-day predicted requested units = 7 x (requested RBC units in the preceding 28 days / 28)

"Preceding" means strictly before the origin day: days [origin - 28, origin). Nothing at or after
the origin is read.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from forecasting.config import CONFIG, ForecastConfig
from forecasting.demand import period_totals


def baseline_forecast(
    daily: pd.DataFrame,
    origin: date,
    hospitals: tuple[str, ...],
    groups: tuple[str, ...],
    config: ForecastConfig = CONFIG,
) -> pd.Series:
    """Seven-day forecast per (facility_id, blood_group) made at ``origin`` (00:00 EAT)."""
    window_start = origin - timedelta(days=config.baseline_window_days)
    if window_start < config.data_start:
        raise ValueError(
            f"28-day window starting {window_start} begins before the data starts "
            f"({config.data_start}); choose a later origin."
        )
    trailing = period_totals(
        daily, window_start, origin, hospitals, groups, config.assume_complete_requests
    )
    return trailing * (config.horizon_days / config.baseline_window_days)
