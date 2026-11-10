"""DG-02: the one SQLite schema shared by the pipeline, the API (Timi) and the evaluator (Blessings).

- Official tables keep their official names and column names (data/raw/DATA_DICTIONARY.md).
- Everything Damu Grid adds is prefixed `dg_` so it can never be mistaken for official data.
- Recommendation logic stays out of the movement tables: `dg_moves` only records the human
  decision and the physical steps (reserve, dispatch, receive), never a model score.
- The audit trail is append-only at database level (UPDATE and DELETE are refused).

Timestamps are stored as text. Official timestamps, and the `dg_` columns copied or derived from
them (`dg_snapshot_units.on_shelf_since`, `dg_cold_chain_flags.start_at` and `end_at`), are EAT
without an offset (`YYYY-MM-DD HH:MM:SS`, as in the CSVs): the API adds `+03:00` when it serialises
them. Records created by the application (`dg_moves`, `dg_audit_events`, `dg_snapshot_meta`)
carry an explicit offset, e.g. 2026-11-10T21:00:00+03:00.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.schema import TABLES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "damu_grid.sqlite"
# Bump when a table or constraint changes; older databases are refused, not silently reused.
SCHEMA_VERSION = 1

_SQL_TYPE = {"str": "TEXT", "int": "INTEGER", "float": "REAL", "bool": "INTEGER",
             "date": "TEXT", "datetime": "TEXT"}

_PRIMARY = {
    "facilities": "facility_id", "donors": "donor_id", "drives": "drive_id", "donations": "donation_id",
    "units": "unit_id", "transfers": "transfer_id", "requests": "request_id", "power_outages": "outage_id",
}
_COMPOSITE = {
    "routes": ("from_facility_id", "to_facility_id"),
    "daily_stock": ("date", "facility_id", "component", "blood_group"),
}

# Moves follow the state machine in docs/ARCHITECTURE.md.
MOVE_STATES = ("Suggested", "Rejected", "Reserved", "Cancelled", "Blocked", "Dispatched",
               "InTransit", "Received", "ReceivedHeld", "Quarantined")
# A unit may be in at most one move in these states (atomic reservation, duplicate accept fails).
ACTIVE_MOVE_STATES = ("Reserved", "Dispatched", "InTransit", "ReceivedHeld")

DG_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS dg_snapshot_meta (
    as_of TEXT PRIMARY KEY,           -- ISO time with +03:00
    built_at TEXT NOT NULL,
    product_scope TEXT NOT NULL,      -- JSON list of components in the live queue
    units_on_shelf INTEGER NOT NULL,
    daily_stock_total INTEGER NOT NULL,
    reconciliation TEXT NOT NULL      -- JSON: per-cell differences vs daily_stock (empty = match)
);

CREATE TABLE IF NOT EXISTS dg_snapshot_units (
    as_of TEXT NOT NULL REFERENCES dg_snapshot_meta(as_of),
    unit_id TEXT NOT NULL REFERENCES units(unit_id),
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    component TEXT NOT NULL,
    blood_group TEXT,                 -- kept missing if missing, never guessed
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL,
    temp_excursion_exposed INTEGER NOT NULL,
    on_shelf_since TEXT,              -- receipt time or release date; NULL if unconfirmed
    receipt_status TEXT NOT NULL CHECK (receipt_status IN
        ('never_moved', 'received', 'unconfirmed')),
    released_on TEXT,                 -- donations.tested_date (or collection date for opening stock)
    PRIMARY KEY (as_of, unit_id)
);

CREATE TABLE IF NOT EXISTS dg_cold_chain_flags (
    flag_id TEXT PRIMARY KEY,
    flag_type TEXT NOT NULL CHECK (flag_type IN
        ('fridge_excursion', 'outage_no_backup', 'coolbox_excursion', 'logger_gap',
         'sensor_glitch', 'receipt_unconfirmed', 'official_exposure')),
    scope TEXT NOT NULL CHECK (scope IN ('site', 'unit')),
    facility_id TEXT REFERENCES facilities(facility_id),
    unit_id TEXT REFERENCES units(unit_id),
    start_at TEXT NOT NULL,           -- evidence timestamp (EAT)
    end_at TEXT,
    value REAL,                       -- max temp, outage hours or gap hours
    source_table TEXT NOT NULL,
    source_ref TEXT,
    blocks_suggestion INTEGER NOT NULL,
    note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dg_moves (
    move_id TEXT PRIMARY KEY,
    suggestion_id TEXT,
    unit_id TEXT NOT NULL REFERENCES units(unit_id),
    from_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    to_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    component TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ({", ".join(repr(s) for s in MOVE_STATES)})),
    version INTEGER NOT NULL DEFAULT 1,   -- optimistic lock: every write increments it
    reserved_until TEXT,                  -- lease end (settings: at most 30 minutes)
    policy TEXT,                          -- expiry_aware | nearest | fallback
    fallback INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'accepted'
        CHECK (sync_status IN ('pending_sync', 'accepted', 'rejected_on_reconcile')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (from_facility_id <> to_facility_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS dg_moves_one_active_per_unit ON dg_moves(unit_id)
    WHERE state IN ({", ".join(repr(s) for s in ACTIVE_MOVE_STATES)});
CREATE INDEX IF NOT EXISTS dg_moves_state ON dg_moves(state);

CREATE TABLE IF NOT EXISTS dg_audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,        -- idempotency key (offline sync)
    at TEXT NOT NULL,                     -- server time with offset
    actor_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('coordinator', 'sender', 'receiver', 'safety', 'operator', 'system')),
    action TEXT NOT NULL,
    move_id TEXT REFERENCES dg_moves(move_id),
    unit_id TEXT,
    from_state TEXT,
    to_state TEXT,
    reason TEXT,
    payload_json TEXT,
    prev_hash TEXT,
    hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS dg_audit_chain_link BEFORE INSERT ON dg_audit_events
WHEN NEW.prev_hash IS NOT (SELECT hash FROM dg_audit_events ORDER BY seq DESC LIMIT 1)
BEGIN SELECT RAISE(ABORT, 'dg_audit_events prev_hash must be the hash of the last event'); END;
CREATE TRIGGER IF NOT EXISTS dg_audit_no_update BEFORE UPDATE ON dg_audit_events
BEGIN SELECT RAISE(ABORT, 'dg_audit_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS dg_audit_no_delete BEFORE DELETE ON dg_audit_events
BEGIN SELECT RAISE(ABORT, 'dg_audit_events is append-only'); END;
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_units_site ON units(current_facility_id, component, blood_group, status)",
    "CREATE INDEX IF NOT EXISTS ix_transfers_unit ON transfers(unit_id, dispatched_at)",
    "CREATE INDEX IF NOT EXISTS ix_requests_site ON requests(facility_id, requested_at)",
    "CREATE INDEX IF NOT EXISTS ix_temp_site ON temperature_logs(facility_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS ix_outages_site ON power_outages(facility_id, start_time)",
]


def official_ddl(name: str) -> str:
    """CREATE TABLE statement of an official table, with its official column names."""
    cols = []
    for col, kind in TABLES[name].items():
        line = f"    {col} {_SQL_TYPE[kind]}"
        if _PRIMARY.get(name) == col:
            line += " PRIMARY KEY"
        cols.append(line)
    if name in _COMPOSITE:
        cols.append(f"    PRIMARY KEY ({', '.join(_COMPOSITE[name])})")
    return f"CREATE TABLE IF NOT EXISTS {name} (\n" + ",\n".join(cols) + "\n);"


class SchemaVersionError(RuntimeError):
    """The database was built by a different version of this schema: rebuild it."""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every table, index and trigger. Safe to run twice on the same schema version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        raise SchemaVersionError(f"database schema v{version}, code expects v{SCHEMA_VERSION}: "
                                 "delete data/processed/damu_grid.sqlite and run python -m pipeline build")
    conn.execute("PRAGMA foreign_keys = ON")
    for name in TABLES:
        conn.execute(official_ddl(name))
    conn.executescript(DG_SCHEMA)
    for stmt in _INDEXES:
        conn.execute(stmt)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


_AUDIT_FIELDS = ("event_id", "at", "actor_id", "role", "action", "move_id", "unit_id", "from_state",
                 "to_state", "reason", "payload_json", "prev_hash")


def _audit_hash(row: dict) -> str:
    """SHA-256 of the canonical JSON of an audit event."""
    canonical = json.dumps({k: row[k] for k in _AUDIT_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_event(conn: sqlite3.Connection, *, event_id: str, at: str, actor_id: str, role: str,
                       action: str, move_id: str | None = None, unit_id: str | None = None,
                       from_state: str | None = None, to_state: str | None = None,
                       reason: str | None = None, payload: dict | None = None) -> str:
    """Append one event to the hash-chained audit trail and return its hash.

    `at` must carry a UTC offset (e.g. 2026-11-10T21:00:00+03:00). Re-sending the same `event_id`
    with the same content is a no-op (offline sync retries); with different content it fails.
    Call it inside the same transaction as the state change it records."""
    if datetime.fromisoformat(at).tzinfo is None:
        raise ValueError("audit timestamps need an explicit offset, e.g. +03:00")
    payload_json = None if payload is None else json.dumps(payload, sort_keys=True, separators=(",", ":"))
    existing = conn.execute("SELECT * FROM dg_audit_events WHERE event_id = ?", (event_id,)).fetchone()
    last = conn.execute("SELECT hash FROM dg_audit_events ORDER BY seq DESC LIMIT 1").fetchone()
    row = dict(event_id=event_id, at=at, actor_id=actor_id, role=role, action=action, move_id=move_id,
               unit_id=unit_id, from_state=from_state, to_state=to_state, reason=reason,
               payload_json=payload_json, prev_hash=last[0] if last else None)
    if existing is not None:
        cols = [d[0] for d in conn.execute("SELECT * FROM dg_audit_events LIMIT 0").description]
        stored = dict(zip(cols, existing, strict=True))
        if all(stored[k] == row[k] for k in _AUDIT_FIELDS if k != "prev_hash"):
            return stored["hash"]
        raise sqlite3.IntegrityError(f"event_id {event_id} already recorded with different content")
    row["hash"] = _audit_hash(row)
    conn.execute(f"INSERT INTO dg_audit_events ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                 tuple(row.values()))
    return row["hash"]


def verify_audit_chain(conn: sqlite3.Connection) -> tuple[bool, int | None]:
    """Recompute every hash in order. Returns (True, None) or (False, seq of the first bad event)."""
    cur = conn.execute(f"SELECT seq, hash, {', '.join(_AUDIT_FIELDS)} FROM dg_audit_events ORDER BY seq")
    prev = None
    for seq, stored_hash, *values in cur:
        row = dict(zip(_AUDIT_FIELDS, values, strict=True))
        if row["prev_hash"] != prev or _audit_hash(row) != stored_hash:
            return False, seq
        prev = stored_hash
    return True, None


def _to_sql_frame(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Convert typed pandas columns to SQLite-friendly text, integers and None."""
    out = df.copy()
    for col, kind in TABLES[name].items():
        s = out[col]
        if kind == "date":
            out[col] = s.dt.strftime("%Y-%m-%d").astype(object).where(s.notna(), None)
        elif kind == "datetime":
            out[col] = s.dt.strftime("%Y-%m-%d %H:%M:%S").astype(object).where(s.notna(), None)
        else:
            out[col] = s.astype(object).where(s.notna(), None)
            if kind == "bool":
                out[col] = out[col].map(lambda v: None if v is None else int(v))
    return out


def write_official(conn: sqlite3.Connection, tables: dict[str, pd.DataFrame]) -> None:
    """Replace the content of the official tables with the validated frames. Derived dg_ rows that
    point at official rows (snapshot, moves, flags) are kept; foreign keys are checked after the reload
    and any dangling reference fails the build."""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        _replace_official(conn, tables)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        raise sqlite3.IntegrityError(f"{len(broken)} references broken after reload, e.g. {broken[:3]}")


def _replace_official(conn: sqlite3.Connection, tables: dict[str, pd.DataFrame]) -> None:
    """Delete and reload the official tables from the validated frames."""
    for name, df in tables.items():
        frame = _to_sql_frame(df, name)
        conn.execute(f"DELETE FROM {name}")
        cols = list(TABLES[name])
        conn.executemany(
            f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            frame[cols].itertuples(index=False, name=None),
        )
    conn.commit()


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the SQLite database (creating its folder) with foreign keys enforced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
