// One interface for the screens, two backends behind it:
//  - "fastapi" (alias "spec"): the team API in backend/app (#51), docs/API_SPEC.md
//  - "prototype": Blessings' backend/prototype.py (#50)
// Choose with NEXT_PUBLIC_BACKEND=fastapi|prototype (default prototype).
import { z } from "zod";
import { ApiError, apiFetch } from "./client";
import {
  ActionResultSchema,
  MoveSchema,
  SuggestionListSchema,
  SuggestionSchema,
  type ActionResult,
  type AuditEvent,
  type ColdChainEvidence,
  type Move,
  type MoveAction,
  type Policy,
  type Role,
  type Suggestion,
  type SuggestionAction,
} from "./schemas";

export type DecisionInput = {
  event_id: string;
  actor_id: string;
  role: Role;
  reason: string;
  to_facility_id?: string; // change only
  unit_ids?: string[]; // change only
};

export type MoveActionInput = {
  event_id: string;
  actor_id: string;
  role: Role;
  note?: string;
  cold_chain_evidence?: ColdChainEvidence; // receive only
  coolbox_max_temp_c?: number | null; // receive only
};

export interface Backend {
  name: "spec" | "prototype";
  listSuggestions(policy: Policy): Promise<Suggestion[]>;
  decide(action: SuggestionAction, s: Suggestion, input: DecisionInput): Promise<ActionResult>;
  listMoves(states: string[]): Promise<Move[]>;
  getMove(moveId: string): Promise<Move>;
  moveAction(action: MoveAction, m: Move, input: MoveActionInput): Promise<ActionResult>;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

// ---------------------------------------------------------------------------
// FastAPI backend (backend/app, #51). Request models are strict (extra fields
// are rejected), moves report `status`, and there is no move list endpoint yet.

const ApiMoveSchema = z.object({
  move_id: z.string(),
  suggestion_id: z.string(),
  unit_ids: z.array(z.string()),
  from_facility_id: z.string(),
  to_facility_id: z.string(),
  status: z.string(),
  lease_expires_at: z.string().nullable().optional(),
});
type ApiMove = z.infer<typeof ApiMoveSchema>;

// A future GET /moves?status= list, in the same shape as GET /moves/{id}.
const ApiMoveListSchema = z
  .union([z.array(ApiMoveSchema), z.object({ items: z.array(ApiMoveSchema) })])
  .transform((v) => (Array.isArray(v) ? v : v.items));

const ApiAuditSchema = z.array(
  z.object({
    event_id: z.string(),
    event_type: z.string(),
    occurred_at: z.string(),
    actor_id: z.string().nullable(),
    move_id: z.string().nullable(),
    unit_id: z.string().nullable(),
    payload: z.record(z.string(), z.unknown()).default({}),
  }),
);
type ApiAuditRow = z.infer<typeof ApiAuditSchema>[number];

const ApiActionResultSchema = z
  .object({ status: z.string().optional() })
  .passthrough()
  .transform((r) => ({ ...r, state: r.status }));

/**
 * One audit entry per move event. The API writes one row per unit, each with
 * its own timestamp and event_id, so rows are grouped by what they share.
 */
function apiAuditEvents(rows: ApiAuditRow[]): AuditEvent[] {
  const seen = new Set<string>();
  return rows
    .filter((r) => {
      const key = [r.move_id, r.event_type, r.actor_id, JSON.stringify(r.payload)].join("|");
      return seen.has(key) ? false : (seen.add(key), true);
    })
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
    .map((r) => ({
      event_id: r.event_id,
      ts: r.occurred_at,
      actor_id: r.actor_id ?? "system",
      role: "",
      action: r.event_type.replace(/^(decision|move)_/, "").replace(/_/g, " "),
      to_state: typeof r.payload.status === "string" ? r.payload.status : null,
      reason: typeof r.payload.reason === "string" && r.payload.reason ? r.payload.reason : null,
    }));
}

async function apiToMove(m: ApiMove, audit: ApiAuditRow[]): Promise<Move> {
  // Moves carry no blood group or expiry: read them from the stored suggestion.
  const s = await apiFetch(
    `/suggestions/${encodeURIComponent(m.suggestion_id)}`,
    SuggestionSchema,
  ).catch(() => null);
  return MoveSchema.parse({
    move_id: m.move_id,
    suggestion_id: m.suggestion_id,
    state: m.status,
    component: s?.component ?? "(component not reported)",
    blood_group: s?.blood_group ?? "(group not reported)",
    unit_ids: m.unit_ids,
    from_facility_id: m.from_facility_id,
    to_facility_id: m.to_facility_id,
    expiry_date: s?.expiry_date,
    typical_travel_hours: s?.typical_travel_hours ?? null,
    lease_expires_at: m.lease_expires_at ?? null,
    audit: apiAuditEvents(audit.filter((r) => r.move_id === m.move_id)),
  });
}

const fetchApiMove = (id: string) => apiFetch(`/moves/${encodeURIComponent(id)}`, ApiMoveSchema);
const fetchApiAudit = () => apiFetch("/audit", ApiAuditSchema);

const specBackend: Backend = {
  name: "spec",
  listSuggestions: (policy) => apiFetch(`/suggestions?policy=${policy}`, SuggestionListSchema),

  decide: (action, s, input) =>
    apiFetch(
      `/suggestions/${encodeURIComponent(s.suggestion_id)}/${action}`,
      ApiActionResultSchema,
      post({
        event_id: input.event_id,
        actor_id: input.actor_id,
        role: input.role,
        reason: input.reason,
        unit_version: s.unit_version ?? 0,
        ...(action === "change" && { unit_ids: input.unit_ids, to_facility_id: input.to_facility_id }),
      }),
    ),

  async listMoves(states) {
    // Use a list endpoint if the API grows one; until then, rebuild from /audit.
    try {
      const listed = await apiFetch(
        `/moves?${states.map((s) => `status=${encodeURIComponent(s)}`).join("&")}`,
        ApiMoveListSchema,
      );
      const audit = listed.length ? await fetchApiAudit() : [];
      return Promise.all(listed.map((m) => apiToMove(m, audit)));
    } catch (error) {
      if (!(error instanceof ApiError) || ![404, 405].includes(error.status)) throw error;
    }
    const audit = await fetchApiAudit();
    const ids = [...new Set(audit.map((r) => r.move_id).filter((id): id is string => !!id))];
    const moves = await Promise.all(ids.map(fetchApiMove));
    return Promise.all(moves.filter((m) => states.includes(m.status)).map((m) => apiToMove(m, audit)));
  },

  async getMove(id) {
    const [m, audit] = await Promise.all([
      fetchApiMove(id),
      apiFetch(`/audit?move_id=${encodeURIComponent(id)}`, ApiAuditSchema),
    ]);
    return apiToMove(m, audit);
  },

  moveAction: (action, m, input) => {
    const temp = input.coolbox_max_temp_c;
    return apiFetch(
      `/moves/${encodeURIComponent(m.move_id)}/${action}`,
      ApiActionResultSchema,
      post({
        event_id: input.event_id,
        actor_id: input.actor_id,
        role: input.role,
        reason: input.note ?? "",
        ...(action === "receive" && {
          cold_chain_evidence_complete:
            input.cold_chain_evidence === "ok" && (temp == null || temp <= 10),
        }),
      }),
    );
  },
};

// ---------------------------------------------------------------------------
// Prototype backend (backend/prototype.py)

const ProtoMoveSchema = z.object({
  id: z.string(),
  unit_id: z.string(),
  origin: z.string(),
  destination: z.string(),
  state: z.string(),
  lease_until: z.string().nullable().optional(),
  eta: z.string().nullable().optional(),
});
type ProtoMove = z.infer<typeof ProtoMoveSchema>;

const ProtoAuditSchema = z.object({
  events: z.array(
    z.object({
      event_id: z.string(),
      payload: z.string(),
      result: z.string(),
      actor: z.string(),
      role: z.string(),
      at: z.string(),
    }),
  ),
});
type ProtoAuditRow = z.infer<typeof ProtoAuditSchema>["events"][number];

const parseJson = (text: string): Record<string, unknown> => {
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return {};
  }
};

