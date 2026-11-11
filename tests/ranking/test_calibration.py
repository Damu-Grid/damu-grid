"""DG-19 step 4: scoring rules, reliability table and isotonic fit on known values."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ranking.calibration import (
    auc,
    brier,
    calibration_gap,
    isotonic_apply,
    isotonic_fit,
    log_loss,
    reliability_table,
)


def test_brier_and_log_loss_known_values():
    p, y = np.array([0.9, 0.1]), np.array([1, 0])
    assert brier(p, y) == pytest.approx(0.01)
    assert log_loss(p, y) == pytest.approx(-math.log(0.9))
    assert log_loss(np.array([0.0, 1.0]), np.array([1, 0])) == pytest.approx(-math.log(1e-6))


def test_auc_textbook_example_ties_and_one_class():
    assert auc(np.array([0.1, 0.4, 0.35, 0.8]), np.array([0, 0, 1, 1])) == pytest.approx(0.75)
    assert auc(np.full(6, 0.3), np.array([0, 1, 0, 1, 1, 0])) == pytest.approx(0.5)
    assert auc(np.array([0.2, 0.9]), np.array([0, 1])) == 1.0
    assert math.isnan(auc(np.array([0.2, 0.9]), np.array([1, 1])))


def test_auc_matches_pair_counting_with_ties():
    rng = np.random.default_rng(3)
    p = np.round(rng.random(300), 1)  # many ties
    y = (rng.random(300) < p).astype(float)
    pos, neg = p[y == 1], p[y == 0]
    wins = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    assert auc(p, y) == pytest.approx(wins / (len(pos) * len(neg)))


def test_inputs_are_checked():
    for bad in ((np.array([0.5]), np.array([1, 0])), (np.array([]), np.array([]))):
        with pytest.raises(ValueError):
            brier(*bad)


def test_calibration_gap_is_zero_when_each_bin_is_calibrated():
    p = np.full(4, 0.25)
    assert calibration_gap(p, np.array([1, 0, 0, 0])) == pytest.approx(0.0)
    assert calibration_gap(p, np.array([0, 0, 0, 0])) == pytest.approx(0.25)


def test_reliability_table_keeps_every_unit_and_the_mean_score():
    rng = np.random.default_rng(1)
    p = rng.random(2000) ** 0.3
    y = (rng.random(2000) < p).astype(float)
    table = reliability_table(p, y, min_bin=50)
    assert table["n"].sum() == 2000
    assert (table["n"] * table["announced"]).sum() / 2000 == pytest.approx(p.mean())
    assert (table["n"] * table["observed"]).sum() / 2000 == pytest.approx(y.mean())
    assert (table["n"] >= 50).all()
    assert (table["p_low"] <= table["p_high"]).all() and table["p_high"].is_monotonic_increasing


def test_small_bins_merge_into_their_neighbour_and_one_bin_can_remain():
    p = np.array([0.05] * 150 + [0.15] * 10 + [0.25] * 140 + [0.95] * 300)
    y = np.zeros(p.size)
    table = reliability_table(p, y, min_bin=100)
    assert table["n"].tolist() == [150, 150, 300]  # the 10 units of 0.15 joined the smaller bin
    assert table["p_low"].tolist()[1] == pytest.approx(0.15)
    assert len(reliability_table(p[:30], y[:30], min_bin=100)) == 1
    assert len(reliability_table(p, y, min_bin=1)) == 4


def test_probability_one_falls_in_the_last_decile():
    table = reliability_table(np.array([1.0, 1.0, 0.0]), np.array([1, 1, 0]), min_bin=1)
    assert table["n"].tolist() == [1, 2]


def test_isotonic_pools_adjacent_violators():
    thresholds, values = isotonic_fit(np.array([0.1, 0.2, 0.3, 0.4]), np.array([0, 1, 0, 1]))
    assert thresholds == pytest.approx([0.1, 0.25, 0.4])
    assert values == pytest.approx([0.0, 0.5, 1.0])
    assert isotonic_apply(thresholds, values, np.array([0.25, 0.0, 0.9])) == pytest.approx(
        [0.5, 0.0, 1.0]
    )


def test_isotonic_fit_is_non_decreasing_and_keeps_the_outcome_mean():
    rng = np.random.default_rng(5)
    p = rng.random(500)
    y = (rng.random(500) < 0.8 * p + 0.1).astype(float)
    thresholds, values = isotonic_fit(p, y)
    assert (np.diff(values) > 0).all() and (np.diff(thresholds) >= 0).all()
    assert isotonic_apply(thresholds, values, p).mean() == pytest.approx(y.mean(), abs=0.02)
