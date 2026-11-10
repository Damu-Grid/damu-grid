// Test-only stand-in for the backend, following docs/API_SPEC.md. Used by
// Playwright so the UI can be tested before the real API exists. It is NOT a
// stock ledger and its data is fake (MOCK-... IDs).
import http from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8765);

const card = (id, extra = {}) => ({
  suggestion_id: id,
  as_of: "2026-10-31T23:59:59+03:00",
  data_age_hours: 0,
  component: "RBC",
  blood_group: "O+",
  unit_ids: [`${id}-U1`, `${id}-U2`],
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

const SUGGESTIONS = [
  card("MOCK-1"),
  card("MOCK-CONFLICT"),
  card("MOCK-FB", { policy: "fallback", fallback: true, reason_deterministic: "Mock fallback rule." }),
];

let reserved = new Set();
const events = new Map();
let moves = new Map();

const audit = (actor_id, role, action, from_state, to_state, reason = null) => ({
  event_id: `AUD-${Math.random().toString(36).slice(2, 10)}`,
  ts: new Date().toISOString(),
  actor_id,
  role,
  action,
  from_state,
  to_state,
  reason,
});

function newMove(id, s, state, leaseMinutes) {
  return {
    move_id: id,
    suggestion_id: s.suggestion_id,
    state,
    version: 1,
    component: s.component,
    blood_group: s.blood_group,
    unit_ids: s.unit_ids,
    from_facility_id: s.from_facility_id,
    to_facility_id: s.to_facility_id,
    expiry_date: s.expiry_date,
    typical_travel_hours: s.typical_travel_hours,
    lease_expires_at: new Date(Date.now() + leaseMinutes * 60_000).toISOString(),
    warnings: [],
    audit: [audit("demo-coordinator", "coordinator", "accept", "suggested", "reserved", "Seeded")],
  };
}

function seedMoves() {
  moves = new Map([
    ["MOVE-SEED-EXPIRED", newMove("MOVE-SEED-EXPIRED", card("SEED-EXP"), "reserved", -5)],
    ["MOVE-SEED-TRANSIT", newMove("MOVE-SEED-TRANSIT", card("SEED-TRN"), "in_transit", 30)],
  ]);
}
seedMoves();

function send(res, status, body) {
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  });
  res.end(JSON.stringify(body));
}

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

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    if (req.method === "OPTIONS") return send(res, 204, {});

    if (req.method === "POST" && url.pathname === "/__reset") {
      reserved = new Set();
      events.clear();
      seedMoves();
      return send(res, 200, { ok: true });
    }

    if (req.method === "GET" && url.pathname === "/health") return send(res, 200, { ok: true });

    if (req.method === "GET" && url.pathname === "/suggestions") {
      const fallback = url.searchParams.get("policy") === "fallback";
      return send(
        res,
        200,
        SUGGESTIONS.filter((s) => s.fallback === fallback && !reserved.has(s.suggestion_id)),
      );
    }

    const m = url.pathname.match(/^\/suggestions\/([^/]+)\/(accept|change|reject)$/);
    if (req.method === "POST" && m) {
      const [, id, action] = m;
      const body = await readJson(req);
      if (!body?.event_id || !body.actor_id || !body.reason)
        return send(res, 422, { code: "invalid_body", message: "event_id, actor_id and reason are required." });
      if (body.role !== "coordinator")
        return send(res, 403, { code: "forbidden", message: "Only the coordinator can decide." });
      if (events.has(body.event_id)) return send(res, 200, events.get(body.event_id));
      if (id === "MOCK-CONFLICT" && action === "accept")
        return send(res, 409, { code: "conflict", message: "Unit version changed since you loaded it." });

      const result =
        action === "accept"
          ? { state: "reserved", move_id: `MOVE-${id}`, suggestion_id: id }
          : action === "change"
            ? { state: "suggested", suggestion_id: `${id}-rev` }
            : { state: "rejected", suggestion_id: id };
      if (action === "accept") {
        reserved.add(id);
        const s = SUGGESTIONS.find((x) => x.suggestion_id === id);
        if (s) moves.set(result.move_id, newMove(result.move_id, s, "reserved", 30));
      }
      events.set(body.event_id, result);
      return send(res, 200, result);
    }

    if (req.method === "GET" && url.pathname === "/moves") {
      const states = url.searchParams.getAll("state");
      return send(res, 200, [...moves.values()].filter((mv) => !states.length || states.includes(mv.state)));
    }

    const mv = url.pathname.match(/^\/moves\/([^/]+)(?:\/(dispatch|receive))?$/);
    if (mv) {
      const move = moves.get(decodeURIComponent(mv[1]));
      if (!move) return send(res, 404, { code: "not_found", message: "No such move." });
      if (req.method === "GET" && !mv[2]) return send(res, 200, move);

      const body = await readJson(req);
      if (!body?.event_id || !body.actor_id)
        return send(res, 422, { code: "invalid_body", message: "event_id and actor_id are required." });

      if (mv[2] === "dispatch") {
        if (body.role !== "sender") return send(res, 403, { code: "forbidden", message: "Only the sender dispatches." });
        if (move.state !== "reserved") return send(res, 409, { code: "conflict", message: "Move is not reserved." });
        if (Date.parse(move.lease_expires_at) < Date.now())
          return send(res, 422, { code: "lease_expired", message: "Reservation lease expired." });
        move.audit.push(audit(body.actor_id, body.role, "dispatch", "reserved", "in_transit", body.note));
        Object.assign(move, { state: "in_transit", version: move.version + 1 });
        return send(res, 200, move);
      }

      if (body.role !== "receiver") return send(res, 403, { code: "forbidden", message: "Only the receiver confirms." });
      if (!["in_transit", "dispatched"].includes(move.state))
        return send(res, 409, { code: "conflict", message: "Move is not in transit." });
      const ok =
        body.cold_chain_evidence === "ok" &&
        (body.coolbox_max_temp_c == null || body.coolbox_max_temp_c <= 10);
      const next = ok ? "received" : "received_held";
      move.audit.push(audit(body.actor_id, body.role, "receive", move.state, next, body.note));
      Object.assign(move, { state: next, version: move.version + 1 });
      return send(res, 200, move);
    }

    send(res, 404, { code: "not_found", message: `No mock route for ${req.method} ${url.pathname}` });
  })
  .listen(PORT, () => console.log(`mock API on :${PORT}`));