// The prototype's move rows carry no blood group or expiry. Remember them from
// the suggestion when the coordinator decides (same browser in the demo).
type UnitInfo = Pick<Suggestion, "blood_group" | "component" | "expiry_date" | "typical_travel_hours">;
const UNIT_KEY = "damu.units";

function readUnits(): Record<string, UnitInfo> {
  try {
    return JSON.parse(localStorage.getItem(UNIT_KEY) ?? "{}") as Record<string, UnitInfo>;
  } catch {
    return {};
  }
}

function rememberUnit(unitId: string, s: Suggestion) {
  try {
    const all = readUnits();
    all[unitId] = {
      blood_group: s.blood_group,
      component: s.component,
      expiry_date: s.expiry_date,
      typical_travel_hours: s.typical_travel_hours,
    };
    localStorage.setItem(UNIT_KEY, JSON.stringify(all));
  } catch {
    // Storage blocked: moves show "group not reported".
  }
}

function toAuditEvent(row: ProtoAuditRow): AuditEvent {
  const payload = parseJson(row.payload);
  const result = parseJson(row.result);
  return {
    event_id: row.event_id,
    ts: row.at,
    actor_id: row.actor,
    role: row.role,
    action: String(result.action ?? payload.action ?? "action"),
    to_state: typeof result.state === "string" ? result.state : null,
    reason: typeof payload.reason === "string" ? payload.reason : null,
  };
}

