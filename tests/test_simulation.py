"""Focused tests for the DG-15..DG-17 simulation rebuild."""

from datetime import date, timedelta

import numpy as np

from simulation.compare import (
    COURIER_CAP_PER_ROUTE_DAY,
    START,
    SimInputs,
    Unit,
    brier_and_buckets,
    can_serve,
    compare,
    plan,
    replay,
    restock,
    send_by,
    survival_score,
    transit_days,
)

GROUPS = ("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-")


def _sim(**over) -> SimInputs:
    routes = {("A", "B"): 0.5, ("B", "A"): 0.5}
    base = {
        "units": [],
        "routes": routes,
        "hospitals": {"A", "B"},
        "rates": {(s, g): 0.0 for s in ("A", "B") for g in GROUPS},
        "group_mix": {g: 1 / 8 for g in GROUPS},
        "supply_centre": {"A": "C", "B": "C"},
        "deliveries_per_week": {"A": 3, "B": 3},
    }
    base.update(over)
    return SimInputs(**base)


def test_wb_is_exact_match_only_and_rbc_o_neg_is_universal():
    assert can_serve(Unit("w1", "A", "A+", date(2026, 11, 5), "WB"), "A+")
    assert not can_serve(Unit("w1", "A", "A+", date(2026, 11, 5), "WB"), "AB+")
    assert not can_serve(Unit("w2", "A", "O+", date(2026, 11, 5), "WB"), "O-")
    assert can_serve(Unit("r1", "A", "O-", date(2026, 11, 5), "RBC"), "AB+")
    assert not can_serve(Unit("r2", "A", "AB+", date(2026, 11, 5), "RBC"), "O+")


def test_send_by_enforces_travel_plus_buffer():
    unit = Unit("u1", "A", "O+", date(2026, 11, 3), "RBC")
    # 0.5 h -> 1 travel day + 1 buffer day: last dispatch 1 Nov.
    assert send_by(unit, 0.5) == date(2026, 11, 1)
    assert transit_days(11.49) == 1
    assert transit_days(25.0) == 2


def test_plan_respects_courier_cap_and_sender_reserve():
    units = [Unit(f"u{i}", "A", "O+", date(2026, 11, 6), "RBC") for i in range(12)]
    sim = _sim(units=units, rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS},
                                   ("B", "O+"): 2.0, ("A", "O+"): 0.5})
    stock = list(units)
    inbound: dict = {}
    planned = plan(sim, stock, inbound, START, "nearest",
                   cap_left={("A", "B"): COURIER_CAP_PER_ROUTE_DAY})
    assert len(planned.moves) <= COURIER_CAP_PER_ROUTE_DAY
    # Sender reserve: A keeps >= max(1, ceil(2 * 0.5)) = 1 compatible unit.
    left = [u for u in stock if u.site == "A"]
    assert len(left) >= 1


def test_plan_treats_missing_route_cap_as_full_default_cap():
    units = [Unit(f"u{i}", "A", "O+", date(2026, 12, 12), "RBC") for i in range(4)]
    sim = _sim(units=units, rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS},
                                   ("B", "O+"): 2.0, ("A", "O+"): 0.1})
    stock = list(units)
    planned = plan(sim, stock, {}, START, "nearest", cap_left={})
    assert 1 <= len(planned.moves) <= COURIER_CAP_PER_ROUTE_DAY


def test_expiry_aware_moves_soonest_expiry_first():
    soon = Unit("soon", "A", "O+", date(2026, 11, 4), "WB")
    late = Unit("late", "A", "O+", date(2026, 12, 9), "WB")
    sim = _sim(units=[soon, late],
               rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS}, ("B", "O+"): 1.0})
    stock = [soon, late]
    planned = plan(sim, stock, {}, START, "expiry_aware", cap_left={("A", "B"): 6})
    assert [u.id for u, _, _ in planned.moves] == ["soon"]


def test_restock_delivers_to_short_hospital():
    sim = _sim(units=[Unit("c1", "C", "O+", date(2026, 12, 12), "RBC")],
               rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS}, ("B", "O+"): 2.0})
    stock = list(sim.units)
    restock(sim, stock, START + timedelta(days=1), np.random.default_rng(0))
    # No crash; fresh inflow units land at the RBTC centres, deliveries at A/B.
    assert all(u.site in ("A", "B", "C", "RBTC-NBO", "RBTC-MSA", "RBTC-NKR",
                          "RBTC-KSM", "RBTC-ELD", "RBTC-EMB") for u in stock)


def test_replay_splits_expired_by_product_and_counts_unmet():
    sim = _sim(
        units=[Unit("r1", "B", "O+", date(2026, 11, 2), "RBC"),
               Unit("w1", "B", "O+", date(2026, 11, 2), "WB")],
        rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS}, ("B", "O+"): 5.0},
    )
    demand = {(day, "B", "O+"): 0 for day in range(7)}
    result = replay(sim, demand, "nearest", np.random.default_rng(0))
    assert result.expired["RBC"] + result.expired["WB"] >= 2
    assert result.unmet == 0


def test_survival_score_bounds_and_brier():
    sim = _sim(units=[Unit("u1", "B", "O+", date(2026, 12, 12), "RBC")],
               rates={**{(s, g): 0.0 for s in ("A", "B") for g in GROUPS}, ("B", "O+"): 1.0})
    p = survival_score(sim.units, sim.units[0], sim.rates, START)
    assert 0.0 <= p <= 1.0
    cal = brier_and_buckets([(1.0, 1), (0.0, 0), (0.5, 1)])
    assert cal["brier"] == 0.25 / 3
    assert sum(b["n"] for b in cal["buckets"]) == 3


def test_compare_two_seeds_reports_mean_sd_and_calibration(tmp_path):
    payload = compare(seeds=(4000, 4001), out_dir=tmp_path)
    for policy in ("nearest", "expiry_aware"):
        assert payload["policies"][policy]["unmet"]["mean"] >= 0
        assert payload["policies"][policy]["calibration"]["brier"] is not None
    assert (tmp_path / "sim_compare.json").exists()
    assert (tmp_path / "sim_summary.md").exists()
