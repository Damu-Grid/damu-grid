"""DG-19 step 2: exact oldest-first queue, its rank lower bound and the Monte Carlo oracle."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from ranking.queue import fefo_use_probabilities, rank_lower_bound
from ranking.simulate import simulate_use_probabilities

SIZES = [0.55, 0.25, 0.1, 0.05, 0.03, 0.02]
WEEKDAY = np.array([1.04, 1.03, 1.02, 1.02, 1.04, 1.07, 0.78])


def _cases(count: int, seed: int = 7):
    """Random small queues with constant or weekday-shaped request rates."""
    rng = np.random.default_rng(seed)
    for i in range(count):
        n = int(rng.integers(1, 9))
        left = np.sort(rng.integers(1, 22, size=n))
        base = float(rng.uniform(0.05, 1.6))
        rates = base * (np.resize(WEEKDAY, 30) if i % 2 else np.ones(30))
        yield left, rates


def test_single_unit_matches_closed_form():
    # n = 1, one-unit requests: P(used) = 1 - exp(-Lambda(L))
    rates = np.full(20, 0.3)
    p = fefo_use_probabilities([9], rates, [1.0])
    assert p[0] == pytest.approx(1 - math.exp(-0.3 * 9), abs=1e-12)


def test_ties_match_poisson_closed_form():
    # two units with the same expiry: p1 = P(N >= 1), p2 = P(N >= 2) for N ~ Poisson(Lambda)
    lam = 1.7
    p = fefo_use_probabilities([5, 5], np.full(10, lam / 5), [1.0])
    assert p[0] == pytest.approx(1 - math.exp(-lam), abs=1e-12)
    assert p[1] == pytest.approx(1 - math.exp(-lam) * (1 + lam), abs=1e-12)


def test_oldest_unit_with_one_day_left_uses_that_days_demand_only():
    p = fefo_use_probabilities([1, 4], [0.5, 0.5, 0.5, 0.5], [1.0])
    assert p[0] == pytest.approx(1 - math.exp(-0.5), abs=1e-12)
    assert 0.0 < p[1] < 1.0


def test_probabilities_are_ordered_in_zero_demand_and_heavy_demand():
    assert (fefo_use_probabilities([2, 5, 9], np.zeros(9), SIZES) == 0.0).all()
    heavy = fefo_use_probabilities([2, 5, 9], np.full(9, 50.0), SIZES)
    assert (heavy > 0.999999).all()


def test_empty_queue_and_unsorted_input():
    assert fefo_use_probabilities([], [0.3], SIZES).shape == (0,)
    with pytest.raises(ValueError):
        fefo_use_probabilities([5, 2], np.full(5, 0.3), SIZES)
    with pytest.raises(ValueError):
        fefo_use_probabilities([5], np.full(3, 0.3), SIZES)  # rates do not cover the life


def test_rank_bound_never_exceeds_exact():
    for left, rates in _cases(200):
        exact = fefo_use_probabilities(left, rates, SIZES)
        bound = rank_lower_bound(left, rates, SIZES)
        assert (bound <= exact + 1e-12).all(), (left, rates[:3])


def test_rank_bound_is_exact_for_the_oldest_unit():
    for left, rates in _cases(30):
        assert rank_lower_bound(left, rates, SIZES)[0] == pytest.approx(
            fefo_use_probabilities(left, rates, SIZES)[0], abs=1e-12
        )


def test_total_expected_use_never_exceeds_unit_count_or_expected_demand():
    for left, rates in _cases(50):
        p = fefo_use_probabilities(left, rates, SIZES)
        mean_size = float((np.arange(1, 7) * SIZES).sum())
        demand_units = float(rates[: left[-1]].sum()) * mean_size
        assert p.sum() <= len(left) + 1e-9
        assert p.sum() <= demand_units + 1e-9


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_exact_and_monte_carlo_agree_within_one_percent(seed):
    for left, rates in _cases(20, seed=100 + seed):
        exact = fefo_use_probabilities(left, rates, SIZES)
        sim = simulate_use_probabilities(
            left, np.zeros(len(left), dtype=int), rates, SIZES, paths=50_000, seed=seed
        )
        assert np.abs(exact - sim).max() < 0.01, (left, exact, sim)


def test_monte_carlo_is_reproducible_and_seed_dependent():
    left, rates = [3, 6, 6, 10], np.full(10, 0.4)
    args = (left, [0] * 4, rates, SIZES)
    a = simulate_use_probabilities(*args, paths=500, seed=5)
    b = simulate_use_probabilities(*args, paths=500, seed=5)
    c = simulate_use_probabilities(*args, paths=500, seed=6)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_monte_carlo_release_lag_and_unsorted_input():
    rates = np.full(10, 0.6)
    # unit released on the day it expires is never usable; an arrival lag lowers the score
    p = simulate_use_probabilities([4, 4], [4, 1], rates, [1.0], paths=20_000, seed=3)
    assert p[0] == 0.0 and p[1] > 0.0
    now = simulate_use_probabilities([6], [0], rates, [1.0], paths=40_000, seed=3)
    late = simulate_use_probabilities([6], [3], rates, [1.0], paths=40_000, seed=3)
    assert late[0] < now[0]
    assert late[0] == pytest.approx(1 - math.exp(-0.6 * 3), abs=0.01)
    # results come back in the caller's order even when the queue is not sorted
    mixed = simulate_use_probabilities([9, 2], [0, 0], rates, [1.0], paths=20_000, seed=3)
    assert mixed[1] == pytest.approx(1 - math.exp(-1.2), abs=0.015)


def test_monte_carlo_adherence_lets_older_units_expire():
    left, rates = [2, 8], np.full(8, 0.7)
    strict = simulate_use_probabilities(left, [0, 0], rates, [1.0], paths=30_000, seed=4)
    loose = simulate_use_probabilities(
        left, [0, 0], rates, [1.0], paths=30_000, seed=4, adherence=0.0
    )
    assert loose[0] < strict[0]  # random picks leave the oldest unit unused more often


def test_monte_carlo_request_by_request_path_agrees_with_the_oldest_first_path():
    left, rates = [3, 6, 6, 11], np.full(11, 0.5)
    fast = simulate_use_probabilities(left, [0] * 4, rates, SIZES, paths=40_000, seed=8)
    slow = simulate_use_probabilities(
        left, [0] * 4, rates, SIZES, paths=40_000, seed=9, adherence=1 - 1e-12
    )
    assert np.abs(fast - slow).max() < 0.01


def test_monte_carlo_random_picks_do_not_change_a_single_unit_or_tied_units():
    rates = np.full(6, 0.5)
    one = simulate_use_probabilities([6], [0], rates, [1.0], paths=40_000, seed=2, adherence=0.0)
    assert one[0] == pytest.approx(1 - math.exp(-3.0), abs=0.01)
    tied = simulate_use_probabilities(
        [6, 6], [0, 0], rates, [1.0], paths=40_000, seed=2, adherence=0.0
    )
    assert tied[0] == pytest.approx(tied[1], abs=0.01)  # exchangeable units
    assert tied[0] + tied[1] == pytest.approx(2 - 5 * math.exp(-3.0), abs=0.02)


def test_monte_carlo_rejects_bad_arguments():
    with pytest.raises(ValueError):
        simulate_use_probabilities([3], [0], np.full(3, 0.2), [1.0], paths=0, seed=1)
    with pytest.raises(ValueError):
        simulate_use_probabilities([3], [0], np.full(3, 0.2), [1.0], paths=10, seed=1, adherence=2)
    with pytest.raises(ValueError):
        simulate_use_probabilities([5], [0], np.full(3, 0.2), [1.0], paths=10, seed=1)


def test_a_queue_of_sixty_units_scores_in_under_fifty_milliseconds():
    left = np.sort(np.random.default_rng(0).integers(1, 30, size=60))
    rates = np.full(30, 1.1)
    fefo_use_probabilities(left, rates, SIZES)  # warm up
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        fefo_use_probabilities(left, rates, SIZES)
        timings.append(time.perf_counter() - start)
    assert sorted(timings)[2] < 0.050
