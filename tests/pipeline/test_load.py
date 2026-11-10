"""DG-01: loading and validation of the official CSVs."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.load import RAW_DIR, SchemaError, load_all, read_table
from pipeline.schema import EXPECTED_ROWS

FACILITIES = (
    "facility_id,name,facility_type,county,lat,lon,keph_level,beds,grid_reliability,connectivity,"
    "supply_centre_id,makes_platelets,separates_components,has_blood_fridge_backup_power,"
    "routine_deliveries_per_week\n"
    "RBTC-A,Centre A,regional_blood_centre,X,-1.0,36.0,,0,0.9,4G,,True,True,True,\n"
    "HSP-1,Hospital 1,county_referral,X,-1.1,36.1,4,100,0.8,3G,RBTC-A,False,False,False,3\n"
)
LOGS_HEADER = "facility_id,recorded_at,temp_c\n"


def _write(tmp: Path, name: str, text: str) -> Path:
    (tmp / f"{name}.csv").write_text(text)
    return tmp


def test_reads_typed_columns(tmp_path):
    _write(tmp_path, "facilities", FACILITIES)
    df = read_table("facilities", tmp_path)
    assert df["has_blood_fridge_backup_power"].tolist() == [True, False]
    assert df["beds"].dtype.name == "Int64"
    assert df["keph_level"].isna().iloc[0]  # empty cell = not recorded, kept missing


def test_missing_column_fails_loudly(tmp_path):
    _write(tmp_path, "temperature_logs", "facility_id,recorded_at\nHSP-1,2026-01-01 00:00:00\n")
    with pytest.raises(SchemaError, match="missing columns"):
        read_table("temperature_logs", tmp_path)


def test_unexpected_column_fails_loudly(tmp_path):
    text = "facility_id,recorded_at,temp_c,extra\nHSP-1,2026-01-01 00:00:00,4.0,1\n"
    _write(tmp_path, "temperature_logs", text)
    with pytest.raises(SchemaError, match="unexpected columns"):
        read_table("temperature_logs", tmp_path)


def test_mistyped_value_fails_loudly(tmp_path):
    _write(tmp_path, "temperature_logs", LOGS_HEADER + "HSP-1,2026-01-01 00:00:00,warm\n")
    with pytest.raises(SchemaError, match="not float"):
        read_table("temperature_logs", tmp_path)


def test_unknown_facility_id_fails(tmp_path):
    _write(tmp_path, "facilities", FACILITIES)
    _write(tmp_path, "temperature_logs", LOGS_HEADER + "HSP-404,2026-01-01 00:00:00,4.0\n")
    with pytest.raises(SchemaError, match="not in facilities.csv"):
        load_all(tmp_path, ["facilities", "temperature_logs"])


def test_raw_dir_is_not_modified(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write(raw, "facilities", FACILITIES)
    before = (raw / "facilities.csv").read_bytes()
    load_all(raw, ["facilities"])
    assert (raw / "facilities.csv").read_bytes() == before
    assert sorted(p.name for p in raw.iterdir()) == ["facilities.csv"]


@pytest.mark.dataset
def test_official_row_counts_match_docs():
    if not (RAW_DIR / "units.csv").exists():
        pytest.skip("official dataset not present")
    tables, report = load_all()
    assert report.ok, report.row_count_discrepancies
    assert {n: len(df) for n, df in tables.items()} == EXPECTED_ROWS
