"""Seven-day synthetic redistribution simulation (issues DG-15, DG-16, DG-17).

Compares two transfer rankings -- nearest-site-first vs expiry-aware -- on shared
synthetic demand, with daily restocking from the blood centres and a per-route
courier limit. Red-cell (RBC) requests are served from one pooled queue of RBC
plus whole-blood (WB) units: WB matches ABO-identical requests only (exact group
match), RBC follows standard red-cell compatibility. Every unit keeps its
``product_type`` and waste/movement results are reported separately for WB and RBC.

What is synthetic: the November demand (Poisson draws around October rates plus
one documented surge), the restock group mix draws, and the calibration below.
The closing stock, routes, rates, inflow means and shelf lives come from
``data/raw/``. Nothing here is a claim about real facilities, lives or money.

Time split (mirrors the forecast rule: features use only data strictly before
the test window). TRAIN (everything <= 2026-10-31): October 4-31 demand rates,
October centre inflow means, October network group mix, 31 October closing
snapshot. TEST: synthetic 1-7 November demand. The test window starts after all
forecast evaluation origins (1 Jul-21 Oct 2026), so it is also out-of-sample
relative to the forecast calibration.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from forecasting.config import KNOWN_GROUPS, RAW_DIR

START = date(2026, 11, 1)
HORIZON_DAYS = 7
SEEDS = tuple(range(4000, 4030))  # 30 fixed seeds; shared demand draw per seed
TRAIN_START = date(2026, 10, 4)
TRAIN_END = date(2026, 11, 1)  # exclusive; 28 days strictly before START

# Measured medians of (expiry_date - collection_date) in data/raw/units.csv:
# RBC 42 days, WB 35 days, PLT 5 days. Fresh restock units use these lives.
SHELF_LIFE_DAYS = {"RBC": 42, "WB": 35}

# Measured mean processed units/day/centre over 2026-10-04..31 from
# data/raw/units.csv grouped by (processed_at_id, component) / 28.
# Only RBC and WB restock the hospital queue in this simulation.
CENTRE_INFLOW_PER_DAY = {
    "RBTC-NBO": {"RBC": 16.07, "WB": 6.82},
    "RBTC-MSA": {"RBC": 13.61, "WB": 5.93},
    "RBTC-NKR": {"RBC": 11.32, "WB": 4.93},
    "RBTC-KSM": {"RBC": 10.07, "WB": 3.54},
    "RBTC-ELD": {"RBC": 7.64, "WB": 2.93},
    "RBTC-EMB": {"RBC": 0.00, "WB": 1.36},
}

# Planning assumptions (documented choices, not clinical rules).
RESERVE_DAYS = 2  # sender keeps this many days of compatible demand
FORECAST_LOOKAHEAD_DAYS = 7  # recipient gap measured over this window
SEND_BY_BUFFER_DAYS = 1  # unit must arrive at least this long before expiry
COURIER_CAP_PER_ROUTE_DAY = 6  # max redistribution units per route per day

# Seeded imbalance overlay (synthetic, identical for both policies).
# Donor HSP-001 holds 34 closing WB units expiring on/before 8 Nov 2026
# (A+ 14, O+ 11, B+ 7, AB+ 2; measured from data/raw/units.csv). Recipient
# HSP-004 is 0.48 h away by routes.csv, holds zero closing RBC/WB units, and
# requests ~2.9 RBC units/day. No units were added; the seeding is the choice
# of pair plus a fixed extra-demand surge on days 2-3 in the donor's groups.
IMBALANCE = {
    "donor": "HSP-001",
    "recipient": "HSP-004",
    "surge_days": (2, 3),
    "surge_extra": {"O+": 6, "A+": 6},
}

# Standard red-cell compatibility (donor group -> request groups it can serve).
# Used only to allocate synthetic demand to units, never for clinical matching.
RBC_COMPATIBLE_WITH = {
    "O-": set(KNOWN_GROUPS),
    "O+": {"O+", "A+", "B+", "AB+"},
    "A-": {"A-", "A+", "AB-", "AB+"},
    "A+": {"A+", "AB+"},
    "B-": {"B-", "B+", "AB-", "AB+"},
    "B+": {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},
}


@dataclass
class Unit:
    """One physical unit. ``product`` is the product_type (RBC or WB)."""

    id: str
    site: str
    group: str
    expiry: date
    product: str = "RBC"


@dataclass
class SimInputs:
    units: list[Unit]
    routes: dict[tuple[str, str], float]
    hospitals: set[str]
    rates: dict[tuple[str, str], float]  # (site, group) -> RBC units/day
    group_mix: dict[str, float]  # network request share per group (Oct)
    supply_centre: dict[str, str]  # hospital -> blood centre
    deliveries_per_week: dict[str, int]


def read_csv(raw_dir: Path, name: str):
    with (raw_dir / name).open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def can_serve(unit: Unit, request_group: str) -> bool:
    """Whether a unit may cover one RBC-requested unit of ``request_group``."""
    if unit.product == "WB":
        return unit.group == request_group  # ABO-identical only
    return request_group in RBC_COMPATIBLE_WITH[unit.group]


def transit_days(hours: float) -> int:
    return max(1, math.ceil(hours / 24))


def send_by(unit: Unit, hours: float) -> date:
    """Latest date a unit may be dispatched and still arrive usable.

    send_by = expiry - travel days - buffer. A move is eligible only if it
    arrives on or before ``expiry - SEND_BY_BUFFER_DAYS``.
    """
    return unit.expiry - timedelta(days=transit_days(hours) + SEND_BY_BUFFER_DAYS)


def inputs(raw_dir: Path = RAW_DIR) -> SimInputs:
    """Closing snapshot, routes, pre-START rates, supply mapping (all TRAIN)."""
    units = [
        Unit(
            r["unit_id"],
            r["current_facility_id"],
            r["blood_group"],
            date.fromisoformat(r["expiry_date"]),
            r["component"],
        )
        for r in read_csv(raw_dir, "units.csv")
        if r["component"] in ("RBC", "WB")
        and r["blood_group"] in KNOWN_GROUPS
        and r["status"] == "in_stock"
        and r["temp_excursion_exposed"] == "False"
        and r["expiry_date"] > "2026-10-31"
    ]
    routes = {
        (r["from_facility_id"], r["to_facility_id"]): float(r["typical_travel_hours"])
        for r in read_csv(raw_dir, "routes.csv")
        if r["typical_travel_hours"]
    }
    hospitals: set[str] = set()
    supply_centre: dict[str, str] = {}
    deliveries: dict[str, int] = {}
    for r in read_csv(raw_dir, "facilities.csv"):
        if r["facility_type"].endswith("hospital") or r["facility_type"] in {
            "national_referral",
            "county_referral",
        }:
            hospitals.add(r["facility_id"])
            centre = r["supply_centre_id"] or "RBTC-NBO"
            supply_centre[r["facility_id"]] = centre
            try:
                deliveries[r["facility_id"]] = max(1, int(float(r["routine_deliveries_per_week"])))
            except (TypeError, ValueError):
                deliveries[r["facility_id"]] = 3
    counts: dict[tuple[str, str], int] = defaultdict(int)
    mix_counts: dict[str, int] = defaultdict(int)
    lo, hi = TRAIN_START.isoformat(), TRAIN_END.isoformat()
    for r in read_csv(raw_dir, "requests.csv"):
        day = r["requested_at"][:10]
        if not (lo <= day < hi):
            continue
        if (
            r["facility_id"] in hospitals
            and r["component_requested"] == "RBC"
            and r["patient_blood_group"] in KNOWN_GROUPS
        ):
            counts[r["facility_id"], r["patient_blood_group"]] += int(r["units_requested"])
            mix_counts[r["patient_blood_group"]] += int(r["units_requested"])
    days = (TRAIN_END - TRAIN_START).days
    rates = {key: value / days for key, value in counts.items()}
    total = sum(mix_counts.values()) or 1
    group_mix = {group: mix_counts.get(group, 0) / total for group in KNOWN_GROUPS}
    return SimInputs(units, routes, hospitals, rates, group_mix, supply_centre, deliveries)


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def survival_score(units: list[Unit], unit: Unit, rates: dict[tuple[str, str], float],
                   today: date) -> float:
    """Model P(this unit is used before it expires if it stays put).

    Normal approximation to P(Poisson(compatible demand over the remaining
    life) >= units ahead of it in FEFO order). A planning aid with the same
    field names as the API's ``survival_score_if_stays`` /
    ``survival_score_if_moved`` (``backend/app/schemas.py``); the pipeline has
    no producer yet, so the simulator computes its own scores. Not clinical.
    """
    compat = [u for u in units if u.site == unit.site and u.expiry <= unit.expiry
              and any(can_serve(u, g) for g in KNOWN_GROUPS)]
    position = sum(1 for u in compat if (u.expiry, u.id) <= (unit.expiry, unit.id))
    lam = sum(
        rates.get((unit.site, g), 0.0)
        for g in KNOWN_GROUPS
        if can_serve(unit, g)
    )
    return _score_from_position(position, lam, (unit.expiry - today).days)


def _score_from_position(position: int, lam: float, remaining_days: int) -> float:
    """Shared math for the survival score: P(Poisson demand covers ``position``)."""
    if remaining_days <= 0 or lam <= 0:
        return 0.0
    mu = lam * remaining_days
    return min(1.0, max(0.0, 1.0 - _phi((position - 0.5 - mu) / math.sqrt(mu))))


@dataclass
class DayPlan:
    moves: list[tuple[Unit, str, float]] = field(default_factory=list)  # unit, dest, hours


def plan(sim: SimInputs, stock: list[Unit], inbound: dict[tuple[str, str], int],
         today: date, policy: str, cap_left: dict[tuple[str, str], int]) -> DayPlan:
    """Propose today's redistribution moves under reserve/send-by/courier limits."""
    out = DayPlan()
    # Per-site FEFO lists (built once) plus O(1) compatible-stock counts.
    by_site: dict[str, list[Unit]] = defaultdict(list)
    for unit in stock:
        by_site[unit.site].append(unit)
    for site_units in by_site.values():
        site_units.sort(key=lambda u: (u.expiry, u.id))
    compat_count: dict[tuple[str, str], int] = defaultdict(int)
    for unit in stock:
        for req_group in KNOWN_GROUPS:
            if can_serve(unit, req_group):
                compat_count[unit.site, req_group] += 1
    for dest in sorted(sim.hospitals):
        for group in KNOWN_GROUPS:
            need = math.ceil(FORECAST_LOOKAHEAD_DAYS * sim.rates.get((dest, group), 0.0))
            have = compat_count.get((dest, group), 0) + inbound.get((dest, group), 0)
            gap = need - have
            while gap > 0:
                best: tuple | None = None
                for src in sorted(by_site):
                    if src == dest:
                        continue
                    hours = sim.routes.get((src, dest))
                    if hours is None:
                        continue
                    # NOTE: cap_left may be a defaultdict or a plain dict;
                    # .get() never triggers a defaultdict factory, so an
                    # absent route means the full default cap remains.
                    if cap_left.get((src, dest), COURIER_CAP_PER_ROUTE_DAY) <= 0:
                        continue
                    site_best: tuple | None = None
                    for unit in by_site[src]:
                        if not can_serve(unit, group):
                            continue
                        if today > send_by(unit, hours):
                            continue
                        lam_src = sum(
                            sim.rates.get((src, g), 0.0)
                            for g in KNOWN_GROUPS if can_serve(unit, g)
                        )
                        reserve = max(1, math.ceil(RESERVE_DAYS * lam_src))
                        if compat_count[src, group] - 1 < reserve:
                            continue
                        key = (hours, hours, unit.id, dest) if policy == "nearest" else (
                            (unit.expiry - today).days, hours, unit.id, unit.site)
                        if site_best is None or key < site_best[0]:
                            site_best = (key, unit, hours, src)
                        if policy != "nearest":
                            break  # FEFO: first eligible is this site's best
                    if site_best is not None and (best is None or site_best[0] < best[0]):
                        best = site_best
                if best is None:
                    break
                _, unit, hours, src = best
                stock.remove(unit)
                by_site[src].remove(unit)
                for req_group in KNOWN_GROUPS:
                    if can_serve(unit, req_group):
                        compat_count[src, req_group] -= 1
                out.moves.append((unit, dest, hours))
                route = (src, dest)
                cap_left[route] = cap_left.get(route, COURIER_CAP_PER_ROUTE_DAY) - 1
                inbound[dest, group] = inbound.get((dest, group), 0) + 1
                gap -= 1
    out.moves.sort(key=lambda m: (m[1], m[0].id))
    return out


