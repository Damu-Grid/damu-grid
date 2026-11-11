"""Compound Poisson demand: requests arrive as a Poisson process, each asks for 1 to K units."""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import lru_cache

import numpy as np


def checked_sizes(size_pmf: Sequence[float]) -> tuple[float, ...]:
    """Validate a request-size law and return it as a tuple (hashable, for the cache)."""
    sizes = np.asarray(size_pmf, dtype=float)
    if sizes.ndim != 1 or sizes.size == 0 or (sizes < 0).any():
        raise ValueError("size_pmf must be a non-empty vector of non-negative probabilities")
    if not math.isclose(float(sizes.sum()), 1.0, abs_tol=1e-9):
        raise ValueError("size_pmf must sum to 1")
    return tuple(float(s) for s in sizes)


@lru_cache(maxsize=65536)
def cached_pmf(rate: float, sizes: tuple[float, ...], cap: int) -> np.ndarray:
    """Read-only Panjer law for an already validated size law; shared by every caller.

    Plain Python arithmetic: with at most six request sizes it is several times faster than
    numpy on such short vectors, and the queues call it thousands of times.
    """
    weighted = [k * s for k, s in enumerate(sizes, start=1)]  # k * s_k
    pmf = [0.0] * (cap + 1)
    pmf[0] = math.exp(-rate)
    for n in range(1, cap + 1):
        total = 0.0
        for k in range(min(n, len(weighted))):  # pairs k + 1 with g_{n-k-1}
            total += weighted[k] * pmf[n - 1 - k]
        pmf[n] = rate / n * total
    pmf[cap] += max(0.0, 1.0 - math.fsum(pmf))
    law = np.array(pmf)
    law.setflags(write=False)
    return law


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
    return cached_pmf(float(rate), checked_sizes(size_pmf), int(cap)).copy()
