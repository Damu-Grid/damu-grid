"""DG-07: cold-chain and power-outage flags with evidence timestamps."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from pipeline.coldchain import (
    COLD_CHAIN_QUERY,
    agreement_with_official,
    custody_intervals,
    fridge_excursions,
    site_flags,
    unit_flags,
    write_flags,
)
from pipeline.config import PipelineConfig
from pipeline.eligibility import unit_eligibility
from pipeline.quality import logger_gaps
from pipeline.snapshot import build_snapshot
from pipeline.store import create_schema, write_official

CFG = PipelineConfig()


@pytest.fixture
def snap(mini_tables):
    """Test helper: snap."""
    return build_snapshot(mini_tables, CFG)


@pytest.fixture
def sites(mini_tables):
    """Test helper: sites."""
    return site_flags(mini_tables, CFG)


@pytest.fixture
def units(snap, mini_tables, sites):
    """Test helper: units."""
    return unit_flags(snap.units, mini_tables, CFG, snap.as_of, sites)


def _types(flags, unit_id):
    """Test helper: types."""
    return set(flags.loc[flags["unit_id"] == unit_id, "flag_type"])


def test_excursion_needs_consecutive_hours(mini_tables):
    """Excursion needs consecutive hours."""
    ex = fridge_excursions(mini_tables["temperature_logs"], CFG)
    assert len(ex) == 1  # the single 6.8 C reading on 26 Oct is not an event
    e = ex.iloc[0]
    assert e["facility_id"] == "HSP-1" and e["hours"] == 3 and e["peak_c"] == 7.5
    assert e["start_at"] == pd.Timestamp("2026-10-25 02:00")


def test_glitches_are_never_clinical_events(sites, units):
    """Glitches are never clinical events."""
    glitches = sites[sites["flag_type"] == "sensor_glitch"]
    assert len(glitches) == 2 and not glitches["blocks_suggestion"].any()
    assert "sensor_glitch" not in set(units["flag_type"])
    assert not (sites["flag_type"].eq("fridge_excursion") & sites["facility_id"].eq("RBTC-A")).any()


def test_outage_with_backup_is_not_a_flag(sites):
    """Outage with backup is not a flag."""
    outages = sites[sites["flag_type"] == "outage_no_backup"]
    assert set(outages["source_ref"]) == {"OUT-1", "OUT-3"}


def test_site_event_flags_units_on_the_shelf_at_that_time(units):
    """Site event flags units on the shelf at that time."""
    assert "fridge_excursion" in _types(units, "U1")          # U1 at HSP-1 since 19 Oct
    assert "outage_no_backup" not in _types(units, "U1")      # HSP-1 outage on 5 Oct, before U1 arrived


def test_every_kind_of_unit_evidence(units):
    """Every kind of unit evidence."""
    assert {"outage_no_backup", "logger_gap", "coolbox_excursion", "official_exposure"} <= _types(units, "U6")
    assert "receipt_unconfirmed" in _types(units, "U5")


def test_flags_carry_evidence_timestamps(units):
    """Flags carry evidence timestamps."""
    assert units["start_at"].notna().all()
    gap = units[(units["unit_id"] == "U6") & (units["flag_type"] == "logger_gap")].iloc[0]
    assert gap["start_at"] == pd.Timestamp("2026-10-27 23:00") and gap["value"] == 10


def test_custody_follows_the_unit_history(snap, mini_tables):
    """Custody follows the unit history."""
    stays = custody_intervals(snap.units, mini_tables["transfers"], snap.as_of)
    u1 = stays[stays["unit_id"] == "U1"].sort_values("stay_start")
    assert list(u1["facility_id"]) == ["RBTC-A", "HSP-1"]
    assert u1.iloc[0]["stay_end"] == pd.Timestamp("2026-10-19 08:00")   # dispatched from the centre
    assert u1.iloc[1]["stay_start"] == pd.Timestamp("2026-10-19 10:30")  # received at the hospital
    # U5's receipt was never confirmed: no invented stay at HSP-1.
    assert list(stays.loc[stays["unit_id"] == "U5", "facility_id"]) == ["RBTC-A"]


def test_evidence_at_an_earlier_site_is_attached(snap, mini_tables):
    """Evidence at an earlier site is attached."""
    t = dict(mini_tables)
    extra = pd.DataFrame({"outage_id": ["OUT-9"], "facility_id": ["RBTC-A"],
                          "start_time": [pd.Timestamp("2026-10-18 10:00")],
                          "end_time": [pd.Timestamp("2026-10-18 14:00")],
                          "duration_hours": [4.0], "backup_power_engaged": [False]})
    t["power_outages"] = pd.concat([t["power_outages"], extra], ignore_index=True)
    flags = unit_flags(snap.units, t, CFG, snap.as_of)
    u1 = flags[(flags["unit_id"] == "U1") & (flags["flag_type"] == "outage_no_backup")]
    assert len(u1) == 1 and u1.iloc[0]["facility_id"] == "RBTC-A" and "at RBTC-A" in u1.iloc[0]["note"]


def test_agreement_with_the_official_flag(snap, units):
    """Agreement with the official flag."""
    rep = agreement_with_official(snap.units[snap.units["component"] == "RBC"], units)
    assert rep["official_exposed"] == 1 and rep["official_exposed_with_our_evidence"] == 1  # U6
    assert rep["our_evidence_not_officially_exposed"] == 1                                 # U1


def test_fridge_evidence_is_not_attached_to_platelets(units):
    # U10 (PLT) sits at RBTC-A like U2; fridge logs describe the 2-6 C blood fridge only.
    """Fridge evidence is not attached to platelets."""
    assert _types(units, "U10") == set()


def test_clean_unit_has_no_blocking_flag(units):
    """Clean unit has no blocking flag."""
    assert not units.loc[units["unit_id"] == "U2", "blocks_suggestion"].any()


def test_flags_feed_eligibility(snap, units):
    """Flags feed eligibility."""
    res = unit_eligibility(snap.units, CFG, snap.as_of, unit_flags=units).units.set_index("unit_id")
    assert "cold_chain_evidence" in res.loc["U1", "reasons"]
    assert res.loc["U2", "eligible"]


def test_missing_evidence_cannot_mark_a_unit_safe(snap, mini_tables):
    """A clean unit (U2 at RBTC-A) loses eligibility when its fridge goes silent for good."""
    t = dict(mini_tables)
    logs = t["temperature_logs"]
    t["temperature_logs"] = logs[~((logs["facility_id"] == "RBTC-A")
                                   & (logs["recorded_at"] > pd.Timestamp("2026-10-20")))]
    assert _types(unit_flags(snap.units, mini_tables, CFG, snap.as_of), "U2") == set()
    flags = unit_flags(snap.units, t, CFG, snap.as_of)
    assert "logger_gap" in _types(flags, "U2")
    res = unit_eligibility(snap.units, CFG, snap.as_of, unit_flags=flags).units.set_index("unit_id")
    assert not res.loc["U2", "eligible"] and "cold_chain_evidence" in res.loc["U2", "reasons"]


def test_trailing_silence_is_closed_by_the_as_of_time(mini_tables, snap):
    """Without the as-of time a fridge that stops reporting shows no gap; with it, it does."""
    logs = mini_tables["temperature_logs"]
    quiet = logs[~((logs["facility_id"] == "RBTC-A")
                   & (logs["recorded_at"] > pd.Timestamp("2026-10-20")))]
    assert logger_gaps(quiet, CFG).query("facility_id == 'RBTC-A'").empty
    gap = logger_gaps(quiet, CFG, snap.as_of).query("facility_id == 'RBTC-A'").iloc[0]
    assert gap["gap_start"] == pd.Timestamp("2026-10-20 00:00")
    assert gap["gap_end"] == snap.as_of and gap["missing_hours"] > 250


def test_query_contract_for_the_api(mini_tables, snap, sites, units):
    """Query contract for the api."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    write_official(conn, mini_tables)
    write_flags(conn, pd.concat([sites, units], ignore_index=True))
    rows = conn.execute(COLD_CHAIN_QUERY, {"facility_id": None, "unit_id": "U6"}).fetchall()
    assert {r[1] for r in rows} >= {"outage_no_backup", "logger_gap", "coolbox_excursion"}
    site_rows = conn.execute(COLD_CHAIN_QUERY, {"facility_id": "RBTC-A", "unit_id": None}).fetchall()
    assert all(r[1] != "sensor_glitch" for r in site_rows)
