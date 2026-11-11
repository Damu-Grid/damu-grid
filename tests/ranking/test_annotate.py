"""DG-19 step 6: batch annotation, its Suggestion update and the SQLite loader."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.app.schemas import Suggestion, Uncertainty
from forecasting.config import PROCESSED_DIR
from ranking.annotate import UNCERTAINTY, annotate_batch, load_annotation_inputs
from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.queue import fefo_use_probabilities

ORIGIN = date(2026, 11, 2)  # a Monday
SIZES = (0.49, 0.28, 0.115, 0.085, 0.0, 0.03)
EAT = timezone(timedelta(hours=3))


def _stock(rows):
    frame = pd.DataFrame(
        rows, columns=["unit_id", "facility_id", "blood_group", "component", "days"]
    )
    frame["expiry_date"] = pd.Timestamp(ORIGIN) + pd.to_timedelta(frame.pop("days") - 1, unit="D")
    return frame


STOCK = _stock(
    [
        ("S1", "H1", "O+", "RBC", 9),
        ("S2", "H1", "O+", "WB", 11),
        ("S3", "H1", "O+", "RBC", 14),
        ("S4", "H1", "O+", "RBC", 15),
        ("S5", "H1", "O+", "RBC", 16),
        ("D1", "H2", "O+", "RBC", 20),
        ("X1", "H2", "A+", "RBC", 3),
        ("X2", "H3", "O+", "RBC", 3),
    ]
)
DEMAND = DemandModel(
    ORIGIN,
    {("H1", "O+"): 0.1, ("H2", "O+"): 1.4, ("H2", "A+"): 0.5},
    {("H2", "O+"): 40},
    SIZES,
    (1.0,) * 7,
)


def _annotate(unit_ids=("S4", "S5"), **kwargs):
    units = STOCK[STOCK["unit_id"].isin(unit_ids)]
    args = dict(travel_hours=2.0, routine_run_days=frozenset(), config=RankingConfig())
    args.update(kwargs)
    return annotate_batch(units, "H2", STOCK, DEMAND, ORIGIN, **args)


def _suggestion(**update) -> Suggestion:
    base = Suggestion(
        suggestion_id="sug-1",
        as_of=datetime(2026, 11, 1, 23, 59, 59, tzinfo=EAT),
        data_age_hours=1.0,
        component="RBC",
        blood_group="O+",
        unit_ids=["S4", "S5"],
        from_facility_id="H1",
        to_facility_id="H2",
        expiry_date=date(2026, 11, 16),
        typical_travel_hours=2.0,
        sender_reserve_units=2,
        sender_stock_after=3,
        recipient_gap_units=4,
        uncertainty=Uncertainty(method="trailing_28_day_request_average", label="x"),
        reason_deterministic="provider text",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
        warnings=["provider warning"],
    )
    return base.model_copy(update=update)


def test_scores_at_the_sender_come_from_the_complete_pooled_queue():
    note = _annotate()
    p = fefo_use_probabilities([9, 11, 14, 15, 16], DEMAND.request_rates("H1", "O+", 16), SIZES)
    assert note.expected_use_if_stays == pytest.approx(p[3] + p[4])
    assert note.survival_score_if_stays == pytest.approx((p[3] + p[4]) / 2)
    lo, hi = note.interval_if_stays
    assert lo <= note.survival_score_if_stays <= hi


def test_a_site_with_demand_scores_higher_and_the_batch_leaves_now():
    note = _annotate()
    assert note.survival_score_if_moved > note.survival_score_if_stays
    assert note.interval_if_moved[0] <= note.survival_score_if_moved <= note.interval_if_moved[1]
    assert note.send_by == ORIGIN and note.net_gain >= RankingConfig().min_gain_units
    assert note.warnings == ("timing_uses_special_trip",)
    assert note.gain_by_day[0] - note.gain_by_day[1] == pytest.approx(note.waiting_cost_per_day)


def test_a_routine_run_day_is_flagged():
    note = _annotate(routine_run_days=frozenset({0}))  # Monday run on the origin day
    assert note.send_by == ORIGIN and note.warnings == ("routine_run_available",)


def test_small_gain_gives_no_send_by():
    note = _annotate(config=RankingConfig(min_gain_units=5.0))
    assert note.send_by is None and note.warnings == ("net_gain_below_minimum",)


def test_send_by_never_passes_the_latest_feasible_day():
    cfg = RankingConfig(trip_cost_units=0.5, max_wait_days=7)
    units = STOCK[STOCK["unit_id"].isin(["S4", "S5"])]
    note = annotate_batch(
        units, "H2", STOCK, DEMAND, ORIGIN, 30.0, frozenset({6}), cfg, min_remaining_days=1
    )
    # transit 2 days + 1 day buffer before the earliest expiry (15 days left -> 15 Nov)
    assert note.latest_feasible == date(2026, 11, 16) - timedelta(days=3)
    assert note.send_by is None or note.send_by <= note.latest_feasible


def test_every_number_in_the_reason_comes_from_a_field_or_a_setting():
    note = _annotate(unit_ids=("S3", "S4", "S5"))
    cfg = RankingConfig()
    text = note.reason
    dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", text))
    allowed_dates = {d.isoformat() for d in (note.send_by, note.latest_feasible, ORIGIN) if d}
    assert dates <= allowed_dates
    numbers = set(re.findall(r"\d+\.\d+|\b\d+\b", re.sub(r"\d{4}-\d{2}-\d{2}", "", text)))
    n = 3
    values = [
        note.expected_use_if_stays,
        note.expected_use_if_moved,
        note.survival_score_if_stays,
        note.survival_score_if_moved,
        *note.interval_if_stays,
        *note.interval_if_moved,
        note.net_gain,
        note.waiting_cost_per_day,
        *note.gain_by_day,
        cfg.trip_cost_units,
        cfg.min_gain_units,
    ]
    allowed = {f"{v:.2f}" for v in values} | {str(n), "1"}  # "1" from site names such as H1
    assert numbers <= allowed, numbers - allowed


def test_the_update_validates_the_suggestion_schema_and_keeps_its_warnings():
    note = _annotate()
    original = _suggestion()
    update = note.as_suggestion_update(original.warnings)
    assert update["uncertainty"] == UNCERTAINTY and update["uncertainty"]["nominal_level"] == 0.8
    validated = Suggestion.model_validate({**original.model_dump(), **update})
    assert validated.send_by == note.send_by
    assert validated.survival_score_if_moved == pytest.approx(note.survival_score_if_moved)
    assert (
        validated.warnings[0] == "provider warning"
        and "timing_uses_special_trip" in validated.warnings
    )
    assert validated.policy == "expiry_aware"  # the policy is not touched
    copied = original.model_copy(
        update={**update, "uncertainty": Uncertainty(**update["uncertainty"])}
    )
    assert copied.uncertainty.method == "fefo_compound_poisson"


def test_bad_batches_are_refused():
    with pytest.raises(ValueError):
        annotate_batch(
            STOCK.iloc[0:0], "H2", STOCK, DEMAND, ORIGIN, 2.0, frozenset(), RankingConfig()
        )
    with pytest.raises(ValueError):
        _annotate(unit_ids=("S4", "X1"))  # two groups / two sites
    with pytest.raises(ValueError):
        annotate_batch(
            STOCK[STOCK["unit_id"] == "S4"],
            "H1",
            STOCK,
            DEMAND,
            ORIGIN,
            2.0,
            frozenset(),
            RankingConfig(),
        )


def test_loader_reads_the_snapshot_requests_and_routine_calendar(tmp_path):
    db = tmp_path / "damu_grid.sqlite"
    as_of = datetime(2026, 1, 31, 23, 59, 59, tzinfo=EAT)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE dg_snapshot_units (as_of TEXT, unit_id TEXT, facility_id TEXT, "
            "component TEXT, blood_group TEXT, expiry_date TEXT)"
        )
        conn.executemany(
            "INSERT INTO dg_snapshot_units VALUES (?, ?, ?, ?, ?, ?)",
            [
                (as_of.isoformat(), "U1", "HSP-1", "RBC", "O+", "2026-02-10"),
                ("2026-01-30T23:59:59+03:00", "OLD", "HSP-1", "RBC", "O+", "2026-02-10"),
            ],
        )
        conn.execute(
            "CREATE TABLE requests (facility_id TEXT, requested_at TEXT, "
            "patient_blood_group TEXT, component_requested TEXT, units_requested INTEGER)"
        )
        conn.executemany(
            "INSERT INTO requests VALUES (?, ?, ?, ?, ?)",
            [
                ("HSP-1", "2026-01-10 10:00:00", "O+", "RBC", 2),
                ("HSP-1", "2026-02-01 10:00:00", "O+", "RBC", 6),
            ],  # after the snapshot: ignored
        )
        conn.execute(
            "CREATE TABLE facilities (facility_id TEXT, facility_type TEXT, "
            "supply_centre_id TEXT, routine_deliveries_per_week REAL)"
        )
        conn.executemany(
            "INSERT INTO facilities VALUES (?, ?, ?, ?)",
            [
                ("RBTC-1", "regional_blood_centre", None, None),
                ("HSP-1", "county_hospital", "RBTC-1", 3.0),
            ],
        )
    inputs = load_annotation_inputs(db, as_of, RankingConfig())
    assert inputs.origin == date(2026, 2, 1)
    assert inputs.stock["unit_id"].tolist() == ["U1"]
    assert inputs.demand.daily_unit_rate[("HSP-1", "O+")] == pytest.approx(2 / 92)
    assert inputs.routine_run_days("RBTC-1", "HSP-1") == frozenset({0, 2, 4})
    with pytest.raises(ValueError):
        load_annotation_inputs(db, datetime(2025, 1, 1, tzinfo=EAT), RankingConfig())


DATABASE = PROCESSED_DIR / "damu_grid.sqlite"


@pytest.mark.dataset
@pytest.mark.skipif(not DATABASE.is_file(), reason="run `uv run python -m pipeline build` first")
def test_annotates_a_real_eligible_batch_from_the_pipeline_database():
    as_of = datetime(2026, 10, 31, 23, 59, 59, tzinfo=EAT)
    inputs = load_annotation_inputs(DATABASE, as_of, RankingConfig())
    red = inputs.stock[
        (inputs.stock["component"] == "RBC")
        & inputs.stock["facility_id"].eq("HSP-025")
        & inputs.stock["blood_group"].eq("O+")
    ].sort_values("expiry_date")
    note = annotate_batch(
        red.tail(2),
        "HSP-003",
        inputs.stock,
        inputs.demand,
        inputs.origin,
        3.84,
        inputs.routine_run_days("HSP-025", "HSP-003"),
        RankingConfig(),
    )
    assert 0.0 <= note.survival_score_if_stays <= 1.0 and 0.0 <= note.survival_score_if_moved <= 1.0
    assert note.send_by is None or inputs.origin <= note.send_by <= note.latest_feasible
