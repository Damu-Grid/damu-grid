"""DG-05: the deliberate data-quality problems of the official dataset, handled so that none of them
silently becomes a clinical fact (data/raw/README.md, "Deliberate data quality problems").

- Requests are keyed by `facility_id`; `facility_name_raw` is kept as typed and only compared.
- Unknown patient blood groups stay `unknown`.
- A transfer without `received_at` is incomplete evidence; no receipt time is ever filled in.
- Temperature readings of -99.0, 99.9 or 0.0 are sensor glitches, not excursions.
- Logger silences are reported as gaps (missing evidence), not as "no problem".
- Donor records that look like the same person are reported, never merged automatically.
"""

from __future__ import annotations

import pandas as pd

from pipeline.config import PipelineConfig


def _normalise_name(s: pd.Series) -> pd.Series:
    return s.str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()


def requests_with_facility_check(requests: pd.DataFrame, facilities: pd.DataFrame) -> pd.DataFrame:
    """Add `facility_name` (official) and `name_variant`: exact, case_or_spacing, or other.
    The key stays `facility_id`; the typed name is never used for joins."""
    official = facilities.set_index("facility_id")["name"]
    out = requests.copy()
    out["facility_name"] = out["facility_id"].map(official)
    raw, ref = out["facility_name_raw"].fillna(""), out["facility_name"].fillna("")
    variant = pd.Series("other", index=out.index, dtype="string")
    variant[_normalise_name(raw) == _normalise_name(ref)] = "case_or_spacing"
    variant[raw == ref] = "exact"
    out["name_variant"] = variant
    out["patient_group_known"] = out["patient_blood_group"].ne("unknown") & out["patient_blood_group"].notna()
    return out


def transfers_with_receipt_evidence(transfers: pd.DataFrame) -> pd.DataFrame:
    """`receipt_status` is received or unconfirmed; `transit_hours` only exists when received."""
    out = transfers.copy()
    out["receipt_status"] = out["received_at"].notna().map({True: "received", False: "unconfirmed"})
    out["transit_hours"] = (out["received_at"] - out["dispatched_at"]) / pd.Timedelta(hours=1)
    return out


def classify_temperatures(logs: pd.DataFrame, config: PipelineConfig, component: str = "RBC") -> pd.DataFrame:
    """Label each fridge reading: glitch, in_range, above_range or below_range (range of `component`)."""
    pol = config.policy(component)
    out = logs.copy()
    t = out["temp_c"]
    cls = pd.Series("in_range", index=out.index, dtype="string")
    cls[t > pol.storage_max_c] = "above_range"
    cls[t < pol.storage_min_c] = "below_range"
    cls[t.isin(config.glitch_values)] = "glitch"  # checked last: a glitch is never an excursion
    cls[t.isna()] = "missing"
    out["reading_class"] = cls
    return out


def logger_gaps(logs: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    """Silences longer than `config.logger_gap_hours` between two hourly readings of the same fridge.
    Returns facility_id, gap_start (last reading), gap_end (next reading), missing_hours."""
    ordered = logs.sort_values(["facility_id", "recorded_at"])
    nxt = ordered.groupby("facility_id")["recorded_at"].shift(-1)
    hours = (nxt - ordered["recorded_at"]) / pd.Timedelta(hours=1) - 1
    gaps = ordered.assign(gap_end=nxt, missing_hours=hours)
    gaps = gaps[gaps["missing_hours"] >= config.logger_gap_hours]
    return gaps.rename(columns={"recorded_at": "gap_start"})[
        ["facility_id", "gap_start", "gap_end", "missing_hours"]].reset_index(drop=True)


def possible_duplicate_donors(donors: pd.DataFrame) -> pd.DataFrame:
    """Donor ids sharing birth date, sex, county and phone last 4 digits (official README rule).
    For review only: records are never merged automatically."""
    keys = ["birth_date", "sex", "home_county", "phone_last4"]
    full = donors.dropna(subset=keys)
    dup = full[full.duplicated(keys, keep=False)].sort_values(keys)
    dup = dup.assign(match_group=dup.groupby(keys, sort=False).ngroup())
    return dup[["match_group", "donor_id", *keys]].reset_index(drop=True)


def quality_report(tables: dict[str, pd.DataFrame], config: PipelineConfig) -> dict[str, int | float]:
    """Counts behind each deliberate problem, for docs/DATA.md and the demo."""
    out: dict[str, int | float] = {}
    if {"requests", "facilities"} <= tables.keys():
        r = requests_with_facility_check(tables["requests"], tables["facilities"])
        out["requests"] = len(r)
        out["requests_name_not_exact"] = int((r["name_variant"] != "exact").sum())
        out["requests_name_case_or_spacing"] = int((r["name_variant"] == "case_or_spacing").sum())
        out["requests_name_other_variant"] = int((r["name_variant"] == "other").sum())
        em = r[r["urgency"] == "emergency"]
        out["emergency_requests"] = len(em)
        out["emergency_requests_group_unknown"] = int((~em["patient_group_known"]).sum())
        out["requests_group_unknown"] = int((~r["patient_group_known"]).sum())
    if "transfers" in tables:
        t = transfers_with_receipt_evidence(tables["transfers"])
        out["transfers"] = len(t)
        out["transfers_receipt_unconfirmed"] = int((t["receipt_status"] == "unconfirmed").sum())
    if "temperature_logs" in tables:
        logs = classify_temperatures(tables["temperature_logs"], config)
        counts = logs["reading_class"].value_counts()
        for cls in ("in_range", "above_range", "below_range", "glitch", "missing"):
            out[f"temperature_{cls}"] = int(counts.get(cls, 0))
        for value in config.glitch_values:
            out[f"temperature_glitch_{value}"] = int((logs["temp_c"] == value).sum())
        gaps = logger_gaps(tables["temperature_logs"], config)
        out["logger_gaps"] = len(gaps)
        out["logger_gap_hours_total"] = float(gaps["missing_hours"].sum())
    if "donors" in tables:
        d = tables["donors"]
        dup = possible_duplicate_donors(d)
        out["donors"] = len(d)
        out["donors_group_missing"] = int(d["blood_group"].isna().sum())
        out["donor_records_in_possible_duplicate_sets"] = len(dup)
        out["possible_duplicate_sets"] = int(dup["match_group"].nunique())
    return out
