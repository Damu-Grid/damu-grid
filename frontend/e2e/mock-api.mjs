// Test-only stand-in for the FastAPI backend (backend/app, #51), so the UI can
// be tested without Python. It mirrors that API's paths, strict request bodies,
// `status` fields, audit rows and error shape. It is NOT a stock ledger and its
// data is fake (MOCK-… IDs).
import http from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8765);

const card = (id, extra = {}) => ({
  suggestion_id: id,
  as_of: "2026-10-31T23:59:59+03:00",
  data_age_hours: 0,
  component: "RBC",
  blood_group: "O+",
  unit_ids: [`${id}-U1`, `${id}-U2`],
  unit_version: 0,
  from_facility_id: "MOCK-SITE-A",
  to_facility_id: "MOCK-SITE-B",
  expiry_date: "2026-11-06",
  typical_travel_hours: 2.5,
  sender_reserve_units: 4,
  sender_stock_after: 6,
  recipient_gap_units: 3,
  expected_use_if_moved: 1.8,
  expected_use_if_stays: 0.4,
  uncertainty: { method: "mock", nominal_level: 0.95, label: "Mock estimate for tests" },
  reason_deterministic: `Mock reason for ${id}.`,
  reason_llm: null,
  policy: "expiry_aware",
  fallback: false,
  eligibility_ok: true,
  warnings: [],
  ...extra,
});

const QUEUE = [
  card("MOCK-1"),
  card("MOCK-CONFLICT"),
  card("MOCK-FB", { policy: "fallback", fallback: true, reason_deterministic: "Mock fallback rule." }),
];
const SEEDS = [card("SEED-EXP"), card("SEED-TRN")];
const ALL = new Map([...QUEUE, ...SEEDS].map((s) => [s.suggestion_id, s]));

let decided, events, moves, audit;

function addAudit(eventType, actorId, move, payload) {
  for (const unitId of move.unit_ids) {
    audit.push({
      event_id: `AUD-${audit.length + 1}`,
      event_type: eventType,
      occurred_at: new Date(Date.now() + audit.length).toISOString(),
      actor_id: actorId,
      move_id: move.move_id,
      unit_id: unitId,
      payload,
    });
  }
}

function newMove(moveId, s, status, leaseMinutes) {
  const move = {
    move_id: moveId,
    suggestion_id: s.suggestion_id,
    unit_ids: s.unit_ids,
    from_facility_id: s.from_facility_id,
    to_facility_id: s.to_facility_id,
    status,
    lease_expires_at: new Date(Date.now() + leaseMinutes * 60_000).toISOString(),
  };
  moves.set(moveId, move);
  addAudit("decision_accept", "demo-coordinator", move, { reason: "Seeded", suggestion_id: s.suggestion_id });
  return move;
}

function reset() {
  decided = new Set();
  events = new Map();
  moves = new Map();
  audit = [];
  newMove("MOVE-SEED-EXPIRED", ALL.get("SEED-EXP"), "reserved", -5);
  newMove("MOVE-SEED-TRANSIT", ALL.get("SEED-TRN"), "in_transit", 30);
}
reset();

function send(res, status, body) {
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  });
  res.end(JSON.stringify(body));
}

const error = (res, status, code, message) => send(res, status, { code, message });

function readJson(req) {
  return new Promise((resolve) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      try {
        resolve(JSON.parse(raw || "{}"));
      } catch {
        resolve(null);
      }
    });
  });
}

/** Like the API's strict Pydantic models: unknown or missing fields are a 422. */
function strict(body, required, optional = []) {
  if (!body) return "Invalid JSON";
  const extra = Object.keys(body).filter((k) => !required.includes(k) && !optional.includes(k));
  const missing = required.filter((k) => !(k in body));
  if (extra.length) return `Extra fields not permitted: ${extra.join(", ")}`;
  if (missing.length) return `Missing fields: ${missing.join(", ")}`;
  return null;
}

