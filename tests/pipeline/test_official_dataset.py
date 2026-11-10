"""DG-06: smoke checks on the full official dataset and the build command end to end.

These pin the measured facts written in docs/DATA.md, so a change in the pipeline that moves a
number shows up here first. Marked `dataset`: run alone with `pytest -m dataset`.
"""

from __future__ import annotations

import sqlite3

import pytest

from pipeline.__main__ import main
from pipeline.coldchain import agreement_with_official, unit_flags
from pipeline.config import load_config
from pipeline.eligibility import unit_eligibility
from pipeline.load import RAW_DIR, load_all
from pipeline.quality import quality_report
from pipeline.snapshot import build_snapshot

pytestmark = pytest.mark.dataset

NEEDED = ["facilities", "routes", "donations", "units", "transfers", "daily_stock", "power_outages",
          "temperature_logs", "requests"]


@pytest.fixture(scope="module")
def official():
    """Test helper: official."""
    if not (RAW_DIR / "units.csv").exists():
        pytest.skip("official dataset not present")
    tables, _ = load_all(names=NEEDED)
    cfg = load_config()
    snap = build_snapshot(tables, cfg)
    return tables, cfg, snap


def test_snapshot_reconciles_with_daily_stock(official):
    """Snapshot reconciles with daily stock."""
    _, _, snap = official
    assert len(snap.units) == 8666 and snap.daily_stock_total == 8666
    assert snap.reconciliation.empty
    assert set(snap.excluded["reason"]) == set()  # no in_stock unit is in transit or unreleased at as-of


def test_rbc_eligibility_counts(official):
    """Rbc eligibility counts."""
    tables, cfg, snap = official
    before = unit_eligibility(snap.units, cfg, snap.as_of)
    assert len(before.eligible) == 637
    flags = unit_flags(snap.units, tables, cfg, snap.as_of)
    after = unit_eligibility(snap.units, cfg, snap.as_of, unit_flags=flags)
    assert len(after.eligible) == 488
    rbc = snap.units[snap.units["component"] == "RBC"]
    agree = agreement_with_official(rbc, flags[flags["unit_id"].isin(rbc["unit_id"])])
    assert agree["official_exposed_with_our_evidence"] == agree["official_exposed"] == 87
    assert set(after.eligible["component"]) == {"RBC"}
    assert after.eligible["blood_group"].isin(cfg.known_blood_groups).all()
    assert not after.eligible["temp_excursion_exposed"].any()


def test_data_quality_counts(official):
    """Data quality counts."""
    tables, cfg, _ = official
    rep = quality_report(tables, cfg)
    assert rep["temperature_glitch"] == 55
    assert rep["transfers_receipt_unconfirmed"] == 1046
    assert rep["emergency_requests_group_unknown"] == 442


def test_build_command_end_to_end(tmp_path):
    """Build command end to end."""
    if not (RAW_DIR / "units.csv").exists():
        pytest.skip("official dataset not present")
    db = tmp_path / "damu_grid.sqlite"
    assert main(["build", "--db", str(db)]) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 49426
    assert conn.execute("SELECT units_on_shelf FROM dg_snapshot_meta").fetchone()[0] == 8666
    blocking = "SELECT COUNT(*) FROM dg_cold_chain_flags WHERE blocks_suggestion = 1"
    assert conn.execute(blocking).fetchone()[0] > 0
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
