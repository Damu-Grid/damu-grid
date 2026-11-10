from datetime import date

from simulation.compare import Unit, plan, replay


def test_plan_respects_sender_reserve_and_does_not_move_same_unit_twice():
    units = [Unit(f"u{i}", "A", "O+", date(2026, 11, 5)) for i in range(3)]
    routes = {("A", "B"): 1.0, ("A", "C"): 2.0}
    rates = {("B", "O+"): 1.0, ("C", "O+"): 1.0, ("A", "O+"): 0.5}
    moves = plan(units, routes, {"B", "C"}, rates, "nearest")
    assert len(moves) <= 2
    assert len({unit.id for unit, _ in moves}) == len(moves)


def test_replay_counts_demand_at_empty_sites_and_moves():
    unit = Unit("u1", "A", "O+", date(2026, 11, 5))
    demand = {(0, "B", "O+"): 1, (1, "B", "O+"): 1}
    result = replay([unit], [(unit, "B")], demand)
    assert result["unmet"] == 1
    assert result["moved"] == 1
    assert result["route_batches"] == 1
