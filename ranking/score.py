"""Survival score of every unit of a stock table."""

from __future__ import annotations

from datetime import date

import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel


def survival_scores(
    stock: pd.DataFrame, demand: DemandModel, origin: date, config: RankingConfig
) -> pd.DataFrame:
    """Add p, p_lo, p_hi, rank and days_left to a stock table.

    `stock` has unit_id, facility_id, blood_group, component (the product_type, RBC or WB) and
    expiry_date (the snapshot units of pipeline.snapshot). One queue per (facility_id,
    blood_group) holding the products of config.pool_components ordered by expiry; the queue holds
    every unit on the shelf, eligible or not, because an excluded unit still occupies a place. The
    product_type column is kept on every row so results can be reported per product. p_lo and p_hi
    are the score at the config.lambda_quantiles of the demand rate. Step 3.
    """
    raise NotImplementedError("DG-19 step 3")
