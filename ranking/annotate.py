"""Fill the survival-score fields of a suggestion. The backend provider calls this.

The backend provider (backend/app/ranking.py) already builds the suggestions from the pipeline
eligibility and the 28-day request average. This module only adds what it leaves empty:
expected_use_*, survival_score_*, send_by and an uncertainty label. Plain data in, plain data
out, so nothing here imports the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel


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

    def as_suggestion_update(self) -> dict:
        """Fields to copy onto a backend Suggestion with model_copy(update=...).

        `uncertainty` is returned as a dict (method, nominal_level, label) so that this module
        does not import the backend; the caller builds its Uncertainty model from it."""
        raise NotImplementedError("DG-19 step 6")


def annotate_batch(
    units: pd.DataFrame,
    destination: str,
    stock: pd.DataFrame,
    demand: DemandModel,
    origin: date,
    travel_hours: float,
    routine_run_days: frozenset[int],
    config: RankingConfig,
) -> BatchAnnotation:
    """Score a batch at the sender and at the destination and choose the dispatch day.

    `units` are the batch rows (unit_id, facility_id, blood_group, component, expiry_date);
    `stock` is every unit on the shelf of both sites, so the queues are complete. `send_by` comes
    from ranking.timing.decide_dispatch and is never later than the latest feasible day
    (expiry minus travel minus the buffer the backend already applies). Step 6.
    """
    raise NotImplementedError("DG-19 step 6")
