"""Exact use probabilities of the units of one perishable queue under oldest-first issuing."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def fefo_use_probabilities(
    days_left: Sequence[int],
    daily_request_rates: Sequence[float],
    size_pmf: Sequence[float],
    cap_extra: int = 6,
) -> np.ndarray:
    """P(unit j is transfused before it expires), units sorted by days_left ascending.

    days_left[j] is the number of days the unit can still be issued, today included
    (expiry_date - origin + 1). daily_request_rates[d] is the expected number of requests on
    day d from the origin. Lindley recursion: X_0 = 0, A_j = X_{j-1} + D_j,
    unit j used iff A_j >= 1, X_j = max(A_j - 1, 0), D_j = demand in (L_{j-1}, L_j].
    So p_j = 1 - P(X_{j-1} = 0) * P(D_j = 0). Carry the full distribution of X, truncated at
    n + cap_extra with the tail in the last cell. Step 2.
    """
    raise NotImplementedError("DG-19 step 2")


def rank_lower_bound(
    days_left: Sequence[int],
    daily_request_rates: Sequence[float],
    size_pmf: Sequence[float],
) -> np.ndarray:
    """Pessimistic bound P(D(L_j) >= j) used to cross-check the exact recursion. Step 2."""
    raise NotImplementedError("DG-19 step 2")
