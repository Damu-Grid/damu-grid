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

    Unit j can be issued on the days d with release_days[j] <= d < days_left[j] (day 0 is the
    origin). Each day a Poisson number of requests arrives at daily_request_rates[d]; a request
    asks for k units with probability size_pmf[k - 1] and takes them one at a time. `adherence`
    is the share of units taken oldest-first (the rest pick a random unit on the shelf).
    Vectorised over paths and seeded, so a run is reproducible.
    """
    left = np.asarray(days_left, dtype=int)
    release = np.asarray(release_days, dtype=int)
    rates = np.asarray(daily_request_rates, dtype=float)
    sizes = np.asarray(size_pmf, dtype=float)
    if left.shape != release.shape or left.ndim != 1:
        raise ValueError("days_left and release_days must be vectors of the same length")
    if paths < 1 or not 0.0 <= adherence <= 1.0:
        raise ValueError("paths must be positive and adherence must lie in [0, 1]")
    if left.size and left.max() > rates.size:
        raise ValueError("daily_request_rates must cover every day up to the largest days_left")
    n = left.size
    if n == 0:
        return np.empty(0)

    order = np.argsort(left, kind="stable")  # oldest first; the result is mapped back below
    left_s, release_s = left[order], release[order]
    rng = np.random.default_rng(seed)
    used = np.zeros((paths, n), dtype=bool)
    rows = np.arange(paths)
    for day in range(int(left_s.max())):
        shelf = (release_s <= day) & (day < left_s)
        if not shelf.any():
            continue
        requests = rng.poisson(rates[day], size=paths)
        asked = rng.choice(sizes.size, size=int(requests.sum()), p=sizes) + 1
        demand = np.bincount(np.repeat(rows, requests), weights=asked, minlength=paths).astype(int)
        if adherence >= 1.0:  # oldest first: the `demand` oldest units on the shelf are taken
            available = ~used & shelf
            used |= available & (np.cumsum(available, axis=1) <= demand[:, None])
            continue
        for _ in range(int(demand.max())):
            active = demand > 0
            available = ~used & shelf  # (paths, n)
            has_unit = available.any(axis=1)
            take_oldest = rng.random(paths) < adherence
            oldest = available.argmax(axis=1)
            at_random = (available * rng.random((paths, n))).argmax(axis=1)
            pick = np.where(take_oldest, oldest, at_random)
            served = active & has_unit
            used[rows[served], pick[served]] = True
            demand -= active
    result = np.empty(n)
    result[order] = used.mean(axis=0)
    return result
