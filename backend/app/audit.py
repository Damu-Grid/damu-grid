import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

EAT = timezone(timedelta(hours=3))


class AuditStore:
    """Append-only local audit events for demo actions and LLM calls."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def append_llm_call(
        self,
        *,
        provider: str,
        model: str | None,
        latency_ms: int,
        outcome: str,
    ) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            ensure_audit_schema(connection)
            append_event(
                connection,
                event_type="llm_explanation",
                payload={
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                    "outcome": outcome,
                },
            )


def ensure_audit_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor_id TEXT,
            move_id TEXT,
            unit_id TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(audit_events)").fetchall()
    }
    for column in ("actor_id", "move_id", "unit_id"):
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE audit_events ADD COLUMN {column} TEXT")
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS audit_events_no_update
        BEFORE UPDATE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
        BEFORE DELETE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END
        """
    )


def append_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    payload: dict,
    actor_id: str | None = None,
    move_id: str | None = None,
    unit_id: str | None = None,
) -> str:
    event_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO audit_events
            (event_id, event_type, occurred_at, actor_id, move_id, unit_id, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            datetime.now(EAT).isoformat(),
            actor_id,
            move_id,
            unit_id,
            json.dumps(payload, sort_keys=True),
        ),
    )
    return event_id
