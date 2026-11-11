"""Monte Carlo simulator of an oldest-first queue: the reference oracle for the exact recursion.

Demand is drawn for every day and path before any unit is served, so two scenarios run with the
same seed see the same requests (common random numbers): their difference is a low-noise
estimate of the effect of a transfer.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

NEVER = np.iinfo(np.int32).max  # release day of a unit that never reaches the shelf


def _draw_demand(
    rates: np.ndarray, sizes: np.ndarray, days: int, paths: int, rng: np.random.Generator
) -> np.ndarray:
    """Units requested per (day, path): Poisson requests, each of 1..K units."""
    rows = np.arange(paths)
    demand = np.zeros((days, paths), dtype=int)
    for day in range(days):
        requests = rng.poisson(rates[day], size=paths)
        asked = rng.choice(sizes.size, size=int(requests.sum()), p=sizes) + 1
        demand[day] = np.bincount(np.repeat(rows, requests), weights=asked, minlength=paths)
    return demand


def _serve(
    left: np.ndarray,
    release: np.ndarray,
    leave: np.ndarray,
    demand: np.ndarray,
    adherence: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Which unit is used on which path; units are columns sorted by expiry (oldest first).

    A unit is on the shelf on day d when release <= d < min(expiry, leave); `release` and
    `leave` broadcast to (paths, n), so they may differ per path.
    """
    paths, n = demand.shape[1], left.size
    rows = np.arange(paths)
    used = np.zeros((paths, n), dtype=bool)
    last = np.minimum(left, leave)
    for day in range(demand.shape[0]):
        shelf = np.broadcast_to((release <= day) & (day < last), (paths, n))
        if not shelf.any():
            continue
        wanted = demand[day].copy()
        if adherence >= 1.0:  # oldest first: the `wanted` oldest units on the shelf are taken
            available = ~used & shelf
            used |= available & (np.cumsum(available, axis=1) <= wanted[:, None])
            continue
        for _ in range(int(wanted.max())):
            active = wanted > 0
            available = ~used & shelf
            has_unit = available.any(axis=1)
            take_oldest = rng.random(paths) < adherence
            oldest = available.argmax(axis=1)
            at_random = (available * rng.random((paths, n))).argmax(axis=1)
            pick = np.where(take_oldest, oldest, at_random)
            served = active & has_unit
            used[rows[served], pick[served]] = True
            wanted -= active
    return used


def _check(left: np.ndarray, rates: np.ndarray, paths: int) -> None:
    """Refuse a horizon the rates do not cover, or no path at all."""
    if paths < 1:
        raise ValueError("paths must be positive")
    if left.size and left.max() > rates.size:
        raise ValueError("daily_request_rates must cover every day up to the largest days_left")


def simulate_use_probabilities(
    days_left: Sequence[int],
    release_days: Sequence[int],
    daily_request_rates: Sequence[float],
    size_pmf: Sequence[float],
    *,
    paths: int,
    seed: int,
    adherence: float = 1.0,
    leave_days: Sequence[int] | None = None,
) -> np.ndarray:
    """Estimated P(unit used before expiry) per unit, with units released on `release_days`.

    Unit j can be issued on the days d with release_days[j] <= d < days_left[j] (day 0 is the
    origin) and, when `leave_days` is given, d < leave_days[j] (the unit leaves the shelf, for
    example on a truck). Each day a Poisson number of requests arrives at daily_request_rates[d];
    a request asks for k units with probability size_pmf[k - 1] and takes them one at a time.
    `adherence` is the share of units taken oldest-first (the rest pick a random unit on the
    shelf). Vectorised over paths and seeded, so a run is reproducible.
    """
    left = np.asarray(days_left, dtype=int)
    release = np.asarray(release_days, dtype=int)
    leave = left if leave_days is None else np.asarray(leave_days, dtype=int)
    rates = np.asarray(daily_request_rates, dtype=float)
    if left.ndim != 1 or release.shape != left.shape or leave.shape != left.shape:
        raise ValueError("days_left, release_days and leave_days must be vectors of one length")
    if not 0.0 <= adherence <= 1.0:
        raise ValueError("adherence must lie in [0, 1]")
    _check(left, rates, paths)
    if left.size == 0:
        return np.empty(0)
    order = np.argsort(left, kind="stable")
    rng = np.random.default_rng(seed)
    demand = _draw_demand(rates, np.asarray(size_pmf, float), int(left.max()), paths, rng)
    used = _serve(left[order], release[order], leave[order], demand, adherence, rng)
    result = np.empty(left.size)
    result[order] = used.mean(axis=0)
    return result


