"""Monte Carlo simulator of an oldest-first queue: the reference oracle for the exact recursion."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def simulate_use_probabilities(
    days_left: Sequence[int],
    release_days: Sequence[int],
    daily_request_rates: Sequence[float],
    size_pmf: Sequence[float],
    *,
    paths: int,
    seed: int,
    adherence: float = 1.0,
) -> np.ndarray:
    """Estimated P(unit used before expiry) per unit, with units released on `release_days`.

    `adherence` is the share of requests served oldest-first (the rest pick a random unit).
    Vectorised over paths, seeded, supports arrival lags and weekday profiles. Step 2.
    """
    raise NotImplementedError("DG-19 step 2")
