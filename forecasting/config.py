"""Frozen specification for the demand forecast evaluation (issues DG-09 to DG-14).

Everything that defines the experiment lives here and is committed BEFORE any evaluation
result is computed in this repository, so the git history shows the specification was fixed
first. Do not tune these values after looking at July to October scores (docs/EVALUATION.md).

Disclosure: the author of this module explored a similar demand-forecasting split on the same
starter data earlier on 9 to 10 November, before the build window, using throwaway code that is
not part of this repository. The formulas below are the team's written specification in
docs/EVALUATION.md, not values chosen to flatter the candidate, but a reader should know that
the author had seen comparable numbers before.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# docs/DATA.md: the seven hospital classes (32 sites). Blood centres are not demand sites.
HOSPITAL_FACILITY_TYPES = (
    "county_referral",
    "county_hospital",
    "national_referral",
    "private_hospital",
    "maternity_hospital",
    "mission_hospital",
    "sub_county_hospital",
)

# Known exact ABO/RhD groups only. "unknown" and missing stay out of the slice.
KNOWN_GROUPS = ("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-")


@dataclass(frozen=True)
class ForecastConfig:
    """Frozen experiment configuration."""

    # Data slice
    component: str = "RBC"
    quantity_column: str = "units_requested"  # never units_issued (shortages constrain issues)

    # Forecast target
    horizon_days: int = 7

    # Mandatory baseline: 7 x (requested units in the preceding 28 calendar days / 28)
    baseline_window_days: int = 28

    # Time split. All dates are calendar days in East Africa Time.
    data_start: date = date(2025, 11, 1)
    learn_end: date = date(2026, 4, 30)  # estimator specification learned on data up to here
    calibration_start: date = date(2026, 5, 1)
    calibration_end: date = date(2026, 6, 30)
    first_origin: date = date(2026, 7, 1)
    last_origin: date = date(2026, 10, 21)  # outcomes then end 27 October, inside the data
    origin_step_days: int = 7

    # Completeness assumption (docs/EVALUATION.md): requests.csv is treated as the complete
    # request record for every hospital, so a missing hospital x group x day is zero demand.
    assume_complete_requests: bool = True

    # Residual upper bound (DG-13): scaled split-conformal style bound, calibrated on
    # May to June origins, then checked for coverage on the July to October origins.
    upper_bound_level: float = 0.90
    upper_bound_scale_offset: float = 1.0  # score = (actual - pred) / sqrt(pred + offset)


CONFIG = ForecastConfig()


def evaluation_origins(config: ForecastConfig = CONFIG) -> list[date]:
    """Weekly forecast origins for the frozen evaluation window (inclusive of both ends)."""
    origins: list[date] = []
    current = config.first_origin
    while current <= config.last_origin:
        origins.append(current)
        current += timedelta(days=config.origin_step_days)
    return origins


def calibration_origins(config: ForecastConfig = CONFIG) -> list[date]:
    """Weekly origins in May to June whose 7-day outcomes all end by 30 June.

    They are the evaluation origins stepped back whole weeks from the first evaluation origin,
    so calibration and evaluation fall on the same weekday.
    """
    origins: list[date] = []
    current = config.first_origin - timedelta(days=config.origin_step_days)
    while current >= config.calibration_start:
        outcome_end = current + timedelta(days=config.horizon_days - 1)
        if outcome_end <= config.calibration_end:
            origins.append(current)
        current -= timedelta(days=config.origin_step_days)
    return sorted(origins)