const DECISION = ["event_id", "actor_id", "role", "reason", "unit_version"];
const MOVE_ACTION = ["event_id", "actor_id", "role"];

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const path = url.pathname;
    if (req.method === "OPTIONS") return send(res, 204, {});
    if (req.method === "POST" && path === "/__reset") return reset(), send(res, 200, { ok: true });
    if (req.method === "GET" && path === "/health") return send(res, 200, { status: "ok" });

    if (req.method === "GET" && path === "/suggestions") {
      const fallback = url.searchParams.get("policy") === "fallback";
      const items = QUEUE.filter((s) => s.fallback === fallback && !decided.has(s.suggestion_id));
      return send(res, 200, { items });
    }

    let m = path.match(/^\/suggestions\/([^/]+)$/);
    if (req.method === "GET" && m) {
      const s = ALL.get(decodeURIComponent(m[1]));
      return s ? send(res, 200, s) : error(res, 404, "suggestion_not_found", "Suggestion not found.");
    }

    m = path.match(/^\/suggestions\/([^/]+)\/(accept|change|reject)$/);
    if (req.method === "POST" && m) {
      const [, id, action] = m;
      const body = await readJson(req);
      const invalid = strict(body, action === "change" ? [...DECISION, "unit_ids", "to_facility_id"] : DECISION);
      if (invalid) return error(res, 422, "invalid_body", invalid);
      if (body.role !== "coordinator") return error(res, 403, "forbidden", "Only the coordinator can decide.");
      if (events.has(body.event_id)) return send(res, 200, events.get(body.event_id));
      if (id === "MOCK-CONFLICT" && action === "accept")
        return error(res, 409, "stale_version", "The unit version is stale; reload the suggestion.");

      const s = ALL.get(id);
      let result;
      if (action === "accept") {
        newMove(`MOVE-${id}`, s, "reserved", 30);
        result = { move_id: `MOVE-${id}`, suggestion_id: id, status: "reserved" };
      } else if (action === "reject") {
        result = { move_id: null, suggestion_id: id, status: "rejected" };
      } else {
        result = { suggestion: { ...s, suggestion_id: `${id}-rev`, to_facility_id: body.to_facility_id }, status: "suggested" };
      }
      decided.add(id);
      events.set(body.event_id, result);
      return send(res, 200, result);
    }

    if (req.method === "GET" && path === "/audit") {
      const moveId = url.searchParams.get("move_id");
      return send(res, 200, audit.filter((r) => !moveId || r.move_id === moveId));
    }

    m = path.match(/^\/moves\/([^/]+)(?:\/(dispatch|receive))?$/);
    if (m) {
      const move = moves.get(decodeURIComponent(m[1]));
      if (!move) return error(res, 404, "move_not_found", "Move not found.");
      if (req.method === "GET" && !m[2]) return send(res, 200, { ...move, unit_ids_json: JSON.stringify(move.unit_ids) });

      const action = m[2];
      const body = await readJson(req);
      const invalid = strict(body, MOVE_ACTION, action === "receive" ? ["reason", "cold_chain_evidence_complete"] : ["reason"]);
      if (invalid) return error(res, 422, "invalid_body", invalid);
      if (events.has(body.event_id)) return send(res, 200, events.get(body.event_id));

      let next;
      if (action === "dispatch") {
        if (body.role !== "sender") return error(res, 403, "forbidden", "Only the sender dispatches.");
        if (move.status !== "reserved") return error(res, 409, "invalid_state", "Move is not reserved.");
        if (Date.parse(move.lease_expires_at) <= Date.now())
          return error(res, 422, "lease_expired", "Reservation lease expired.");
        next = "in_transit";
      } else {
        if (body.role !== "receiver") return error(res, 403, "forbidden", "Only the receiver confirms.");
        if (move.status !== "in_transit") return error(res, 409, "invalid_state", "Move is not in transit.");
        next = body.cold_chain_evidence_complete ? "received" : "received_held";
      }
      move.status = next;
      addAudit(`move_${action}`, body.actor_id, move, { status: next, reason: body.reason ?? "" });
      const result = { move_id: move.move_id, status: next };
      events.set(body.event_id, result);
      return send(res, 200, result);
    }

    // FastAPI's own 404 shape for unknown paths (e.g. GET /moves without an id).
    send(res, 404, { detail: "Not Found" });
  })
  .listen(PORT, () => console.log(`mock API on :${PORT}`));
