import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.audit import AuditStore
from backend.app.explanations import ExplanationService, ExplanationSettings
from backend.app.main import create_app
from backend.app.ranking import SQLiteSuggestionProvider
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
