import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.audit import AuditStore
from backend.app.explanations import ExplanationService, ExplanationSettings
from backend.app.main import create_app
from backend.app.ranking import SQLiteSuggestionProvider, clear_ranking_cache
from backend.app.schemas import Suggestion
from backend.app.services import SuggestionServiceUnavailable
from backend.app.state import ActionStore

EAT = timezone(timedelta(hours=3))
AS_OF = datetime(2026, 10, 31, 23, 59, 59, tzinfo=EAT)
AS_OF_TEXT = AS_OF.isoformat(timespec="seconds")


def build_snapshot(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE facilities (
                facility_id TEXT, name TEXT, facility_type TEXT
            );
            CREATE TABLE routes (
                from_facility_id TEXT, to_facility_id TEXT,
                typical_travel_hours REAL, road_quality TEXT
            );
            CREATE TABLE requests (
                facility_id TEXT, requested_at TEXT, patient_blood_group TEXT,
                units_requested INTEGER, component_requested TEXT
            );
            CREATE TABLE dg_snapshot_meta (as_of TEXT);
            CREATE TABLE dg_snapshot_units (
                as_of TEXT, unit_id TEXT, facility_id TEXT, component TEXT, blood_group TEXT,
                expiry_date TEXT, status TEXT, temp_excursion_exposed INTEGER,
                receipt_status TEXT
            );
            CREATE TABLE dg_cold_chain_flags (
                flag_type TEXT, scope TEXT, unit_id TEXT, blocks_suggestion INTEGER
            );
            CREATE TABLE units (
                unit_id TEXT, current_facility_id TEXT, blood_group TEXT, component TEXT,
                expiry_date TEXT, status TEXT, temp_excursion_exposed TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO facilities VALUES (?, ?, ?)",
            [
                ("RBTC-001", "Synthetic Centre", "regional_blood_centre"),
                ("HSP-001", "Synthetic Hospital", "county_hospital"),
            ],
        )
        connection.execute(
            "INSERT INTO routes VALUES (?, ?, ?, ?)",
            ("RBTC-001", "HSP-001", 2.0, "good"),
        )
        connection.execute(
            "INSERT INTO requests VALUES (?, ?, ?, ?, ?)",
            ("HSP-001", "2026-10-10 12:00:00", "O+", 28, "RBC"),
        )
        connection.execute("INSERT INTO dg_snapshot_meta VALUES (?)", (AS_OF_TEXT,))
        eligible_rows = [
            (f"U{i}", "O+", "2026-12-01", "never_moved", 0) for i in range(4)
        ]
        excluded_rows = [
            ("exposed", "O+", "2026-12-01", "never_moved", 1),
            ("unknown", "unknown", "2026-12-01", "never_moved", 0),
            ("expired", "O+", "2026-10-30", "never_moved", 0),
            ("unconfirmed", "O+", "2026-12-01", "unconfirmed", 0),
            ("flagged", "O+", "2026-12-01", "never_moved", 0),
        ]
        connection.executemany(
            "INSERT INTO dg_snapshot_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    AS_OF_TEXT,
                    unit_id,
                    "RBTC-001",
                    "RBC",
                    group,
                    expiry,
                    "in_stock",
                    exposed,
                    receipt,
                )
                for unit_id, group, expiry, receipt, exposed in eligible_rows + excluded_rows
            ],
        )
        connection.execute(
            "INSERT INTO dg_cold_chain_flags VALUES (?, ?, ?, ?)",
            ("fridge_excursion", "unit", "flagged", 1),
        )
        connection.executemany(
            "INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("late-receipt", "RBTC-001", "O+", "RBC", "2026-12-01", "in_stock", "False"),
                ("not-in-snapshot", "RBTC-001", "O+", "RBC", "2026-12-01", "in_stock", "False"),
            ],
        )


def disabled_explainer(path) -> ExplanationService:
    return ExplanationService(
        ExplanationSettings(enabled=False),
        AuditStore(path),
    )


