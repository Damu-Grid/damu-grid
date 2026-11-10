"""DG-07 (Tier 2): cold-chain and power evidence for sites and for the units on their shelves.

Sources: `temperature_logs` (hourly fridge readings), `power_outages`, `transfers.coolbox_max_temp_c`
and the official `units.temp_excursion_exposed`. Ranges from the data dictionary: RBC/WB fridge 2-6 C,
cool box above 10 C is an excursion. Durations and thresholds are settings (pipeline/config.py).

Flag types:
- fridge_excursion   consecutive readings out of range for at least `excursion_min_hours`
- outage_no_backup   power cut of at least `outage_min_hours` with no backup on the blood fridge
- logger_gap         the fridge logger was silent for at least `logger_gap_hours` (missing evidence)
- coolbox_excursion  a cool box above `coolbox_max_c` on one of the unit's trips
- receipt_unconfirmed  the unit's last receipt was never confirmed, so its shelf time is unknown
- official_exposure  `temp_excursion_exposed = True` in the official data
- sensor_glitch      -99.0, 99.9 or 0.0 readings; informational, never a clinical event

A site event becomes a unit flag only if it happened while the unit was on that shelf (from its
receipt or release to the as-of time). Flags only ever add caution: nothing here can mark a unit
safe or clear a quarantine, and incomplete evidence is itself a flag.
"""

from __future__ import annotations

import pandas as pd

from pipeline.config import PipelineConfig
from pipeline.quality import classify_temperatures, logger_gaps

FLAG_COLUMNS = ["flag_id", "flag_type", "scope", "facility_id", "unit_id", "start_at", "end_at", "value",
                "source_table", "source_ref", "blocks_suggestion", "note"]


def fridge_excursions(logs: pd.DataFrame, config: PipelineConfig, component: str = "RBC") -> pd.DataFrame:
    """Runs of consecutive hourly out-of-range readings. Glitches and gaps break a run."""
    classified = classify_temperatures(logs, config, component)
    out_of_range = classified[classified["reading_class"].isin(["above_range", "below_range"])]
    out_of_range = out_of_range.sort_values(["facility_id", "recorded_at"])
    if out_of_range.empty:
        return pd.DataFrame(columns=["facility_id", "start_at", "end_at", "hours", "peak_c"])
    pol = config.policy(component)
    prev = out_of_range.groupby("facility_id")["recorded_at"].shift()
    new_run = (out_of_range["recorded_at"] - prev).ne(pd.Timedelta(hours=1))
    # Peak = the reading furthest outside the safe range (above the maximum or below the minimum).
    t = out_of_range["temp_c"].astype(float)
    outside = (t - pol.storage_max_c).clip(lower=0) + (pol.storage_min_c - t).clip(lower=0)
    out_of_range = out_of_range.assign(run=new_run.cumsum(), outside=outside)
    peak_idx = out_of_range.groupby("run")["outside"].idxmax()
    runs = out_of_range.groupby("run").agg(
        facility_id=("facility_id", "first"), start_at=("recorded_at", "min"),
        last=("recorded_at", "max"), hours=("recorded_at", "size"),
    )
    runs["peak_c"] = out_of_range.loc[peak_idx.to_numpy(), "temp_c"].to_numpy()
    runs = runs[runs["hours"] >= config.excursion_min_hours]
    runs["end_at"] = runs["last"] + pd.Timedelta(hours=1)
    return runs[["facility_id", "start_at", "end_at", "hours", "peak_c"]].reset_index(drop=True)


