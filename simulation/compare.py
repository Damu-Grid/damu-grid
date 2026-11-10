"""One-shot seven-day synthetic comparison of two transfer rankings.

This is a small scenario experiment, not a historical replay or patient outcome model.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from forecasting.config import KNOWN_GROUPS, RAW_DIR

START = date(2026, 11, 1)
SEEDS = tuple(range(4000, 4030))


@dataclass(frozen=True)
class Unit:
    id: str
    site: str
    group: str
    expiry: date


def read_csv(raw_dir: Path, name: str):
    with (raw_dir / name).open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def inputs(raw_dir: Path = RAW_DIR):
    units = [Unit(r["unit_id"], r["current_facility_id"], r["blood_group"],
                  date.fromisoformat(r["expiry_date"])) for r in read_csv(raw_dir, "units.csv")
             if r["component"] == "RBC" and r["blood_group"] in KNOWN_GROUPS
             and r["status"] == "in_stock" and r["temp_excursion_exposed"] == "False"
             and r["expiry_date"] > "2026-10-31"]
    routes = {(r["from_facility_id"], r["to_facility_id"]): float(r["typical_travel_hours"])
              for r in read_csv(raw_dir, "routes.csv") if r["typical_travel_hours"]}
    hospitals = {r["facility_id"] for r in read_csv(raw_dir, "facilities.csv")
                 if r["facility_type"].endswith("hospital") or
                 r["facility_type"] in {"national_referral", "county_referral"}}
    counts = defaultdict(int)
    for r in read_csv(raw_dir, "requests.csv"):
        if (r["facility_id"] in hospitals and r["component_requested"] == "RBC"
            and r["patient_blood_group"] in KNOWN_GROUPS
            and "2026-10-04" <= r["requested_at"][:10] <= "2026-10-31"):
            counts[r["facility_id"], r["patient_blood_group"]] += int(r["units_requested"])
    rates = {key: value / 28 for key, value in counts.items()}
    return units, routes, hospitals, rates


def plan(units, routes, hospitals, rates, policy):
    """Select only exact-group RBC moves; retain a two-day sender reserve."""
    stock = defaultdict(list)
    for unit in units:
        stock[unit.site, unit.group].append(unit)
    for group in stock.values():
        group.sort(key=lambda u: (u.expiry, u.id))
    proposed = []
    for (site, group), inventory in list(stock.items()):
        reserve = max(1, math.ceil(2 * rates.get((site, group), 0)))
        for unit in inventory[: max(0, len(inventory) - reserve)]:
            if unit.expiry > START + timedelta(days=7):
                continue
            for dest in hospitals:
                hours = routes.get((site, dest))
                if not hours or dest == site or unit.expiry <= START + timedelta(days=1):
                    continue
                gap = math.ceil(7 * rates.get((dest, group), 0)) - len(stock[dest, group])
                if gap <= 0:
                    continue
                rank = hours if policy == "nearest" else (
                    -gap / max(1, (unit.expiry - START).days) + hours / 100
                )
                proposed.append((rank, hours, unit.id, unit, dest))
    proposed.sort(key=lambda r: (r[0], r[1], r[2], r[4]))
    selected = []
    moved = set()
    outbound = defaultdict(int)
    inbound = defaultdict(int)
    for _, _, _, unit, dest in proposed:
        source_key = (unit.site, unit.group)
        dest_key = (dest, unit.group)
        reserve = max(1, math.ceil(2 * rates.get(source_key, 0)))
        if (unit.id in moved or len(stock[source_key]) - outbound[source_key] <= reserve
            or math.ceil(7 * rates.get(dest_key, 0)) <= len(stock[dest_key]) + inbound[dest_key]):
            continue
        selected.append((unit, dest))
        moved.add(unit.id)
        outbound[source_key] += 1
        inbound[dest_key] += 1
    return selected


def replay(units, transfers, demand):
    stock = defaultdict(list)
    moved_ids = {unit.id for unit, _ in transfers}
    for unit in units:
        if unit.id not in moved_ids:
            stock[unit.site, unit.group].append(unit)
    unmet = expired = 0
    for day in range(7):
        today = START + timedelta(days=day)
        if day == 1:
            for unit, dest in transfers:
                stock[dest, unit.group].append(unit)
        keys = set(stock) | {(site, group) for d, site, group in demand if d == day}
        for key in keys:
            inventory = stock[key]
            valid = [unit for unit in inventory if unit.expiry > today]
            expired += len(inventory) - len(valid)
            valid.sort(key=lambda unit: (unit.expiry, unit.id))
            requested = demand.get((day, *key), 0)
            supplied = min(requested, len(valid))
            unmet += requested - supplied
            stock[key] = valid[supplied:]
    return {"unmet": unmet, "expired": expired, "moved": len(transfers),
            "route_batches": len({(unit.site, dest) for unit, dest in transfers})}


def compare(raw_dir: Path = RAW_DIR, seeds=SEEDS):
    units, routes, hospitals, rates = inputs(raw_dir)
    policies = {policy: plan(units, routes, hospitals, rates, policy)
                for policy in ("nearest", "expiry_aware")}
    output = {policy: [] for policy in policies}
    for seed in seeds:
        rng = np.random.default_rng(seed)
        demand = {(day, site, group): int(rng.poisson(rates.get((site, group), 0)))
                  for day in range(7) for site in sorted(hospitals) for group in KNOWN_GROUPS}
        for policy, transfers in policies.items():
            output[policy].append(replay(units, transfers, demand))
    return {"source": "official synthetic closing inventory and October request rates",
            "scenario": (
                "seven days, no replenishment, all proposed moves accepted, "
                "next-day arrival"
            ),
            "seeds": list(seeds), "policies": {
                policy: {key: float(np.mean([row[key] for row in records]))
                         for key in ("unmet", "expired", "moved", "route_batches")}
                for policy, records in output.items()}}


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
