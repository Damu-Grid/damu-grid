"""DG-02: the one SQLite schema shared by the pipeline, the API (Timi) and the evaluator (Blessings).

- Official tables keep their official names and column names (data/raw/DATA_DICTIONARY.md).
- Everything Damu Grid adds is prefixed `dg_` so it can never be mistaken for official data.
- Recommendation logic stays out of the movement tables: `dg_moves` only records the human
  decision and the physical steps (reserve, dispatch, receive), never a model score.
- The audit trail is append-only at database level (UPDATE and DELETE are refused).

Timestamps are stored as ISO 8601 text. Official timestamps are EAT without an offset (as in the
CSVs); new `dg_` records must carry an explicit offset, e.g. 2026-11-10T21:00:00+03:00.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from pipeline.schema import TABLES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "damu_grid.sqlite"

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
    cols = []
    for col, kind in TABLES[name].items():
        line = f"    {col} {_SQL_TYPE[kind]}"
        if _PRIMARY.get(name) == col:
            line += " PRIMARY KEY"
        cols.append(line)
    if name in _COMPOSITE:
        cols.append(f"    PRIMARY KEY ({', '.join(_COMPOSITE[name])})")
    return f"CREATE TABLE IF NOT EXISTS {name} (\n" + ",\n".join(cols) + "\n);"


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every table, index and trigger. Safe to run twice."""
    conn.execute("PRAGMA foreign_keys = ON")
    for name in TABLES:
        conn.execute(official_ddl(name))
    conn.executescript(DG_SCHEMA)
    for stmt in _INDEXES:
        conn.execute(stmt)
    conn.commit()


def _to_sql_frame(df: pd.DataFrame, name: str) -> pd.DataFrame:
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
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
