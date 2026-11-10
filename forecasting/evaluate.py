"""Frozen seven-day synthetic RBC request forecast comparison.

Origins: 1 July through 21 October 2026, every seven days. Every prediction
uses requests strictly before its origin. No operational stock is inferred.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")
HOSPITAL_TYPES = {"county_referral", "county_hospital", "national_referral",
                  "private_hospital", "maternity_hospital", "mission_hospital",
                  "sub_county_hospital"}


def load():
    with (ROOT / "data/raw/facilities.csv").open(newline="", encoding="utf-8") as stream:
        hospitals = {r["facility_id"] for r in csv.DictReader(stream)
                     if r["facility_type"] in HOSPITAL_TYPES}
    counts = defaultdict(float)
    excluded_unknown = 0
    with (ROOT / "data/raw/requests.csv").open(newline="", encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            if r["facility_id"] not in hospitals or r["component_requested"] != "RBC":
                continue
            if r["patient_blood_group"] not in GROUPS:
                excluded_unknown += 1
                continue
            counts[dt.date.fromisoformat(r["requested_at"][:10]), r["facility_id"],
                   r["patient_blood_group"]] += int(r["units_requested"])
    return sorted(hospitals), counts, excluded_unknown


def evaluate():
    hospitals, counts, excluded = load()
    start = dt.date(2026, 7, 1)
    last = dt.date(2026, 10, 21)
    origins = []
    while start <= last:
        origins.append(start)
        start += dt.timedelta(days=7)
    squared = [0., 0.]
    absolute = [0., 0.]
    n = 0
    for origin in origins:
        window = [origin - dt.timedelta(days=i) for i in range(1, 29)]
        future = [origin + dt.timedelta(days=i) for i in range(7)]
        group_total = {g: sum(counts[d, h, g] for d in window for h in hospitals) for g in GROUPS}
        network_total = sum(group_total.values())
        for h in hospitals:
            site_total = sum(counts[d, h, g] for d in window for g in GROUPS)
            for g in GROUPS:
                baseline = 7 / 28 * sum(counts[d, h, g] for d in window)
                candidate = 7 / 28 * site_total * group_total[g] / network_total if network_total else 0
                actual = sum(counts[d, h, g] for d in future)
                for idx, estimate in enumerate((baseline, candidate)):
                    squared[idx] += (estimate - actual) ** 2
                    absolute[idx] += abs(estimate - actual)
                n += 1
    return {"data_origin": "official synthetic starter dataset", "scope": "hospital RBC known exact groups",
            "origins": len(origins), "first_origin": origins[0].isoformat(),
            "last_origin": origins[-1].isoformat(), "horizon_days": 7,
            "sample_size": n, "excluded_unknown_group_rbc_requests": excluded,
            "reporting_assumption": "No request row is treated as zero observed demand; reporting completeness is unverified",
            "baseline_28_day": {"rmse": math.sqrt(squared[0] / n), "mae": absolute[0] / n},
            "pooled_candidate": {"rmse": math.sqrt(squared[1] / n), "mae": absolute[1] / n}}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
