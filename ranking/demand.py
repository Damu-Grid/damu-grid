"""Demand rates per (site, blood group), request-size law and weekday profile."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DemandModel:
    """Everything the score needs about demand, learned only from data before `origin`."""

    origin: date
    daily_unit_rate: Mapping[tuple[str, str], float]  # (facility_id, blood_group) -> units/day
    request_counts: Mapping[tuple[str, str], int]  # history size, for the rate interval
    size_pmf: tuple[float, ...]  # P(request asks for k units), k = 1..6
    weekday_weights: tuple[float, ...]  # Monday..Sunday, mean 1

    def request_rates(self, facility_id: str, blood_group: str, days: int) -> np.ndarray:
        """Expected requests per day for `days` days from the origin (unit rate / E[size])."""
        raise NotImplementedError("DG-19 step 3")

    @classmethod
    def from_history(
        cls, requests: pd.DataFrame, facilities: pd.DataFrame, origin: date
    ) -> DemandModel:
        """Use forecasting.candidate.candidate_forecast / 7 for the unit rate (do not recompute
        it elsewhere); size law and weekday weights from requests strictly before `origin`."""
        raise NotImplementedError("DG-19 step 3")