def site_flags(tables: dict[str, pd.DataFrame], config: PipelineConfig) -> pd.DataFrame:
    """Site-level evidence with timestamps."""
    rows = []
    ex = fridge_excursions(tables["temperature_logs"], config)
    for r in ex.itertuples(index=False):
        rows.append(("fridge_excursion", r.facility_id, None, r.start_at, r.end_at, float(r.peak_c),
                     "temperature_logs", None,
                     f"{r.hours} consecutive hourly readings outside 2-6 C, peak {r.peak_c} C"))
    po = tables["power_outages"]
    po = po[(po["backup_power_engaged"] == False) & (po["duration_hours"] >= config.outage_min_hours)]  # noqa: E712
    for r in po.itertuples(index=False):
        rows.append(("outage_no_backup", r.facility_id, None, r.start_time, r.end_time,
                     float(r.duration_hours), "power_outages", r.outage_id,
                     f"power cut of {r.duration_hours} h with no backup on the blood fridge"))
    gaps = logger_gaps(tables["temperature_logs"], config)
    for r in gaps.itertuples(index=False):
        rows.append(("logger_gap", r.facility_id, None, r.gap_start, r.gap_end, float(r.missing_hours),
                     "temperature_logs", None,
                     f"no fridge reading for {int(r.missing_hours)} h: temperature unknown"))
    logs = classify_temperatures(tables["temperature_logs"], config)
    for r in logs[logs["reading_class"] == "glitch"].itertuples(index=False):
        rows.append(("sensor_glitch", r.facility_id, None, r.recorded_at, None, float(r.temp_c),
                     "temperature_logs", None, f"sensor glitch value {r.temp_c}; not a clinical event"))
    return _frame(rows, "site", config)


def unit_flags(snapshot_units: pd.DataFrame, tables: dict[str, pd.DataFrame], config: PipelineConfig,
               as_of: pd.Timestamp, sites: pd.DataFrame | None = None) -> pd.DataFrame:
    """Evidence attached to units on the shelf at the as-of time."""
    sites = site_flags(tables, config) if sites is None else sites
    units = snapshot_units
    rows = []

    t = tables["transfers"]
    hot = t[(t["coolbox_max_temp_c"] > config.coolbox_max_c) & t["unit_id"].isin(units["unit_id"])
            & (t["dispatched_at"] <= as_of)]
    for r in hot.itertuples(index=False):
        rows.append(("coolbox_excursion", r.to_facility_id, r.unit_id, r.dispatched_at, r.received_at,
                     float(r.coolbox_max_temp_c), "transfers", r.transfer_id,
                     f"cool box reached {r.coolbox_max_temp_c} C (limit {config.coolbox_max_c} C)"))
    for r in units[units["temp_excursion_exposed"].fillna(True).astype(bool)].itertuples(index=False):
        rows.append(("official_exposure", r.facility_id, r.unit_id, as_of, None, None, "units", r.unit_id,
                     "temp_excursion_exposed is True (or not recorded) in the official data"))
    for r in units[units["receipt_status"] == "unconfirmed"].itertuples(index=False):
        rows.append(("receipt_unconfirmed", r.facility_id, r.unit_id, as_of, None, None, "transfers",
                     r.unit_id, "last receipt never confirmed: time on this shelf unknown"))

    # Fridge logs and fridge backup power only describe components kept in the 2-6 C blood fridge
    # (RBC, WB). Frozen plasma and platelets have no storage evidence in this dataset.
    in_fridge = [c for c, p in config.components.items() if p.storage_max_c is not None]
    stays = custody_intervals(units[units["component"].isin(in_fridge)], t, as_of)
    events = sites.loc[sites["flag_type"] != "sensor_glitch"].drop(columns=["unit_id"])
    joined = stays.merge(events, on="facility_id")
    end = joined["end_at"].fillna(joined["start_at"])
    during = (end >= joined["stay_start"]) & (joined["start_at"] <= joined["stay_end"])
    for r in joined[during].itertuples(index=False):
        where = "on this shelf" if r.facility_id == r.current_facility_id else f"at {r.facility_id}"
        rows.append((r.flag_type, r.facility_id, r.unit_id, r.start_at, r.end_at, r.value,
                     r.source_table, r.source_ref, f"while {where}: {r.note}"))
    return _frame(rows, "unit", config)


