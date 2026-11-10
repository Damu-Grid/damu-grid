"""DG-05: deliberate data-quality problems stay visible and never become clinical facts."""

from __future__ import annotations

import pandas as pd

from pipeline.config import PipelineConfig
from pipeline.quality import (
    classify_temperatures,
    logger_gaps,
    possible_duplicate_donors,
    quality_report,
    requests_with_facility_check,
    transfers_with_receipt_evidence,
)

CFG = PipelineConfig()


def test_requests_are_keyed_by_facility_id(mini_tables):
    """Requests are keyed by facility id."""
    r = requests_with_facility_check(mini_tables["requests"], mini_tables["facilities"])
    r = r.set_index("request_id")
    assert r.loc["R2", "facility_id"] == "HSP-1"            # typed "HOSPITAL  ONE"
    assert r.loc["R2", "name_variant"] == "case_or_spacing"
    assert r.loc["R3", "name_variant"] == "abbreviation"    # "Hosp. Two"
    assert r.loc["R1", "name_variant"] == "exact"
    assert r.loc["R2", "facility_name_raw"] == "HOSPITAL  ONE"  # original text kept as typed


def test_ambiguous_and_wrong_site_names_are_flagged():
    """Ambiguous and wrong site names are flagged."""
    facilities = pd.DataFrame({
        "facility_id": ["HSP-A", "HSP-B", "HSP-C"],
        "name": ["Kisumu County Referral Hospital", "Kisumu County Referral Hospital Annex",
                 "Busia County Referral Hospital"],
    })
    requests = pd.DataFrame({
        "request_id": ["R1", "R2", "R3", "R4"],
        "facility_id": ["HSP-A", "HSP-A", "HSP-A", "HSP-A"],
        "facility_name_raw": ["Kisumu CRH", "Kisumu County Referral", "Busia CRH", "Somewhere Else"],
        "patient_blood_group": ["O+"] * 4,
    })
    r = requests_with_facility_check(requests, facilities).set_index("request_id")["name_variant"]
    assert r["R1"] == "abbreviation"  # expands to exactly HSP-A's name
    assert r["R2"] == "ambiguous"     # a prefix of both Kisumu sites
    assert r["R3"] == "mismatch"    # typed name is another facility: worth a human look
    assert r["R4"] == "unmatched"


def test_unknown_patient_group_stays_unknown(mini_tables):
    """Unknown patient group stays unknown."""
    r = requests_with_facility_check(mini_tables["requests"], mini_tables["facilities"])
    r = r.set_index("request_id")
    assert r.loc["R2", "patient_blood_group"] == "unknown"
    assert not r.loc["R2", "patient_group_known"]


def test_missing_receipt_is_not_fabricated(mini_tables):
    """Missing receipt is not fabricated."""
    t = transfers_with_receipt_evidence(mini_tables["transfers"]).set_index("transfer_id")
    assert t.loc["T5", "receipt_status"] == "unconfirmed"
    assert pd.isna(t.loc["T5", "received_at"]) and pd.isna(t.loc["T5", "transit_hours"])
    assert t.loc["T1", "transit_hours"] == 2.5


def test_glitch_values_are_glitches_not_excursions(mini_tables):
    """Glitch values are glitches not excursions."""
    logs = classify_temperatures(mini_tables["temperature_logs"], CFG)
    at = logs.set_index(["facility_id", "recorded_at"])["reading_class"]
    assert at[("RBTC-A", pd.Timestamp("2026-10-22 03:00"))] == "glitch"      # 99.9
    assert at[("RBTC-A", pd.Timestamp("2026-10-22 04:00"))] == "glitch"      # 0.0, not "below range"
    assert at[("HSP-1", pd.Timestamp("2026-10-25 02:00"))] == "above_range"  # 7.5 C is real


def test_logger_gaps_are_reported(mini_tables):
    """Logger gaps are reported."""
    gaps = logger_gaps(mini_tables["temperature_logs"], CFG)
    assert len(gaps) == 1
    g = gaps.iloc[0]
    assert g["facility_id"] == "HSP-2" and g["missing_hours"] == 10


def test_possible_duplicate_donors_are_listed_not_merged():
    """Possible duplicate donors are listed not merged."""
    donors = pd.DataFrame({
        "donor_id": ["A", "B", "C"], "birth_date": pd.to_datetime(["2000-01-01"] * 3),
        "sex": ["F", "F", "M"], "home_county": ["X", "X", "X"], "phone_last4": ["1234", "1234", "1234"],
    })
    dup = possible_duplicate_donors(donors)
    assert set(dup["donor_id"]) == {"A", "B"} and dup["match_group"].nunique() == 1


def test_quality_report_counts(mini_tables):
    """Quality report counts."""
    rep = quality_report(mini_tables, CFG)
    assert rep["requests_name_not_exact"] == 2
    assert rep["emergency_requests_group_unknown"] == 1
    assert rep["transfers_receipt_unconfirmed"] == 1
    assert rep["temperature_glitch"] == 2
    assert rep["logger_gaps"] == 1
