"""DG-02: shared SQLite schema."""

from __future__ import annotations

import sqlite3

import pytest

from pipeline.schema import TABLES
from pipeline.store import create_schema

NOW = "2026-11-10T21:00:00+03:00"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    c.execute("PRAGMA foreign_keys = OFF")  # moves/audit tests do not need the official rows
    yield c
    c.close()


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_official_tables_keep_official_column_names(conn):
    for name, spec in TABLES.items():
        assert _cols(conn, name) == list(spec), name


def test_added_tables_are_prefixed(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    added = tables - set(TABLES) - {"sqlite_sequence"}
    assert added and all(t.startswith("dg_") for t in added)


def test_schema_creation_is_repeatable(conn):
    create_schema(conn)


def _move(conn, move_id, unit, state):
    conn.execute(
        "INSERT INTO dg_moves (move_id, unit_id, from_facility_id, to_facility_id, component, blood_group,"
        " state, created_at, updated_at) VALUES (?, ?, 'RBTC-A', 'HSP-1', 'RBC', 'O+', ?, ?, ?)",
        (move_id, unit, state, NOW, NOW),
    )


def test_a_unit_cannot_be_reserved_twice(conn):
    _move(conn, "m1", "U1", "Reserved")
    with pytest.raises(sqlite3.IntegrityError):
        _move(conn, "m2", "U1", "Reserved")


def test_closed_moves_do_not_block_a_new_reservation(conn):
    _move(conn, "m1", "U1", "Rejected")
    _move(conn, "m2", "U1", "Cancelled")
    _move(conn, "m3", "U1", "Reserved")


def test_unknown_state_is_refused(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _move(conn, "m1", "U1", "Released")


def test_audit_trail_is_append_only(conn):
    conn.execute(
        "INSERT INTO dg_audit_events (event_id, at, actor_id, role, action, hash)"
        " VALUES ('e1', ?, 'coord-1', 'coordinator', 'accept', 'h1')", (NOW,))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE dg_audit_events SET reason = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM dg_audit_events")