def test_provider_uses_pipeline_eligibility_and_preserves_sender_reserve(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    provider = SQLiteSuggestionProvider(database_path, AS_OF)
    settings = ActionStore.DEFAULT_SETTINGS

    suggestions = provider.suggest("expiry_aware", settings, set())

    assert len(suggestions) == 2
    assert {suggestion.unit_ids[0] for suggestion in suggestions} == {"U0", "U1"}
    assert all(suggestion.to_facility_id == "HSP-001" for suggestion in suggestions)
    assert all(
        suggestion.sender_stock_after >= settings["sender_reserve_units"]
        for suggestion in suggestions
    )
    assert all(suggestion.recipient_gap_units > 0 for suggestion in suggestions)
    assert all(suggestion.fallback is False for suggestion in suggestions)
    assert not {"late-receipt", "not-in-snapshot"}.intersection(
        unit_id for suggestion in suggestions for unit_id in suggestion.unit_ids
    )


def test_provider_uses_nearest_order_and_excludes_reserved_units(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    provider = SQLiteSuggestionProvider(database_path, AS_OF)

    suggestions = provider.suggest("fallback", ActionStore.DEFAULT_SETTINGS, {"U0"})

    assert len(suggestions) == 1
    assert suggestions[0].unit_ids == ["U1"]
    assert suggestions[0].policy == "fallback"


def test_provider_rejects_snapshot_with_a_different_as_of(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    provider = SQLiteSuggestionProvider(
        database_path, datetime(2026, 10, 30, 23, 59, 59, tzinfo=EAT)
    )

    try:
        provider.suggest("expiry_aware", ActionStore.DEFAULT_SETTINGS, set())
    except SuggestionServiceUnavailable as exc:
        assert "does not match AS_OF_DATE" in str(exc)
    else:
        raise AssertionError("a mismatched pipeline snapshot must not be used")


def test_provider_rejects_suggestion_fields_that_do_not_match_snapshot_units(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    provider = SQLiteSuggestionProvider(database_path, AS_OF)
    suggestion = provider.suggest("expiry_aware", ActionStore.DEFAULT_SETTINGS, set())[0]

    mismatched = suggestion.model_copy(update={"from_facility_id": "HSP-001"})

    assert not provider.is_eligible(mismatched, ActionStore.DEFAULT_SETTINGS, set())


def test_default_api_provider_returns_suggestions_and_completes_review_flow(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    action_database_path = tmp_path / "actions.sqlite"
    build_snapshot(database_path)
    client = TestClient(
        create_app(
            database_path=database_path,
            action_database_path=action_database_path,
            explanation_service=disabled_explainer(tmp_path / "audit.sqlite"),
        )
    )

    response = client.get("/suggestions")

    assert response.status_code == 200
    suggestion = response.json()["items"][0]
    assert suggestion["unit_ids"]
    assert suggestion["explanation_source"] == "template"

    accepted = client.post(
        f"/suggestions/{suggestion['suggestion_id']}/accept",
        json={
            "event_id": "accept-1",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "reason": "Synthetic review",
            "unit_version": suggestion["unit_version"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "reserved"

    refreshed = client.get("/suggestions")
    assert refreshed.status_code == 200
    assert len(refreshed.json()["items"]) == 1
    assert refreshed.json()["items"][0]["recipient_gap_units"] == 6

    dispatched = client.post(
        f"/moves/{accepted.json()['move_id']}/dispatch",
        json={
            "event_id": "dispatch-1",
            "actor_id": "demo-sender",
            "role": "sender",
            "reason": "Synthetic dispatch check",
        },
    )
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "in_transit"


def test_default_provider_stays_explicitly_unavailable_without_a_snapshot(tmp_path):
    client = TestClient(
        create_app(
            database_path=tmp_path / "missing.sqlite",
            action_database_path=tmp_path / "actions.sqlite",
            explanation_service=disabled_explainer(tmp_path / "audit.sqlite"),
        )
    )

    response = client.get("/suggestions")

    assert response.status_code == 503
    assert response.json()["code"] == "suggestions_not_ready"


def test_default_provider_supports_changed_destination_and_unit_selection(tmp_path):
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    client = TestClient(
        create_app(
            database_path=database_path,
            action_database_path=tmp_path / "actions.sqlite",
            explanation_service=disabled_explainer(tmp_path / "audit.sqlite"),
        )
    )
    suggestion = client.get("/suggestions").json()["items"][0]
    accepted = client.post(
        f"/suggestions/{suggestion['suggestion_id']}/accept",
        json={
            "event_id": "accept-before-change",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "reason": "Synthetic review",
            "unit_version": suggestion["unit_version"],
        },
    )
    assert accepted.status_code == 200

    changed = client.post(
        f"/suggestions/{suggestion['suggestion_id']}/change",
        json={
            "event_id": "change-selection",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "reason": "Synthetic review change",
            "unit_version": suggestion["unit_version"],
            "unit_ids": ["U1"],
            "to_facility_id": "HSP-001",
        },
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "suggested"
    assert changed.json()["suggestion"]["unit_ids"] == ["U1"]
    assert changed.json()["suggestion"]["to_facility_id"] == "HSP-001"


SURVIVAL_FIELDS = (
    "expected_use_if_stays",
    "expected_use_if_moved",
    "survival_score_if_stays",
    "survival_score_if_moved",
)


def build_scored_snapshot(path) -> None:
    """A snapshot with a full year of request and unit history, so a score can be computed.

    HSP-A (sender) has little demand and six eligible O+ red cells plus one exposed unit;
    HSP-B (recipient) asks for three units a day. RBTC-X, a blood centre, also holds eligible
    units: the centre has no demand model, so its suggestions cannot be scored.
    """
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE facilities (
                facility_id TEXT, name TEXT, facility_type TEXT, supply_centre_id TEXT,
                routine_deliveries_per_week REAL
            );
            CREATE TABLE routes (
                from_facility_id TEXT, to_facility_id TEXT,
                typical_travel_hours REAL, road_quality TEXT
            );
            CREATE TABLE requests (
                facility_id TEXT, requested_at TEXT, patient_blood_group TEXT,
                units_requested INTEGER, component_requested TEXT
            );
            CREATE TABLE dg_snapshot_meta (as_of TEXT);
            CREATE TABLE dg_snapshot_units (
                as_of TEXT, unit_id TEXT, facility_id TEXT, component TEXT, blood_group TEXT,
                expiry_date TEXT, status TEXT, temp_excursion_exposed INTEGER,
                receipt_status TEXT
            );
            CREATE TABLE dg_cold_chain_flags (
                flag_type TEXT, scope TEXT, unit_id TEXT, blocks_suggestion INTEGER
            );
            CREATE TABLE units (
                unit_id TEXT, component TEXT, current_facility_id TEXT, status TEXT,
                status_date TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO facilities VALUES (?, ?, ?, ?, ?)",
            [
                ("RBTC-X", "Synthetic Centre", "regional_blood_centre", None, None),
                ("HSP-A", "Synthetic Sender", "county_hospital", "RBTC-X", 3.0),
                ("HSP-B", "Synthetic Recipient", "county_hospital", "RBTC-X", 3.0),
            ],
        )
        connection.executemany(
            "INSERT INTO routes VALUES (?, ?, ?, ?)",
            [("HSP-A", "HSP-B", 2.0, "good"), ("RBTC-X", "HSP-B", 3.0, "good")],
        )
        start = datetime(2025, 11, 1, 10, 0, 0)
        requests = []
        for day in range(365):
            stamp = (start + timedelta(days=day)).strftime("%Y-%m-%d %H:%M:%S")
            requests.append(("HSP-B", stamp, "O+", 3, "RBC"))
            if day % 7 == 0:
                requests.append(("HSP-A", stamp, "O+", 1, "RBC"))
        connection.executemany("INSERT INTO requests VALUES (?, ?, ?, ?, ?)", requests)
        connection.execute("INSERT INTO dg_snapshot_meta VALUES (?)", (AS_OF_TEXT,))
        shelf = [(f"A{i}", "HSP-A", f"2026-11-{20 + i}", 0) for i in range(6)]
        shelf += [("A-exposed", "HSP-A", "2026-11-28", 1)]
        shelf += [(f"C{i}", "RBTC-X", f"2026-11-{24 + i}", 0) for i in range(4)]
        connection.executemany(
            "INSERT INTO dg_snapshot_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (AS_OF_TEXT, unit, site, "RBC", "O+", expiry, "in_stock", exposed, "never_moved")
                for unit, site, expiry, exposed in shelf
            ],
        )
        history = [(f"H{i}", "RBC", "HSP-B", "transfused", "2026-06-01") for i in range(30)]
        history += [(f"W{i}", "WB", "HSP-B", "transfused", "2026-06-01") for i in range(3)]
        history += [(f"S{i}", "RBC", "HSP-A", "transfused", "2026-06-01") for i in range(5)]
        connection.executemany("INSERT INTO units VALUES (?, ?, ?, ?, ?)", history)


def _moves(suggestions):
    return [(s.unit_ids, s.from_facility_id, s.to_facility_id, s.policy) for s in suggestions]


def test_survival_fields_stay_empty_when_no_score_can_be_computed(tmp_path):
    # the provider's minimal snapshot has no unit history and a blood-centre sender
    database_path = tmp_path / "snapshot.sqlite"
    build_snapshot(database_path)
    provider = SQLiteSuggestionProvider(database_path, AS_OF)

    suggestions = provider.suggest("expiry_aware", ActionStore.DEFAULT_SETTINGS, set())

    assert {s.unit_ids[0] for s in suggestions} == {"U0", "U1"}  # eligibility decided
    for suggestion in suggestions:
        assert all(getattr(suggestion, field) is None for field in SURVIVAL_FIELDS)
        # send_by stays the provider's latest safe dispatch date (DG-17), not a guessed day:
        # 2026-12-01 00:00 minus (2 h travel + 6 h allowance + 10 days)
        assert suggestion.send_by == date(2026, 11, 20)
        assert suggestion.uncertainty.method == "trailing_28_day_request_average"
        assert "fefo" not in suggestion.reason_deterministic


def test_survival_fields_are_filled_when_a_score_can_be_computed(tmp_path, monkeypatch):
    database_path = tmp_path / "scored.sqlite"
    build_scored_snapshot(database_path)
    settings = ActionStore.DEFAULT_SETTINGS
    scored = SQLiteSuggestionProvider(database_path, AS_OF).suggest("expiry_aware", settings, set())

    def unavailable(*args, **kwargs):
        raise ValueError("ranking disabled for the comparison")

    monkeypatch.setattr("backend.app.ranking.load_annotation_inputs", unavailable)
    clear_ranking_cache()
    plain = SQLiteSuggestionProvider(database_path, AS_OF).suggest("expiry_aware", settings, set())

    # the score never adds, drops or reorders what eligibility allowed
    assert _moves(scored) == _moves(plain) and scored
    deadlines = {s.suggestion_id: s.send_by for s in plain}
    assert "A-exposed" not in {unit for s in scored for unit in s.unit_ids}
    hospital = [s for s in scored if s.from_facility_id == "HSP-A"]
    centre = [s for s in scored if s.from_facility_id == "RBTC-X"]
    assert hospital and centre
    for suggestion in hospital:
        assert 0.0 <= suggestion.survival_score_if_stays <= 1.0
        assert 0.0 <= suggestion.survival_score_if_moved <= 1.0
        assert suggestion.survival_score_if_moved > suggestion.survival_score_if_stays
        assert suggestion.expected_use_if_moved == pytest.approx(
            suggestion.survival_score_if_moved * len(suggestion.unit_ids)
        )
        assert suggestion.uncertainty.method == "fefo_compound_poisson"
        assert suggestion.uncertainty.nominal_level == 0.8
        assert suggestion.reason_deterministic.startswith("1 eligible RBC unit(s)")
        assert suggestion.warnings[0].startswith("Synthetic request history")
        deadline = deadlines[suggestion.suggestion_id]  # DG-17 latest safe dispatch date
        assert AS_OF.date() < suggestion.send_by <= deadline  # never after the safe deadline
        if "net_gain_below_minimum" in suggestion.warnings:
            assert suggestion.send_by == deadline  # no recommended day: the deadline is kept
        Suggestion.model_validate(suggestion.model_dump())
    assert any("timing_uses_special_trip" in s.warnings for s in hospital)
    for suggestion in centre:  # no demand model for a blood centre: nothing is guessed
        assert all(getattr(suggestion, field) is None for field in SURVIVAL_FIELDS)
        assert suggestion.send_by == deadlines[suggestion.suggestion_id]
        assert suggestion.uncertainty.method == "trailing_28_day_request_average"
    for suggestion in plain:
        assert all(getattr(suggestion, field) is None for field in SURVIVAL_FIELDS)
    clear_ranking_cache()


def test_survival_inputs_are_reloaded_when_the_database_changes(tmp_path):
    database_path = tmp_path / "scored.sqlite"
    build_scored_snapshot(database_path)
    settings = ActionStore.DEFAULT_SETTINGS
    first = SQLiteSuggestionProvider(database_path, AS_OF).suggest("expiry_aware", settings, set())
    again = SQLiteSuggestionProvider(database_path, AS_OF).suggest("expiry_aware", settings, set())

    def fields(items):  # data_age_hours follows the clock, everything else must be identical
        return [s.model_dump(exclude={"data_age_hours"}) for s in items]

    assert fields(again) == fields(first)  # served from the cache
    with sqlite3.connect(database_path) as connection:  # the pipeline rebuilds the snapshot
        connection.execute("DELETE FROM units")
    os.utime(database_path, ns=(1, database_path.stat().st_mtime_ns + 10**9))
    rebuilt = SQLiteSuggestionProvider(database_path, AS_OF).suggest(
        "expiry_aware", settings, set()
    )
    assert _moves(rebuilt) == _moves(first)
    # without unit history the product shares are unknown, so nothing is guessed any more
    assert all(s.survival_score_if_stays is None for s in rebuilt)
    clear_ranking_cache()