def _delivery_days(facility_id: str, per_week: int) -> set[int]:
    """Deterministic weekday pattern (0=Monday) for routine deliveries."""
    offset = sum(ord(c) for c in facility_id) % 7  # stable across hash seeds
    return {(offset + 2 * i) % 7 for i in range(per_week)}


def restock(sim: SimInputs, stock: list[Unit], today: date,
            rng: np.random.Generator) -> list[Unit]:
    """One day of centre inflow plus scheduled need-based hospital deliveries."""
    fresh: list[Unit] = []
    groups = list(KNOWN_GROUPS)
    weights = [sim.group_mix[g] for g in groups]
    for centre, flows in CENTRE_INFLOW_PER_DAY.items():
        for product, mean in flows.items():
            n = int(rng.poisson(mean)) if mean > 0 else 0
            for i in range(n):
                group = groups[int(rng.choice(len(groups), p=weights))]
                fresh.append(Unit(
                    id=f"RESTOCK-{today.isoformat()}-{centre}-{product}-{i}",
                    site=centre,
                    group=group,
                    expiry=today + timedelta(days=SHELF_LIFE_DAYS[product]),
                    product=product,
                ))
    stock.extend(fresh)
    weekday = today.weekday()
    for hospital in sorted(sim.hospitals):
        if weekday not in _delivery_days(hospital, sim.deliveries_per_week.get(hospital, 3)):
            continue
        centre = sim.supply_centre.get(hospital, "RBTC-NBO")
        lam_h = sum(sim.rates.get((hospital, g), 0.0) for g in KNOWN_GROUPS)
        need = max(0, math.ceil(3 * lam_h) - sum(
            1 for u in stock if u.site == hospital and
            any(can_serve(u, g) for g in KNOWN_GROUPS)))
        while need > 0:
            cands = [u for u in stock if u.site == centre and
                     any(can_serve(u, g) for g in KNOWN_GROUPS)]
            if not cands:
                break
            cands.sort(key=lambda u: (u.expiry, u.id))
            unit = cands[0]
            stock.remove(unit)
            unit.site = hospital
            stock.append(unit)
            need -= 1
    return fresh


