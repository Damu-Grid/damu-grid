"""DG-19 step 5: gain of a transfer, waiting value, dispatch day and batch construction."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.gain import (
    arrival_lag_days,
    expected_use,
    gain_by_day,
    marginal_gain,
    max_wait_days,
    plan_batches,
)
from ranking.simulate import simulate_transfer_gain
from ranking.timing import decide_dispatch, routine_run_weekdays, routine_weekdays

SIZES = (0.49, 0.28, 0.115, 0.085, 0.0, 0.03)
MONDAY = date(2026, 11, 2)


def _random_transfer(rng):
    """A random sender queue, destination queue, moved units and rates."""
    s = np.sort(rng.integers(3, 30, int(rng.integers(2, 12))))
    d = np.sort(rng.integers(3, 30, int(rng.integers(0, 8))))
    moved = sorted(
        int(v) for v in rng.choice(s, int(rng.integers(1, min(3, s.size) + 1)), replace=False)
    )
    rs, rd = np.full(30, rng.uniform(0.05, 0.6)), np.full(30, rng.uniform(0.2, 1.5))
    return s, d, moved, rs, rd


def _positions(sender, moved):
    """Positions gain_by_day uses for the moved units: the last of tied units."""
    taken: list[int] = []
    for value in moved:
        taken.append([int(i) for i in np.flatnonzero(sender == value) if i not in taken][-1])
    return taken


def test_moving_the_only_unit_to_an_empty_site_has_a_closed_form():
    rs, rd = np.full(10, 0.1), np.full(10, 0.5)
    gain = marginal_gain([8], [], [8], rs, rd, (1.0,) + (0.0,) * 5)
    assert gain == pytest.approx((1 - math.exp(-0.5 * 8)) - (1 - math.exp(-0.1 * 8)))


def test_day_zero_gain_without_lag_equals_the_exact_marginal_gain():
    rng = np.random.default_rng(2)
    for _ in range(50):
        s, d, moved, rs, rd = _random_transfer(rng)
        g = gain_by_day(s, d, moved, rs, rd, SIZES, arrival_lag=0, max_tau=2)
        assert g[0] == pytest.approx(
            marginal_gain(list(s), list(d), moved, rs, rd, SIZES), abs=1e-9
        )


def test_a_moved_unit_must_be_in_the_sender_queue():
    with pytest.raises(ValueError):
        marginal_gain([5, 9], [], [7], np.full(9, 0.2), np.full(9, 0.2), SIZES)
    with pytest.raises(ValueError):
        gain_by_day([5, 9], [], [9, 9], np.full(9, 0.2), np.full(9, 0.2), SIZES,
                    arrival_lag=0, max_tau=0)  # fmt: skip


def test_destination_value_is_concave_in_the_number_of_units_added():
    rng = np.random.default_rng(4)
    for _ in range(40):
        d = list(np.sort(rng.integers(2, 25, int(rng.integers(0, 10)))))
        rates = np.full(25, rng.uniform(0.1, 2.0))
        life = int(rng.integers(5, 25))
        values = [expected_use(d + [life] * k, rates, SIZES) for k in range(8)]
        steps = np.diff(values)
        assert (steps >= -1e-12).all() and (np.diff(steps) <= 1e-9).all()


def test_gain_approximation_is_within_three_hundredths_of_monte_carlo_on_average():
    rng = np.random.default_rng(11)
    errors = []
    for case in range(12):
        s, d, moved, rs, rd = _random_transfer(rng)
        lag = int(rng.integers(0, 3))
        g = gain_by_day(s, d, moved, rs, rd, SIZES, arrival_lag=lag, max_tau=2)
        for tau in range(3):
            mc, se = simulate_transfer_gain(s, d, _positions(s, moved), rs, rd, SIZES,
                                            dispatch_day=tau, arrival_lag=lag, paths=20_000,
                                            seed=case)  # fmt: skip
            assert se < 0.02
            errors.append(abs(g[tau] - mc))
    assert np.mean(errors) < 0.03


def test_monte_carlo_gain_matches_the_exact_gain_without_lag():
    s, d, rs, rd = np.array([4, 9, 15, 15, 22]), np.array([20]), np.full(22, 0.3), np.full(22, 1.0)
    exact = marginal_gain(list(s), list(d), [15], rs, rd, SIZES)
    mc, se = simulate_transfer_gain(s, d, [3], rs, rd, SIZES, dispatch_day=0, arrival_lag=0,
                                    paths=40_000, seed=1)  # fmt: skip
    assert abs(mc - exact) < max(0.01, 4 * se)


def test_waiting_loses_value_every_day_when_the_destination_needs_the_unit():
    rng = np.random.default_rng(6)
    for _ in range(30):
        s = np.sort(rng.integers(8, 30, int(rng.integers(3, 10))))
        moved = [int(s[-1])]
        rs, rd = np.full(30, rng.uniform(0.02, 0.15)), np.full(30, rng.uniform(0.8, 2.0))
        g = gain_by_day(s, [], moved, rs, rd, SIZES, arrival_lag=1, max_tau=6)
        assert (np.diff(g) <= 1e-9).all(), g


def test_arrival_lag_and_longest_wait():
    assert arrival_lag_days(0.5, 6.0) == 1 and arrival_lag_days(0.0, 0.0) == 0
    assert arrival_lag_days(20.0, 6.0) == 2
    cfg = RankingConfig()
    assert max_wait_days([30, 20], 1, 7, cfg) == 7  # capped by max_wait_days
    assert max_wait_days([12], 1, 7, cfg) == 4
    assert max_wait_days([6], 1, 7, cfg) == 0  # very short life: today only


def test_free_trips_choose_the_first_day():
    cfg = RankingConfig(trip_cost_units=0.0)
    decision = decide_dispatch((0.5, 0.48, 0.45), frozenset(), cfg, origin=MONDAY)
    assert decision.send_by == MONDAY and decision.net_gain == pytest.approx(0.5)
    assert decision.waiting_cost_per_day == pytest.approx(0.02)


def test_a_cheaper_routine_day_makes_the_batch_wait():
    cfg = RankingConfig(trip_cost_units=0.2)
    gains = (0.5, 0.49, 0.48, 0.47)
    decision = decide_dispatch(gains, frozenset({2}), cfg, origin=MONDAY)  # Wednesday run
    assert decision.send_by == MONDAY + timedelta(days=2) and decision.uses_routine_run
    assert decision.net_gain == pytest.approx(0.48)
    assert "0.02" in decision.reason and "Wednesday" in decision.reason
    # a steep waiting loss makes the special trip today worth it
    steep = decide_dispatch((0.6, 0.45, 0.30), frozenset({2}), cfg, origin=MONDAY)
    assert steep.send_by == MONDAY and not steep.uses_routine_run


def test_a_later_day_must_beat_today_by_more_than_the_tolerance():
    cfg = RankingConfig(timing_tolerance_units=0.03)
    noise = decide_dispatch((0.60, 0.62, 0.61), frozenset(), cfg, origin=MONDAY)
    assert noise.send_by == MONDAY  # a 0.02 rise is within the accuracy of the approximation
    real = decide_dispatch((0.60, 0.70, 0.65), frozenset(), cfg, origin=MONDAY)
    assert real.send_by == MONDAY + timedelta(days=1) and not real.uses_routine_run
    assert "special trip" in real.reason and "routine" not in real.reason
    assert "0.70" in real.reason and "0.60" in real.reason


def test_a_later_day_that_clears_the_minimum_is_not_discarded_by_the_tolerance():
    # net = (0.08, 0.11): day 0 is within the tolerance of day 1 but below the 0.10 minimum
    decision = decide_dispatch((0.28, 0.31), frozenset(), RankingConfig(), origin=MONDAY)
    assert decision.send_by == MONDAY + timedelta(days=1)
    assert decision.net_gain == pytest.approx(0.11)


def test_a_very_short_life_unit_leaves_today():
    cfg = RankingConfig()
    tau_max = max_wait_days([8], 1, 7, cfg)
    decision = decide_dispatch((0.9,) * (tau_max + 1), frozenset({1, 4}), cfg, origin=MONDAY)
    assert tau_max == 0 and decision.send_by == MONDAY


def test_small_gains_give_no_suggestion_and_the_reason_quotes_the_numbers():
    cfg = RankingConfig()
    decision = decide_dispatch((0.25, 0.2), frozenset(), cfg, origin=MONDAY)
    assert decision.send_by is None and decision.net_gain == pytest.approx(0.05)
    assert "0.05" in decision.reason and "0.10" in decision.reason
    with pytest.raises(ValueError):
        decide_dispatch((), frozenset(), cfg, origin=MONDAY)


def test_routine_runs_only_go_from_a_centre_to_the_hospitals_it_supplies():
    facilities = pd.DataFrame(
        {
            "facility_id": ["RBTC-X", "HSP-1", "HSP-2"],
            "facility_type": ["regional_blood_centre", "county_hospital", "county_hospital"],
            "supply_centre_id": [None, "RBTC-X", "RBTC-Y"],
            "routine_deliveries_per_week": [None, 3.0, 2.0],
        }
    )
    assert routine_run_weekdays(facilities, "RBTC-X", "HSP-1") == frozenset({0, 2, 4})
    assert routine_run_weekdays(facilities, "RBTC-X", "HSP-2") == frozenset()  # not its centre
    assert routine_run_weekdays(facilities, "HSP-1", "HSP-2") == frozenset()  # lateral move
    assert routine_weekdays(2) == frozenset({1, 4}) and routine_weekdays(None) == frozenset()


def _random_network(rng):
    """Random shelves of four hospitals and a random subset of allowed moves."""
    sites = ["H1", "H2", "H3", "H4"]
    rows, moves = [], []
    for site in sites:
        for group in ("O+", "A+"):
            for k in range(int(rng.integers(0, 7))):
                unit = f"{site}-{group}-{k}"
                expiry = pd.Timestamp(MONDAY) + pd.Timedelta(days=int(rng.integers(1, 30)))
                component = "RBC" if rng.random() < 0.8 else "WB"
                rows.append((unit, site, group, component, expiry))
                if component == "RBC" and rng.random() < 0.6:
                    for dest in sites:
                        if dest != site and rng.random() < 0.5:
                            moves.append(
                                (unit, site, dest, group, component, float(rng.uniform(0, 30)))
                            )
    stock = pd.DataFrame(
        rows, columns=["unit_id", "facility_id", "blood_group", "component", "expiry_date"]
    )
    eligible = pd.DataFrame(
        moves, columns=["unit_id", "from_facility_id", "to_facility_id", "blood_group", "component",
                        "typical_travel_hours"],
    )  # fmt: skip
    rates = {(s, g): float(rng.uniform(0.0, 2.0)) for s in sites for g in ("O+", "A+")}
    used = {(s, p): int(rng.integers(0, 40)) for s in sites for p in ("RBC", "WB")}
    demand = DemandModel(MONDAY, rates, {k: 50 for k in rates}, SIZES, (1.0,) * 7, used)
    return stock, eligible, demand


def test_batches_only_contain_allowed_moves_and_respect_reserve_and_cooler():
    rng = np.random.default_rng(9)
    cfg = RankingConfig(cooler_capacity_units=3, min_gain_units=0.05)
    proposed = 0
    for _ in range(200):
        stock, eligible, demand = _random_network(rng)
        plan = plan_batches(eligible, stock, demand, cfg, sender_reserve_units=1)
        if plan.empty:
            continue
        proposed += len(plan)
        allowed = set(zip(eligible["unit_id"], eligible["to_facility_id"], strict=True))
        assert set(zip(plan["unit_id"], plan["to_facility_id"], strict=True)) <= allowed
        assert plan["unit_id"].is_unique
        assert (plan.groupby(["from_facility_id", "to_facility_id"]).size() <= 3).all()
        assert (plan["unit_gain"] >= 0.05).all()
        eligible_left = eligible.drop_duplicates("unit_id").groupby(
            ["from_facility_id", "component", "blood_group"]).size()  # fmt: skip
        sent = plan.groupby(["from_facility_id", "component", "blood_group"]).size()
        assert ((eligible_left.reindex(sent.index) - sent) >= 1).all()  # reserve of 1 kept
        assert plan.loc[plan["suggested"], "send_by"].notna().all()
    assert proposed > 50  # the property was exercised on real plans


def test_plan_moves_a_short_life_unit_to_a_site_with_demand():
    day = pd.Timestamp(MONDAY)
    stock = pd.DataFrame(
        {
            "unit_id": ["A1", "A2", "A3", "A4"],
            "facility_id": ["H1"] * 4,
            "blood_group": ["O+"] * 4,
            "component": ["RBC"] * 4,
            "expiry_date": [day + pd.Timedelta(days=d) for d in (12, 13, 14, 15)],
        }
    )
    eligible = pd.DataFrame(
        {
            "unit_id": ["A3", "A4"], "from_facility_id": ["H1", "H1"],
            "to_facility_id": ["H2", "H2"], "blood_group": ["O+", "O+"],
            "component": ["RBC", "RBC"], "typical_travel_hours": [2.0, 2.0],
        }
    )  # fmt: skip
    used = {("H1", "RBC"): 20, ("H2", "RBC"): 60}
    demand = DemandModel(
        MONDAY, {("H1", "O+"): 0.05, ("H2", "O+"): 1.5}, {}, SIZES, (1.0,) * 7, used
    )
    # the reserve counts eligible units, as pipeline.eligibility.check_move does
    assert plan_batches(eligible, stock, demand, RankingConfig(), sender_reserve_units=2).empty
    plan = plan_batches(eligible, stock, demand, RankingConfig(), sender_reserve_units=0)
    assert sorted(plan["unit_id"]) == ["A3", "A4"]
    assert plan["batch_id"].nunique() == 1 and plan["suggested"].all()
    assert (plan["send_by"] == MONDAY).all()  # waiting only loses value on a lateral move
    assert plan_batches(eligible.iloc[0:0], stock, demand, RankingConfig()).empty
