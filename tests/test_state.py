import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import Suggestion, Uncertainty
from backend.app.state import ActionStore


def card(unit_ids: list[str] | None = None) -> Suggestion:
    return Suggestion(
        suggestion_id="sug-state",
        as_of="2026-10-31T23:59:59+03:00",
        data_age_hours=1.0,
        component="RBC",
        blood_group="O+",
        unit_ids=unit_ids or ["unit-a"],
        from_facility_id="RBTC-test",
        to_facility_id="HSP-test",
        expiry_date="2026-11-15",
        typical_travel_hours=1.0,
        sender_reserve_units=2,
        sender_stock_after=4,
        recipient_gap_units=1,
        uncertainty=Uncertainty(method="test", label="synthetic fixture"),
        reason_deterministic="Move one test unit before expiry.",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
    )


def make_client(tmp_path, *, checker=lambda _suggestion, _connection: True, changer=None):
    app = create_app(
        database_path=tmp_path / "snapshot.sqlite",
        action_database_path=tmp_path / "actions.sqlite",
        suggestion_provider=lambda _policy: [card()],
        eligibility_check=checker,
        change_suggestion=changer,
    )
    client = TestClient(app)
    assert client.get("/suggestions").status_code == 200
    return client


def decision(event_id: str, *, role: str = "coordinator", version: int = 0) -> dict:
    return {
        "event_id": event_id,
        "actor_id": "demo-coordinator",
        "role": role,
        "reason": "reviewed for synthetic test",
        "unit_version": version,
    }


def test_accept_is_idempotent_and_double_reservation_conflicts(tmp_path) -> None:
    client = make_client(tmp_path)

    first = client.post("/suggestions/sug-state/accept", json=decision("event-1"))
    replay = client.post("/suggestions/sug-state/accept", json=decision("event-1"))
    conflict = client.post("/suggestions/sug-state/accept", json=decision("event-2"))

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["status"] == "reserved"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "reservation_conflict"
    assert client.get("/suggestions").json()["items"] == []