def _draw_demand(sim: SimInputs, day: int, rng: np.random.Generator
                 ) -> dict[tuple[int, str, str], int]:
    """Poisson demand per (day, site, group) plus the fixed HSP-004 surge."""
    demand: dict[tuple[int, str, str], int] = {}
    for site in sorted(sim.hospitals):
        for group in KNOWN_GROUPS:
            demand[day, site, group] = int(rng.poisson(sim.rates.get((site, group), 0.0)))
    if day in IMBALANCE["surge_days"]:
        for group, extra in IMBALANCE["surge_extra"].items():
            key = (day, IMBALANCE["recipient"], group)
            demand[key] = demand.get(key, 0) + extra
    return demand


@dataclass
class ReplayResult:
    unmet: int = 0
    expired: dict[str, int] = field(default_factory=lambda: {"RBC": 0, "WB": 0})
    moved: dict[str, int] = field(default_factory=lambda: {"RBC": 0, "WB": 0})
    route_batches: int = 0
    scores: list[tuple[float, int]] = field(default_factory=list)  # (p, used)


def replay(sim: SimInputs, demand: dict[tuple[int, str, str], int],
           policy: str, rng: np.random.Generator) -> ReplayResult:
    """Run the 7-day test window: restock, plan, move, use, expire."""
    stock = [Unit(u.id, u.site, u.group, u.expiry, u.product) for u in sim.units]
    used: set[str] = set()
    result = ReplayResult()
    in_transit: dict[int, list[tuple[Unit, str]]] = defaultdict(list)
    cap_left: dict[tuple[str, str], int] = {}
    for day in range(HORIZON_DAYS):
        today = START + timedelta(days=day)
        for unit, dest in in_transit.pop(day, []):
            unit.site = dest
            stock.append(unit)
        restock(sim, stock, today, rng)
        # Daily site index: FEFO rank among usable units, computed once.
        usable: dict[str, list[Unit]] = defaultdict(list)
        for unit in stock:
            if any(can_serve(unit, g) for g in KNOWN_GROUPS):
                usable[unit.site].append(unit)
        rank: dict[str, int] = {}
        for site_units in usable.values():
            site_units.sort(key=lambda u: (u.expiry, u.id))
            for i, unit in enumerate(site_units, 1):
                rank[unit.id] = i
        lam_cache: dict[tuple[str, str, str], float] = {}
        for unit in stock:
            key = (unit.site, unit.product, unit.group)
            lam = lam_cache.get(key)
            if lam is None:
                lam = sum(sim.rates.get((unit.site, g), 0.0)
                          for g in KNOWN_GROUPS if can_serve(unit, g))
                lam_cache[key] = lam
            p = _score_from_position(rank.get(unit.id, 1), lam,
                                     (unit.expiry - today).days)
            result.scores.append((p, unit.id))  # outcome resolved below
        cap_left = defaultdict(lambda: COURIER_CAP_PER_ROUTE_DAY)
        inbound: dict[tuple[str, str], int] = defaultdict(int)
        day_plan = plan(sim, stock, inbound, today, policy, cap_left)
        arrived_routes: set[tuple[str, str]] = set()
        for unit, dest, hours in day_plan.moves:
            arrival = day + transit_days(hours)
            if arrival < HORIZON_DAYS:
                in_transit[arrival].append((unit, dest))
                result.moved[unit.product] += 1
                arrived_routes.add((unit.site, dest))
            else:
                stock.append(unit)  # arrives after the window; stays put
        result.route_batches += len(arrived_routes)
        # Per-site FEFO lists for demand fulfillment (plan() already mutated stock).
        site_stock: dict[str, list[Unit]] = defaultdict(list)
        for unit in stock:
            site_stock[unit.site].append(unit)
        for site_units in site_stock.values():
            site_units.sort(key=lambda u: (u.expiry, u.id))
        for site in sorted(sim.hospitals):
            for group in KNOWN_GROUPS:
                requested = demand.get((day, site, group), 0)
                for _ in range(requested):
                    shelf = site_stock.get(site, [])
                    pick = next((u for u in shelf if u.expiry >= today
                                 and can_serve(u, group)), None)
                    if pick is None:
                        result.unmet += 1
                        continue
                    shelf.remove(pick)
                    stock.remove(pick)
                    used.add(pick.id)
        kept = []
        for unit in stock:
            if unit.expiry <= today:
                result.expired[unit.product] += 1
            else:
                kept.append(unit)
        stock[:] = kept
    # Scores are unit-days: each morning's P(used before expiry) paired with
    # whether that unit was eventually used. Pooled for Brier/reliability.
    result.scores = [(p, 1 if uid in used else 0) for p, uid in result.scores]
    return result


