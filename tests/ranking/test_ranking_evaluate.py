"""DG-19 step 4: the evaluation harness (shelf reconstruction, outputs, plan health check)."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from forecasting.config import calibration_origins as forecasting_calibration_origins
from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.evaluate import (
    arrived_units,
    calibration_origins,
    evaluate,
    main,
    rank_rule,
    render_markdown,
    shelf_at,
)
from ranking.score import survival_scores


def _units(rows):
    frame = pd.DataFrame(
        rows,
        columns=["unit_id", "component", "blood_group", "current_facility_id", "status",
                 "status_date", "expiry_date"],
    )  # fmt: skip
    for column in ("status_date", "expiry_date"):
        frame[column] = pd.to_datetime(frame[column])
    return frame


def _transfers(rows):
    frame = pd.DataFrame(rows, columns=["unit_id", "dispatched_at", "received_at"])
    for column in ("dispatched_at", "received_at"):
        frame[column] = pd.to_datetime(frame[column])
    return frame


UNITS = _units(
    [
        ("A", "RBC", "O+", "HSP-1", "transfused", "2026-07-10", "2026-08-01"),
        ("B", "RBC", "O+", "HSP-1", "expired", "2026-08-01", "2026-08-01"),
        ("C", "WB", "O+", "HSP-1", "expired", "2026-08-05", "2026-08-05"),
        ("D", "RBC", "A+", "RBTC-1", "transfused", "2026-07-10", "2026-08-01"),  # not a hospital
        ("E", "RBC", None, "HSP-1", "transfused", "2026-07-10", "2026-08-01"),  # no group
        ("F", "RBC", "O+", "HSP-1", "expired", "2026-08-01", "2026-08-01"),  # never moved
    ]
)
TRANSFERS = _transfers(
    [
        ("A", "2026-06-29 08:00", "2026-06-29 15:00"),
        ("B", "2026-07-02 08:00", None),  # receipt unconfirmed: the dispatch day is used
        ("C", "2026-07-03 08:00", "2026-07-03 20:00"),
        ("D", "2026-06-29 08:00", "2026-06-29 15:00"),
        ("E", "2026-06-29 08:00", "2026-06-29 15:00"),
    ]
)


def test_units_appear_on_the_shelf_from_arrival_until_they_leave():
    pool = arrived_units(UNITS, TRANSFERS, {"HSP-1"}, ("RBC", "WB"))
    assert sorted(pool["unit_id"]) == ["A", "B", "C"]  # D, E and F are out of scope
    assert sorted(shelf_at(pool, date(2026, 6, 30))["unit_id"]) == ["A"]  # B, C not there yet
    assert sorted(shelf_at(pool, date(2026, 7, 3))["unit_id"]) == ["A", "B", "C"]
    assert sorted(shelf_at(pool, date(2026, 7, 11))["unit_id"]) == ["B", "C"]  # A used on 10 July
    assert sorted(shelf_at(pool, date(2026, 8, 2))["unit_id"]) == ["C"]  # B expired on 1 August


def test_pool_components_decide_which_products_are_kept():
    only_red = arrived_units(UNITS, TRANSFERS, {"HSP-1"}, ("RBC",))
    assert sorted(only_red["unit_id"]) == ["A", "B"]


def test_rank_rule_matches_the_queue_bound_and_skips_unqueued_rows():
    requests = pd.DataFrame(
        {
            "request_id": ["R1", "R2"],
            "facility_id": ["HSP-1", "HSP-1"],
            "requested_at": pd.to_datetime(["2026-01-05 10:00", "2026-01-06 10:00"]),
            "patient_blood_group": ["O+", "O+"],
            "component_requested": ["RBC", "RBC"],
            "units_requested": [1, 2],
        }
    )
    facilities = pd.DataFrame({"facility_id": ["HSP-1"], "facility_type": ["county_hospital"]})
    origin = date(2026, 2, 1)
    demand = DemandModel.from_history(requests, facilities, origin)
    stock = pd.DataFrame(
        {
            "unit_id": ["X", "Y", "Z"],
            "facility_id": ["HSP-1"] * 3,
            "blood_group": ["O+", "O+", "O+"],
            "component": ["RBC", "RBC", "PLT"],
            "expiry_date": pd.to_datetime(["2026-02-10", "2026-02-20", "2026-02-20"]),
        }
    )
    pooled = RankingConfig(issue_model="pooled")
    scored = survival_scores(stock, demand, origin, pooled, with_interval=False)
    bound = rank_rule(scored, demand, pooled)
    assert bound.iloc[:2].notna().all() and np.isnan(bound.iloc[2])
    assert (bound.iloc[:2] <= scored["p"].iloc[:2] + 1e-12).all()
    assert scored[["p_lo", "p_hi"]].isna().all().all()  # intervals skipped on request


def test_calibration_origins_are_the_teams():
    origins = calibration_origins()
    assert origins == forecasting_calibration_origins()  # one split for the whole project
    assert origins[0] == date(2026, 5, 6) and origins[-1] == date(2026, 6, 24)
    assert len(origins) == 8


@pytest.fixture(scope="module")
def red_cell_run(tmp_path_factory):
    """The plan's health-check configuration, run through the command line entry point."""
    out = tmp_path_factory.mktemp("evaluation")
    assert main(["--pool-components", "RBC", "--flat-weekdays", "--output-dir", str(out)]) == 0
    return json.loads((out / "ranking_evaluation.json").read_text(encoding="utf-8")), out


