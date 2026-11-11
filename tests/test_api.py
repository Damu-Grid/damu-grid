from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import Suggestion, Uncertainty
from backend.app.services import SuggestionServiceUnavailable


def test_health_is_live() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_snapshot_does_not_invent_counts_when_store_is_missing(tmp_path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "missing.sqlite"))

    response = client.get("/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["data_ready"] is False
    assert body["as_of"] is None
    assert body["table_counts"] is None
    assert body["product_scope"] == {
        "component": "RBC",
        "blood_groups": ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"],
    }


def test_snapshot_counts_tables_from_read_only_processed_store(tmp_path) -> None:
    import sqlite3

    database_path = tmp_path / "processed.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE snapshot_units (unit_id TEXT)")
        connection.executemany("INSERT INTO snapshot_units VALUES (?)", [("u1",), ("u2",)])
    client = TestClient(create_app(database_path=database_path))

    response = client.get("/snapshot")

    assert response.status_code == 200
    assert response.json()["data_ready"] is True
    assert response.json()["table_counts"] == {"snapshot_units": 2}


def test_suggestions_return_explicit_error_when_data_is_not_ready(tmp_path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "missing.sqlite"))

    response = client.get("/suggestions")

    assert response.status_code == 503
    assert response.json()["code"] == "suggestions_not_ready"


def test_suggestion_service_error_is_not_replaced_with_fixture_cards(tmp_path) -> None:
    def unavailable(_policy: str):
        raise SuggestionServiceUnavailable("eligible pipeline output is not connected")

    client = TestClient(
        create_app(database_path=tmp_path / "missing.sqlite", suggestion_provider=unavailable)
    )

    response = client.get("/suggestions?policy=fallback")

    assert response.status_code == 503
    assert response.json()["code"] == "suggestions_not_ready"
    assert "fixture" not in response.text.lower()


def test_fallback_policy_is_marked_in_suggestion_payload(tmp_path) -> None:
    suggestion = Suggestion(
        suggestion_id="sug-fallback",
        as_of="2026-10-31T23:59:59+03:00",
        data_age_hours=None,
        component="RBC",
        blood_group="O+",
        unit_ids=["unit-fallback"],
        from_facility_id="RBTC-test",
        to_facility_id="HSP-test",
        expiry_date="2026-11-15",
        typical_travel_hours=None,
        sender_reserve_units=None,
        sender_stock_after=None,
        recipient_gap_units=None,
        uncertainty=Uncertainty(method="test", label="synthetic test"),
        reason_deterministic="Fallback policy test.",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [suggestion],
        )
    )

    response = client.get("/suggestions?policy=fallback")

    assert response.status_code == 200
    assert response.json()["items"][0]["policy"] == "fallback"
    assert response.json()["items"][0]["fallback"] is True


def test_suggestions_serialize_optional_pipeline_values_as_null(tmp_path) -> None:
    suggestion = Suggestion(
        suggestion_id="sug-test",
        as_of="2026-10-31T23:59:59+03:00",
        data_age_hours=None,
        component="RBC",
        blood_group="O+",
        unit_ids=["unit-test"],
        from_facility_id="RBTC-test",
        to_facility_id="HSP-test",
        expiry_date="2026-11-15",
        typical_travel_hours=None,
        sender_reserve_units=None,
        sender_stock_after=None,
        recipient_gap_units=None,
        uncertainty=Uncertainty(method="not_computed", label="not computed"),
        reason_deterministic="This is a computed test card.",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [suggestion],
        )
    )

    response = client.get("/suggestions")

    assert response.status_code == 200
    body = response.json()["items"][0]
    assert body["send_by"] is None
    assert body["expected_use_if_moved"] is None
    assert body["expected_use_if_stays"] is None
    assert body["survival_score_if_moved"] is None
    assert body["survival_score_if_stays"] is None
    assert body["explanation_source"] == "template"
    assert body["explanation_model"] is None
    assert body["latency_ms"] is None


def test_build_suggestion_populates_send_by_from_expiry_travel_and_buffer() -> None:
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path
    from types import SimpleNamespace

    import pandas as pd

    from backend.app.ranking import SQLiteSuggestionProvider, _send_by_date

    eat = timezone(timedelta(hours=3))
    provider = SQLiteSuggestionProvider(
        database_path=Path("unused.sqlite"),
        as_of=datetime(2026, 11, 1, 12, 0, tzinfo=eat),
    )
    context = {
        "as_of": provider.as_of,
        "facilities": pd.DataFrame(
            [{"facility_id": "RBTC-NBO", "name": "Nairobi Centre"},
             {"facility_id": "HSP-004", "name": "HSP-004"}]
        ),
        "config": SimpleNamespace(arrival_allowance_hours=6.0),
    }
    units = [{
        "unit_id": "U1",
        "facility_id": "RBTC-NBO",
        "component": "RBC",
        "blood_group": "O+",
        "expiry_date": pd.Timestamp("2026-11-15"),
    }]
    settings = {"sender_reserve_units": 2, "remaining_life_min_days": {"RBC": 10}}

    card = provider._build_suggestion(
        context, units, "HSP-004", (0.5, "good"), 5, 3, "expiry_aware", settings
    )
    # 2026-11-15 00:00 minus (0.5 travel + 6 allowance + 240 buffer) hours: the latest safe
    # dispatch date, which caps the survival score's recommended day (DG-19).
    deadline = _send_by_date(pd.Timestamp("2026-11-15"), 0.5, 6.0, 10)
    assert deadline == date(2026, 11, 4)
    assert deadline <= card.expiry_date
    # No survival score can be computed here (no database, blood-centre sender), so send_by is
    # left empty rather than guessed.
    assert card.send_by is None

    unknown_route = provider._build_suggestion(
        context, units, "HSP-004", (None, None), 5, 3, "nearest", settings
    )
    assert unknown_route.send_by is None