def custody_intervals(units: pd.DataFrame, transfers: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Where each unit was, and when, from its own time-stamped history (not from its final location):
    at the processing centre from release to the first dispatch, then at each destination from the
    recorded receipt to the next dispatch or the as-of time. A stay that starts with an unconfirmed
    receipt has no known start and is left out (the unit is already flagged `receipt_unconfirmed`)."""
    moves = transfers[transfers["unit_id"].isin(units["unit_id"]) & (transfers["dispatched_at"] <= as_of)]
    moves = moves.sort_values(["unit_id", "dispatched_at"])
    first_dispatch = moves.groupby("unit_id")["dispatched_at"].first()
    home = pd.DataFrame({
        "unit_id": units["unit_id"].to_numpy(),
        "facility_id": units["processed_at_id"].to_numpy(),
        "stay_start": pd.to_datetime(units["released_on"]).to_numpy(),
    })
    home["stay_end"] = home["unit_id"].map(first_dispatch).fillna(as_of)
    later = moves.assign(stay_end=moves.groupby("unit_id")["dispatched_at"].shift(-1).fillna(as_of))
    later = later.rename(columns={"to_facility_id": "facility_id", "received_at": "stay_start"})
    later = later[later["stay_start"].notna()][["unit_id", "facility_id", "stay_start", "stay_end"]]
    stays = pd.concat([home, later], ignore_index=True)
    current = units.set_index("unit_id")["facility_id"]
    stays["current_facility_id"] = stays["unit_id"].map(current)
    return stays[stays["stay_start"].notna() & (stays["stay_end"] >= stays["stay_start"])]


def agreement_with_official(units: pd.DataFrame, flags: pd.DataFrame) -> dict[str, int]:
    """Compare our site evidence (fridge excursion, outage without backup, logger gap, cool box) with
    the official `temp_excursion_exposed` on the same units. The official flag is the dataset's own
    record, so this checks the method; it does not make either one ground truth for a real unit."""
    evidence = {"fridge_excursion", "outage_no_backup", "logger_gap", "coolbox_excursion"}
    ours = set(flags.loc[flags["flag_type"].isin(evidence), "unit_id"])
    official = units["temp_excursion_exposed"].fillna(False).astype(bool)
    ids = units["unit_id"]
    is_ours = ids.isin(ours)
    return {
        "units_compared": len(units),
        "official_exposed": int(official.sum()),
        "official_exposed_with_our_evidence": int((official & is_ours).sum()),
        "official_exposed_without_our_evidence": int((official & ~is_ours).sum()),
        "our_evidence_not_officially_exposed": int((~official & is_ours).sum()),
        "neither": int((~official & ~is_ours).sum()),
    }


def _frame(rows: list[tuple], scope: str, config: PipelineConfig) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["flag_type", "facility_id", "unit_id", "start_at", "end_at", "value",
                                     "source_table", "source_ref", "note"])
    df["scope"] = scope
    df["blocks_suggestion"] = df["flag_type"].isin(config.blocking_flags)
    df["flag_id"] = [f"{scope}-{i:06d}" for i in range(len(df))]
    return df[FLAG_COLUMNS]


def write_flags(conn, flags: pd.DataFrame) -> None:
    def ts(v):
        return None if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("DELETE FROM dg_cold_chain_flags")
    conn.executemany(
        "INSERT INTO dg_cold_chain_flags VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(r.flag_id, r.flag_type, r.scope, r.facility_id, r.unit_id, ts(r.start_at), ts(r.end_at),
          None if pd.isna(r.value) else float(r.value), r.source_table,
          None if pd.isna(r.source_ref) else r.source_ref, int(r.blocks_suggestion), r.note)
         for r in flags.itertuples(index=False)],
    )
    conn.commit()


# Contract for GET /flags/cold-chain (docs/API_SPEC.md): the backend can run this query as is.
COLD_CHAIN_QUERY = """
SELECT flag_id, flag_type, scope, facility_id, unit_id, start_at AS evidence_at, end_at, value,
       source_table, source_ref, blocks_suggestion, note
FROM dg_cold_chain_flags
WHERE (:facility_id IS NULL OR facility_id = :facility_id)
  AND (:unit_id IS NULL OR unit_id = :unit_id)
  AND flag_type <> 'sensor_glitch'
ORDER BY start_at DESC
"""
