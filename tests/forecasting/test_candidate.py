from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from forecasting.candidate import candidate_forecast
from forecasting.config import CONFIG, KNOWN_GROUPS

HOSPITALS = ("HSP-001", "HSP-002")


def _daily(rows):
    frame = pd.DataFrame(rows, columns=["facility_id", "blood_group", "day", "units_requested"])
    frame["day"] = pd.to_datetime(frame["day"])
    return frame


def test_hospital_total_is_expanding_daily_mean_and_groups_follow_network_shares():
    origin = CONFIG.data_start + timedelta(days=10)  # 10 days of history
    day = CONFIG.data_start + timedelta(days=2)
    # HSP-001 requested 30 units of O+ and 10 of A+; HSP-002 requested 20 of O+.
    daily = _daily(
        [
            ("HSP-001", "O+", day, 30),
            ("HSP-001", "A+", day, 10),
            ("HSP-002", "O+", day, 20),
        ]
    )
    forecast = candidate_forecast(daily, origin, HOSPITALS, KNOWN_GROUPS)
    # network shares: O+ 50/60, A+ 10/60. HSP-001 daily mean = 40/10 = 4 -> 28 per 7 days.
    assert forecast[("HSP-001", "O+")] == pytest.approx(28 * 50 / 60)
    assert forecast[("HSP-001", "A+")] == pytest.approx(28 * 10 / 60)
    # HSP-002 daily mean = 2 -> 14 per 7 days.
    assert forecast[("HSP-002", "O+")] == pytest.approx(14 * 50 / 60)
    assert forecast[("HSP-002", "O-")] == 0.0


def test_group_shares_sum_to_one_so_hospital_totals_are_preserved():
    origin = CONFIG.data_start + timedelta(days=14)
    day = CONFIG.data_start + timedelta(days=1)
    daily = _daily(
        [("HSP-001", "O+", day, 7), ("HSP-001", "B-", day, 7), ("HSP-002", "A+", day, 14)]
    )
    forecast = candidate_forecast(daily, origin, HOSPITALS, KNOWN_GROUPS)
    assert forecast.loc["HSP-001"].sum() == pytest.approx(7 * 14 / 14)
    assert forecast.loc["HSP-002"].sum() == pytest.approx(7 * 14 / 14)


def test_requests_on_or_after_the_origin_are_never_used():
    origin = CONFIG.data_start + timedelta(days=20)
    before = [("HSP-001", "O+", origin - timedelta(days=3), 10)]
    with_future = before + [
        ("HSP-001", "O+", origin + timedelta(days=k), 500) for k in range(0, 10)
    ]
    a = candidate_forecast(_daily(before), origin, HOSPITALS, KNOWN_GROUPS)
    b = candidate_forecast(_daily(with_future), origin, HOSPITALS, KNOWN_GROUPS)
    pd.testing.assert_series_equal(a, b)


def test_no_history_is_rejected():
    with pytest.raises(ValueError):
        candidate_forecast(_daily([]), CONFIG.data_start, HOSPITALS, KNOWN_GROUPS)
    with pytest.raises(ValueError):
        candidate_forecast(
            _daily([]), CONFIG.data_start + timedelta(days=5), HOSPITALS, KNOWN_GROUPS
        )