def brier_and_buckets(scores: list[tuple[float, int]], bins: int = 5) -> dict:
    """Brier score plus a reliability table over equal-width probability bins."""
    if not scores:
        return {"brier": None, "buckets": [], "n": 0}
    brier = float(sum((p - o) ** 2 for p, o in scores) / len(scores))
    buckets = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        cell = [(p, o) for p, o in scores if (p >= lo and (p < hi or (i == bins - 1 and p <= hi)))]
        if not cell:
            buckets.append({"bin": [lo, hi], "n": 0, "mean_predicted": None,
                            "observed_rate": None})
        else:
            buckets.append({"bin": [lo, hi], "n": len(cell),
                            "mean_predicted": float(sum(p for p, _ in cell) / len(cell)),
                            "observed_rate": float(sum(o for _, o in cell) / len(cell))})
    return {"brier": brier, "buckets": buckets, "n": len(scores)}


def compare(raw_dir: Path = RAW_DIR, seeds: tuple[int, ...] = SEEDS,
            out_dir: Path | None = None) -> dict:
    """Run both policies over shared demand draws; mean +- SD across seeds."""
    sim = inputs(raw_dir)
    per_policy: dict[str, list[ReplayResult]] = {"nearest": [], "expiry_aware": []}
    for seed in seeds:
        rng = np.random.default_rng(seed)
        demand: dict[tuple[int, str, str], int] = {}
        for day in range(HORIZON_DAYS):
            demand.update(_draw_demand(sim, day, rng))
        for policy in per_policy:
            run_rng = np.random.default_rng(seed)  # identical restock stream
            result = replay(sim, demand, policy, run_rng)
            per_policy[policy].append(result)
    summary: dict[str, dict] = {}
    for policy, runs in per_policy.items():
        series = {
            "unmet": [r.unmet for r in runs],
            "expired_RBC": [r.expired["RBC"] for r in runs],
            "expired_WB": [r.expired["WB"] for r in runs],
            "moved_RBC": [r.moved["RBC"] for r in runs],
            "moved_WB": [r.moved["WB"] for r in runs],
            "route_batches": [r.route_batches for r in runs],
        }
        summary[policy] = {
            key: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
                  "min": int(min(v)), "max": int(max(v))}
            for key, v in series.items()
        }
        pooled = [row for r in runs for row in
                  [(p, o) for p, o in r.scores]]
        summary[policy]["calibration"] = brier_and_buckets(pooled)
    payload = {
        "source": "official synthetic closing inventory and October request rates",
        "scenario": (
            f"{HORIZON_DAYS} days from {START.isoformat()}, daily centre restock, "
            f"courier cap {COURIER_CAP_PER_ROUTE_DAY}/route/day, next-day arrival, "
            f"HSP-001->HSP-004 imbalance with day-{IMBALANCE['surge_days']} surge, "
            "WB ABO-identical / RBC compatible, send-by = expiry - travel - "
            f"{SEND_BY_BUFFER_DAYS}d buffer"
        ),
        "train": f"rates/inflow/mix/snapshot from data <= {TRAIN_END.isoformat()} only",
        "test": (f"synthetic {START.isoformat()}.."
                 f"{(START + timedelta(days=HORIZON_DAYS - 1)).isoformat()} demand"),
        "seeds": list(seeds),
        "assumptions": "all proposed moves accepted; deliveries need-based 3x/week; "
                       "fresh units RBC +42d / WB +35d; scores are planning aids, not clinical",
        "policies": summary,
    }
    if out_dir is None:
        out_dir = Path(__file__).resolve().parents[1] / "data" / "processed"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sim_compare.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "sim_summary.md").write_text(summary_markdown(payload), encoding="utf-8")
    return payload