function eventsFor(rows: ProtoAuditRow[], moveId: string) {
  return rows
    .filter((r) => parseJson(r.result).move_id === moveId || parseJson(r.payload).move_id === moveId)
    .sort((a, b) => a.at.localeCompare(b.at));
}

/** Map prototype states onto the names the screens use. */
function normaliseState(raw: string, rows: ProtoAuditRow[]): string {
  if (raw === "transit") return "in_transit";
  if (raw === "received") {
    const receipt = rows.map((r) => parseJson(r.result)).find((r) => r.action === "receive");
    if (receipt && receipt.safety !== "cleared") return "received_held";
  }
  return raw;
}

function toMove(m: ProtoMove, rows: ProtoAuditRow[]): Move {
  const unit = readUnits()[m.unit_id];
  return MoveSchema.parse({
    move_id: m.id,
    state: normaliseState(m.state, rows),
    component: unit?.component ?? "(component not reported)",
    blood_group: unit?.blood_group ?? "(group not reported)",
    unit_ids: [m.unit_id],
    from_facility_id: m.origin,
    to_facility_id: m.destination,
    expiry_date: unit?.expiry_date,
    typical_travel_hours: unit?.typical_travel_hours ?? null,
    // The prototype runs a frozen demo clock just after 31 Oct, so its lease
    // times would all look expired against the real clock. It enforces the
    // lease itself and refuses an expired dispatch (422).
    lease_expires_at: null,
    warnings: ["Prototype backend: frozen demo clock; the lease is checked by the backend"],
    audit: rows.map(toAuditEvent),
  });
}

const fetchAudit = async () => (await apiFetch("/audit", ProtoAuditSchema)).events;
const fetchProtoMove = (id: string) => apiFetch(`/moves/${encodeURIComponent(id)}`, ProtoMoveSchema);

const prototypeBackend: Backend = {
  name: "prototype",
  listSuggestions: specBackend.listSuggestions,

  async decide(action, s, input) {
    const unitId = s.unit_ids[0];
    if (action !== "reject") rememberUnit(unitId, s);
    return apiFetch(
      `/${action}`,
      ActionResultSchema,
      post({
        event_id: input.event_id,
        actor_id: input.actor_id,
        role: input.role,
        reason: input.reason,
        unit_id: unitId,
        unit_version: s.unit_version,
        destination: action === "change" ? input.to_facility_id : s.to_facility_id,
      }),
    );
  },

  // No list endpoint yet: rebuild the list from moves created in the audit log.
  async listMoves(states) {
    const audit = await fetchAudit();
    const ids = [
      ...new Set(
        audit
          .map((r) => parseJson(r.result))
          .filter((r) => (r.action === "accept" || r.action === "change") && typeof r.move_id === "string")
          .map((r) => r.move_id as string),
      ),
    ];
    const moves = await Promise.all(ids.map(async (id) => toMove(await fetchProtoMove(id), eventsFor(audit, id))));
    return moves.filter((m) => states.includes(m.state));
  },

  async getMove(moveId) {
    const [m, audit] = await Promise.all([fetchProtoMove(moveId), fetchAudit()]);
    return toMove(m, eventsFor(audit, moveId));
  },

  async moveAction(action, m, input) {
    const temp = input.coolbox_max_temp_c;
    const result = await apiFetch(
      `/${action}`,
      ActionResultSchema,
      post({
        event_id: input.event_id,
        actor_id: input.actor_id,
        role: input.role,
        // The prototype requires a reason on every action.
        reason: input.note || (action === "dispatch" ? "Dispatched after recheck" : "Receipt recorded"),
        unit_id: m.unit_ids[0],
        move_id: m.move_id,
        site: action === "dispatch" ? m.from_facility_id : m.to_facility_id,
        ...(action === "receive" && {
          cold_chain_verified: input.cold_chain_evidence === "ok" && (temp == null || temp <= 10),
        }),
      }),
    );
    // The prototype reports a doubtful receipt as state "received" plus
    // safety "unknown"; the screens call that a hold, never a clean receipt.
    if (result.state === "received" && result.safety !== "cleared") {
      return { ...result, state: "received_held" };
    }
    return result;
  },
};

export const backend: Backend =
  process.env.NEXT_PUBLIC_BACKEND === "fastapi" || process.env.NEXT_PUBLIC_BACKEND === "spec"
    ? specBackend
    : prototypeBackend;
