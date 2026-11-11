"""Survival score of every unit of a stock table."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.queue import fefo_use_probabilities

SCORE_COLUMNS = ["product_type", "days_left", "rank", "p", "p_lo", "p_hi"]


def survival_scores(
    stock: pd.DataFrame,
    demand: DemandModel,
    origin: date,
    config: RankingConfig,
    *,
    with_interval: bool = True,
) -> pd.DataFrame:
    """Add p, p_lo, p_hi, rank and days_left to a stock table.

    `stock` has unit_id, facility_id, blood_group, component (the product_type, RBC or WB) and
    expiry_date (the snapshot units of pipeline.snapshot). One queue per (facility_id,
    blood_group) holding the products of config.pool_components ordered by expiry; the queue holds
    every unit on the shelf, eligible or not, because an excluded unit still occupies a place. The
    product_type column is kept on every row so results can be reported per product. p_lo and p_hi
    are the score at the config.lambda_quantiles of the demand rate.

    `days_left` is the number of days a unit can still be issued, today included
    (expiry_date - origin + 1); a unit already expired is scored 0 and leaves the queue. Rows
    that cannot be scored (a product outside the pool, no blood group, a site with no demand
    model) keep NaN in p, p_lo, p_hi and rank. Row order and index are those of `stock`.
    `with_interval=False` skips p_lo and p_hi (left NaN), which saves two thirds of the time when
    only the score itself is needed, as in the historical evaluation.
    """
    result = stock.copy()
    result["product_type"] = result["component"]
    expiry = pd.to_datetime(result["expiry_date"]).dt.normalize()
    result["days_left"] = (expiry - pd.Timestamp(origin)).dt.days + 1
    for column in ("rank", "p", "p_lo", "p_hi"):
        result[column] = np.nan

    pooled = result["component"].isin(config.pool_components) & result["blood_group"].notna()
    sites = {site for site in result.loc[pooled, "facility_id"].unique() if demand.has_site(site)}
    scorable = result[pooled & result["facility_id"].isin(sites)].assign(_expiry=expiry)
    for (site, group), queue in scorable.groupby(["facility_id", "blood_group"], sort=False):
        _score_queue(result, queue, demand, site, group, config, with_interval)
    return result[list(stock.columns) + [c for c in SCORE_COLUMNS if c not in stock.columns]]


def _score_queue(
    result: pd.DataFrame,
    queue: pd.DataFrame,
    demand: DemandModel,
    site: str,
    group: str,
    config: RankingConfig,
    with_interval: bool,
) -> None:
    """Fill rank, p, p_lo and p_hi of one (site, group) queue inside `result`."""
    expired = queue["days_left"] < 1
    result.loc[queue.index[expired], ["p", "p_lo", "p_hi"]] = 0.0
    live = queue[~expired].sort_values(["_expiry", "unit_id"], kind="stable")
    if live.empty:
        return
    left = live["days_left"].to_numpy(dtype=int)
    rates = demand.request_rates(site, group, int(left.max()))
    pmf = demand.size_pmf
    result.loc[live.index, "rank"] = np.arange(1, len(live) + 1)
    result.loc[live.index, "p"] = fefo_use_probabilities(left, rates, pmf, config.cap_extra)
    if not with_interval:
        return
    low, high = demand.rate_interval_factors(site, group, config.lambda_quantiles)
    result.loc[live.index, "p_lo"] = fefo_use_probabilities(
        left, rates * low, pmf, config.cap_extra
    )
    result.loc[live.index, "p_hi"] = fefo_use_probabilities(
        left, rates * high, pmf, config.cap_extra
    )