def simulate_transfer_gain(
    sender_days_left: Sequence[int],
    destination_days_left: Sequence[int],
    moved: Sequence[int],
    sender_rates: Sequence[float],
    destination_rates: Sequence[float],
    size_pmf: Sequence[float],
    *,
    dispatch_day: int,
    arrival_lag: int,
    paths: int,
    seed: int,
) -> tuple[float, float]:
    """Expected extra units used when the sender units at positions `moved` are shipped.

    The batch stays on the sender's shelf until `dispatch_day`; each of its units that is still
    unused then leaves and reaches the destination shelf `arrival_lag` days later. Both sites
    issue oldest-first. Returns (gain, standard error), estimated with the same demand paths with
    and without the transfer.
    """
    s_left = np.asarray(sender_days_left, dtype=int)
    d_left = np.asarray(destination_days_left, dtype=int)
    s_rates = np.asarray(sender_rates, dtype=float)
    d_rates = np.asarray(destination_rates, dtype=float)
    sizes = np.asarray(size_pmf, dtype=float)
    moved_idx = np.asarray(moved, dtype=int)
    _check(s_left, s_rates, paths)
    _check(np.concatenate([d_left, s_left[moved_idx]]), d_rates, paths)
    if dispatch_day < 0 or arrival_lag < 0:
        raise ValueError("dispatch_day and arrival_lag must be non-negative")

    s_order = np.argsort(s_left, kind="stable")
    s_sorted = s_left[s_order]
    is_moved = np.isin(s_order, moved_idx)
    s_days = int(s_sorted.max()) if s_sorted.size else 0
    s_demand = _draw_demand(s_rates, sizes, s_days, paths, np.random.default_rng([seed, 1]))
    picks = np.random.default_rng([seed, 3])
    zero = np.zeros(s_sorted.size, dtype=int)
    stay = _serve(s_sorted, zero, s_sorted, s_demand, 1.0, picks)
    leave = np.where(is_moved, dispatch_day, s_sorted)
    go = _serve(s_sorted, zero, leave, s_demand, 1.0, picks)

    batch = s_sorted[is_moved]
    all_left = np.concatenate([d_left, batch])
    d_order = np.argsort(all_left, kind="stable")
    d_sorted = all_left[d_order]
    d_days = int(d_sorted.max()) if d_sorted.size else 0
    d_demand = _draw_demand(d_rates, sizes, d_days, paths, np.random.default_rng([seed, 2]))
    arrives = ~go[:, is_moved]  # unused at the sender by the dispatch day
    release = np.zeros((paths, all_left.size), dtype=int)
    release[:, d_left.size :] = np.where(arrives, dispatch_day + arrival_lag, NEVER)
    release_sorted = release[:, d_order]
    base_release = np.where(np.arange(all_left.size) < d_left.size, 0, NEVER)[d_order]
    base = _serve(d_sorted, base_release, d_sorted, d_demand, 1.0, picks)
    moved_dest = _serve(d_sorted, release_sorted, d_sorted, d_demand, 1.0, picks)

    difference = (go.sum(axis=1) + moved_dest.sum(axis=1)) - (stay.sum(axis=1) + base.sum(axis=1))
    return float(difference.mean()), float(difference.std(ddof=1) / np.sqrt(paths))
