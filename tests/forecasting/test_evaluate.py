from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from forecasting.config import calibration_origins, evaluation_origins
from forecasting.evaluate import error_metrics, paired_rmse_difference, summarise


def test_evaluation_origins_are_weekly_from_1_july_to_21_october():
    origins = evaluation_origins()
    assert origins[0] == date(2026, 7, 1)
    assert origins[-1] == date(2026, 10, 21)
    assert len(origins) == 17
    assert all((b - a).days == 7 for a, b in zip(origins, origins[1:], strict=False))


def test_calibration_origins_share_the_weekday_and_finish_before_july():
    origins = calibration_origins()
    assert origins[0] == date(2026, 5, 6)
    assert origins[-1] == date(2026, 6, 24)
    assert len(origins) == 8
    assert {o.weekday() for o in origins} == {date(2026, 7, 1).weekday()}


def test_error_metrics_known_values():
    actual = pd.Series([0.0, 2.0, 4.0])
    predicted = pd.Series([1.0, 2.0, 1.0])  # errors +1, 0, -3
    m = error_metrics(actual, predicted)
    assert m["n"] == 3
    assert m["mae"] == pytest.approx(4 / 3)
    assert m["rmse"] == pytest.approx(np.sqrt(10 / 3))
    assert m["bias"] == pytest.approx(-2 / 3)


def _table(candidate_error: float, baseline_error: float) -> pd.DataFrame:
    rows = []
    for origin in pd.date_range("2026-07-01", periods=17, freq="7D"):
        for h in ("HSP-001", "HSP-002"):
            for g in ("O+", "O-"):
                rows.append((origin, h, g, 5.0, 5.0 + baseline_error, 5.0 + candidate_error))
    return pd.DataFrame(
        rows, columns=["origin", "facility_id", "blood_group", "actual", "baseline", "candidate"]
    )


def test_summary_marks_a_better_candidate_and_reports_both_models():
    metrics = summarise(_table(candidate_error=1.0, baseline_error=2.0))
    assert metrics["candidate_wins"] is True
    assert metrics["overall"]["candidate"]["rmse"] == pytest.approx(1.0)
    assert metrics["overall"]["baseline"]["rmse"] == pytest.approx(2.0)
    assert metrics["rmse_reduction_pct"] == pytest.approx(50.0)
    assert metrics["observations"]["rows"] == 17 * 4


def test_summary_is_honest_when_the_candidate_loses():
    metrics = summarise(_table(candidate_error=3.0, baseline_error=1.0))
    assert metrics["candidate_wins"] is False
    assert metrics["rmse_reduction_pct"] < 0


def test_paired_bootstrap_is_reproducible_and_signed():
    table = _table(candidate_error=1.0, baseline_error=2.0)
    first = paired_rmse_difference(table, draws=500, seed=1)
    second = paired_rmse_difference(table, draws=500, seed=1)
    assert first == second
    assert first["rmse_difference"] < 0
    assert first["ci95_high"] < 0
