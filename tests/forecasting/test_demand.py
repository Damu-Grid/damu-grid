from __future__ import annotations

from datetime import date

import pandas as pd

from forecasting.config import KNOWN_GROUPS
from forecasting.demand import build_demand_slice, hospital_ids, period_totals


def test_hospital_filter_keeps_only_hospital_types(facilities):
    assert hospital_ids(facilities) == ("HSP-001", "HSP-002")


def test_unknown_group_other_component_and_non_hospital_are_excluded_and_counted(
    requests_frame, facilities
):
    sliced = build_demand_slice(requests_frame, facilities)
    ex = sliced.exclusions
    assert ex["request_rows_total"] == 7
    assert ex["not_hospital"] == 1
    assert ex["other_component"] == 1
    assert ex["unknown_or_missing_group"] == 1
    assert ex["request_rows_used"] == 4
    assert sliced.daily["units_requested"].sum() == 2 + 1 + 4 + 3


def test_daily_aggregation_sums_same_day_requests(requests_frame, facilities):
    daily = build_demand_slice(requests_frame, facilities).daily
    row = daily[(daily.facility_id == "HSP-001") & (daily.blood_group == "O+")]
    assert len(row) == 1
    assert row["units_requested"].iloc[0] == 3  # 2 + 1 on the same day


def test_period_totals_end_is_exclusive_and_missing_cells_are_zero(requests_frame, facilities):
    sliced = build_demand_slice(requests_frame, facilities)
    totals = period_totals(
        sliced.daily, date(2026, 1, 5), date(2026, 1, 6), sliced.hospitals, sliced.groups
    )
    assert totals[("HSP-001", "O+")] == 3
    assert totals[("HSP-001", "A+")] == 0  # request is on 6 Jan, outside [5 Jan, 6 Jan)
    assert len(totals) == len(sliced.hospitals) * len(KNOWN_GROUPS)


def test_without_completeness_assumption_missing_cells_are_nan(requests_frame, facilities):
    sliced = build_demand_slice(requests_frame, facilities)
    totals = period_totals(
        sliced.daily,
        date(2026, 1, 5),
        date(2026, 1, 6),
        sliced.hospitals,
        sliced.groups,
        assume_complete=False,
    )
    assert pd.isna(totals[("HSP-001", "A+")])
