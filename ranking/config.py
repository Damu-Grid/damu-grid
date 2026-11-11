"""All settings of the ranking layer in one frozen object (no magic numbers elsewhere)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankingConfig:
    # Cost of a special trip, in expected units of blood. Not in the data: a team choice to confirm
    # with a blood-service expert.
    trip_cost_units: float = 0.2
    # A batch is only suggested if its net expected gain reaches this many units.
    min_gain_units: float = 0.10
    # Longest wait considered when looking for the best dispatch day.
    max_wait_days: int = 7
    cooler_capacity_units: int = 10
    # Extra cells kept beyond the queue length when truncating the demand distribution.
    cap_extra: int = 6
    # Quantiles of the demand rate used for the score interval.
    lambda_quantiles: tuple[float, float] = (0.1, 0.9)
    # Learn where each patient group's demand lands in unit groups (optional, see the plan, 1.1).
    use_routing_matrix: bool = False
    weekday_profile: bool = True
    # Team decision: red cells and whole blood form one queue for red-cell requests; every unit
    # keeps its product_type. ("RBC",) reproduces the red-cell-only validation figures.
    pool_components: tuple[str, ...] = ("RBC", "WB")
    mc_paths: int = 2000
    seed: int = 20261110
    # A reliability bin with fewer units than this is merged with its neighbour.
    calibration_min_bin: int = 100

    def __post_init__(self) -> None:
        if self.trip_cost_units < 0 or self.min_gain_units < 0:
            raise ValueError("trip_cost_units and min_gain_units must be non-negative")
        if self.max_wait_days < 0 or self.cooler_capacity_units < 1 or self.cap_extra < 1:
            raise ValueError("max_wait_days >= 0, cooler_capacity_units >= 1, cap_extra >= 1")
        lo, hi = self.lambda_quantiles
        if not 0.0 < lo < hi < 1.0:
            raise ValueError("lambda_quantiles must satisfy 0 < low < high < 1")
        if not self.pool_components or self.mc_paths < 1 or self.calibration_min_bin < 1:
            raise ValueError("pool_components, mc_paths and calibration_min_bin must be set")
