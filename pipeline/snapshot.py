"""DG-03: the closing snapshot (as-of end of 31 October 2026) without leakage.

Units on the shelf at the as-of time are the `units` rows with `status = in_stock` at
`current_facility_id` and `expiry_date` after the as-of time, minus anything the data only
shows *after* the as-of time:

- a unit whose last transfer was received after the as-of time was still in transit;
- a unit whose donation was tested after the as-of time was not yet released.

`current_facility_id` and `status` are year-end values, so this snapshot is only valid at the end
of the data. Asking for an earlier as-of raises `LeakageError` instead of reconstructing history
from final locations (docs/DATA.md, snapshot convention). The result is reconciled with
`daily_stock` for the same date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from pipeline.config import PipelineConfig


class LeakageError(ValueError):
    """The requested as-of time would use information from after it."""


@dataclass
class Snapshot:
    """The closing snapshot: units on the shelf, exclusions and daily_stock check."""
    as_of: pd.Timestamp                      # naive EAT, as in the official data
    as_of_iso: str                           # with +03:00 offset
    units: pd.DataFrame                      # one row per unit on the shelf
    excluded: pd.DataFrame                   # in_stock rows not counted, with reason
    reconciliation: pd.DataFrame             # cells where units and daily_stock differ
    daily_stock_total: int = 0
    counts: dict[str, int] = field(default_factory=dict)

    def summary_lines(self) -> list[str]:
        """Human-readable counts for the build command."""
        lines = [f"as-of {self.as_of_iso}"]
        lines += [f"  {k}: {v:,}" for k, v in self.counts.items()]
        lines.append(f"  daily_stock total on {self.as_of.date()}: {self.daily_stock_total:,}")
        lines.append("  reconciliation with daily_stock: "
                     + ("all cells match" if self.reconciliation.empty
                        else f"{len(self.reconciliation)} cells differ"))
        return lines


def _as_of(config: PipelineConfig) -> tuple[pd.Timestamp, str]:
    """Return the as-of time as a naive EAT timestamp and as ISO 8601 with offset."""
    aware = datetime.fromisoformat(config.as_of)
    naive = pd.Timestamp(aware.replace(tzinfo=None))
    return naive, aware.isoformat()


def check_no_leakage(as_of: pd.Timestamp, tables: dict[str, pd.DataFrame]) -> None:
    """Final unit locations describe the end of the data. Refuse an as-of before the last recorded
    movement or status change, which would place units where they were only later."""
    last_status = tables["units"]["status_date"].max()
    last_dispatch = tables["transfers"]["dispatched_at"].max()
    latest = max(t for t in (last_status, last_dispatch) if pd.notna(t))
    if as_of < latest:
        raise LeakageError(
            f"as-of {as_of} is before the last recorded event {latest}: year-end locations would leak "
            "into the past. Only the closing snapshot is supported."
        )


def build_snapshot(tables: dict[str, pd.DataFrame], config: PipelineConfig) -> Snapshot:
    """Build the closing snapshot at the as-of time without using later information."""
    as_of, as_of_iso = _as_of(config)
    check_no_leakage(as_of, tables)
    units = tables["units"]
    transfers = tables["transfers"]
    tested = tables["donations"].set_index("donation_id")["tested_date"]

    cand = units[units["status"].eq("in_stock")].copy()
    cand["released_on"] = cand["donation_id"].map(tested)
    # Opening stock may predate the testing records; fall back to the collection date.
    cand["released_on"] = cand["released_on"].fillna(cand["collection_date"])

    moved = transfers[transfers["dispatched_at"] <= as_of].sort_values("dispatched_at")
    last = moved.groupby("unit_id").tail(1).set_index("unit_id")
    last = last.reindex(cand["unit_id"])
    cand["last_to"] = last["to_facility_id"].to_numpy()
    cand["received_at"] = last["received_at"].to_numpy()
    has_move = last["transfer_id"].notna().to_numpy()

    reason = pd.Series(pd.NA, index=cand.index, dtype="string")
    reason[cand["expiry_date"] <= as_of.normalize()] = "expired_by_as_of"
    reason[reason.isna() & (cand["released_on"] > as_of)] = "released_after_as_of"
    reason[reason.isna() & has_move & (cand["received_at"] > as_of)] = "in_transit_at_as_of"
    reason[reason.isna() & has_move & (cand["last_to"] != cand["current_facility_id"])] = "location_conflict"

    receipt = pd.Series("never_moved", index=cand.index, dtype="string")
    receipt[has_move & cand["received_at"].notna()] = "received"
    receipt[has_move & cand["received_at"].isna()] = "unconfirmed"  # never fabricate a receipt time
    cand["receipt_status"] = receipt
    cand["on_shelf_since"] = cand["received_at"].where(has_move, cand["released_on"])

    keep = reason.isna()
    shelf = cand.loc[keep, ["unit_id", "current_facility_id", "component", "blood_group", "expiry_date",
                            "status", "temp_excursion_exposed", "on_shelf_since", "receipt_status",
                            "released_on", "collection_date", "processed_at_id"]]
    shelf = shelf.rename(columns={"current_facility_id": "facility_id"}).reset_index(drop=True)
    excluded = cand.loc[~keep, ["unit_id", "current_facility_id", "component"]].assign(
        reason=reason[~keep]).reset_index(drop=True)

    ds = tables["daily_stock"]
    ds_day = ds[ds["date"] == as_of.normalize()]
    keys = ["facility_id", "component", "blood_group"]
    a = ds_day.groupby(keys)["units_in_stock_end_of_day"].sum().astype(int)
    b = shelf.groupby(keys).size()
    rec = pd.concat([a, b], axis=1, keys=["daily_stock", "units"]).fillna(0).astype(int)
    rec = rec[rec["daily_stock"] != rec["units"]].reset_index()

    counts = {
        "in_stock rows in units.csv": len(cand),
        "on the shelf at as-of": len(shelf),
        **{f"excluded: {k}": int(v) for k, v in excluded["reason"].value_counts().items()},
        "receipt unconfirmed (kept, flagged)": int((shelf["receipt_status"] == "unconfirmed").sum()),
        "officially exposed (kept, flagged)": int(shelf["temp_excursion_exposed"].fillna(True).sum()),
    }
    return Snapshot(as_of, as_of_iso, shelf, excluded, rec, int(a.sum()), counts)


def write_snapshot(conn, snap: Snapshot, config: PipelineConfig) -> None:
    """Store the snapshot in dg_snapshot_meta and dg_snapshot_units."""
    conn.execute("DELETE FROM dg_snapshot_units WHERE as_of = ?", (snap.as_of_iso,))
    conn.execute("DELETE FROM dg_snapshot_meta WHERE as_of = ?", (snap.as_of_iso,))
    conn.execute(
        "INSERT INTO dg_snapshot_meta VALUES (?, ?, ?, ?, ?, ?)",
        (snap.as_of_iso, datetime.now().astimezone().isoformat(timespec="seconds"),
         json.dumps(list(config.enabled_components())), len(snap.units), snap.daily_stock_total,
         snap.reconciliation.to_json(orient="records")),
    )

    def _d(v, fmt):
        """Format a timestamp with `fmt`, or None if missing."""
        return None if pd.isna(v) else pd.Timestamp(v).strftime(fmt)

    rows = [
        (snap.as_of_iso, r.unit_id, r.facility_id, r.component,
         None if pd.isna(r.blood_group) else r.blood_group, _d(r.expiry_date, "%Y-%m-%d"), r.status,
         int(bool(r.temp_excursion_exposed)) if pd.notna(r.temp_excursion_exposed) else 1,
         _d(r.on_shelf_since, "%Y-%m-%d %H:%M:%S"), r.receipt_status, _d(r.released_on, "%Y-%m-%d"))
        for r in snap.units.itertuples(index=False)
    ]
    conn.executemany("INSERT INTO dg_snapshot_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
