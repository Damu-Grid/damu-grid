"""DG-19 step 1: the ranking settings are validated and have the documented defaults."""

from __future__ import annotations

import dataclasses

import pytest

from ranking.config import RankingConfig


def test_documented_defaults():
    cfg = RankingConfig()
    assert cfg.trip_cost_units == 0.2 and cfg.min_gain_units == 0.10
    assert cfg.max_wait_days == 7 and cfg.cooler_capacity_units == 10
    assert cfg.pool_components == ("RBC", "WB") and cfg.use_routing_matrix is False


def test_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        RankingConfig().trip_cost_units = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "bad",
    [
        {"trip_cost_units": -0.1},
        {"min_gain_units": -1.0},
        {"max_wait_days": -1},
        {"cooler_capacity_units": 0},
        {"lambda_quantiles": (0.9, 0.1)},
        {"lambda_quantiles": (0.0, 0.5)},
        {"pool_components": ()},
    ],
)
def test_invalid_settings_are_refused(bad):
    with pytest.raises(ValueError):
        RankingConfig(**bad)
