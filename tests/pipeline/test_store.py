"""DG-02: shared SQLite schema."""

from __future__ import annotations

import sqlite3

import pytest

from pipeline.schema import TABLES
from pipeline.store import SchemaVersionError, append_audit_event, create_schema, verify_audit_chain

NOW = "2026-11-10T21:00:00+03:00"


@pytest.fixture
def conn():
    """Test helper: conn."""
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("PRAGMA foreign_keys = OFF")  # moves/audit tests do not need the official rows
    yield c
    c.close()


def _cols(conn, table):
    """Test helper: cols."""
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_official_tables_keep_official_column_names(conn):
    """Official tables keep official column names."""
    for name, spec in TABLES.items():
        assert _cols(conn, name) == list(spec), name


def test_added_tables_are_prefixed(conn):
    """Added tables are prefixed."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    added = tables - set(TABLES) - {"sqlite_sequence"}
    assert added and all(t.startswith("dg_") for t in added)


def test_schema_creation_is_repeatable(conn):
    """Schema creation is repeatable."""
    create_schema(conn)


def _move(conn, move_id, unit, state):
    """Test helper: move."""
    conn.execute(
        "INSERT INTO dg_moves (move_id, unit_id, from_facility_id, to_facility_id, component, blood_group,"
        " state, created_at, updated_at) VALUES (?, ?, 'RBTC-A', 'HSP-1', 'RBC', 'O+', ?, ?, ?)",
        (move_id, unit, state, NOW, NOW),
    )


def test_a_unit_cannot_be_reserved_twice(conn):
    """A unit cannot be reserved twice."""
    _move(conn, "m1", "U1", "Reserved")
    with pytest.raises(sqlite3.IntegrityError):
        _move(conn, "m2", "U1", "Reserved")


def test_closed_moves_do_not_block_a_new_reservation(conn):
    """Closed moves do not block a new reservation."""
    _move(conn, "m1", "U1", "Rejected")
    _move(conn, "m2", "U1", "Cancelled")
    _move(conn, "m3", "U1", "Reserved")


def test_unknown_state_is_refused(conn):
    """Unknown state is refused."""
    with pytest.raises(sqlite3.IntegrityError):
        _move(conn, "m1", "U1", "Released")


def _event(conn, eid, **kw):
    """Test helper: event."""
    args = dict(event_id=eid, at=NOW, actor_id="coord-1", role="coordinator", action="accept",
                move_id=None, unit_id="U1", from_state="Suggested", to_state="Reserved")
    args.update(kw)
    return append_audit_event(conn, **args)


def test_audit_events_are_hash_chained(conn):
    """Audit events are hash chained."""
    h1 = _event(conn, "e1")
    h2 = _event(conn, "e2", action="dispatch", from_state="Reserved", to_state="Dispatched")
    assert h1 != h2
    assert conn.execute("SELECT prev_hash FROM dg_audit_events WHERE event_id='e2'").fetchone()[0] == h1
    assert verify_audit_chain(conn) == (True, None)


def test_a_broken_link_is_refused_by_the_database(conn):
    """A broken link is refused by the database."""
    _event(conn, "e1")
    with pytest.raises(sqlite3.DatabaseError, match="prev_hash"):
        conn.execute("INSERT INTO dg_audit_events (event_id, at, actor_id, role, action, prev_hash, hash)"
                     " VALUES ('e2', ?, 'x', 'system', 'forged', 'not-the-last-hash', 'h')", (NOW,))


def test_tampering_is_detected(conn):
    """Tampering is detected."""
    _event(conn, "e1")
    _event(conn, "e2")
    conn.execute("DROP TRIGGER dg_audit_no_update")  # simulate someone editing the file directly
    conn.execute("UPDATE dg_audit_events SET reason = 'edited' WHERE event_id = 'e1'")
    assert verify_audit_chain(conn) == (False, 1)


def test_retrying_the_same_event_is_idempotent(conn):
    """Retrying the same event is idempotent."""
    assert _event(conn, "e1") == _event(conn, "e1")
    assert conn.execute("SELECT COUNT(*) FROM dg_audit_events").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="different content"):
        _event(conn, "e1", reason="changed")


def test_audit_time_needs_an_offset(conn):
    """Audit time needs an offset."""
    with pytest.raises(ValueError, match="offset"):
        _event(conn, "e1", at="2026-11-10T21:00:00")


def test_old_schema_version_is_refused():
    """Old schema version is refused."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA user_version = 99")
    with pytest.raises(SchemaVersionError):
        create_schema(c)


def test_audit_trail_is_append_only(conn):
    """Audit trail is append only."""
    conn.execute(
        "INSERT INTO dg_audit_events (event_id, at, actor_id, role, action, hash)"
        " VALUES ('e1', ?, 'coord-1', 'coordinator', 'accept', 'h1')", (NOW,))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE dg_audit_events SET reason = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM dg_audit_events")
