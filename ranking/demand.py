"""Demand rates per (site, blood group), request-size law and weekday profile."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import NormalDist

import numpy as np
import pandas as pd

from forecasting.candidate import candidate_forecast
from forecasting.config import CONFIG, KNOWN_GROUPS
from forecasting.demand import build_demand_slice

MAX_REQUEST_SIZE = 6  # the data asks for 1 to 6 units per request; larger sizes are counted as 6


@dataclass(frozen=True)
class DemandModel:
    """Everything the score needs about demand, learned only from data before `origin`."""

    origin: date
    daily_unit_rate: Mapping[tuple[str, str], float]  # (facility_id, blood_group) -> units/day
    request_counts: Mapping[tuple[str, str], int]  # history size, for the rate interval
    size_pmf: tuple[float, ...]  # P(request asks for k units), k = 1..6
    weekday_weights: tuple[float, ...]  # Monday..Sunday, mean 1

    @property
    def mean_request_size(self) -> float:
        """E[K], the average number of units asked for by one request."""
        return float(np.dot(np.arange(1, len(self.size_pmf) + 1), self.size_pmf))

    def has_site(self, facility_id: str) -> bool:
        """True when the model has a demand rate for this site (a hospital)."""
        return any(site == facility_id for site, _ in self.daily_unit_rate)

    def request_rates(self, facility_id: str, blood_group: str, days: int) -> np.ndarray:
        """Expected requests per day for `days` days from the origin (unit rate / E[size]).

        Day d carries the weekday weight of origin + d. A site or group with no rate gets zeros.
        """
        base = self.daily_unit_rate.get((facility_id, blood_group), 0.0) / self.mean_request_size
        first = self.origin.weekday()
        weights = np.array([self.weekday_weights[(first + d) % 7] for d in range(days)])
        return base * weights

    def rate_interval_factors(
        self, facility_id: str, blood_group: str, quantiles: tuple[float, float]
    ) -> tuple[float, float]:
        """Factors applied to the demand rate for the low and high ends of the score interval.

        The rate is taken as Gamma(N + 0.5) distributed, N being the number of past requests of
        the pair; the factors are its quantiles divided by its mean (Wilson-Hilferty
        approximation). Uncertainty on the rate only, not model error.
        """
        shape = self.request_counts.get((facility_id, blood_group), 0) + 0.5
        spread = 1.0 / (9.0 * shape)
        normal = NormalDist()
        low, high = (
            max(0.0, shape * (1.0 - spread + normal.inv_cdf(q) * spread**0.5) ** 3) / shape
            for q in quantiles
        )
        return low, high

    @classmethod
    def from_history(
        cls,
        requests: pd.DataFrame,
        facilities: pd.DataFrame,
        origin: date,
        *,
        weekday_profile: bool = True,
    ) -> DemandModel:
        """Learn demand from the requests strictly before `origin` and nothing else.

        The unit rate is forecasting.candidate.candidate_forecast / 7 (never recomputed
        elsewhere). The size law is the empirical law of units_requested over every red-cell
        request before the origin (all sites and groups: the largest sample); the weekday weights
        come from the hospital red-cell requests of known groups. `weekday_profile=False` gives
        flat weights.
        """
        history = requests[requests["requested_at"] < pd.Timestamp(origin)]
        slice_ = build_demand_slice(history, facilities)
        forecast = candidate_forecast(slice_.daily, origin, slice_.hospitals, slice_.groups)
        daily_unit_rate = {key: float(value) / 7.0 for key, value in forecast.items()}

        rows = _slice_rows(history, slice_.hospitals)
        counts = rows.groupby(["facility_id", "patient_blood_group"]).size()
        request_counts = {
            (site, group): int(counts.get((site, group), 0))
            for site in slice_.hospitals
            for group in KNOWN_GROUPS
        }
        red_cell = history[history["component_requested"] == CONFIG.component]
        sizes = red_cell["units_requested"].clip(1, MAX_REQUEST_SIZE).astype(int)
        size_counts = sizes.value_counts().reindex(range(1, MAX_REQUEST_SIZE + 1), fill_value=0)
        if size_counts.sum() == 0:
            raise ValueError(f"No red-cell requests before {origin}; cannot learn request sizes.")
        size_pmf = tuple((size_counts / size_counts.sum()).astype(float))

        weights = _weekday_weights(slice_.daily, origin) if weekday_profile else (1.0,) * 7
        return cls(origin, daily_unit_rate, request_counts, size_pmf, weights)


def _slice_rows(requests: pd.DataFrame, hospitals: tuple[str, ...]) -> pd.DataFrame:
    """Request rows of the demand slice: hospital, configured component, known blood group."""
    keep = (
        requests["facility_id"].isin(hospitals)
        & (requests["component_requested"] == CONFIG.component)
        & requests["patient_blood_group"].isin(KNOWN_GROUPS)
    )
    return requests[keep]


def _weekday_weights(daily: pd.DataFrame, origin: date) -> tuple[float, ...]:
    """Mean requested units per calendar day for each weekday, scaled to average 1.

    Calendar days with no request count as zero demand (the documented completeness
    assumption). Falls back to flat weights when a weekday has not been seen yet.
    """
    start = CONFIG.data_start
    days = [start + timedelta(days=i) for i in range((origin - start).days)]
    occurrences = np.bincount([d.weekday() for d in days], minlength=7).astype(float)
    units = daily.groupby(daily["day"].dt.day_of_week)["units_requested"].sum()
    totals = units.reindex(range(7), fill_value=0.0).to_numpy(dtype=float)
    if (occurrences == 0).any() or totals.sum() <= 0:
        return (1.0,) * 7
    per_day = totals / occurrences
    return tuple(float(w) for w in per_day / per_day.mean())
