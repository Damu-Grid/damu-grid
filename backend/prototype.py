"""Local synthetic Damu Grid demo. No clinical or production authority."""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import sqlite3
import threading
import uuid
from collections import defaultdict
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "processed" / "prototype.sqlite"
AS_OF = dt.datetime(2026, 10, 31, 23, 59, 59, tzinfo=dt.timezone(dt.timedelta(hours=3)))
GROUPS = {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
LOCK = threading.RLock()


def rows(name):
    with (RAW / name).open(newline="", encoding="utf-8") as stream:
        yield from csv.DictReader(stream)


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def init():
    """Use only the explicit closing snapshot; never infer prior stock from final locations."""
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS units(id TEXT PRIMARY KEY, site TEXT, grp TEXT, expiry TEXT,
          safety TEXT, state TEXT DEFAULT 'stock', version INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS moves(id TEXT PRIMARY KEY, unit_id TEXT, origin TEXT,
          destination TEXT, state TEXT, lease_until TEXT, eta TEXT);
        CREATE TABLE IF NOT EXISTS audit(event_id TEXT PRIMARY KEY, payload TEXT, result TEXT,
          actor TEXT, role TEXT, at TEXT);
        CREATE TABLE IF NOT EXISTS decisions(unit_id TEXT PRIMARY KEY, state TEXT);
        CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, actor TEXT, message TEXT, at TEXT);
        """)
        if db.execute("SELECT COUNT(*) FROM units").fetchone()[0]:
            return
        for u in rows("units.csv"):
            if (u["component"] != "RBC" or u["blood_group"] not in GROUPS
                or u["status"] != "in_stock" or u["expiry_date"] <= "2026-10-31"
                or u["temp_excursion_exposed"].lower() != "false"):
                continue
            db.execute("INSERT INTO units(id,site,grp,expiry,safety) VALUES(?,?,?,?,?)",
                       (u["unit_id"], u["current_facility_id"], u["blood_group"],
                        u["expiry_date"], "cleared"))


def demand_rates():
    counts = defaultdict(float)
    days = 28
    for r in rows("requests.csv"):
        if (r["component_requested"] == "RBC" and r["patient_blood_group"] in GROUPS
            and "2026-10-04" <= r["requested_at"][:10] <= "2026-10-31"):
            counts[r["facility_id"], r["patient_blood_group"]] += int(r["units_requested"])
    return {key: value / days for key, value in counts.items()}


def routes():
    return {(r["from_facility_id"], r["to_facility_id"]): float(r["typical_travel_hours"])
            for r in rows("routes.csv") if r["typical_travel_hours"]}


def suggestions(policy="expiry_aware", limit=30, unique_units=True):
    fallback = policy in ("fallback", "nearest")
    if policy not in ("expiry_aware", "fallback", "nearest"):
        raise ValueError("Unknown policy")
    rates, travel = demand_rates(), routes()
    if not fallback:
        site_total = defaultdict(float)
        group_total = defaultdict(float)
        for (site, group), rate in rates.items():
            site_total[site] += rate
            group_total[group] += rate
        total = sum(group_total.values())
        if total:
            rates = {(site, group): amount * group_total[group] / total
                     for site, amount in site_total.items() for group in GROUPS}
    with connect() as db:
        stock = [dict(u) for u in db.execute("SELECT * FROM units WHERE state='stock' AND safety='cleared'")]
        rejected = {r[0] for r in db.execute("SELECT unit_id FROM decisions WHERE state='rejected'")}
    counts = defaultdict(int)
    for u in stock:
        counts[u["site"], u["grp"]] += 1
    output = []
    for u in stock:
        if u["id"] in rejected:
            continue
        origin, grp = u["site"], u["grp"]
        reserve = max(1, math.ceil(2 * rates.get((origin, grp), 0)))
        if counts[origin, grp] <= reserve or u["expiry"] > "2026-11-07":
            continue
        for (source, dest), hours in travel.items():
            if source != origin or dest == origin or hours <= 0:
                continue
            arrival = AS_OF + dt.timedelta(hours=hours)
            if arrival.date().isoformat() >= u["expiry"]:
                continue
            target = math.ceil(7 * rates.get((dest, grp), 0))
            gap = target - counts[dest, grp]
            if gap <= 0:
                continue
            remaining = (dt.date.fromisoformat(u["expiry"]) - arrival.date()).days
            score = -hours if fallback else gap / (1 + remaining) - hours / 100
            output.append({"suggestion_id": u["id"] + ":" + dest,
                "unit_ids": [u["id"]], "unit_version": u["version"],
                "as_of": AS_OF.isoformat(), "component": "RBC", "blood_group": grp,
                "from_facility_id": origin, "to_facility_id": dest,
                "expiry_date": u["expiry"], "typical_travel_hours": hours,
                "sender_reserve_units": reserve, "sender_stock_after": counts[origin, grp] - 1,
                "recipient_gap_units": gap, "expected_use_if_moved": None,
                "expected_use_if_stays": None, "uncertainty": {"method": "28-day site/group request rate" if fallback else "28-day site total allocated by network group mix",
                    "label": "Estimate from synthetic requests; reporting completeness assumed"},
                "reason_deterministic": f"{grp} RBC expires {u['expiry']}; {dest} has an estimated gap of {gap}; {origin} retains at least {reserve} units. Review current stock and safety before approval.",
                "reason_llm": None, "policy": policy, "fallback": fallback,
                "eligibility_ok": True, "warnings": ["Synthetic closing snapshot; no live stock feed"],
                "score": score})
    output.sort(key=lambda x: (-x["score"], x["expiry_date"], x["suggestion_id"]))
    seen = set()
    result = [s for s in output if not unique_units or not (s["unit_ids"][0] in seen or seen.add(s["unit_ids"][0]))]
    return result[:limit] if limit is not None else result


class ActionError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def act(action, body):
    """Serialize decision and audit in one SQLite write transaction."""
    required = {"accept": "coordinator", "change": "coordinator", "reject": "coordinator",
                "dispatch": "sender", "receive": "receiver", "quarantine": "safety"}
    if action not in required:
        raise ActionError(404, "Unknown action")
    if body.get("role") != required[action]:
        raise ActionError(403, "Role is not permitted")
    # Local demo identities only; a real host must authenticate and scope facilities.
    demo_actor = {"coordinator": "demo-coordinator", "sender": "demo-sender",
                  "receiver": "demo-receiver", "safety": "demo-safety"}
    if body.get("actor_id") != demo_actor[required[action]]:
        raise ActionError(403, "Demo actor does not match role")
    if not body.get("actor_id") or not body.get("reason") or not body.get("event_id"):
        raise ActionError(422, "Actor, reason and event ID required")
    # Frozen demo clock: actions replay immediately after the official closing snapshot.
    now = AS_OF + dt.timedelta(minutes=1)
    payload = json.dumps({"action": action, **body}, sort_keys=True)
    with LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT payload,result FROM audit WHERE event_id=?", (body["event_id"],)).fetchone()
        if old:
            if old["payload"] != payload:
                raise ActionError(409, "Event ID used with different payload")
            return json.loads(old["result"])
        unit_id = body.get("unit_id")
        u = db.execute("SELECT * FROM units WHERE id=?", (unit_id,)).fetchone()
        if u is None:
            raise ActionError(404, "Unknown unit")
        result = {"unit_id": unit_id, "action": action}
        if action in ("accept", "change"):
            if body.get("unit_version") != u["version"]:
                raise ActionError(409, "Stale unit version")
            if u["state"] not in (("stock", "reserved") if action == "change" else ("stock",)):
                raise ActionError(409, "Unit unavailable")
            if u["safety"] != "cleared":
                raise ActionError(422, "Uncleared unit")
            dest = body.get("destination")
            if action == "change" and u["state"] == "reserved":
                db.execute("UPDATE units SET state='stock' WHERE id=?", (unit_id,))
            available = next((s for s in suggestions("fallback", None, False) if s["unit_ids"] == [unit_id]
                              and s["to_facility_id"] == dest), None)
            if not available:
                raise ActionError(422, "Destination is no longer eligible")
            if action == "change" and u["state"] == "reserved":
                db.execute("UPDATE moves SET state='cancelled' WHERE unit_id=? AND state='reserved'", (unit_id,))
            move_id = str(uuid.uuid4())
            lease = now + dt.timedelta(minutes=30)
            eta = now + dt.timedelta(hours=available["typical_travel_hours"])
            if eta.date().isoformat() >= u["expiry"]:
                raise ActionError(422, "Arrival is after expiry")
            db.execute("INSERT INTO moves VALUES(?,?,?,?,?,?,?)", (move_id, unit_id, u["site"], dest,
                       "reserved", lease.isoformat(), eta.isoformat()))
            db.execute("UPDATE units SET state='reserved',version=version+1 WHERE id=?", (unit_id,))
            result.update(move_id=move_id, state="reserved")
        elif action == "reject":
            if body.get("unit_version") != u["version"]:
                raise ActionError(409, "Stale unit version")
            if u["state"] == "reserved":
                db.execute("UPDATE moves SET state='cancelled' WHERE unit_id=? AND state='reserved'", (unit_id,))
                db.execute("UPDATE units SET state='stock',version=version+1 WHERE id=?", (unit_id,))
            elif u["state"] != "stock":
                raise ActionError(409, "Cannot cancel dispatched movement")
            result["state"] = "rejected"
            db.execute("INSERT OR REPLACE INTO decisions VALUES(?,?)", (unit_id, "rejected"))
        elif action == "quarantine":
            db.execute("UPDATE units SET safety='quarantined',version=version+1 WHERE id=?", (unit_id,))
            result["state"] = "quarantined"
        else:
            m = db.execute("SELECT * FROM moves WHERE id=? AND unit_id=?", (body.get("move_id"), unit_id)).fetchone()
            if not m:
                raise ActionError(404, "Unknown move")
            if action == "dispatch":
                if (m["state"] != "reserved" or u["state"] != "reserved" or u["safety"] != "cleared"
                    or now >= dt.datetime.fromisoformat(m["lease_until"])
                    or now >= dt.datetime.fromisoformat(m["eta"])
                    or body.get("site") != m["origin"]):
                    raise ActionError(422, "Dispatch blocked by state, safety, lease, ETA or site")
                db.execute("UPDATE moves SET state='transit' WHERE id=?", (m["id"],))
                db.execute("UPDATE units SET state='transit',version=version+1 WHERE id=?", (unit_id,))
                result.update(move_id=m["id"], state="transit")
            else:
                if m["state"] != "transit" or u["state"] != "transit" or body.get("site") != m["destination"]:
                    raise ActionError(422, "Receipt blocked by state or site")
                safety = "quarantined" if u["safety"] == "quarantined" else (
                    "cleared" if body.get("cold_chain_verified") is True and now.date().isoformat() < u["expiry"] else "unknown")
                db.execute("UPDATE moves SET state='received' WHERE id=?", (m["id"],))
                db.execute("UPDATE units SET site=?,state='stock',safety=?,version=version+1 WHERE id=?",
                           (m["destination"], safety, unit_id))
                result.update(move_id=m["id"], state="received", safety=safety,
                              clinical_release=False)
        db.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)",
                   (body["event_id"], payload, json.dumps(result), body["actor_id"], body["role"], now.isoformat()))
        return result


def expire_leases(at):
    """Recover un-dispatched reservations at a trusted server time."""
    when = dt.datetime.fromisoformat(at)
    if when.tzinfo is None:
        raise ValueError("Timezone required")
    recovered = []
    with LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for m in db.execute("SELECT * FROM moves WHERE state='reserved'").fetchall():
            if dt.datetime.fromisoformat(m["lease_until"]) > when:
                continue
            db.execute("UPDATE moves SET state='lease_expired' WHERE id=?", (m["id"],))
            db.execute("UPDATE units SET state='stock',version=version+1 WHERE id=? AND state='reserved'",
                       (m["unit_id"],))
            event = {"action": "expire_lease", "move_id": m["id"], "unit_id": m["unit_id"]}
            db.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)",
                       ("expire:" + m["id"], json.dumps(event, sort_keys=True), json.dumps(event),
                        "system", "system", when.isoformat()))
            recovered.append(m["id"])
    return recovered


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, value):
        content = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path)
        try:
            if path.path == "/":
                content = (ROOT / "frontend" / "prototype.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif path.path == "/health":
                self.respond(200, {"ok": True, "synthetic": True})
            elif path.path == "/snapshot":
                with connect() as db:
                    counts = {r["state"]: r["n"] for r in db.execute("SELECT state,COUNT(*) n FROM units GROUP BY state")}
                self.respond(200, {"as_of": AS_OF.isoformat(), "counts": counts, "component": "RBC",
                                   "synthetic": True, "source": "official closing snapshot"})
            elif path.path == "/suggestions":
                policy = parse_qs(path.query).get("policy", ["expiry_aware"])[0]
                self.respond(200, {"suggestions": suggestions(policy), "synthetic": True})
            elif path.path == "/audit":
                params = parse_qs(path.query)
                with connect() as db:
                    records = [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY rowid DESC LIMIT 500")]
                for field in ("actor", "from", "to"):
                    if field in params:
                        column = "at" if field in ("from", "to") else "actor"
                        value = params[field][0]
                        records = [r for r in records if (r[column] >= value if field == "from"
                                    else r[column] <= value if field == "to" else r[column] == value)]
                for key in ("unit_id", "move_id"):
                    if key in params:
                        value = params[key][0]
                        records = [r for r in records if json.loads(r["payload"]).get(key) == value
                                   or json.loads(r["result"]).get(key) == value]
                self.respond(200, {"events": records})
            elif path.path == "/evaluation/forecast":
                from forecasting.evaluate import evaluate
                self.respond(200, evaluate())
            elif path.path == "/settings":
                self.respond(200, {"scope": "synthetic demo", "component": "RBC",
                                   "blood_groups": sorted(GROUPS), "sender_reserve_days": 2,
                                   "planning_horizon_days": 7, "lease_minutes": 30,
                                   "language": "English", "country": "Kenya-modelled synthetic data",
                                   "editable": False})
            elif path.path == "/map/stock":
                with connect() as db:
                    counts = {r[0]: r[1] for r in db.execute("SELECT site,COUNT(*) FROM units WHERE state='stock' AND safety='cleared' GROUP BY site")}
                sites = [{"facility_id": r["facility_id"], "name": r["name"],
                          "lat": float(r["lat"]), "lon": float(r["lon"]),
                          "connectivity": r["connectivity"], "eligible_rbc_stock": counts.get(r["facility_id"], 0)}
                         for r in rows("facilities.csv") if r["lat"] and r["lon"]]
                self.respond(200, {"as_of": AS_OF.isoformat(), "synthetic": True, "sites": sites})
            elif path.path == "/flags/cold-chain":
                flags = []
                for r in rows("power_outages.csv"):
                    if (r["backup_power_engaged"].lower() == "false"
                        and r["start_time"][:10] == "2026-10-31"):
                        flags.append({"facility_id": r["facility_id"], "at": r["start_time"],
                                      "kind": "outage_without_backup", "clinical_status": "review_required"})
                self.respond(200, {"as_of": AS_OF.isoformat(), "synthetic": True,
                                   "flags": flags, "scope": "recent outage flags only; logger gaps not evaluated"})
            elif path.path == "/alerts":
                with connect() as db:
                    messages = [dict(r) for r in db.execute("SELECT * FROM alerts ORDER BY at DESC LIMIT 20")]
                self.respond(200, {"synthetic": True, "messages": messages})
            elif path.path.startswith("/moves/"):
                with connect() as db:
                    m = db.execute("SELECT * FROM moves WHERE id=?", (path.path[7:],)).fetchone()
                self.respond(200 if m else 404, dict(m) if m else {"error": "Unknown move"})
            else:
                self.respond(404, {"error": "Unknown endpoint"})
        except (ValueError, KeyError) as exc:
            self.respond(422, {"error": str(exc)})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            action = self.path.strip("/")
            if action == "alerts/simulate":
                if body.get("actor") not in ("demo-coordinator", "demo-sender", "demo-receiver"):
                    raise ActionError(422, "Demo officer recipient only")
                if not isinstance(body.get("message"), str) or not 0 < len(body["message"]) <= 240:
                    raise ActionError(422, "Short message required")
                item = {"id": str(uuid.uuid4()), "actor": body["actor"],
                        "message": body["message"], "at": dt.datetime.now(dt.timezone.utc).isoformat()}
                with connect() as db:
                    db.execute("INSERT INTO alerts VALUES(?,?,?,?)", tuple(item.values()))
                self.respond(200, {"simulated": True, "sent": False, **item})
            else:
                self.respond(200, act(action, body))
        except ActionError as exc:
            self.respond(exc.status, {"error": exc.message})
        except (ValueError, KeyError, TypeError) as exc:
            self.respond(422, {"error": str(exc)})


if __name__ == "__main__":
    init()
    print("Synthetic Damu Grid prototype: http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
