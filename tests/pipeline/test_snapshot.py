"""DG-03: closing snapshot without leakage."""

from __future__ import annotations

import dataclasses
import sqlite3

import pandas as pd
import pytest

from pipeline.config import PipelineConfig
from pipeline.snapshot import LeakageError, build_snapshot, write_snapshot
from pipeline.store import create_schema, write_official


@pytest.fixture
def snap(mini_tables):
    """Test helper: snap."""
    return build_snapshot(mini_tables, PipelineConfig())


def _ids(df):
    """Test helper: ids."""
    return set(df["unit_id"])


def test_shelf_contains_only_units_on_the_shelf_at_as_of(snap):
    """Shelf contains only units on the shelf at as of."""
    assert _ids(snap.units) == {"U1", "U2", "U5", "U6", "U7", "U9", "U10", "U11", "U12"}


def test_unit_received_after_as_of_is_not_on_the_shelf(snap):
    # U3 was dispatched at 22:00 on 31 Oct and received on 1 Nov: in transit at as-of.
    """Unit received after as of is not on the shelf."""
    row = snap.excluded.set_index("unit_id").loc["U3"]
    assert row["reason"] == "in_transit_at_as_of"


def test_unit_released_after_as_of_is_not_on_the_shelf(snap):
    """Unit released after as of is not on the shelf."""
    assert snap.excluded.set_index("unit_id").loc["U4", "reason"] == "released_after_as_of"


def test_transfused_units_are_not_on_the_shelf(snap):
    """Transfused units are not on the shelf."""
    assert "U8" not in _ids(snap.units) | _ids(snap.excluded)


def test_missing_receipt_is_flagged_not_invented(snap):
    """Missing receipt is flagged not invented."""
    u5 = snap.units.set_index("unit_id").loc["U5"]
    assert u5["receipt_status"] == "unconfirmed"
    assert u5["on_shelf_since"] != u5["on_shelf_since"]  # NaT: no fabricated receipt time


def test_unknown_group_stays_unknown(snap):
    """Unknown group stays unknown."""
    assert pd.isna(snap.units.set_index("unit_id").loc["U7", "blood_group"])


def test_exposure_flag_is_carried(snap):
    """Exposure flag is carried."""
    assert bool(snap.units.set_index("unit_id").loc["U6", "temp_excursion_exposed"]) is True


def test_reconciles_with_daily_stock(snap):
    """Reconciles with daily stock."""
    assert snap.reconciliation.empty
    assert snap.daily_stock_total == 8


def test_earlier_as_of_is_refused(mini_tables):
    """Earlier as of is refused."""
    july = dataclasses.replace(PipelineConfig(), as_of="2026-07-01T23:59:59+03:00")
    with pytest.raises(LeakageError):
        build_snapshot(mini_tables, july)


def test_rebuild_over_an_existing_database_works(mini_tables, snap, tmp_path):
    """Rebuild over an existing database works."""
    conn = sqlite3.connect(tmp_path / "db.sqlite")
    for _ in range(2):
        create_schema(conn)
        write_official(conn, mini_tables)
        write_snapshot(conn, snap, PipelineConfig())
    assert conn.execute("SELECT COUNT(*) FROM dg_snapshot_units").fetchone()[0] == len(snap.units)


def test_snapshot_is_written_with_as_of(mini_tables, snap):
    """Snapshot is written with as of."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    write_official(conn, mini_tables)
    write_snapshot(conn, snap, PipelineConfig())
    as_of, n = conn.execute("SELECT as_of, units_on_shelf FROM dg_snapshot_meta").fetchone()
    assert as_of == "2026-10-31T23:59:59+03:00" and n == len(snap.units)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(dg_snapshot_units)")]
    for needed in ("as_of", "unit_id", "facility_id", "component", "blood_group", "expiry_date", "status",
                   "temp_excursion_exposed"):
        assert needed in cols
