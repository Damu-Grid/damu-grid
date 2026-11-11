"""Compound Poisson demand: requests arrive as a Poisson process, each asks for 1 to K units."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def panjer_pmf(rate: float, size_pmf: Sequence[float], cap: int) -> np.ndarray:
    """P(total demand = n units) for n = 0..cap; the last cell holds the tail mass.

    `rate` is the expected number of requests in the interval, `size_pmf[k - 1]` the probability
    that a request asks for k units. Recursion (Panjer): g_0 = exp(-rate) and
    g_n = (rate / n) * sum_{k=1..min(n, K)} k * s_k * g_{n-k}.
    The cell `cap` then receives everything beyond it, so the result always sums to 1.
    """
    if rate < 0 or not math.isfinite(rate):
        raise ValueError("rate must be a finite, non-negative number")
    if cap < 0:
        raise ValueError("cap must be non-negative")
    sizes = np.asarray(size_pmf, dtype=float)
    if sizes.ndim != 1 or sizes.size == 0 or (sizes < 0).any():
        raise ValueError("size_pmf must be a non-empty vector of non-negative probabilities")
    if not math.isclose(float(sizes.sum()), 1.0, abs_tol=1e-9):
        raise ValueError("size_pmf must sum to 1")

    weighted = np.arange(1, sizes.size + 1) * sizes  # k * s_k
    pmf = np.zeros(cap + 1)
    pmf[0] = math.exp(-rate)
    for n in range(1, cap + 1):
        m = min(n, sizes.size)
        # g_{n-1}, g_{n-2}, ..., g_{n-m} pair with k = 1..m
        pmf[n] = rate / n * float(np.dot(weighted[:m], pmf[n - 1 :: -1][:m]))
    pmf[cap] += max(0.0, 1.0 - float(pmf.sum()))
    return pmf
