"""DG-04: eligibility exclusions, each with its reason."""

from __future__ import annotations

import dataclasses
import sqlite3

import pandas as pd
import pytest

from pipeline.config import PipelineConfig, load_config
from pipeline.eligibility import (
    active_reserved_units,
    candidate_moves,
    check_move,
    sender_reserves_from_demand,
    unit_eligibility,
)
from pipeline.snapshot import build_snapshot
from pipeline.store import create_schema

CFG = PipelineConfig()


@pytest.fixture
def snap(mini_tables):
    return build_snapshot(mini_tables, CFG)


@pytest.fixture
def result(snap):
    return unit_eligibility(snap.units, CFG, snap.as_of)


def _reason(result, unit_id):
    return result.units.set_index("unit_id").loc[unit_id, "reasons"]


def test_clean_rbc_units_are_eligible(result):
    assert set(result.eligible["unit_id"]) == {"U1", "U2", "U9", "U11", "U12"}


def test_exposed_unit_is_excluded(result):
    assert "temp_excursion_exposed" in _reason(result, "U6")


def test_unknown_group_is_excluded(result):
    assert "unknown_blood_group" in _reason(result, "U7")


def test_unconfirmed_receipt_is_excluded(result):
    assert "receipt_unconfirmed" in _reason(result, "U5")


def test_platelets_are_out_of_the_tier1_queue(result):
    assert "component_not_in_queue" in _reason(result, "U10")


def test_expired_unit_is_excluded(snap):
    late = pd.Timestamp("2026-11-26 00:00:00")
    res = unit_eligibility(snap.units, CFG, late)
    assert "expired_at_as_of" in res.units.set_index("unit_id").loc["U1", "reasons"]


def test_reserved_unit_is_excluded(snap):
    res = unit_eligibility(snap.units, CFG, snap.as_of, reserved_unit_ids={"U2"})
    assert "reserved_or_in_transit" in res.units.set_index("unit_id").loc["U2", "reasons"]


def test_missing_exposure_value_is_conservative(snap):
    units = snap.units.copy()
    units["temp_excursion_exposed"] = units["temp_excursion_exposed"].astype("boolean")
    units.loc[units["unit_id"] == "U2", "temp_excursion_exposed"] = pd.NA
    res = unit_eligibility(units, CFG, snap.as_of)
    assert "exposure_not_recorded" in res.units.set_index("unit_id").loc["U2", "reasons"]


def test_blocking_cold_chain_flag_excludes(snap):
    flags = pd.DataFrame({"unit_id": ["U1"], "flag_type": ["fridge_excursion"], "blocks_suggestion": [True]})
    res = unit_eligibility(snap.units, CFG, snap.as_of, unit_flags=flags)
    assert "cold_chain_evidence" in res.units.set_index("unit_id").loc["U1", "reasons"]


def test_exclusion_counts_cover_every_reason(result):
    counts = result.exclusion_counts()
    assert counts["unknown_blood_group"] == 1 and counts["temp_excursion_exposed"] == 1


def _unit(result, uid):
    return result.units.set_index("unit_id").loc[uid].to_dict() | {"unit_id": uid}


def _move(result, mini_tables, uid, dest, **kw):
    args = dict(as_of=pd.Timestamp("2026-10-31 23:59:59"), config=CFG, routes=mini_tables["routes"],
                facilities=mini_tables["facilities"], sender_available=4, recipient_gap=2)
    args.update(kw)
    return check_move(_unit(result, uid), dest, **args)


def test_move_without_route_is_excluded(result, mini_tables):
    routes = mini_tables["routes"]
    no_route = routes[~((routes["from_facility_id"] == "RBTC-A") & (routes["to_facility_id"] == "HSP-1"))]
    move = _move(result, mini_tables, "U2", "HSP-1", routes=no_route)
    assert "no_route" in move["reasons"]