def _mean_sd(section: dict, key: str) -> str:
    cell = section[key]
    return f"{cell['mean']:.1f}+-{cell['sd']:.1f}"


def _bucket_cell(bucket: dict) -> str:
    lo, hi = bucket["bin"]
    pred = bucket["mean_predicted"]
    obs = bucket["observed_rate"]
    pred_txt = "n/a" if pred is None else f"{pred:.2f}"
    obs_txt = "n/a" if obs is None else f"{obs:.2f}"
    return f"[{lo:.1f},{hi:.1f}]: n={bucket['n']}, pred={pred_txt}, obs={obs_txt}"


def summary_markdown(payload: dict) -> str:
    lines = [
        "## Transfer policy comparison (synthetic, 7-day window)",
        "",
        f"Scenario: {payload['scenario']}.",
        f"Train: {payload['train']}; test: {payload['test']}.",
        f"Seeds: {len(payload['seeds'])} fixed ({min(payload['seeds'])}..{max(payload['seeds'])}); "
        "both policies face the same demand draw per seed. Values are mean +- SD.",
        "",
        "| Policy | Unmet | Expired RBC | Expired WB | Moved RBC | Moved WB | Batches |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in ("nearest", "expiry_aware"):
        s = payload["policies"][policy]
        row = " | ".join(_mean_sd(s, k) for k in
                         ("unmet", "expired_RBC", "expired_WB", "moved_RBC",
                          "moved_WB", "route_batches"))
        lines.append(f"| {policy} | {row} |")
    lines += ["",
              "Used-before-expiry calibration (pooled unit-days; lower Brier is better):"]
    for policy in ("nearest", "expiry_aware"):
        cal = payload["policies"][policy]["calibration"]
        cells = "; ".join(_bucket_cell(b) for b in cal["buckets"])
        lines.append(f"- {policy}: Brier {cal['brier']:.3f} (n={cal['n']:,}). {cells}")
    lines += ["",
              "Honesty notes: synthetic demand, not observed November events; the 90% "
              "demand upper bound under-covers overall (88.8% measured, see forecast "
              "summary); scores are planning aids, never transfusion decisions. "
              "Calibration outcomes are use-within-the-7-day-window, a lower bound on "
              "use-before-expiry, so high-predicted buckets over-shoot by construction; "
              "the Brier score reflects that horizon mismatch, not just score quality."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