@pytest.mark.dataset
def test_health_check_reproduces_the_design_figures_for_red_cells(red_cell_run):
    payload, out = red_cell_run
    total = payload["methods"]["total"]
    assert total["n"] == 8865 and total["calibration_n"] == 4710  # the team's 8 May-June origins
    assert total["observed_rate"] == pytest.approx(0.931, abs=0.0005)
    assert total["calibration_observed_rate"] == pytest.approx(0.977, abs=0.0005)
    exact = total["methods"]["exact"]
    assert exact["brier"] == pytest.approx(0.0371, abs=0.003)
    assert exact["auc"] == pytest.approx(0.966, abs=0.005)
    assert exact["log_loss"] == pytest.approx(0.118, abs=0.003)
    assert exact["calibration_gap"] == pytest.approx(0.023, abs=0.003)
    assert total["methods"]["rank_rule"]["brier"] == pytest.approx(0.0413, abs=0.003)
    assert total["methods"]["constant"]["auc"] == 0.5
    assert payload["closing_stock"]["total"]["units"] == 504
    assert payload["closing_stock"]["total"]["expected_expired"] == pytest.approx(17.1, abs=0.1)
    assert set(payload["methods"]) == {"RBC", "total"}
    assert (out / "ranking_evaluation.md").read_text(encoding="utf-8").startswith("# Survival")


@pytest.fixture(scope="module")
def pooled_run():
    """The default configuration: red cells and whole blood in one queue."""
    return evaluate(RankingConfig())


@pytest.mark.dataset
def test_pooled_run_reports_each_product_and_the_total(pooled_run):
    methods = pooled_run["methods"]
    assert set(methods) == {"RBC", "WB", "total"}
    assert methods["total"]["n"] == methods["RBC"]["n"] + methods["WB"]["n"]
    closing = pooled_run["closing_stock"]
    assert closing["total"]["units"] == closing["RBC"]["units"] + closing["WB"]["units"]
    assert closing["total"]["expected_expired"] == pytest.approx(
        closing["RBC"]["expected_expired"] + closing["WB"]["expected_expired"]
    )
    assert set(pooled_run["reliability_exact_test"]) == {"RBC", "WB", "total"}
    text = render_markdown(pooled_run)
    assert "Test window, WB" in text and "Closing stock" in text
    assert "true 85% of the time" in text  # the warning about reading the score is in the report


@pytest.mark.dataset
def test_closing_plan_moves_only_eligible_red_cells_and_matches_its_monte_carlo_check(pooled_run):
    plan = pooled_run["closing_plan"]
    assert plan["eligible_moves"] > 0 and plan["units_planned"] >= plan["units_suggested"]
    assert plan["batches_planned"] >= plan["batches_suggested"] == len(plan["batches"])
    low, high = plan["monte_carlo_interval_95"]
    assert low <= plan["monte_carlo_gain_total"] <= high
    for batch in plan["batches"]:
        assert set(batch["products"]) == {"RBC"}  # only the queue component is ever moved
        assert batch["net_gain"] >= RankingConfig().min_gain_units
        assert abs(batch["model_gain"] - batch["monte_carlo_gain"]) < 0.1


@pytest.mark.dataset
def test_product_preference_is_reported(pooled_run):
    preference = pooled_run["product_preference"]
    assert preference["hospitals"] == 32
    assert 0 < preference["whole_blood_first"] < preference["hospitals"]
    assert "Product used first" in render_markdown(pooled_run)


@pytest.mark.dataset
def test_units_left_out_of_the_history_expire_before_the_first_origin(pooled_run):
    missing = pooled_run["units_without_arrival"]
    assert missing["units"] > 0
    assert date.fromisoformat(missing["latest_expiry"]) < calibration_origins()[0]
    assert pooled_run["config"]["issue_model"] == "by_product"