def test_reused_event_id_with_different_payload_conflicts(tmp_path) -> None:
    client = make_client(tmp_path)
    client.post("/suggestions/sug-state/reject", json=decision("same-event"))

    conflict = client.post(
        "/suggestions/sug-state/reject",
        json={**decision("same-event"), "reason": "different payload"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["code"] == "event_id_conflict"
    assert client.get("/suggestions").json()["items"] == []


def test_rejecting_reserved_suggestion_conflicts_without_stranding_reservation(tmp_path) -> None:
    client = make_client(tmp_path)
    accepted = client.post("/suggestions/sug-state/accept", json=decision("event-accept"))
    move_id = accepted.json()["move_id"]

    rejected = client.post("/suggestions/sug-state/reject", json=decision("event-reject"))

    assert rejected.status_code == 409
    assert rejected.json()["code"] == "move_still_reserved"
    assert client.get(f"/moves/{move_id}").json()["status"] == "reserved"
    with sqlite3.connect(tmp_path / "actions.sqlite") as connection:
        assert connection.execute(
            "SELECT count(*) FROM reservations WHERE move_id = ?", (move_id,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT active FROM suggestions WHERE suggestion_id = 'sug-state'"
        ).fetchone()[0] == 1


def test_wrong_role_stale_version_and_eligibility_are_rejected(tmp_path) -> None:
    client = make_client(tmp_path)

    wrong_role = client.post(
        "/suggestions/sug-state/accept", json=decision("event-role", role="sender")
    )
    stale = client.post("/suggestions/sug-state/accept", json=decision("event-stale", version=3))
    ineligible_client = TestClient(
        create_app(
            database_path=tmp_path / "other-snapshot.sqlite",
            action_database_path=tmp_path / "other-actions.sqlite",
            suggestion_provider=lambda _policy: [card()],
            eligibility_check=lambda _suggestion, _connection: False,
        )
    )
    ineligible_client.get("/suggestions")
    ineligible = ineligible_client.post(
        "/suggestions/sug-state/accept", json=decision("event-ineligible")
    )

    assert wrong_role.status_code == 403
    assert stale.status_code == 409
    assert ineligible.status_code == 422


def test_change_after_reserve_cancels_reservation_and_rechecks_eligibility(tmp_path) -> None:
    def change(
        original: Suggestion,
        unit_ids: list[str],
        destination: str,
        _connection: sqlite3.Connection,
    ) -> Suggestion:
        return original.model_copy(
            update={
                "suggestion_id": "sug-state-changed",
                "unit_ids": unit_ids,
                "to_facility_id": destination,
            }
        )

    client = make_client(tmp_path, changer=change)
    move = client.post("/suggestions/sug-state/accept", json=decision("event-accept")).json()
    changed_body = {
        **decision("event-change"),
        "unit_ids": ["unit-b"],
        "to_facility_id": "HSP-other",
    }

    response = client.post("/suggestions/sug-state/change", json=changed_body)
    old_move = client.get(f"/moves/{move['move_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "suggested"
    assert response.json()["suggestion"]["unit_ids"] == ["unit-b"]
    assert old_move.json()["status"] == "cancelled"
    assert client.get("/audit?unit_id=unit-a").json()


def test_dispatch_receipt_and_quarantine_states_are_not_release_actions(tmp_path) -> None:
    client = make_client(tmp_path)
    move = client.post("/suggestions/sug-state/accept", json=decision("event-accept")).json()
    move_id = move["move_id"]
    dispatched = client.post(
        f"/moves/{move_id}/dispatch",
        json={"event_id": "event-dispatch", "actor_id": "demo-sender", "role": "sender"},
    )
    received = client.post(
        f"/moves/{move_id}/receive",
        json={
            "event_id": "event-receive",
            "actor_id": "demo-receiver",
            "role": "receiver",
            "cold_chain_evidence_complete": False,
        },
    )

    assert dispatched.json()["status"] == "in_transit"
    assert client.get("/suggestions").json()["items"] == []
    assert received.json()["status"] == "received_held"
    assert "release" not in received.text.lower()


def test_quarantine_raised_in_transit_is_preserved_at_receipt(tmp_path) -> None:
    client = make_client(tmp_path)
    move = client.post("/suggestions/sug-state/accept", json=decision("event-accept")).json()
    move_id = move["move_id"]
    client.post(
        f"/moves/{move_id}/dispatch",
        json={"event_id": "event-dispatch", "actor_id": "demo-sender", "role": "sender"},
    )
    quarantined = client.post(
        f"/moves/{move_id}/quarantine",
        json={"event_id": "event-quarantine", "actor_id": "demo-safety", "role": "safety"},
    )
    receive_body = {
        "event_id": "event-receive",
        "actor_id": "demo-receiver",
        "role": "receiver",
        "cold_chain_evidence_complete": True,
    }
    received = client.post(f"/moves/{move_id}/receive", json=receive_body)
    replay = client.post(f"/moves/{move_id}/receive", json=receive_body)
    second_receipt = client.post(
        f"/moves/{move_id}/receive", json={**receive_body, "event_id": "event-receive-again"}
    )

    assert quarantined.json()["status"] == "quarantined"
    assert received.status_code == 200
    assert received.json()["status"] == "quarantined"
    assert replay.status_code == 200
    assert replay.json() == received.json()
    assert second_receipt.status_code == 409
    assert second_receipt.json()["code"] == "already_received"


def test_reserved_move_quarantined_before_dispatch_cannot_be_received(tmp_path) -> None:
    client = make_client(tmp_path)
    move = client.post("/suggestions/sug-state/accept", json=decision("event-accept")).json()
    move_id = move["move_id"]
    quarantined = client.post(
        f"/moves/{move_id}/quarantine",
        json={"event_id": "event-quarantine", "actor_id": "demo-safety", "role": "safety"},
    )

    received = client.post(
        f"/moves/{move_id}/receive",
        json={
            "event_id": "event-receive",
            "actor_id": "demo-receiver",
            "role": "receiver",
            "cold_chain_evidence_complete": True,
        },
    )

    assert quarantined.status_code == 200
    assert received.status_code == 409
    assert received.json()["code"] == "move_not_dispatched"
    assert client.get(f"/moves/{move_id}").json()["status"] == "quarantined"
    with sqlite3.connect(tmp_path / "actions.sqlite") as connection:
        assert connection.execute(
            "SELECT count(*) FROM reservations WHERE move_id = ?", (move_id,)
        ).fetchone()[0] == 0


def test_read_only_store_connections_are_closed(tmp_path) -> None:
    class TrackingActionStore(ActionStore):
        def __init__(self, database_path):
            super().__init__(database_path)
            self.connections = []

        def _connect(self):
            connection = super()._connect()
            self.connections.append(connection)
            return connection

    store = TrackingActionStore(tmp_path / "actions.sqlite")
    store.save_suggestions([card()])

    reads = [
        lambda: store.read_suggestion("sug-state"),
        lambda: store.list_audit({}),
        store.get_settings,
        store.list_sync_status,
    ]
    for read in reads:
        before = len(store.connections)
        read()
        assert len(store.connections) == before + 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            store.connections[-1].execute("SELECT 1")


def test_lease_expiry_cancels_a_reservation_and_audit_is_append_only(tmp_path) -> None:
    client = make_client(tmp_path)
    move = client.post("/suggestions/sug-state/accept", json=decision("event-accept")).json()
    with sqlite3.connect(tmp_path / "actions.sqlite") as connection:
        connection.execute(
            "UPDATE reservations SET expires_at = '2000-01-01T00:00:00+00:00' WHERE move_id = ?",
            (move["move_id"],),
        )
    result = client.get(f"/moves/{move['move_id']}").json()
    audit = client.get(f"/audit?move_id={move['move_id']}").json()
    with sqlite3.connect(tmp_path / "actions.sqlite") as connection:
        try:
            connection.execute("DELETE FROM audit_events")
        except sqlite3.IntegrityError:
            delete_blocked = True
        else:
            delete_blocked = False

    assert result["status"] == "cancelled"
    assert any(item["event_type"] == "reservation_expired" for item in audit)
    assert delete_blocked
