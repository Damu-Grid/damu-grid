import sqlite3

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import Suggestion, Uncertainty


def suggestion() -> Suggestion:
    return Suggestion(
        suggestion_id="sug-tier2",
        as_of="2026-10-31T23:59:59+03:00",
        data_age_hours=1,
        component="RBC",
        blood_group="A+",
        unit_ids=["unit-tier2"],
        from_facility_id="RBTC-test",
        to_facility_id="HSP-test",
        expiry_date="2026-11-15",
        typical_travel_hours=1,
        sender_reserve_units=2,
        sender_stock_after=3,
        recipient_gap_units=1,
        uncertainty=Uncertainty(method="test", label="synthetic fixture"),
        reason_deterministic="Move a synthetic unit before expiry.",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
    )


def client_for(tmp_path):
    app = create_app(
        database_path=tmp_path / "snapshot.sqlite",
        action_database_path=tmp_path / "actions.sqlite",
        suggestion_provider=lambda _policy: [suggestion()],
        eligibility_check=lambda _suggestion, _connection: True,
    )
    client = TestClient(app)
    client.get("/suggestions")
    return client


def test_settings_are_validated_and_audited(tmp_path) -> None:
    client = client_for(tmp_path)

    default = client.get("/settings").json()
    updated = client.put(
        "/settings",
        json={
            "event_id": "settings-event",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "settings": {"sender_reserve_units": 3},
        },
    )
    invalid = client.put(
        "/settings",
        json={
            "event_id": "invalid-settings-event",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "settings": {"reservation_lease_minutes": 31},
        },
    )

    assert default["settings"]["sender_reserve_units"] == 2
    assert default["settings"]["remaining_life_min_days"]["RBC"] == 10
    assert updated.json()["settings"]["sender_reserve_units"] == 3
    assert invalid.status_code == 422
    audit = client.get("/audit?actor_id=demo-coordinator").json()
    assert any(item["event_type"] == "settings_updated" for item in audit)


def test_alerts_are_simulated_and_reject_contact_fields(tmp_path) -> None:
    client = client_for(tmp_path)
    body = {
        "event_id": "alert-event",
        "actor_id": "demo-coordinator",
        "role": "coordinator",
        "recipient_role": "sender",
        "message": "A synthetic move is ready for review.",
    }

    response = client.post("/alerts/simulate", json=body)
    with_contact = client.post(
        "/alerts/simulate",
        json={**body, "event_id": "alert-event-2", "phone_number": "+254700000000"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "simulated"
    assert with_contact.status_code == 422


def test_sync_reconciles_idempotently_and_exposes_status(tmp_path) -> None:
    client = client_for(tmp_path)
    request = {
        "events": [
            {
                "event_id": "offline-accept",
                "action": "accept",
                "resource_id": "sug-tier2",
                "actor_id": "demo-coordinator",
                "role": "coordinator",
                "payload": {"reason": "offline review", "unit_version": 0},
            }
        ]
    }

    first = client.post("/sync/queue", json=request)
    replay = client.post("/sync/queue", json=request)
    status = client.get("/sync/status?event_ids=offline-accept")

    assert first.json()["items"][0]["status"] == "accepted"
    assert replay.json()["items"][0]["status"] == "accepted"
    assert status.json()["items"][0]["status"] == "accepted"


def test_sync_validation_error_is_rejected_on_reconcile(tmp_path) -> None:
    client = client_for(tmp_path)
    response = client.post(
        "/sync/queue",
        json={
            "events": [
                {
                    "event_id": "offline-invalid-accept",
                    "action": "accept",
                    "resource_id": "sug-tier2",
                    "actor_id": "demo-coordinator",
                    "role": "coordinator",
                    "payload": {},
                }
            ]
        },
    )

    item = response.json()["items"][0]
    assert item["status"] == "rejected_on_reconcile"
    assert item["result"]["code"] == "invalid_pending_action"


def test_sync_database_error_is_retryable_and_stays_pending(tmp_path, monkeypatch) -> None:
    client = client_for(tmp_path)
    store = client.app.state.action_store

    def fail_decision(**_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "decide", fail_decision)
    request = {
        "events": [
            {
                "event_id": "offline-retry-accept",
                "action": "accept",
                "resource_id": "sug-tier2",
                "actor_id": "demo-coordinator",
                "role": "coordinator",
                "payload": {"reason": "offline review", "unit_version": 0},
            }
        ]
    }

    response = client.post("/sync/queue", json=request)
    status = client.get("/sync/status?event_ids=offline-retry-accept")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "sync_temporarily_unavailable"
    assert status.json()["items"][0]["status"] == "pending"


def test_sync_safety_conflict_is_rejected_and_quarantine_stays_blocked(tmp_path) -> None:
    client = client_for(tmp_path)
    accepted = client.post(
        "/suggestions/sug-tier2/accept",
        json={
            "event_id": "accept-first",
            "actor_id": "demo-coordinator",
            "role": "coordinator",
            "reason": "reviewed",
            "unit_version": 0,
        },
    ).json()
    move_id = accepted["move_id"]
    client.post(
        f"/moves/{move_id}/dispatch",
        json={"event_id": "dispatch-first", "actor_id": "demo-sender", "role": "sender"},
    )
    client.post(
        f"/moves/{move_id}/quarantine",
        json={"event_id": "quarantine-first", "actor_id": "demo-safety", "role": "safety"},
    )

    response = client.post(
        "/sync/queue",
        json={
            "events": [
                {
                    "event_id": "offline-dispatch-conflict",
                    "action": "dispatch",
                    "resource_id": move_id,
                    "actor_id": "demo-sender",
                    "role": "sender",
                    "payload": {},
                }
            ]
        },
    )

    item = response.json()["items"][0]
    assert item["status"] == "rejected_on_reconcile"
    assert client.get(f"/moves/{move_id}").json()["status"] == "quarantined"
