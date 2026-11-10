import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.audit import append_event, ensure_audit_schema
from backend.app.schemas import Suggestion


class ActionError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


EligibilityCheck = Callable[[Suggestion], bool]
ChangeSuggestion = Callable[[Suggestion, list[str], str], Suggestion]
EAT = timezone(timedelta(hours=3))


class ActionStore:
    def __init__(self, database_path: Path, lease_minutes: int = 30) -> None:
        if not 1 <= lease_minutes <= 30:
            raise ValueError("reservation lease must be between 1 and 30 minutes")
        self.database_path = database_path
        self.lease_minutes = lease_minutes

    DEFAULT_SETTINGS = {
        "country_code": "KE",
        "language": "en",
        "branding": "Damu Grid",
        "enabled_components": ["RBC"],
        "shelf_life_days": {"RBC": 42, "WB": 35, "PLT": 5, "FFP": 365, "CRYO": 365},
        "remaining_life_min_days": {"RBC": 10},
        "sender_reserve_units": 2,
        "reservation_lease_minutes": 30,
    }

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                suggestion_id TEXT PRIMARY KEY,
                body_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS unit_state (
                unit_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL DEFAULT 0,
                eligible INTEGER NOT NULL DEFAULT 0,
                quarantined INTEGER NOT NULL DEFAULT 0,
                inventory_status TEXT NOT NULL DEFAULT 'in_stock'
            );
            CREATE TABLE IF NOT EXISTS moves (
                move_id TEXT PRIMARY KEY,
                suggestion_id TEXT NOT NULL,
                unit_ids_json TEXT NOT NULL,
                from_facility_id TEXT NOT NULL,
                to_facility_id TEXT NOT NULL,
                status TEXT NOT NULL,
                lease_expires_at TEXT,
                created_by TEXT NOT NULL,
                reason TEXT NOT NULL,
                cold_chain_evidence_complete INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                dispatched_at TEXT,
                received_at TEXT
            );
            CREATE TABLE IF NOT EXISTS reservations (
                unit_id TEXT PRIMARY KEY,
                move_id TEXT NOT NULL REFERENCES moves(move_id),
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                payload_hash TEXT NOT NULL,
                response_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS simulated_alerts (
                alert_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                actor_id TEXT NOT NULL,
                recipient_role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_events (
                event_id TEXT PRIMARY KEY,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        suggestion_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(suggestions)").fetchall()
        }
        if "active" not in suggestion_columns:
            connection.execute(
                "ALTER TABLE suggestions ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
            )
        move_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(moves)").fetchall()
        }
        if "dispatched_at" not in move_columns:
            connection.execute("ALTER TABLE moves ADD COLUMN dispatched_at TEXT")
        if "received_at" not in move_columns:
            connection.execute("ALTER TABLE moves ADD COLUMN received_at TEXT")
        ensure_audit_schema(connection)
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(EAT)

    def _expire_reservations(self, connection: sqlite3.Connection) -> None:
        now = self._now().isoformat()
        expired = connection.execute(
            "SELECT unit_id, move_id FROM reservations WHERE expires_at <= ?", (now,)
        ).fetchall()
        if not expired:
            return
        move_ids = {row["move_id"] for row in expired}
        for move_id in move_ids:
            connection.execute(
                "UPDATE moves SET status = 'cancelled' WHERE move_id = ? AND status = 'reserved'",
                (move_id,),
            )
        for row in expired:
            connection.execute("DELETE FROM reservations WHERE unit_id = ?", (row["unit_id"],))
            append_event(
                connection,
                event_type="reservation_expired",
                move_id=row["move_id"],
                unit_id=row["unit_id"],
                payload={"reason": "reservation lease expired"},
            )

    def _configured_lease_minutes(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT payload_json FROM app_settings WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return self.lease_minutes
        return json.loads(row[0]).get("reservation_lease_minutes", self.lease_minutes)

    def save_suggestions(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        saved: list[Suggestion] = []
        with self.transaction() as connection:
            self._expire_reservations(connection)
            for suggestion in suggestions:
                for unit_id in suggestion.unit_ids:
                    connection.execute(
                        "INSERT OR IGNORE INTO unit_state (unit_id, eligible) VALUES (?, ?)",
                        (unit_id, int(suggestion.eligibility_ok)),
                    )
                if not suggestion.unit_ids:
                    continue
                versions = [
                    connection.execute(
                        "SELECT version FROM unit_state WHERE unit_id = ?", (unit_id,)
                    ).fetchone()[0]
                    for unit_id in suggestion.unit_ids
                ]
                suggestion = suggestion.model_copy(update={"unit_version": max(versions)})
                unit_placeholders = ",".join("?" for _ in suggestion.unit_ids)
                blocked = connection.execute(
                    "SELECT 1 FROM unit_state WHERE unit_id IN "
                    f"({unit_placeholders}) AND "
                    "(eligible = 0 OR quarantined = 1 OR inventory_status != 'in_stock') LIMIT 1",
                    suggestion.unit_ids,
                ).fetchone()
                reserved = connection.execute(
                    f"SELECT 1 FROM reservations WHERE unit_id IN ({unit_placeholders}) LIMIT 1",
                    suggestion.unit_ids,
                ).fetchone()
                existing = connection.execute(
                    "SELECT active FROM suggestions WHERE suggestion_id = ?",
                    (suggestion.suggestion_id,),
                ).fetchone()
                if blocked or reserved or (existing and not existing["active"]):
                    continue
                connection.execute(
                    "INSERT INTO suggestions (suggestion_id, body_json, created_at, active) "
                    "VALUES (?, ?, ?, 1) ON CONFLICT(suggestion_id) DO UPDATE SET "
                    "body_json = excluded.body_json, created_at = excluded.created_at "
                    "WHERE suggestions.active = 1",
                    (
                        suggestion.suggestion_id,
                        suggestion.model_dump_json(),
                        self._now().isoformat(),
                    ),
                )
                saved.append(suggestion)
        return saved

    def get_suggestion(self, connection: sqlite3.Connection, suggestion_id: str) -> Suggestion:
        row = connection.execute(
            "SELECT body_json FROM suggestions WHERE suggestion_id = ? AND active = 1",
            (suggestion_id,),
        ).fetchone()
        if row is None:
            raise ActionError(404, "suggestion_not_found", "Suggestion not found.")
        return Suggestion.model_validate_json(row["body_json"])

    def read_suggestion(self, suggestion_id: str) -> Suggestion:
        with closing(self._connect()) as connection:
            return self.get_suggestion(connection, suggestion_id)

    @staticmethod
    def _event_result(connection: sqlite3.Connection, event_id: str, payload: dict) -> dict | None:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        row = connection.execute(
            "SELECT payload_hash, response_json FROM processed_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        if row["payload_hash"] != payload_hash:
            raise ActionError(
                409,
                "event_id_conflict",
                "This event_id was already used with a different payload.",
            )
        return json.loads(row["response_json"])

    @staticmethod
    def _save_event(
        connection: sqlite3.Connection, event_id: str, payload: dict, result: dict
    ) -> None:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            "INSERT INTO processed_events VALUES (?, ?, ?)",
            (event_id, payload_hash, json.dumps(result, sort_keys=True)),
        )

    @staticmethod
    def _require_role(actual: str, expected: str) -> None:
        if actual != expected:
            raise ActionError(403, "wrong_role", f"This action requires the {expected} role.")

    @staticmethod
    def _check_version(
        connection: sqlite3.Connection, suggestion: Suggestion, expected_version: int
    ) -> None:
        versions = [
            connection.execute(
                "SELECT version FROM unit_state WHERE unit_id = ?", (unit_id,)
            ).fetchone()
            for unit_id in suggestion.unit_ids
        ]
        if any(row is None or row["version"] != expected_version for row in versions):
            raise ActionError(
                409, "stale_version", "The unit version is stale; reload the suggestion."
            )

    def _check_eligibility(self, suggestion: Suggestion, checker: EligibilityCheck | None) -> None:
        if checker is None:
            raise ActionError(503, "eligibility_not_ready", "Eligibility recheck is not connected.")
        try:
            eligible = checker(suggestion)
        except Exception as exc:
            raise ActionError(
                503, "eligibility_unavailable", "Eligibility recheck is unavailable."
            ) from exc
        if not suggestion.eligibility_ok or not eligible:
            raise ActionError(
                422, "eligibility_failed", "The suggestion no longer passes eligibility."
            )

    @staticmethod
    def _audit_for_units(
        connection: sqlite3.Connection,
        *,
        event_type: str,
        actor_id: str,
        move_id: str,
        unit_ids: list[str],
        payload: dict,
    ) -> None:
        for unit_id in unit_ids or [None]:
            append_event(
                connection,
                event_type=event_type,
                actor_id=actor_id,
                move_id=move_id,
                unit_id=unit_id,
                payload=payload,
            )

    def decide(
        self,
        *,
        suggestion_id: str,
        decision: str,
        body: dict,
        checker: EligibilityCheck | None,
    ) -> dict:
        if decision not in {"accept", "reject"}:
            raise ValueError("decision must be accept or reject")
        with self.transaction() as connection:
            self._expire_reservations(connection)
            replay = self._event_result(connection, body["event_id"], body)
            if replay is not None:
                return replay
            self._require_role(body["role"], "coordinator")
            suggestion = self.get_suggestion(connection, suggestion_id)
            self._check_version(connection, suggestion, body["unit_version"])
            if decision == "reject" and connection.execute(
                "SELECT 1 FROM moves WHERE suggestion_id = ? AND status = 'reserved' LIMIT 1",
                (suggestion_id,),
            ).fetchone():
                raise ActionError(
                    409,
                    "move_still_reserved",
                    "Cancel the reserved move before rejecting this suggestion.",
                )
            if decision == "accept":
                self._check_eligibility(suggestion, checker)
                for unit_id in suggestion.unit_ids:
                    unit = connection.execute(
                        "SELECT * FROM unit_state WHERE unit_id = ?", (unit_id,)
                    ).fetchone()
                    if unit["quarantined"] or unit["inventory_status"] != "in_stock":
                        raise ActionError(
                            422, "eligibility_failed", "A unit is unavailable or quarantined."
                        )
                    if connection.execute(
                        "SELECT 1 FROM reservations WHERE unit_id = ?", (unit_id,)
                    ).fetchone():
                        raise ActionError(
                            409, "reservation_conflict", "A unit is already reserved."
                        )
            move_id = str(uuid4())
            now = self._now()
            expires_at = (
                (now + timedelta(minutes=self._configured_lease_minutes(connection))).isoformat()
                if decision == "accept"
                else None
            )
            status = "reserved" if decision == "accept" else "rejected"
            connection.execute(
                "INSERT INTO moves (move_id, suggestion_id, unit_ids_json, from_facility_id, "
                "to_facility_id, status, lease_expires_at, created_by, reason, "
                "cold_chain_evidence_complete, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (
                    move_id,
                    suggestion_id,
                    json.dumps(suggestion.unit_ids),
                    suggestion.from_facility_id,
                    suggestion.to_facility_id,
                    status,
                    expires_at,
                    body["actor_id"],
                    body["reason"],
                    now.isoformat(),
                ),
            )
            if decision == "accept":
                for unit_id in suggestion.unit_ids:
                    connection.execute(
                        "INSERT INTO reservations VALUES (?, ?, ?)",
                        (unit_id, move_id, expires_at),
                    )
                    append_event(
                        connection,
                        event_type="unit_reserved",
                        actor_id=body["actor_id"],
                        move_id=move_id,
                        unit_id=unit_id,
                        payload={"expires_at": expires_at},
                    )
            else:
                connection.execute(
                    "UPDATE suggestions SET active = 0 WHERE suggestion_id = ?",
                    (suggestion_id,),
                )
            self._audit_for_units(
                connection,
                event_type=f"decision_{decision}",
                actor_id=body["actor_id"],
                move_id=move_id,
                unit_ids=suggestion.unit_ids,
                payload={"reason": body["reason"], "suggestion_id": suggestion_id},
            )
            result = {"move_id": move_id, "suggestion_id": suggestion_id, "status": status}
            self._save_event(connection, body["event_id"], body, result)
            return result

    def change(
        self,
        *,
        suggestion_id: str,
        body: dict,
        checker: EligibilityCheck | None,
        change_suggestion: ChangeSuggestion | None,
    ) -> dict:
        with self.transaction() as connection:
            self._expire_reservations(connection)
            replay = self._event_result(connection, body["event_id"], body)
            if replay is not None:
                return replay
            self._require_role(body["role"], "coordinator")
            original = self.get_suggestion(connection, suggestion_id)
            self._check_version(connection, original, body["unit_version"])
            if change_suggestion is None:
                raise ActionError(
                    503, "eligibility_not_ready", "Change eligibility is not connected."
                )
            revised = change_suggestion(original, body["unit_ids"], body["to_facility_id"])
            if not revised.unit_ids or len(set(revised.unit_ids)) != len(revised.unit_ids):
                raise ActionError(
                    422, "invalid_change", "Changed unit IDs must be nonempty and unique."
                )
            if (
                revised.suggestion_id == suggestion_id
                or set(revised.unit_ids) != set(body["unit_ids"])
                or revised.to_facility_id != body["to_facility_id"]
            ):
                raise ActionError(
                    422,
                    "invalid_change",
                    "A change must return a distinct suggestion with the requested units "
                    "and destination.",
                )
            self._check_eligibility(revised, checker)
            active_moves = connection.execute(
                "SELECT move_id, unit_ids_json FROM moves "
                "WHERE suggestion_id = ? AND status = 'reserved'",
                (suggestion_id,),
            ).fetchall()
            own_move_ids = {move["move_id"] for move in active_moves}
            for unit_id in revised.unit_ids:
                state = connection.execute(
                    "SELECT eligible, quarantined, inventory_status FROM unit_state "
                    "WHERE unit_id = ?",
                    (unit_id,),
                ).fetchone()
                if state and (
                    not state["eligible"]
                    or state["quarantined"]
                    or state["inventory_status"] != "in_stock"
                ):
                    raise ActionError(
                        422, "eligibility_failed", "A changed unit is blocked or unavailable."
                    )
                reservation = connection.execute(
                    "SELECT move_id FROM reservations WHERE unit_id = ?", (unit_id,)
                ).fetchone()
                if reservation and reservation["move_id"] not in own_move_ids:
                    raise ActionError(
                        409, "reservation_conflict", "A changed unit is already reserved."
                    )
            for move in active_moves:
                connection.execute(
                    "UPDATE moves SET status = 'cancelled' WHERE move_id = ?", (move["move_id"],)
                )
                for unit_id in json.loads(move["unit_ids_json"]):
                    connection.execute("DELETE FROM reservations WHERE unit_id = ?", (unit_id,))
                    append_event(
                        connection,
                        event_type="reservation_cancelled",
                        actor_id=body["actor_id"],
                        move_id=move["move_id"],
                        unit_id=unit_id,
                        payload={"reason": "suggestion changed"},
                    )
            revised_versions = []
            for unit_id in revised.unit_ids:
                connection.execute(
                    "INSERT OR IGNORE INTO unit_state (unit_id, eligible) VALUES (?, ?)",
                    (unit_id, int(revised.eligibility_ok)),
                )
                revised_versions.append(
                    connection.execute(
                        "SELECT version FROM unit_state WHERE unit_id = ?", (unit_id,)
                    ).fetchone()[0]
                )
            revised = revised.model_copy(update={"unit_version": max(revised_versions)})
            connection.execute(
                "UPDATE suggestions SET active = 0 WHERE suggestion_id = ?", (suggestion_id,)
            )
            connection.execute(
                "INSERT OR REPLACE INTO suggestions "
                "(suggestion_id, body_json, created_at, active) VALUES (?, ?, ?, 1)",
                (revised.suggestion_id, revised.model_dump_json(), self._now().isoformat()),
            )
            self._audit_for_units(
                connection,
                event_type="decision_changed",
                actor_id=body["actor_id"],
                move_id=active_moves[0]["move_id"] if active_moves else "",
                unit_ids=revised.unit_ids,
                payload={
                    "from_suggestion_id": suggestion_id,
                    "to_suggestion_id": revised.suggestion_id,
                },
            )
            result = {"suggestion": revised.model_dump(mode="json"), "status": "suggested"}
            self._save_event(connection, body["event_id"], body, result)
            return result

    def transition(
        self,
        *,
        move_id: str,
        action: str,
        body: dict,
        checker: EligibilityCheck | None = None,
    ) -> dict:
        expected_role = {"dispatch": "sender", "receive": "receiver", "quarantine": "safety"}[
            action
        ]
        with self.transaction() as connection:
            self._expire_reservations(connection)
            replay = self._event_result(connection, body["event_id"], body)
            if replay is not None:
                return replay
            self._require_role(body["role"], expected_role)
            move = connection.execute(
                "SELECT * FROM moves WHERE move_id = ?", (move_id,)
            ).fetchone()
            if move is None:
                raise ActionError(404, "move_not_found", "Move not found.")
            units = json.loads(move["unit_ids_json"])
            unit_placeholders = ",".join("?" for _ in units)
            if action == "dispatch":
                if move["status"] != "reserved":
                    raise ActionError(
                        409, "invalid_move_state", "Only a reserved move can be dispatched."
                    )
                if (
                    not move["lease_expires_at"]
                    or datetime.fromisoformat(move["lease_expires_at"]) <= self._now()
                ):
                    raise ActionError(
                        409, "reservation_expired", "The reservation lease has expired."
                    )
                suggestion = self.get_suggestion(connection, move["suggestion_id"])
                self._check_eligibility(suggestion, checker)
                for unit_id in units:
                    state = connection.execute(
                        "SELECT quarantined, inventory_status FROM unit_state WHERE unit_id = ?",
                        (unit_id,),
                    ).fetchone()
                    if (
                        state is None
                        or state["quarantined"]
                        or state["inventory_status"] != "in_stock"
                    ):
                        raise ActionError(
                            422, "eligibility_failed", "A unit is blocked or unavailable."
                        )
                new_status = "in_transit"
                connection.execute(
                    "UPDATE moves SET status = ?, dispatched_at = ? WHERE move_id = ?",
                    (new_status, self._now().isoformat(), move_id),
                )
                connection.execute(
                    "UPDATE unit_state SET inventory_status = 'in_transit' "
                    f"WHERE unit_id IN ({unit_placeholders})",
                    units,
                )
                connection.execute(
                    f"UPDATE unit_state SET version = version + 1 "
                    f"WHERE unit_id IN ({unit_placeholders})",
                    units,
                )
                connection.execute("DELETE FROM reservations WHERE move_id = ?", (move_id,))
            elif action == "receive":
                if move["received_at"] is not None:
                    raise ActionError(409, "already_received", "This move was already received.")
                if move["status"] == "quarantined" and move["dispatched_at"] is None:
                    raise ActionError(
                        409,
                        "move_not_dispatched",
                        "A quarantined move cannot be received unless it was dispatched first.",
                    )
                if move["status"] not in {"in_transit", "quarantined"}:
                    raise ActionError(
                        409, "invalid_move_state", "Only an in-transit move can be received."
                    )
                blocked = any(
                    row["quarantined"]
                    for row in connection.execute(
                        "SELECT quarantined FROM unit_state "
                        f"WHERE unit_id IN ({unit_placeholders})",
                        units,
                    ).fetchall()
                )
                if blocked or move["status"] == "quarantined":
                    new_status = "quarantined"
                else:
                    new_status = (
                        "received" if body["cold_chain_evidence_complete"] else "received_held"
                    )
                connection.execute(
                    "UPDATE moves SET status = ?, cold_chain_evidence_complete = ?, "
                    "received_at = ? "
                    "WHERE move_id = ?",
                    (
                        new_status,
                        int(body["cold_chain_evidence_complete"]),
                        self._now().isoformat(),
                        move_id,
                    ),
                )
                connection.execute(
                    "UPDATE unit_state SET inventory_status = ? "
                    f"WHERE unit_id IN ({unit_placeholders})",
                    ("received" if new_status == "received" else "held", *units),
                )
                connection.execute(
                    f"UPDATE unit_state SET version = version + 1 "
                    f"WHERE unit_id IN ({unit_placeholders})",
                    units,
                )
            else:
                if move["status"] not in {"reserved", "in_transit", "received_held"}:
                    raise ActionError(
                        409,
                        "invalid_move_state",
                        "This move cannot be quarantined in its current state.",
                    )
                new_status = "quarantined"
                connection.execute(
                    "UPDATE moves SET status = ?, lease_expires_at = NULL WHERE move_id = ?",
                    (new_status, move_id),
                )
                if move["status"] == "reserved":
                    connection.execute("DELETE FROM reservations WHERE move_id = ?", (move_id,))
                connection.execute(
                    "UPDATE unit_state SET quarantined = 1, inventory_status = 'quarantined', "
                    f"version = version + 1 WHERE unit_id IN ({unit_placeholders})",
                    units,
                )
            self._audit_for_units(
                connection,
                event_type=f"move_{action}",
                actor_id=body["actor_id"],
                move_id=move_id,
                unit_ids=units,
                payload={"status": new_status, "reason": body.get("reason", "")},
            )
            result = {"move_id": move_id, "status": new_status}
            self._save_event(connection, body["event_id"], body, result)
            return result

    def get_move(self, move_id: str) -> dict:
        with self.transaction() as connection:
            self._expire_reservations(connection)
            row = connection.execute("SELECT * FROM moves WHERE move_id = ?", (move_id,)).fetchone()
            if row is None:
                raise ActionError(404, "move_not_found", "Move not found.")
            return {**dict(row), "unit_ids": json.loads(row["unit_ids_json"])}

    def list_audit(self, filters: dict[str, str | None]) -> list[dict]:
        with closing(self._connect()) as connection:
            query = "SELECT * FROM audit_events WHERE 1=1"
            values: list[str] = []
            for field in ("unit_id", "actor_id", "move_id"):
                if filters.get(field):
                    query += f" AND {field} = ?"
                    values.append(filters[field])
            if filters.get("from_time"):
                query += " AND occurred_at >= ?"
                values.append(filters["from_time"])
            if filters.get("to_time"):
                query += " AND occurred_at <= ?"
                values.append(filters["to_time"])
            query += " ORDER BY occurred_at, event_id"
            rows = connection.execute(query, values).fetchall()
            return [
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "occurred_at": row["occurred_at"],
                    "actor_id": row["actor_id"],
                    "move_id": row["move_id"],
                    "unit_id": row["unit_id"],
                    "payload": json.loads(row["payload_json"]),
                }
                for row in rows
            ]

    def get_settings(self) -> dict:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload_json FROM app_settings WHERE singleton = 1"
            ).fetchone()
            if row:
                return json.loads(row[0])
            return {
                **self.DEFAULT_SETTINGS,
                "reservation_lease_minutes": self.lease_minutes,
            }

    def update_settings(self, body: dict) -> dict:
        with self.transaction() as connection:
            replay = self._event_result(connection, body["event_id"], body)
            if replay is not None:
                return replay
            self._require_role(body["role"], "coordinator")
            current = self.get_settings()
            proposed = body["settings"]
            unknown = set(proposed) - set(self.DEFAULT_SETTINGS)
            if unknown:
                raise ActionError(
                    422, "invalid_settings", f"Unknown settings: {', '.join(sorted(unknown))}"
                )
            updated = {**current, **proposed}
            lease = updated["reservation_lease_minutes"]
            reserve = updated["sender_reserve_units"]
            if not isinstance(lease, int) or not 1 <= lease <= 30:
                raise ActionError(
                    422, "invalid_settings", "Reservation lease must be 1–30 minutes."
                )
            if not isinstance(reserve, int) or reserve < 0:
                raise ActionError(
                    422, "invalid_settings", "Sender reserve must be a nonnegative unit count."
                )
            shelf_lives = updated["shelf_life_days"]
            remaining_lives = updated["remaining_life_min_days"]
            if not isinstance(shelf_lives, dict) or any(
                not isinstance(value, int) or value < 1 for value in shelf_lives.values()
            ):
                raise ActionError(
                    422, "invalid_settings", "Shelf lives must be positive whole days."
                )
            if not isinstance(remaining_lives, dict) or any(
                not isinstance(value, int) or value < 0 for value in remaining_lives.values()
            ):
                raise ActionError(
                    422,
                    "invalid_settings",
                    "Minimum remaining lives must be nonnegative whole days.",
                )
            if any(
                remaining_lives.get(component, 0) >= shelf_lives.get(component, 0)
                for component in remaining_lives
            ):
                raise ActionError(
                    422,
                    "invalid_settings",
                    "A minimum remaining life must be shorter than that component's shelf life.",
                )
            connection.execute(
                "INSERT OR REPLACE INTO app_settings VALUES (1, ?)",
                (json.dumps(updated, sort_keys=True),),
            )
            append_event(
                connection,
                event_type="settings_updated",
                actor_id=body["actor_id"],
                payload={"changed_keys": sorted(proposed)},
            )
            result = {"settings": updated}
            self._save_event(connection, body["event_id"], body, result)
            return result

    def simulate_alert(self, body: dict) -> dict:
        with self.transaction() as connection:
            replay = self._event_result(connection, body["event_id"], body)
            if replay is not None:
                return replay
            if body["role"] not in {"coordinator", "sender", "receiver"}:
                raise ActionError(
                    403, "wrong_role", "Only a demo officer role can receive a simulated alert."
                )
            if body["recipient_role"] not in {"coordinator", "sender", "receiver"}:
                raise ActionError(
                    422, "invalid_alert_recipient", "Alerts can target demo officer roles only."
                )
            alert_id = str(uuid4())
            created_at = self._now().isoformat()
            connection.execute(
                "INSERT INTO simulated_alerts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    alert_id,
                    body["event_id"],
                    body["actor_id"],
                    body["recipient_role"],
                    body["message"],
                    created_at,
                ),
            )
            append_event(
                connection,
                event_type="alert_simulated",
                actor_id=body["actor_id"],
                payload={"alert_id": alert_id, "recipient_role": body["recipient_role"]},
            )
            result = {
                "alert_id": alert_id,
                "status": "simulated",
                "recipient_role": body["recipient_role"],
            }
            self._save_event(connection, body["event_id"], body, result)
            return result

    def set_sync_status(self, event_id: str, payload: dict, status: str, result: dict) -> dict:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT payload_hash, status, result_json FROM sync_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing and existing["payload_hash"] != payload_hash:
                raise ActionError(
                    409, "event_id_conflict", "This sync event_id has a different payload."
                )
            if existing and existing["status"] != "pending":
                return {
                    "event_id": event_id,
                    "status": existing["status"],
                    "result": json.loads(existing["result_json"]),
                }
            connection.execute(
                "INSERT OR REPLACE INTO sync_events VALUES (?, ?, ?, ?, ?)",
                (
                    event_id,
                    payload_hash,
                    status,
                    json.dumps(result, sort_keys=True),
                    self._now().isoformat(),
                ),
            )
            return {"event_id": event_id, "status": status, "result": result}

    def list_sync_status(self, event_ids: list[str] | None = None) -> list[dict]:
        with closing(self._connect()) as connection:
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                rows = connection.execute(
                    f"SELECT event_id, status, result_json FROM sync_events "
                    f"WHERE event_id IN ({placeholders}) ORDER BY updated_at",
                    event_ids,
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT event_id, status, result_json FROM sync_events ORDER BY updated_at"
                ).fetchall()
            return [
                {
                    "event_id": row["event_id"],
                    "status": row["status"],
                    "result": json.loads(row["result_json"]),
                }
                for row in rows
            ]
