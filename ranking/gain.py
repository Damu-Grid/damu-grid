"""Expected extra units used when a batch moves, and batch construction."""

from __future__ import annotations

import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel


def marginal_gain(
    sender_days_left: list[int],
    destination_days_left: list[int],
    moved_days_left: list[int],
    sender_rates: list[float],
    destination_rates: list[float],
    size_pmf: tuple[float, ...],
) -> float:
    """EU_dest(with batch) - EU_dest + EU_sender(without batch) - EU_sender, with EU the sum of
    the unit use probabilities of a queue. Exact when the batch arrives on day 0. Step 5."""
    raise NotImplementedError("DG-19 step 5")


def plan_batches(
    eligible_moves: pd.DataFrame,
    stock: pd.DataFrame,
    demand: DemandModel,
    config: RankingConfig,
) -> pd.DataFrame:
    """Greedy with re-scoring: accept the best (unit, destination), update both queues, recompute
    the remaining gains of that site and group, stop at min_gain_units, the sender reserve or the
    cooler capacity; group by (origin, destination, day). Step 5."""
    raise NotImplementedError("DG-19 step 5")
