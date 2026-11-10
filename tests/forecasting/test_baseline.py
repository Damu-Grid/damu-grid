from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from forecasting.baseline import baseline_forecast
from forecasting.config import CONFIG, KNOWN_GROUPS

HOSPITALS = ("HSP-001", "HSP-002")


def _daily(rows):
    frame = pd.DataFrame(rows, columns=["facility_id", "blood_group", "day", "units_requested"])
    frame["day"] = pd.to_datetime(frame["day"])
    return frame


def test_formula_is_seven_times_trailing_28_day_mean():
    origin = date(2026, 7, 1)
    start = origin - timedelta(days=28)
    # 56 units in the 28 days before the origin -> 2 per day -> 14 expected in 7 days
    daily = _daily([("HSP-001", "O+", start, 56)])
    forecast = baseline_forecast(daily, origin, HOSPITALS, KNOWN_GROUPS)
    assert forecast[("HSP-001", "O+")] == pytest.approx(14.0)
    assert forecast[("HSP-002", "O+")] == 0.0
    assert forecast[("HSP-001", "A+")] == 0.0


def test_window_is_strictly_before_origin_and_includes_the_28th_day_back():
    origin = date(2026, 7, 1)
    daily = _daily(
        [
            ("HSP-001", "O+", origin - timedelta(days=28), 28),  # first day inside the window
            ("HSP-001", "O+", origin - timedelta(days=29), 1000),  # one day too old
            ("HSP-001", "O+", origin, 1000),  # on the origin day: must not be read
            ("HSP-001", "O+", origin + timedelta(days=3), 1000),  # future: must not be read
        ]
    )
    forecast = baseline_forecast(daily, origin, HOSPITALS, KNOWN_GROUPS)
    assert forecast[("HSP-001", "O+")] == pytest.approx(7.0)


def test_future_requests_never_change_a_forecast():
    origin = date(2026, 7, 1)
    base = [("HSP-001", "O+", origin - timedelta(days=5), 10)]
    future = base + [("HSP-001", "O+", origin + timedelta(days=d), 99) for d in range(0, 14)]
    a = baseline_forecast(_daily(base), origin, HOSPITALS, KNOWN_GROUPS)
    b = baseline_forecast(_daily(future), origin, HOSPITALS, KNOWN_GROUPS)
    pd.testing.assert_series_equal(a, b)


def test_origin_too_early_for_a_full_window_is_rejected():
    with pytest.raises(ValueError):
        baseline_forecast(
            _daily([]), CONFIG.data_start + timedelta(days=10), HOSPITALS, KNOWN_GROUPS
        )