def test_move_to_a_centre_is_excluded(result, mini_tables):
    move = _move(result, mini_tables, "U1", "RBTC-A")
    assert "recipient_not_hospital" in move["reasons"]


def test_short_life_on_arrival_is_excluded(result, mini_tables):
    # U9 expires 3 Nov: 2 h road + 6 h allowance leaves ~40 h, below the 168 h default.
    move = _move(result, mini_tables, "U9", "HSP-1")
    assert "insufficient_life_on_arrival" in move["reasons"]
    assert move["remaining_hours_on_arrival"] == pytest.approx(48 - 0.0003 - 8, abs=0.01)


def test_sender_reserve_is_respected(result, mini_tables):
    move = _move(result, mini_tables, "U2", "HSP-1", sender_available=2)
    assert "sender_below_reserve" in move["reasons"]


def test_recipient_without_documented_gap_is_excluded(result, mini_tables):
    for gap in (None, 0):
        move = _move(result, mini_tables, "U2", "HSP-1", recipient_gap=gap)
        assert "no_documented_recipient_gap" in move["reasons"]


def test_valid_move_passes_with_card_facts(result, mini_tables):
    move = _move(result, mini_tables, "U2", "HSP-1")
    assert move["ok"] and move["typical_travel_hours"] == 2.0 and move["sender_stock_after"] == 3


def test_candidate_moves_keep_the_sender_reserve(result, mini_tables):
    moves = candidate_moves(
        result, as_of=pd.Timestamp("2026-10-31 23:59:59"), config=CFG, routes=mini_tables["routes"],
        facilities=mini_tables["facilities"], recipient_gaps={("HSP-2", "RBC", "O+"): 3})
    rbtc = moves[(moves["from_facility_id"] == "RBTC-A") & moves["ok"]]
    # RBTC-A holds 4 eligible O+ (U9 too short): at most 4 - 2 = 2 may leave, soonest expiry first.
    assert list(rbtc["unit_id"]) == ["U2", "U11"]


def test_reserves_can_come_from_the_demand_forecast(result, mini_tables):
    reserves = sender_reserves_from_demand({("RBTC-A", "RBC", "O+"): 1.2}, cover_days=2.5, minimum=2)
    assert reserves == {("RBTC-A", "RBC", "O+"): 3}
    moves = candidate_moves(
        result, as_of=pd.Timestamp("2026-10-31 23:59:59"), config=CFG, routes=mini_tables["routes"],
        facilities=mini_tables["facilities"], recipient_gaps={("HSP-2", "RBC", "O+"): 3},
        sender_reserves=reserves)
    assert list(moves.loc[(moves["from_facility_id"] == "RBTC-A") & moves["ok"], "unit_id"]) == ["U2"]


def test_rules_come_from_the_shared_config(snap, tmp_path):
    path = tmp_path / "other_country.toml"
    path.write_text("default_sender_reserve_units = 0\n"
                    "[components.RBC]\nmin_remaining_hours_on_arrival = 24.0\n")
    cfg = load_config(path)
    assert cfg.default_sender_reserve_units == 0 and cfg.policy("RBC").min_remaining_hours_on_arrival == 24.0
    plt = dataclasses.replace(cfg).with_components_enabled("PLT")
    res = unit_eligibility(snap.units, plt, snap.as_of)
    assert "U10" in set(res.eligible["unit_id"])


def test_active_moves_are_read_from_the_action_store():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    now = "2026-11-10T21:00:00+03:00"
    for mid, uid, state in [("m1", "U2", "Reserved"), ("m2", "U11", "Rejected"), ("m3", "U12", "InTransit")]:
        conn.execute("INSERT INTO dg_moves (move_id, unit_id, from_facility_id, to_facility_id, component,"
                     " blood_group, state, created_at, updated_at) VALUES (?, ?, 'RBTC-A', 'HSP-1', 'RBC',"
                     " 'O+', ?, ?, ?)", (mid, uid, state, now, now))
    assert active_reserved_units(conn) == {"U2", "U12"}
