"""DG-19 step 3: demand model (no look-ahead) and the survival score of a stock table."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from forecasting.config import CONFIG
from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.queue import fefo_use_probabilities
from ranking.score import survival_scores

ORIGIN = date(2026, 2, 16)  # a Monday, 107 days after the data start
FACILITIES = pd.DataFrame(
    {
        "facility_id": ["HSP-A", "HSP-B", "RBTC-X"],
        "facility_type": ["county_hospital", "mission_hospital", "regional_blood_centre"],
    }
)


def _requests(seed: int = 1, days: int = 130, sunday_quiet: bool = False) -> pd.DataFrame:
    """Synthetic request table for two hospitals, a blood centre, RBC and platelets."""
    rng = np.random.default_rng(seed)
    rows = []
    for offset in range(days):
        day = CONFIG.data_start + timedelta(days=offset)
        for site in ("HSP-A", "HSP-B", "RBTC-X"):
            for _ in range(0 if (sunday_quiet and day.weekday() == 6) else int(rng.poisson(3))):
                rows.append(
                    (
                        f"R{len(rows):06d}",
                        site,
                        pd.Timestamp(day) + pd.Timedelta(minutes=int(rng.integers(0, 1440))),
                        str(rng.choice(["O+", "A+", "B+", "O-", "unknown"])),
                        str(rng.choice(["RBC", "RBC", "RBC", "PLT"])),
                        int(rng.choice([1, 1, 2, 3, 6])),
                    )
                )
    return pd.DataFrame(
        rows,
        columns=[
            "request_id",
            "facility_id",
            "requested_at",
            "patient_blood_group",
            "component_requested",
            "units_requested",
        ],
    )


@pytest.fixture(scope="module")
def requests_table() -> pd.DataFrame:
    return _requests()


@pytest.fixture(scope="module")
def model(requests_table) -> DemandModel:
    return DemandModel.from_history(requests_table, FACILITIES, ORIGIN)


def test_nothing_after_the_origin_changes_the_model(requests_table, model):
    future = requests_table["requested_at"] >= pd.Timestamp(ORIGIN)
    assert future.any()
    altered = requests_table.copy()
    altered.loc[future, "units_requested"] = 6
    altered.loc[future, "patient_blood_group"] = "AB-"
    altered = pd.concat([altered, altered[future].assign(facility_id="HSP-A")])
    shuffled = altered.sample(frac=1.0, random_state=0)
    assert DemandModel.from_history(shuffled, FACILITIES, ORIGIN) == model
    only_past = requests_table[~future]
    assert DemandModel.from_history(only_past, FACILITIES, ORIGIN) == model


def test_a_request_at_the_origin_midnight_is_not_history(requests_table, model):
    extra = requests_table.iloc[[0]].assign(
        facility_id="HSP-A", requested_at=pd.Timestamp(ORIGIN), units_requested=6,
        patient_blood_group="O+", component_requested="RBC",
    )  # fmt: skip
    again = DemandModel.from_history(pd.concat([requests_table, extra]), FACILITIES, ORIGIN)
    assert again == model


def test_unit_rates_over_seven_days_equal_the_hospital_total(requests_table, model):
    elapsed = (ORIGIN - CONFIG.data_start).days
    past = requests_table[requests_table["requested_at"] < pd.Timestamp(ORIGIN)]
    for site in ("HSP-A", "HSP-B"):
        rows = past[
            (past["facility_id"] == site)
            & (past["component_requested"] == "RBC")
            & (past["patient_blood_group"] != "unknown")
        ]
        expected = 7 * rows["units_requested"].sum() / elapsed
        total = 7 * sum(v for (s, _), v in model.daily_unit_rate.items() if s == site)
        assert total == pytest.approx(expected, rel=1e-9)


def test_only_hospitals_have_rates_and_the_blood_centre_has_none(model):
    assert model.has_site("HSP-A") and model.has_site("HSP-B")
    assert not model.has_site("RBTC-X")
    assert model.request_rates("RBTC-X", "O+", 5).tolist() == [0.0] * 5


def test_size_law_and_mean(model):
    assert len(model.size_pmf) == 6 and sum(model.size_pmf) == pytest.approx(1.0)
    assert model.size_pmf[3] == 0.0 and model.size_pmf[4] == 0.0  # no request of 4 or 5 units
    assert model.mean_request_size == pytest.approx(np.dot(np.arange(1, 7), model.size_pmf))


def test_request_rates_follow_the_weekday_profile_from_the_origin(model):
    rates = model.request_rates("HSP-A", "O+", 14)
    base = model.daily_unit_rate[("HSP-A", "O+")] / model.mean_request_size
    expected = [base * model.weekday_weights[(ORIGIN.weekday() + d) % 7] for d in range(14)]
    assert rates == pytest.approx(expected)
    assert rates[:7] == pytest.approx(rates[7:])


def test_weekday_weights_have_mean_one_and_find_a_quiet_sunday():
    quiet = DemandModel.from_history(_requests(sunday_quiet=True), FACILITIES, ORIGIN)
    assert np.mean(quiet.weekday_weights) == pytest.approx(1.0)
    assert quiet.weekday_weights[6] == 0.0
    assert np.mean(quiet.weekday_weights[:6]) == pytest.approx(7 / 6)  # the others carry the mass


def test_flat_profile_option(requests_table):
    flat = DemandModel.from_history(requests_table, FACILITIES, ORIGIN, weekday_profile=False)
    assert flat.weekday_weights == (1.0,) * 7
    rates = flat.request_rates("HSP-A", "O+", 9)
    assert (rates == rates[0]).all()


def test_rate_interval_factors_bracket_one_and_narrow_with_history(model):
    low, high = model.rate_interval_factors("HSP-A", "O+", (0.1, 0.9))
    assert 0.0 < low < 1.0 < high
    few = DemandModel(ORIGIN, {("S", "O+"): 1.0}, {("S", "O+"): 3}, (1.0,), (1.0,) * 7)
    many = DemandModel(ORIGIN, {("S", "O+"): 1.0}, {("S", "O+"): 3000}, (1.0,), (1.0,) * 7)
    none = DemandModel(ORIGIN, {("S", "O+"): 1.0}, {}, (1.0,), (1.0,) * 7)
    spread = {
        name: m.rate_interval_factors("S", "O+", (0.1, 0.9))
        for name, m in (("few", few), ("many", many), ("none", none))
    }
    assert spread["many"][1] - spread["many"][0] < spread["few"][1] - spread["few"][0]
    assert spread["none"][0] >= 0.0 and spread["none"][1] > spread["few"][1]


def test_no_history_is_refused(requests_table):
    with pytest.raises(ValueError):
        DemandModel.from_history(requests_table, FACILITIES, CONFIG.data_start)


def _stock(rows):
    return pd.DataFrame(
        rows, columns=["unit_id", "facility_id", "blood_group", "component", "expiry_date"]
    )


def test_pooled_queue_keeps_product_type_and_orders_by_expiry(model):
    day = pd.Timestamp(ORIGIN)
    stock = _stock(
        [
            ("U3", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=20)),
            ("U1", "HSP-A", "O+", "WB", day + pd.Timedelta(days=4)),
            ("U2", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=9)),
        ]
    )
    out = survival_scores(stock, model, ORIGIN, RankingConfig())
    assert out["unit_id"].tolist() == ["U3", "U1", "U2"]  # row order of the input kept
    assert out["product_type"].tolist() == ["RBC", "WB", "RBC"]
    assert out["rank"].tolist() == [3, 1, 2]
    assert out["days_left"].tolist() == [21, 5, 10]
    direct = fefo_use_probabilities([5, 10, 21], model.request_rates("HSP-A", "O+", 21),
                                    model.size_pmf)  # fmt: skip
    assert out.set_index("unit_id").loc[["U1", "U2", "U3"], "p"].to_numpy() == pytest.approx(direct)
    assert (out["p_lo"] <= out["p"]).all() and (out["p"] <= out["p_hi"]).all()


def test_whole_blood_occupies_a_place_only_when_it_is_in_the_pool(model):
    day = pd.Timestamp(ORIGIN)
    stock = _stock(
        [
            ("WB1", "HSP-A", "O+", "WB", day + pd.Timedelta(days=2)),
            ("RB1", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=15)),
        ]
    )
    pooled = survival_scores(stock, model, ORIGIN, RankingConfig())
    red_only = survival_scores(stock, model, ORIGIN, RankingConfig(pool_components=("RBC",)))
    assert pooled["p"].notna().all()
    assert np.isnan(red_only.loc[0, "p"]) and red_only.loc[0, "product_type"] == "WB"
    assert red_only.loc[1, "p"] > pooled.loc[1, "p"]  # no whole blood ahead of it in the queue


def test_queues_are_separate_per_site_and_blood_group(model):
    day = pd.Timestamp(ORIGIN)
    one = _stock([("A", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=12))])
    many = _stock(
        [
            ("A", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=12)),
            ("B", "HSP-A", "A+", "RBC", day + pd.Timedelta(days=3)),
            ("C", "HSP-B", "O+", "RBC", day + pd.Timedelta(days=3)),
        ]
    )
    alone = survival_scores(one, model, ORIGIN, RankingConfig())
    together = survival_scores(many, model, ORIGIN, RankingConfig())
    assert together.loc[0, "p"] == pytest.approx(alone.loc[0, "p"], abs=1e-15)
    assert together.loc[0, "rank"] == 1


def test_units_that_cannot_be_scored_stay_nan_and_expired_units_score_zero(model):
    day = pd.Timestamp(ORIGIN)
    stock = _stock(
        [
            ("PLT1", "HSP-A", "O+", "PLT", day + pd.Timedelta(days=3)),  # product outside the pool
            ("NOG", "HSP-A", None, "RBC", day + pd.Timedelta(days=3)),  # no blood group
            ("CTR", "RBTC-X", "O+", "RBC", day + pd.Timedelta(days=3)),  # no demand model
            ("OLD", "HSP-A", "O+", "RBC", day - pd.Timedelta(days=1)),  # already expired
            ("OK", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=3)),
        ]
    )
    out = survival_scores(stock, model, ORIGIN, RankingConfig()).set_index("unit_id")
    assert out.loc[["PLT1", "NOG", "CTR"], "p"].isna().all()
    assert out.loc["OLD", "p"] == 0.0 and np.isnan(out.loc["OLD", "rank"])
    assert out.loc["OK", "rank"] == 1 and out.loc["OK", "p"] > 0.0


def test_scores_use_only_the_demand_model(requests_table):
    day = pd.Timestamp(ORIGIN)
    stock = _stock([("A", "HSP-A", "O+", "RBC", day + pd.Timedelta(days=12))])
    future = requests_table["requested_at"] >= pd.Timestamp(ORIGIN)
    altered = requests_table.copy()
    altered.loc[future, "units_requested"] = 6
    a = survival_scores(stock, DemandModel.from_history(requests_table, FACILITIES, ORIGIN), ORIGIN,
                        RankingConfig())  # fmt: skip
    b = survival_scores(stock, DemandModel.from_history(altered, FACILITIES, ORIGIN), ORIGIN,
                        RankingConfig())  # fmt: skip
    assert a.loc[0, "p"] == b.loc[0, "p"]
