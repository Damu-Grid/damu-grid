"""Exact use probabilities of the units of one perishable queue under oldest-first issuing."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import numpy as np

from ranking.compound import cached_pmf, checked_sizes


def _cumulative_rates(
    days_left: Sequence[int], daily_request_rates: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Validate a sorted queue and return (days_left, cumulative expected requests by day).

    cumulative[d] is the expected number of requests over the first d days, d = 0..len(rates).
    """
    left = np.asarray(days_left, dtype=int)
    rates = np.asarray(daily_request_rates, dtype=float)
    if left.ndim != 1 or (left < 0).any() or (np.diff(left) < 0).any():
        raise ValueError("days_left must be non-negative and sorted ascending")
    if (rates < 0).any() or not np.isfinite(rates).all():
        raise ValueError("daily_request_rates must be finite and non-negative")
    if left.size and left[-1] > rates.size:
        raise ValueError("daily_request_rates must cover every day up to the largest days_left")
    return left, np.concatenate(([0.0], np.cumsum(rates)))


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
    So p_j = 1 - P(X_{j-1} = 0) * P(D_j = 0). The full distribution of X is carried, truncated
    at n + cap_extra with the tail in the last cell. Exact because a request always takes the
    unexpired unit closest to its expiry, so a unit that expires unused never consumed demand.
    """
    left, cumulative = _cumulative_rates(days_left, daily_request_rates)
    sizes = checked_sizes(size_pmf)
    if left.size == 0:
        return np.empty(0)
    horizon = int(left[-1])  # only the rates up to the last expiry matter
    key = (tuple(left.tolist()), tuple(cumulative[: horizon + 1].tolist()), sizes, int(cap_extra))
    return _fefo_cached(*key).copy()


@lru_cache(maxsize=65536)
def _fefo_cached(
    left_key: tuple[int, ...],
    cumulative_key: tuple[float, ...],
    sizes: tuple[float, ...],
    cap_extra: int,
) -> np.ndarray:
    """The recursion of fefo_use_probabilities for validated, hashable inputs (memoised).

    Annotating a whole suggestion list scores the same queues many times (one sender or one
    destination appears on many cards); the result only depends on these inputs.
    """
    left, cumulative = np.array(left_key), np.array(cumulative_key)
    n = left.size
    out = np.empty(n)
    cap = n + cap_extra
    x = np.zeros(cap + 1)  # law of the demand left over for the younger units
    x[0] = 1.0
    demand_laws: dict[float, np.ndarray] = {}
    previous = 0
    for j in range(n):
        interval_rate = round(float(cumulative[left[j]] - cumulative[previous]), 12)
        previous = int(left[j])
        law = demand_laws.get(interval_rate)
        if law is None:
            law = demand_laws[interval_rate] = cached_pmf(max(0.0, interval_rate), sizes, cap)
        arrived = np.convolve(x, law)[: cap + 1]
        arrived[cap] += max(0.0, 1.0 - float(arrived.sum()))
        out[j] = 1.0 - arrived[0]
        x = np.zeros(cap + 1)
        x[0] = arrived[0] + arrived[1]
        x[1:cap] = arrived[2 : cap + 1]
    out.setflags(write=False)
    return out


def rank_lower_bound(
    days_left: Sequence[int],
    daily_request_rates: Sequence[float],
    size_pmf: Sequence[float],
) -> np.ndarray:
    """Pessimistic bound P(D(L_j) >= j) used to cross-check the exact recursion.

    Unit j (1-based, oldest first) is counted as used only if the demand over its whole life
    reaches j, as if every older unit that expires unused had still consumed demand.
    """
    left, cumulative = _cumulative_rates(days_left, daily_request_rates)
    sizes = checked_sizes(size_pmf)
    n = left.size
    out = np.empty(n)
    laws: dict[int, np.ndarray] = {}
    for j in range(n):
        life = int(left[j])
        law = laws.get(life)
        if law is None:
            rate = max(0.0, round(float(cumulative[life]), 12))
            law = laws[life] = cached_pmf(rate, sizes, n + 6)
        out[j] = 1.0 - float(law[: j + 1].sum())
    return out
